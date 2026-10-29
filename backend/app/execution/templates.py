"""Render an operator-supplied payload template.

Placeholders use `{field}` and must be present in the value map. This is an
adapter, not an official schema. If no template file is configured, callers
must refuse the venue call.
"""

from __future__ import annotations

import json
from pathlib import Path


class TemplateError(ValueError):
    pass


def load_template(path: str) -> dict:
    if not path:
        raise TemplateError("template path is empty")
    file = Path(path)
    if not file.is_file():
        raise TemplateError(f"template not found: {path}")
    data = json.loads(file.read_text())
    if not isinstance(data, dict):
        raise TemplateError("template must be a JSON object")
    return data


def render(template: dict, values: dict[str, str]) -> dict:
    rendered: dict = {}
    for key, raw in template.items():
        if isinstance(raw, str):
            try:
                rendered[key] = raw.format(**values)
            except KeyError as exc:
                raise TemplateError(f"missing placeholder {exc}") from exc
        else:
            rendered[key] = raw
    return rendered
