"""Tests for glacier_toolkit.validate.glims_validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from glacier_toolkit.validate.glims_validation import (
    PUBLISHED_REFERENCES,
    compare_to_reference,
    get_published_reference,
    validate_against_references,
)


class TestCompareToReference:
    def test_zero_bias_when_equal(self):
        result = compare_to_reference(100.0, 100.0)
        assert result["bias_km2"] == 0.0
        assert result["bias_pct"] == 0.0

    def test_positive_bias_when_overestimate(self):
        result = compare_to_reference(110.0, 100.0)
        assert result["bias_km2"] == 10.0
        assert result["bias_pct"] == 10.0
        assert result["relative_error_pct"] == 10.0

    def test_negative_bias_when_underestimate(self):
        result = compare_to_reference(90.0, 100.0)
        assert result["bias_km2"] == -10.0
        assert result["bias_pct"] == -10.0
        assert result["relative_error_pct"] == 10.0

    def test_zero_reference_handles_gracefully(self):
        result = compare_to_reference(5.0, 0.0)
        assert np.isnan(result["bias_pct"])
        assert np.isnan(result["relative_error_pct"])


class TestValidateAgainstReferences:
    def test_aggregate_statistics(self):
        comparisons = [
            {"name": "G1", "computed_km2": 105.0, "reference_km2": 100.0},
            {"name": "G2", "computed_km2": 95.0, "reference_km2": 100.0},
            {"name": "G3", "computed_km2": 100.0, "reference_km2": 100.0},
        ]
        val = validate_against_references(comparisons)
        assert val["n_glaciers"] == 3
        assert val["mean_bias_km2"] == 0.0  # +5, -5, 0 → mean 0
        assert val["mean_absolute_error_pct"] > 0

    def test_empty_input(self):
        val = validate_against_references([])
        assert val["n_glaciers"] == 0
        assert np.isnan(val["mean_bias_km2"])

    def test_per_glacier_dataframe(self):
        comparisons = [
            {"name": "Aletsch", "computed_km2": 80.0, "reference_km2": 79.6},
        ]
        val = validate_against_references(comparisons)
        assert isinstance(val["per_glacier"], pd.DataFrame)
        assert "bias_km2" in val["per_glacier"].columns


class TestPublishedReferences:
    def test_registry_has_well_known_glaciers(self):
        keys = {ref["key"] for ref in PUBLISHED_REFERENCES}
        # Sanity check that the registry includes well-known references
        for expected in {"aletsch", "pasterze", "columbia", "gangotri"}:
            assert expected in keys, f"Missing reference for {expected}"

    def test_get_published_reference_known(self):
        ref = get_published_reference("aletsch")
        assert ref is not None
        assert "Aletsch" in ref["name"]
        assert ref["reference_km2"] > 0

    def test_get_published_reference_unknown(self):
        assert get_published_reference("nonexistent") is None

    def test_all_references_have_required_fields(self):
        required = {"key", "name", "reference_km2", "reference_year", "reference_source"}
        for ref in PUBLISHED_REFERENCES:
            missing = required - set(ref.keys())
            assert not missing, f"Reference {ref.get('key')} missing: {missing}"
