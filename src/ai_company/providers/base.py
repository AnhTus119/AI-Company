"""Canonical structured-output provider contract and explicit rate cards."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Protocol


@dataclass(frozen=True)
class StructuredRequest:
    prompt: str
    json_schema: dict
    max_output_tokens: int
    temperature: float = 0.7
    reasoning_effort: str = "low"
    service_tier: str = "default"


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def as_ledger_document(self) -> dict:
        return {
            "input_units": self.input_tokens,
            "output_units": self.output_tokens,
            "total_units": self.total_tokens,
            "unit": "token",
        }


@dataclass(frozen=True)
class StructuredResult:
    value: dict
    usage: ProviderUsage


class StructuredTextProvider(Protocol):
    provider_key: str
    model_key: str

    def generate_structured(self, request: StructuredRequest) -> StructuredResult: ...


class ProviderFailure(RuntimeError):
    """Safe provider failure containing a code only, never response bodies or credentials."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class TokenRateCard:
    version: str
    currency: str
    input_minor_per_million: int
    output_minor_per_million: int

    def __post_init__(self) -> None:
        if not self.version.strip() or len(self.currency) != 3 or self.currency.upper() != self.currency:
            raise ValueError("Rate card needs a version and uppercase three-letter currency.")
        if min(self.input_minor_per_million, self.output_minor_per_million) < 0:
            raise ValueError("Token prices cannot be negative.")

    def upper_bound(self, input_tokens: int, output_tokens: int) -> int:
        if min(input_tokens, output_tokens) < 0:
            raise ValueError("Token bounds cannot be negative.")
        amount = (
            input_tokens * self.input_minor_per_million
            + output_tokens * self.output_minor_per_million
        ) / 1_000_000
        return ceil(amount)

    def actual(self, usage: ProviderUsage) -> int:
        return self.upper_bound(usage.input_tokens, usage.output_tokens)
