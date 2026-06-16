"""Tests for dicom_tool.extractor."""

from __future__ import annotations

from pathlib import Path

import pydicom
import pytest

from dicom_tool.extractor import (
    SeriesMetadata,
    _safe_get,
    extract_metadata,
    extract_series_metadata,
)


# ---------------------------------------------------------------------------
# _safe_get
# ---------------------------------------------------------------------------

class TestSafeGet:
    def test_returns_value_for_present_tag(self, base_ds):
        assert _safe_get(base_ds, "Modality") == "CT"

    def test_returns_default_for_missing_tag(self, base_ds):
        assert _safe_get(base_ds, "NonExistentTag9999", default="X") == "X"

    def test_returns_none_by_default_when_missing(self, base_ds):
        assert _safe_get(base_ds, "NonExistentTag9999") is None

    def test_does_not_raise_on_malformed_access(self):
        from pydicom.dataset import Dataset
        ds = Dataset()
        assert _safe_get(ds, "PixelSpacing") is None


# ---------------------------------------------------------------------------
# extract_series_metadata
# ---------------------------------------------------------------------------

class TestExtractSeriesMetadata:
    def test_returns_metadata_object(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert isinstance(meta, SeriesMetadata)

    def test_counts_slices(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.num_slices == 5

    def test_pixel_spacing(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.pixel_spacing == pytest.approx([0.75, 0.75])

    def test_slice_thickness(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.slice_thickness == pytest.approx(1.0)

    def test_image_orientation_patient(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.image_orientation_patient == pytest.approx([1, 0, 0, 0, 1, 0])

    def test_image_positions_collected(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert len(meta.image_positions) == 5

    def test_manufacturer(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.manufacturer == "Siemens"

    def test_convolution_kernel(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.convolution_kernel == "B31f"

    def test_kvp(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.kvp == pytest.approx(120.0)

    def test_modality(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.modality == "CT"

    def test_series_dir_recorded(self, series_dir):
        meta = extract_series_metadata(series_dir)
        assert meta.series_dir == str(series_dir)

    def test_empty_dir_returns_zero_slices(self, tmp_path):
        meta = extract_series_metadata(tmp_path)
        assert meta.num_slices == 0

    def test_non_dicom_files_skipped(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not dicom")
        meta = extract_series_metadata(tmp_path)
        assert meta.num_slices == 0


# ---------------------------------------------------------------------------
# extract_metadata (recursive walk)
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_finds_nested_series(self, tmp_path):
        from tests.conftest import _make_ds, _write_dicom
        for i in range(5):
            ds = _make_ds(ipp=(0.0, 0.0, float(i)), series_uid="1.2.3.4.5.6")
            _write_dicom(tmp_path / "study1" / "series1" / f"slice_{i:03d}.dcm", ds)

        results = extract_metadata(tmp_path)
        assert len(results) == 1
        assert results[0].num_slices == 5

    def test_returns_empty_list_for_no_dicoms(self, tmp_path):
        results = extract_metadata(tmp_path)
        assert results == []

    def test_multiple_series_found(self, tmp_path):
        from tests.conftest import _make_ds, _write_dicom
        for series_idx in range(3):
            for slice_idx in range(4):
                ds = _make_ds(
                    ipp=(0.0, 0.0, float(slice_idx)),
                    series_uid=f"1.2.3.{series_idx}",
                )
                _write_dicom(
                    tmp_path / f"series_{series_idx}" / f"sl_{slice_idx:02d}.dcm",
                    ds,
                )
        results = extract_metadata(tmp_path)
        assert len(results) == 3
