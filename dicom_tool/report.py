"""Cohort-level summary report from DICOM metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from .extractor import SeriesMetadata
from .validators import ValidationResult, validate_series


OutputFormat = Literal["csv", "json", "stdout"]


def _meta_to_row(meta: SeriesMetadata, val_results: list[ValidationResult]) -> dict:
    spacing_check = next((r for r in val_results if r.check == "slice_spacing"), None)
    kernel_check = next((r for r in val_results if r.check == "kernel"), None)
    orient_check = next((r for r in val_results if r.check == "orientation"), None)

    ps = meta.pixel_spacing
    return {
        "series_dir": meta.series_dir,
        "study_instance_uid": meta.study_instance_uid,
        "series_instance_uid": meta.series_instance_uid,
        "modality": meta.modality,
        "series_description": meta.series_description,
        "manufacturer": meta.manufacturer,
        "manufacturer_model_name": meta.manufacturer_model_name,
        "convolution_kernel": meta.convolution_kernel,
        "kvp": meta.kvp,
        "num_slices": meta.num_slices,
        "rows": meta.rows,
        "columns": meta.columns,
        "pixel_spacing_row": ps[0] if ps and len(ps) > 0 else None,
        "pixel_spacing_col": ps[1] if ps and len(ps) > 1 else None,
        "slice_thickness": meta.slice_thickness,
        "acquisition_date": meta.acquisition_date,
        "val_spacing_status": spacing_check.status if spacing_check else None,
        "val_spacing_message": spacing_check.message if spacing_check else None,
        "val_kernel_status": kernel_check.status if kernel_check else None,
        "val_kernel_message": kernel_check.message if kernel_check else None,
        "val_orientation_status": orient_check.status if orient_check else None,
        "val_orientation_message": orient_check.message if orient_check else None,
        "any_fail": any(r.status == "fail" for r in val_results),
        "any_warn": any(r.status == "warn" for r in val_results),
    }


def build_cohort_report(
    series_list: list[SeriesMetadata],
    output_path: Optional[str | Path] = None,
    output_format: OutputFormat = "stdout",
    spacing_tolerance: float = 0.1,
) -> pd.DataFrame:
    """Aggregate metadata and validation results into a cohort DataFrame."""
    rows = []
    for meta in series_list:
        val = validate_series(meta, spacing_tolerance=spacing_tolerance)
        rows.append(_meta_to_row(meta, val))

    df = pd.DataFrame(rows)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "csv":
            df.to_csv(output_path, index=False)
        elif output_format == "json":
            df.to_json(output_path, orient="records", indent=2)
    elif output_format == "stdout":
        print(df.to_string())

    return df


def print_summary(df: pd.DataFrame) -> None:
    """Print a human-readable cohort summary to stdout."""
    print(f"\n=== Cohort Summary ({len(df)} series) ===\n")

    if "modality" in df.columns:
        print("Series per modality:")
        print(df["modality"].value_counts().to_string(), "\n")

    if "manufacturer" in df.columns:
        print("Scanner distribution:")
        cols = ["manufacturer", "manufacturer_model_name", "convolution_kernel"]
        available = [c for c in cols if c in df.columns]
        print(df[available].value_counts().to_string(), "\n")

    if "slice_thickness" in df.columns:
        print("Slice spacing statistics (mm):")
        print(df["slice_thickness"].describe().to_string(), "\n")

    if "any_fail" in df.columns:
        n_fail = df["any_fail"].sum()
        n_warn = df["any_warn"].sum()
        print(f"Validation: {n_fail} series with failures, {n_warn} with warnings.")
