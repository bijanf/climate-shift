"""Tests for glacier_toolkit.config — registry, lookups, custom glaciers."""

from __future__ import annotations

import pytest

from glacier_toolkit.config import (
    BOOTSTRAP_N,
    BOOTSTRAP_SEED,
    GLACIER_REGISTRY,
    IG_DPI,
    IG_FIG,
    SEASON_NH_SUMMER,
    SEASON_SH_SUMMER,
    get_glacier,
    make_custom_glacier,
)


class TestGlacierRegistry:
    def test_registry_is_populated(self):
        assert len(GLACIER_REGISTRY) >= 18, "Registry should have at least 18 glaciers"

    def test_all_glaciers_have_required_fields(self):
        required = {"name", "region", "lat", "lon", "bbox", "hemisphere", "season", "notes"}
        for key, glacier in GLACIER_REGISTRY.items():
            missing = required - set(glacier.keys())
            assert not missing, f"Glacier '{key}' missing fields: {missing}"

    def test_coordinates_are_valid(self):
        for key, glacier in GLACIER_REGISTRY.items():
            assert -90 <= glacier["lat"] <= 90, f"{key}: invalid latitude"
            assert -180 <= glacier["lon"] <= 180, f"{key}: invalid longitude"

    def test_bbox_contains_center(self):
        for key, glacier in GLACIER_REGISTRY.items():
            w, s, e, n = glacier["bbox"]
            lat, lon = glacier["lat"], glacier["lon"]
            assert w <= lon <= e, f"{key}: lon {lon} not in bbox [{w}, {e}]"
            assert s <= lat <= n, f"{key}: lat {lat} not in bbox [{s}, {n}]"

    def test_hemispheres_are_valid(self):
        valid = {"N", "S", "tropical"}
        for key, glacier in GLACIER_REGISTRY.items():
            assert glacier["hemisphere"] in valid, f"{key}: bad hemisphere"

    def test_glaciers_span_all_continents(self):
        regions = " ".join(g["region"] for g in GLACIER_REGISTRY.values()).lower()
        for expected in ["alaska", "alps", "andes", "himalaya", "africa", "antarctic"]:
            assert expected in regions, f"Missing glaciers in region: {expected}"


class TestGetGlacier:
    def test_lookup_by_exact_key(self):
        g = get_glacier("aletsch")
        assert g["name"] == "Aletsch Glacier"

    def test_lookup_is_case_insensitive(self):
        assert get_glacier("ALETSCH") == get_glacier("aletsch")

    def test_lookup_strips_whitespace(self):
        assert get_glacier("  aletsch  ") == get_glacier("aletsch")

    def test_fuzzy_match_on_name(self):
        # 'gangotri' is the registry key, but should also match name fragments
        g = get_glacier("gangotri")
        assert "Gangotri" in g["name"]

    def test_unknown_raises_keyerror(self):
        with pytest.raises(KeyError, match="not found in registry"):
            get_glacier("nonexistent_glacier_xyz")


class TestMakeCustomGlacier:
    def test_northern_hemisphere_default(self):
        g = make_custom_glacier("Test", lat=50.0, lon=10.0)
        assert g["hemisphere"] == "N"
        assert g["season"] == SEASON_NH_SUMMER

    def test_southern_hemisphere_default(self):
        g = make_custom_glacier("Test", lat=-50.0, lon=10.0)
        assert g["hemisphere"] == "S"
        assert g["season"] == SEASON_SH_SUMMER

    def test_tropical_default(self):
        g = make_custom_glacier("Test", lat=0.0, lon=37.0)
        assert g["hemisphere"] == "tropical"

    def test_bbox_centered_on_coords(self):
        g = make_custom_glacier("Test", lat=45.0, lon=10.0, bbox_pad_deg=0.5)
        w, s, e, n = g["bbox"]
        assert w == 9.5
        assert e == 10.5
        assert s == 44.5
        assert n == 45.5

    def test_explicit_hemisphere_overrides(self):
        g = make_custom_glacier("Test", lat=10.0, lon=10.0, hemisphere="N")
        assert g["hemisphere"] == "N"
        assert g["season"] == SEASON_NH_SUMMER


class TestConstants:
    def test_instagram_dimensions(self):
        # Existing project uses 1080x1350 @ 150 DPI
        assert IG_DPI == 150
        assert IG_FIG == (7.2, 9.0)

    def test_bootstrap_defaults_match_project(self):
        # Must match plot_climate_shift.py:60
        assert BOOTSTRAP_N == 10_000
        assert BOOTSTRAP_SEED == 42

    def test_seasons(self):
        assert SEASON_NH_SUMMER == [6, 7, 8]
        assert SEASON_SH_SUMMER == [12, 1, 2]
