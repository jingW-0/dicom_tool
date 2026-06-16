"""Tests for dicom_tool.converter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dicom_tool.converter import ConversionResult, _enrich_sidecar, convert_series, convert_to_nifti
from dicom_tool.extractor import SeriesMetadata


@pytest.fixture()
def meta() -> SeriesMetadata:
    return SeriesMetadata(
        pixel_spacing=[0.75, 0.75],
        slice_thickness=1.0,
        image_orientation_patient=[1, 0, 0, 0, 1, 0],
        num_slices=5,
        rows=512,
        columns=512,
        manufacturer="Siemens",
        manufacturer_model_name="SOMATOM Force",
        convolution_kernel="B31f",
        kvp=120.0,
        modality="CT",
        series_description="CHEST",
        series_instance_uid="1.2.3.4.5",
        study_instance_uid="1.2.3.4",
        acquisition_date="20240101",
        series_dir="/fake/series",
    )


# ---------------------------------------------------------------------------
# _enrich_sidecar
# ---------------------------------------------------------------------------

class TestEnrichSidecar:
    def test_writes_provenance_block(self, tmp_path, meta):
        json_path = tmp_path / "output.json"
        _enrich_sidecar(json_path, meta)
        data = json.loads(json_path.read_text())
        assert "dicom_tool_provenance" in data

    def test_provenance_contains_expected_fields(self, tmp_path, meta):
        json_path = tmp_path / "output.json"
        _enrich_sidecar(json_path, meta)
        prov = json.loads(json_path.read_text())["dicom_tool_provenance"]
        assert prov["Manufacturer"] == "Siemens"
        assert prov["Modality"] == "CT"
        assert prov["NumSlices"] == 5

    def test_merges_with_existing_sidecar(self, tmp_path, meta):
        json_path = tmp_path / "output.json"
        json_path.write_text(json.dumps({"BidsField": "value"}), encoding="utf-8")
        _enrich_sidecar(json_path, meta)
        data = json.loads(json_path.read_text())
        assert data["BidsField"] == "value"
        assert "dicom_tool_provenance" in data

    def test_none_values_excluded_from_provenance(self, tmp_path):
        sparse = SeriesMetadata(num_slices=3, modality="CT")
        json_path = tmp_path / "output.json"
        _enrich_sidecar(json_path, sparse)
        prov = json.loads(json_path.read_text())["dicom_tool_provenance"]
        assert "Manufacturer" not in prov
        assert prov["Modality"] == "CT"

    def test_handles_corrupt_existing_json(self, tmp_path, meta):
        json_path = tmp_path / "output.json"
        json_path.write_text("NOT JSON {{{{", encoding="utf-8")
        _enrich_sidecar(json_path, meta)  # should not raise
        data = json.loads(json_path.read_text())
        assert "dicom_tool_provenance" in data


# ---------------------------------------------------------------------------
# convert_series
# ---------------------------------------------------------------------------

class TestConvertSeries:
    def test_success_path(self, tmp_path, meta):
        series_dir = tmp_path / "series"
        series_dir.mkdir()
        out_dir = tmp_path / "out"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            result = convert_series(series_dir, out_dir, meta=meta)

        assert result.success is True
        assert result.series_dir == str(series_dir)

    def test_dcm2niix_not_found(self, tmp_path, meta):
        series_dir = tmp_path / "series"
        series_dir.mkdir()
        out_dir = tmp_path / "out"

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = convert_series(series_dir, out_dir, meta=meta)

        assert result.success is False
        assert "dcm2niix not found" in result.error

    def test_nonzero_returncode_fails(self, tmp_path, meta):
        series_dir = tmp_path / "series"
        series_dir.mkdir()
        out_dir = tmp_path / "out"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="bad input", stdout="")
            result = convert_series(series_dir, out_dir, meta=meta)

        assert result.success is False
        assert "bad input" in result.error

    def test_timeout_fails(self, tmp_path, meta):
        series_dir = tmp_path / "series"
        series_dir.mkdir()
        out_dir = tmp_path / "out"

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("dcm2niix", 300)):
            result = convert_series(series_dir, out_dir, meta=meta)

        assert result.success is False
        assert "timed out" in result.error

    def test_output_dir_created(self, tmp_path, meta):
        series_dir = tmp_path / "series"
        series_dir.mkdir()
        out_dir = tmp_path / "nested" / "output"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            convert_series(series_dir, out_dir, meta=meta)

        assert out_dir.exists()

    def test_sidecar_enriched_on_success(self, tmp_path, meta):
        series_dir = tmp_path / "series"
        series_dir.mkdir()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "output.json").write_text("{}", encoding="utf-8")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
            convert_series(series_dir, out_dir, meta=meta)

        data = json.loads((out_dir / "output.json").read_text())
        assert "dicom_tool_provenance" in data


# ---------------------------------------------------------------------------
# convert_to_nifti
# ---------------------------------------------------------------------------

class TestConvertToNifti:
    def test_converts_directories_that_contain_files(self, tmp_path, meta):
        root = tmp_path / "root"
        series_a = root / "study_a" / "series_a"
        series_b = root / "study_b" / "series_b"
        empty_dir = root / "empty"
        series_a.mkdir(parents=True)
        series_b.mkdir(parents=True)
        empty_dir.mkdir(parents=True)
        (series_a / "slice_001.dcm").write_text("placeholder", encoding="utf-8")
        (series_b / "slice_001.dcm").write_text("placeholder", encoding="utf-8")

        meta.series_dir = str(series_a)
        with patch("dicom_tool.converter.convert_series") as mock_convert:
            mock_convert.side_effect = lambda series_dir, output_dir, **kwargs: ConversionResult(
                series_dir=str(series_dir),
                success=True,
            )
            results = convert_to_nifti(
                root,
                tmp_path / "out",
                series_metadata=[meta],
                dcm2niix_path="custom-dcm2niix",
            )

        assert len(results) == 2
        converted_dirs = {str(call.args[0]) for call in mock_convert.call_args_list}
        assert converted_dirs == {str(series_a), str(series_b)}
        first_kwargs = mock_convert.call_args_list[0].kwargs
        assert first_kwargs["dcm2niix_path"] == "custom-dcm2niix"
