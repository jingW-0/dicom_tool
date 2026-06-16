"""dicom_tool — DICOM preprocessing library for ML/AI pipelines."""

from .extractor import SeriesMetadata, extract_metadata, extract_series_metadata
from .pipeline import PipelineResult, run_pipeline
from .report import build_cohort_report
from .validators import ValidationResult, validate_series
from .converter import ConversionResult, convert_to_nifti

__all__ = [
    "SeriesMetadata",
    "extract_metadata",
    "extract_series_metadata",
    "ValidationResult",
    "validate_series",
    "ConversionResult",
    "convert_to_nifti",
    "build_cohort_report",
    "PipelineResult",
    "run_pipeline",
]
