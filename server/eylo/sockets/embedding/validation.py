"""Strict provider-response validation shared by embedding adapters."""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Real

from eylo.common.contracts.embedding import EmbeddingError


def validate_indexed_vectors(
    entries: Sequence[tuple[object, object]],
    *,
    expected_count: int,
    vendor: str,
) -> list[list[float]]:
    """Return vectors in input order only when correspondence and shape are exact."""
    indices = [entry[0] for entry in entries]
    expected_indices = set(range(expected_count))
    if (
        len(entries) != expected_count
        or any(isinstance(index, bool) or not isinstance(index, int) for index in indices)
        or set(indices) != expected_indices
    ):
        raise _invalid_response(
            vendor,
            "Embedding response indices did not match the complete input batch.",
        )

    ordered = sorted(entries, key=lambda entry: int(entry[0]))
    vectors = [_validate_vector(entry[1], vendor=vendor) for entry in ordered]
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) > 1:
        raise _invalid_response(
            vendor,
            "Embedding response vectors did not have one consistent dimension.",
        )
    return vectors


def _validate_vector(value: object, *, vendor: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or not value:
        raise _invalid_response(vendor, "Embedding response contained an empty vector.")
    vector: list[float] = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, Real):
            raise _invalid_response(
                vendor,
                "Embedding response contained a non-numeric component.",
            )
        normalized = float(component)
        if not math.isfinite(normalized):
            raise _invalid_response(
                vendor,
                "Embedding response contained a non-finite component.",
            )
        vector.append(normalized)
    return vector


def _invalid_response(vendor: str, message: str) -> EmbeddingError:
    return EmbeddingError(
        message,
        vendor=vendor,
        code="invalid_response",
        retryable=True,
    )
