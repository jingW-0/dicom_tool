"""Tests for dicom_tool.pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from dicom_tool.converter import ConversionResult
from dicom_tool.extractor import SeriesMetadata
from dicom_tool.pipeline import PipelineResult, run_pipeline
from dicom_tool.validators import ValidationResult


def _meta(series_dir: str = "/fake/series") -> SeriesMetadata:
    return SeriesMetadata(
        num_slices=5,
        modality="CT",
        series_instance_uid="1.2.3",
        series_dir=series_dir,
    )


class TestRunPipeline:
    def test_extract_validate_and_report(self, tmp_path):
        meta = _meta(str(tmp_path / "series"))
        validation = [ValidationResult("kernel", "pass", "OK")]
        report = pd.DataFrame([{"series_dir": meta.series_dir, "any_fail": False}])

        with patch("dicom_tool.pipeline.extract_metadata", return_value=[meta]), \
             patch("dicom_tool.pipeline.validate_series", return_value=validation), \
             patch("dicom_tool.pipeline.build_cohort_report", return_value=report):
            result = run_pipeline(tmp_path)

        assert isinstance(result, PipelineResult)
        assert result.series_metadata == [meta]
        assert result.validation_results[meta.series_dir] == validation
        assert result.cohort_report is report

    def test_runs_conversion_when_requested(self, tmp_path):
        meta = _meta(str(tmp_path / "series"))
        conversion = [ConversionResult(series_dir=meta.series_dir, success=True)]

        with patch("dicom_tool.pipeline.extract_metadata", return_value=[meta]), \
             patch("dicom_tool.pipeline.validate_series", return_value=[]), \
             patch("dicom_tool.pipeline.convert_to_nifti", return_value=conversion) as mock_convert, \
             patch("dicom_tool.pipeline.build_cohort_report", return_value=pd.DataFrame()):
            result = run_pipeline(
                tmp_path,
                output_dir=tmp_path / "out",
                run_conversion=True,
                dcm2niix_path="custom-dcm2niix",
            )

        assert result.conversion_results == conversion
        mock_convert.assert_called_once_with(
            tmp_path,
            tmp_path / "out",
            series_metadata=[meta],
            dcm2niix_path="custom-dcm2niix",
        )

    def test_report_path_uses_output_dir_for_file_formats(self, tmp_path):
        with patch("dicom_tool.pipeline.extract_metadata", return_value=[]), \
             patch("dicom_tool.pipeline.build_cohort_report", return_value=pd.DataFrame()) as mock_report:
            run_pipeline(tmp_path, output_dir=tmp_path / "out", output_format="csv")

        assert mock_report.call_args.kwargs["output_path"] == tmp_path / "out" / "cohort_report.csv"
