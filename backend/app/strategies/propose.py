"""Turn a selector output into a proposed action.

Baselines are intentionally simple and live here so the backtest and the
mock exchange share one accounting path.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.models.types import IndicatorSnapshot
from app.portfolio.accounting import Position
from app.risk.engine import size_entry
from app.strategies.selector import Selection


@dataclass
class Proposal:
    action: str
    quantity: int
    is_exit: bool
    reason: str
    strategy: str


def propose(
    *,
    mode: str,
    settings: Settings,
    snap: IndicatorSnapshot,
    selection: Selection,
    position: Position | None,
    close: float,
    equity: float,
    sim_day: int,
    atr: float | None,
    in_cooldown: bool,
) -> Proposal:
    if mode == "cash":
        return Proposal("HOLD", 0, False, "Cash baseline. No order.", "cash")
    if mode == "buy_hold":
        if position is None and snap.ready and close > 0:
            qty = int((equity * 0.08) // close)
            if qty >= 1:
                return Proposal("BUY", qty, False, "Buy-and-hold baseline entry, sized at 8% of equity.", "buy_hold")
        return Proposal("HOLD", 0, False, "Buy-and-hold baseline is already invested or still warming up.", "buy_hold")

    if position is not None and mode != "buy_hold":
        exit_proposal = _protective_exit(settings, position, close, sim_day, selection, mode)
        if exit_proposal is not None:
            return exit_proposal

    if mode == "momentum":
        return _momentum(settings, snap, position, close, equity, atr)
    if mode == "mean_reversion":
        return _mean_reversion(settings, snap, position, close, equity, atr)
    return _adaptive(settings, selection, position, close, equity, atr, in_cooldown)


def _protective_exit(settings, position, close, sim_day, selection, mode) -> Proposal | None:
    if position.side == "long":
        if close <= position.avg_price * (1 - settings.stop_loss_pct):
            return Proposal("SELL", position.quantity, True, "Stop-loss reached at the candle close. The simulator does not fill intrabar.", "risk_exit")
        if close >= position.avg_price * (1 + settings.take_profit_pct):
            return Proposal("SELL", position.quantity, True, "Take-profit reached at the candle close.", "risk_exit")
        if mode == "adaptive" and (selection.force_flat or selection.action_bias <= -settings.exit_threshold):
            return Proposal("SELL", position.quantity, True, "Defensive overlay or a reversed heuristic score closed the long.", selection.primary)
    if position.side == "short":
        held = sim_day - position.opened_day
        if close >= position.avg_price * (1 + settings.stop_loss_pct):
            return Proposal("COVER", position.quantity, True, "Short stop-loss reached at the candle close.", "risk_exit")
        if close <= position.avg_price * (1 - settings.take_profit_pct):
            return Proposal("COVER", position.quantity, True, "Short take-profit reached at the candle close.", "risk_exit")
        if held >= settings.short_max_hold_days:
            return Proposal(
                "COVER",
                position.quantity,
                True,
                f"Local short square-off after {held} simulated days. This schedule is not the official venue rule.",
                "risk_exit",
            )
        if mode == "adaptive" and (selection.force_flat or selection.action_bias >= settings.exit_threshold):
            return Proposal("COVER", position.quantity, True, "Defensive overlay or a reversed heuristic score covered the short.", selection.primary)
    return None


def _entry_qty(settings, equity, close, atr, score) -> int:
    return size_entry(settings, equity, close, atr, score if score != 0 else 1.0)


def _momentum(settings, snap, position, close, equity, atr) -> Proposal:
    mom = snap.momentum10 or 0.0
    if position is None and mom > 0.01:
        qty = _entry_qty(settings, equity, close, atr, 0.7)
        return Proposal("BUY", qty, False, "Momentum baseline: 10-bar return above 1%.", "momentum")
    if position is None and mom < -0.01 and settings.shorts_enabled:
        qty = _entry_qty(settings, equity, close, atr, 0.7)
        return Proposal("SHORT", qty, False, "Momentum baseline: 10-bar return below -1%.", "momentum")
    if position is not None and position.side == "long" and mom < -0.01:
        return Proposal("SELL", position.quantity, True, "Momentum baseline flipped negative.", "momentum")
    if position is not None and position.side == "short" and mom > 0.01:
        return Proposal("COVER", position.quantity, True, "Momentum baseline flipped positive.", "momentum")
    return Proposal("HOLD", 0, False, "Momentum baseline has no edge beyond the noise band.", "momentum")


def _mean_reversion(settings, snap, position, close, equity, atr) -> Proposal:
    rsi = snap.rsi14
    if rsi is None:
        return Proposal("HOLD", 0, False, "Mean-reversion baseline is waiting for RSI.", "mean_reversion")
    if position is None and rsi <= 30:
        qty = _entry_qty(settings, equity, close, atr, 0.7)
        return Proposal("BUY", qty, False, f"Mean-reversion baseline: RSI {rsi:.1f} at or below 30.", "mean_reversion")
    if position is None and rsi >= 70 and settings.shorts_enabled:
        qty = _entry_qty(settings, equity, close, atr, 0.7)
        return Proposal("SHORT", qty, False, f"Mean-reversion baseline: RSI {rsi:.1f} at or above 70.", "mean_reversion")
    if position is not None and position.side == "long" and rsi >= 55:
        return Proposal("SELL", position.quantity, True, f"Mean-reversion baseline exit: RSI {rsi:.1f} reverted.", "mean_reversion")
    if position is not None and position.side == "short" and rsi <= 45:
        return Proposal("COVER", position.quantity, True, f"Mean-reversion baseline cover: RSI {rsi:.1f} reverted.", "mean_reversion")
    return Proposal("HOLD", 0, False, f"Mean-reversion baseline holds with RSI {rsi:.1f}.", "mean_reversion")


def _adaptive(settings, selection, position, close, equity, atr, in_cooldown) -> Proposal:
    if selection.force_flat:
        return Proposal("HOLD", 0, False, "Defensive regime. New risk is blocked. " + selection.reason, "defensive")
    if in_cooldown:
        return Proposal("HOLD", 0, False, "Cooldown is active after the last entry, so no new order was sent.", selection.primary)
    if position is not None:
        return Proposal("HOLD", 0, False, "Position is open and no exit rule fired. " + selection.reason, selection.primary)
    if selection.action_bias >= settings.entry_threshold:
        qty = size_entry(settings, equity, close, atr, selection.action_bias)
        return Proposal("BUY", qty, False, selection.reason, selection.primary)
    if selection.action_bias <= -settings.entry_threshold and settings.shorts_enabled:
        qty = size_entry(settings, equity, close, atr, selection.action_bias)
        return Proposal("SHORT", qty, False, selection.reason, selection.primary)
    return Proposal(
        "HOLD",
        0,
        False,
        f"Heuristic score {selection.action_bias:.2f} is inside the no-trade band (±{settings.entry_threshold:.2f}). " + selection.reason,
        selection.primary,
    )
