"""Transaction costs.

`synthetic_demo` is a flat fictional brokerage used only so the desk can show
a cost breakdown. It is not the competition's fee schedule. `zero` is the
safe default when the official schedule is unknown and demo costs are off.
`configured` applies operator-supplied rates and still marks them unofficial.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class CostBreakdown:
    brokerage: float
    taxes_and_fees: float
    model: str
    official: bool = False

    @property
    def total(self) -> float:
        return self.brokerage + self.taxes_and_fees


def quote_cost(settings: Settings, turnover: float) -> CostBreakdown:
    model = settings.cost_model
    if model == "zero":
        return CostBreakdown(0.0, 0.0, "zero", False)
    if model == "synthetic_demo":
        return CostBreakdown(round(settings.synthetic_brokerage_inr, 2), 0.0, "synthetic_demo", False)
    if model == "configured":
        brokerage = turnover * settings.configured_brokerage_pct + settings.configured_flat_fee_inr
        taxes = turnover * settings.configured_tax_pct + settings.configured_dp_charge_inr
        return CostBreakdown(round(brokerage, 2), round(taxes, 2), "configured", False)
    raise ValueError(f"unknown cost model {model}")
