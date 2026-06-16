"""Tests for dicom_tool.cli."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from dicom_tool.converter import ConversionResult
from dicom_tool.cli import cli
from dicom_tool.extractor import SeriesMetadata
from dicom_tool.pipeline import PipelineResult
from dicom_tool.validators import ValidationResult


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def fake_meta() -> list[SeriesMetadata]:
    return [
        SeriesMetadata(
            pixel_spacing=[0.75, 0.75],
            slice_thickness=1.0,
            image_orientation_patient=[1, 0, 0, 0, 1, 0],
            image_positions=[[0, 0, z] for z in range(5)],
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
    ]


@pytest.fixture()
def all_pass_results() -> list[ValidationResult]:
    return [
        ValidationResult("slice_spacing", "pass", "OK"),
        ValidationResult("kernel", "pass", "OK"),
        ValidationResult("orientation", "pass", "OK"),
    ]


# ---------------------------------------------------------------------------
# extract command
# ---------------------------------------------------------------------------

class TestExtractCommand:
    def test_stdout_output(self, runner, tmp_path, fake_meta):
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta):
            result = runner.invoke(cli, ["extract", str(tmp_path)])
        assert result.exit_code == 0
        assert "Siemens" in result.output

    def test_json_format(self, runner, tmp_path, fake_meta):
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta):
            result = runner.invoke(cli, ["extract", str(tmp_path), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["manufacturer"] == "Siemens"

    def test_no_series_exits_nonzero(self, runner, tmp_path):
        with patch("dicom_tool.cli.extract_metadata", return_value=[]):
            result = runner.invoke(cli, ["extract", str(tmp_path)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# validate command
# ---------------------------------------------------------------------------

class TestValidateCommand:
    def test_all_pass(self, runner, tmp_path, fake_meta, all_pass_results):
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta), \
             patch("dicom_tool.cli.validate_series", return_value=all_pass_results):
            result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_exit_2_on_fail(self, runner, tmp_path, fake_meta):
        fail_results = [
            ValidationResult("slice_spacing", "fail", "Irregular spacing"),
            ValidationResult("kernel", "pass", "OK"),
            ValidationResult("orientation", "pass", "OK"),
        ]
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta), \
             patch("dicom_tool.cli.validate_series", return_value=fail_results):
            result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code == 2

    def test_strict_exits_1_on_warn(self, runner, tmp_path, fake_meta):
        warn_results = [
            ValidationResult("slice_spacing", "warn", "Mismatch"),
            ValidationResult("kernel", "pass", "OK"),
            ValidationResult("orientation", "pass", "OK"),
        ]
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta), \
             patch("dicom_tool.cli.validate_series", return_value=warn_results):
            result = runner.invoke(cli, ["validate", str(tmp_path), "--strict"])
        assert result.exit_code == 1

    def test_no_series_exits_nonzero(self, runner, tmp_path):
        with patch("dicom_tool.cli.extract_metadata", return_value=[]):
            result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------

class TestReportCommand:
    def test_stdout_report(self, runner, tmp_path, fake_meta):
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta):
            result = runner.invoke(cli, ["report", str(tmp_path)])
        assert result.exit_code == 0
        assert "Cohort Summary" in result.output

    def test_csv_output(self, runner, tmp_path, fake_meta):
        out = tmp_path / "report.csv"
        with patch("dicom_tool.cli.extract_metadata", return_value=fake_meta):
            result = runner.invoke(
                cli, ["report", str(tmp_path), "--output", str(out), "--format", "csv"]
            )
        assert result.exit_code == 0
        assert out.exists()

    def test_no_series_exits_nonzero(self, runner, tmp_path):
        with patch("dicom_tool.cli.extract_metadata", return_value=[]):
            result = runner.invoke(cli, ["report", str(tmp_path)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# convert command
# ---------------------------------------------------------------------------

class TestConvertCommand:
    def test_success_output(self, runner, tmp_path):
        pipeline_result = PipelineResult(
            conversion_results=[
                ConversionResult(series_dir=str(tmp_path / "series"), success=True)
            ]
        )
        with patch("dicom_tool.cli.run_pipeline", return_value=pipeline_result) as mock_run:
            result = runner.invoke(
                cli, ["convert", str(tmp_path), "--output", str(tmp_path / "out")]
            )

        assert result.exit_code == 0
        assert "[OK]" in result.output
        mock_run.assert_called_once()

    def test_failure_output(self, runner, tmp_path):
        pipeline_result = PipelineResult(
            conversion_results=[
                ConversionResult(
                    series_dir=str(tmp_path / "series"),
                    success=False,
                    error="dcm2niix failed",
                )
            ]
        )
        with patch("dicom_tool.cli.run_pipeline", return_value=pipeline_result):
            result = runner.invoke(
                cli, ["convert", str(tmp_path), "--output", str(tmp_path / "out")]
            )

        assert result.exit_code == 0
        assert "[FAIL]" in result.output
        assert "dcm2niix failed" in result.output

    def test_custom_dcm2niix_path_passed_to_pipeline(self, runner, tmp_path):
        pipeline_result = PipelineResult(conversion_results=[])
        with patch("dicom_tool.cli.run_pipeline", return_value=pipeline_result) as mock_run:
            result = runner.invoke(
                cli,
                [
                    "convert",
                    str(tmp_path),
                    "--output",
                    str(tmp_path / "out"),
                    "--dcm2niix",
                    "custom-dcm2niix",
                ],
            )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["dcm2niix_path"] == "custom-dcm2niix"
