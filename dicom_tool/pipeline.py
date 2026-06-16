"""End-to-end orchestration: extract → validate → convert → report."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .converter import ConversionResult, convert_to_nifti
from .extractor import SeriesMetadata, extract_metadata
from .report import build_cohort_report
from .validators import ValidationResult, validate_series


@dataclass
class PipelineResult:
    series_metadata: list[SeriesMetadata] = field(default_factory=list)
    validation_results: dict[str, list[ValidationResult]] = field(default_factory=dict)
    conversion_results: list[ConversionResult] = field(default_factory=list)
    cohort_report: Optional[pd.DataFrame] = None


def run_pipeline(
    dicom_root: str | Path,
    output_dir: Optional[str | Path] = None,
    run_conversion: bool = False,
    output_format: str = "stdout",
    spacing_tolerance: float = 0.1,
    dcm2niix_path: str = "dcm2niix",
) -> PipelineResult:
    """
    Full pipeline over a directory of DICOM studies.

    1. Extract metadata from every series.
    2. Run all validators.
    3. Optionally convert to NIfTI.
    4. Build cohort report.
    """
    dicom_root = Path(dicom_root)
    result = PipelineResult()

    result.series_metadata = extract_metadata(dicom_root)

    for meta in result.series_metadata:
        key = meta.series_dir or str(meta.series_instance_uid)
        result.validation_results[key] = validate_series(meta, spacing_tolerance=spacing_tolerance)

    if run_conversion and output_dir is not None:
        result.conversion_results = convert_to_nifti(
            dicom_root,
            output_dir,
            series_metadata=result.series_metadata,
            dcm2niix_path=dcm2niix_path,
        )

    report_path = None
    fmt = output_format
    if output_dir is not None and output_format in ("csv", "json"):
        report_path = Path(output_dir) / f"cohort_report.{output_format}"
    elif output_format in ("csv", "json"):
        report_path = Path(f"cohort_report.{output_format}")
    else:
        fmt = "stdout"

    result.cohort_report = build_cohort_report(
        result.series_metadata,
        output_path=report_path,
        output_format=fmt,
        spacing_tolerance=spacing_tolerance,
    )

    return result
