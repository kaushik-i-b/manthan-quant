"""Venue client errors. Messages must stay free of tokens and passwords."""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class SchemaNotConfigured(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__("schema", message)
