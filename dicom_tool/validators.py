"""Validation checks for DICOM series metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np

from .extractor import SeriesMetadata

Status = Literal["pass", "warn", "fail"]


@dataclass
class ValidationResult:
    check: str
    status: Status
    message: str


# Kernel name normalisation maps per vendor
_KERNEL_MAP: dict[str, dict[str, str]] = {
    "siemens": {
        "b10": "soft", "b20": "soft", "b30": "standard", "b31": "standard",
        "b40": "standard", "b41": "standard", "b45": "standard",
        "b50": "sharp", "b60": "sharp", "b70": "sharp", "b80": "bone",
        "b90": "bone",
    },
    "ge": {
        "soft": "soft", "standard": "standard", "detail": "sharp",
        "bone": "bone", "lung": "sharp", "edge": "sharp",
    },
    "philips": {
        "b": "soft", "c": "standard", "d": "sharp", "ya": "standard",
        "yb": "sharp", "yc": "bone",
    },
    "canon": {
        "fc01": "soft", "fc02": "soft", "fc03": "standard", "fc04": "standard",
        "fc05": "sharp", "fc06": "sharp", "fc07": "bone", "fc08": "bone",
    },
}


def _normalise_kernel(manufacturer: Optional[str], kernel: Optional[str]) -> Optional[str]:
    if not kernel:
        return None
    k = kernel.lower().strip()
    if manufacturer:
        m = manufacturer.lower()
        for vendor, mapping in _KERNEL_MAP.items():
            if vendor in m:
                for key, category in mapping.items():
                    if k.startswith(key):
                        return category
    # Fallback: direct keyword match
    for category in ("soft", "standard", "sharp", "bone", "lung"):
        if category in k:
            return category
    return None


def check_slice_spacing(
    meta: SeriesMetadata, tolerance: float = 0.1
) -> ValidationResult:
    """Compare declared slice thickness against computed inter-slice distances."""
    if len(meta.image_positions) < 2:
        return ValidationResult(
            "slice_spacing", "warn",
            f"Only {len(meta.image_positions)} position(s) found — cannot compute spacing."
        )

    positions = np.array(meta.image_positions)
    diffs = np.linalg.norm(np.diff(positions, axis=0), axis=1)

    if len(diffs) == 0:
        return ValidationResult("slice_spacing", "warn", "No inter-slice distances computable.")

    mean_spacing = float(np.mean(diffs))
    std_spacing = float(np.std(diffs))
    min_spacing = float(np.min(diffs))
    max_spacing = float(np.max(diffs))

    irregular = std_spacing > tolerance
    mismatch = (
        meta.slice_thickness is not None
        and abs(mean_spacing - meta.slice_thickness) > tolerance
    )

    if irregular:
        return ValidationResult(
            "slice_spacing", "fail",
            f"Irregular slice spacing detected: mean={mean_spacing:.3f}, "
            f"std={std_spacing:.3f}, min={min_spacing:.3f}, max={max_spacing:.3f} mm."
        )
    if mismatch:
        return ValidationResult(
            "slice_spacing", "warn",
            f"Spacing mismatch: declared thickness={meta.slice_thickness:.3f} mm, "
            f"computed mean={mean_spacing:.3f} mm."
        )
    return ValidationResult(
        "slice_spacing", "pass",
        f"Slice spacing consistent: mean={mean_spacing:.3f} mm, std={std_spacing:.4f} mm."
    )


def check_kernel(meta: SeriesMetadata) -> ValidationResult:
    """Normalise reconstruction kernel to a common category."""
    if not meta.convolution_kernel:
        return ValidationResult("kernel", "warn", "ConvolutionKernel tag absent.")

    normalised = _normalise_kernel(meta.manufacturer, meta.convolution_kernel)
    if normalised:
        return ValidationResult(
            "kernel", "pass",
            f"Kernel '{meta.convolution_kernel}' normalised to '{normalised}'."
        )
    return ValidationResult(
        "kernel", "warn",
        f"Kernel '{meta.convolution_kernel}' could not be normalised — unknown vendor/naming."
    )


def check_orientation(meta: SeriesMetadata, tolerance: float = 1e-4) -> ValidationResult:
    """Check that image orientation cosines are consistent and well-formed."""
    iop = meta.image_orientation_patient
    if not iop or len(iop) != 6:
        return ValidationResult("orientation", "warn", "ImageOrientationPatient tag absent or malformed.")

    row_cos = np.array(iop[:3])
    col_cos = np.array(iop[3:])
    normal = np.cross(row_cos, col_cos)

    row_norm = float(np.linalg.norm(row_cos))
    col_norm = float(np.linalg.norm(col_cos))
    dot = float(np.dot(row_cos, col_cos))

    if abs(row_norm - 1.0) > tolerance or abs(col_norm - 1.0) > tolerance:
        return ValidationResult(
            "orientation", "fail",
            f"Orientation cosines not unit vectors: |row|={row_norm:.6f}, |col|={col_norm:.6f}."
        )
    if abs(dot) > tolerance:
        return ValidationResult(
            "orientation", "fail",
            f"Row and column cosines not orthogonal: dot product={dot:.6f}."
        )

    normal_norm = float(np.linalg.norm(normal))
    if abs(normal_norm - 1.0) > tolerance:
        return ValidationResult(
            "orientation", "fail",
            f"Normal vector magnitude={normal_norm:.6f} — affine may be degenerate."
        )

    return ValidationResult("orientation", "pass", "Image orientation cosines are valid and orthonormal.")


def validate_series(meta: SeriesMetadata, spacing_tolerance: float = 0.1) -> list[ValidationResult]:
    """Run all validators and return a list of results."""
    return [
        check_slice_spacing(meta, tolerance=spacing_tolerance),
        check_kernel(meta),
        check_orientation(meta),
    ]
