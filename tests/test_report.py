"""Tests for dicom_tool.report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dicom_tool.extractor import SeriesMetadata
from dicom_tool.report import build_cohort_report, print_summary


def _make_series(n: int = 3) -> list[SeriesMetadata]:
    return [
        SeriesMetadata(
            pixel_spacing=[0.75, 0.75],
            slice_thickness=1.0,
            image_orientation_patient=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            image_positions=[[0, 0, z] for z in range(5)],
            num_slices=5,
            rows=512,
            columns=512,
            manufacturer="Siemens",
            manufacturer_model_name="SOMATOM Force",
            convolution_kernel="B31f",
            kvp=120.0,
            modality="CT",
            series_description=f"CHEST_{i}",
            series_instance_uid=f"1.2.3.{i}",
            study_instance_uid="1.2.3",
            acquisition_date="20240101",
            series_dir=f"/fake/study/series_{i}",
        )
        for i in range(n)
    ]


class TestBuildCohortReport:
    def test_returns_dataframe(self):
        df = build_cohort_report(_make_series(), output_format="stdout")
        assert isinstance(df, pd.DataFrame)

    def test_row_count_matches_series(self):
        series = _make_series(4)
        df = build_cohort_report(series, output_format="stdout")
        assert len(df) == 4

    def test_expected_columns_present(self):
        df = build_cohort_report(_make_series(), output_format="stdout")
        for col in ("manufacturer", "modality", "num_slices", "any_fail", "any_warn"):
            assert col in df.columns, f"Missing column: {col}"

    def test_clean_series_no_failures(self):
        df = build_cohort_report(_make_series(), output_format="stdout")
        assert not df["any_fail"].any()

    def test_csv_output(self, tmp_path):
        out = tmp_path / "report.csv"
        build_cohort_report(_make_series(), output_path=out, output_format="csv")
        assert out.exists()
        loaded = pd.read_csv(out)
        assert len(loaded) == 3

    def test_json_output(self, tmp_path):
        out = tmp_path / "report.json"
        build_cohort_report(_make_series(), output_path=out, output_format="json")
        assert out.exists()
        loaded = pd.read_json(out)
        assert len(loaded) == 3

    def test_output_dir_created_if_missing(self, tmp_path):
        out = tmp_path / "nested" / "deep" / "report.csv"
        build_cohort_report(_make_series(), output_path=out, output_format="csv")
        assert out.exists()

    def test_empty_series_list(self):
        df = build_cohort_report([], output_format="stdout")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestPrintSummary:
    def test_runs_without_error(self, capsys):
        df = build_cohort_report(_make_series(), output_format="stdout")
        print_summary(df)
        captured = capsys.readouterr()
        assert "Cohort Summary" in captured.out
        assert "modality" in captured.out.lower() or "CT" in captured.out
