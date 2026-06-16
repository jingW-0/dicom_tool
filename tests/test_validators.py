"""Tests for dicom_tool.validators."""

from __future__ import annotations

import pytest

from dicom_tool.extractor import SeriesMetadata
from dicom_tool.validators import (
    ValidationResult,
    check_kernel,
    check_orientation,
    check_slice_spacing,
    validate_series,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meta(**kwargs) -> SeriesMetadata:
    defaults = dict(
        pixel_spacing=[0.75, 0.75],
        slice_thickness=1.0,
        image_orientation_patient=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        image_positions=[[0, 0, z] for z in range(5)],
        num_slices=5,
        manufacturer="Siemens",
        convolution_kernel="B31f",
    )
    defaults.update(kwargs)
    return SeriesMetadata(**defaults)


# ---------------------------------------------------------------------------
# check_slice_spacing
# ---------------------------------------------------------------------------

class TestCheckSliceSpacing:
    def test_pass_for_uniform_spacing(self):
        meta = _meta(image_positions=[[0, 0, z] for z in range(5)])
        result = check_slice_spacing(meta)
        assert result.status == "pass"

    def test_fail_for_irregular_spacing(self):
        # Gaps: 1, 1.5, 2, 0.5 — std will exceed default tolerance 0.1
        positions = [[0, 0, z] for z in [0, 1, 2.5, 4.5, 5.0]]
        meta = _meta(image_positions=positions)
        result = check_slice_spacing(meta)
        assert result.status == "fail"
        assert "Irregular" in result.message

    def test_warn_for_declared_vs_computed_mismatch(self):
        # Uniform 2 mm spacing but declared 1 mm thickness
        meta = _meta(
            image_positions=[[0, 0, z * 2] for z in range(5)],
            slice_thickness=1.0,
        )
        result = check_slice_spacing(meta)
        assert result.status == "warn"
        assert "mismatch" in result.message.lower()

    def test_warn_for_single_slice(self):
        meta = _meta(image_positions=[[0, 0, 0]])
        result = check_slice_spacing(meta)
        assert result.status == "warn"

    def test_warn_for_no_positions(self):
        meta = _meta(image_positions=[])
        result = check_slice_spacing(meta)
        assert result.status == "warn"

    def test_custom_tolerance(self):
        # Spacing std ~0.05 — passes at tolerance 0.1, fails at 0.01
        positions = [[0, 0, z + (0.03 if z % 2 else 0)] for z in range(5)]
        meta = _meta(image_positions=positions, slice_thickness=1.0)
        assert check_slice_spacing(meta, tolerance=0.1).status in ("pass", "warn")
        assert check_slice_spacing(meta, tolerance=0.01).status == "fail"

    def test_result_check_name(self):
        meta = _meta()
        result = check_slice_spacing(meta)
        assert result.check == "slice_spacing"


# ---------------------------------------------------------------------------
# check_kernel
# ---------------------------------------------------------------------------

class TestCheckKernel:
    @pytest.mark.parametrize("manufacturer,kernel,expected_category", [
        ("Siemens", "B31f", "standard"),
        ("Siemens", "B70f", "sharp"),
        ("GE", "BONE", "bone"),
        ("GE", "LUNG", "sharp"),
        ("Philips", "YB", "sharp"),
        ("Canon", "FC04", "standard"),
    ])
    def test_known_kernels_normalised(self, manufacturer, kernel, expected_category):
        meta = _meta(manufacturer=manufacturer, convolution_kernel=kernel)
        result = check_kernel(meta)
        assert result.status == "pass"
        assert expected_category in result.message.lower()

    def test_warn_for_missing_kernel(self):
        meta = _meta(convolution_kernel=None)
        result = check_kernel(meta)
        assert result.status == "warn"

    def test_warn_for_unknown_kernel(self):
        meta = _meta(manufacturer="Unknown Corp", convolution_kernel="ZXQV99")
        result = check_kernel(meta)
        assert result.status == "warn"

    def test_result_check_name(self):
        meta = _meta()
        result = check_kernel(meta)
        assert result.check == "kernel"


# ---------------------------------------------------------------------------
# check_orientation
# ---------------------------------------------------------------------------

class TestCheckOrientation:
    def test_pass_for_axial_orientation(self):
        meta = _meta(image_orientation_patient=[1, 0, 0, 0, 1, 0])
        result = check_orientation(meta)
        assert result.status == "pass"

    def test_pass_for_coronal_orientation(self):
        meta = _meta(image_orientation_patient=[1, 0, 0, 0, 0, -1])
        result = check_orientation(meta)
        assert result.status == "pass"

    def test_fail_for_non_unit_row_cosine(self):
        meta = _meta(image_orientation_patient=[2, 0, 0, 0, 1, 0])
        result = check_orientation(meta)
        assert result.status == "fail"

    def test_fail_for_non_orthogonal_cosines(self):
        meta = _meta(image_orientation_patient=[1, 0, 0, 1, 0, 0])
        result = check_orientation(meta)
        assert result.status == "fail"

    def test_warn_for_missing_orientation(self):
        meta = _meta(image_orientation_patient=None)
        result = check_orientation(meta)
        assert result.status == "warn"

    def test_warn_for_wrong_length_orientation(self):
        meta = _meta(image_orientation_patient=[1, 0, 0])
        result = check_orientation(meta)
        assert result.status == "warn"

    def test_result_check_name(self):
        meta = _meta()
        result = check_orientation(meta)
        assert result.check == "orientation"


# ---------------------------------------------------------------------------
# validate_series (integration)
# ---------------------------------------------------------------------------

class TestValidateSeries:
    def test_returns_three_results(self, well_formed_meta):
        results = validate_series(well_formed_meta)
        assert len(results) == 3

    def test_all_checks_present(self, well_formed_meta):
        results = validate_series(well_formed_meta)
        checks = {r.check for r in results}
        assert checks == {"slice_spacing", "kernel", "orientation"}

    def test_clean_series_all_pass(self, well_formed_meta):
        results = validate_series(well_formed_meta)
        for r in results:
            assert r.status == "pass", f"{r.check} was {r.status}: {r.message}"

    def test_result_type(self, well_formed_meta):
        results = validate_series(well_formed_meta)
        for r in results:
            assert isinstance(r, ValidationResult)
