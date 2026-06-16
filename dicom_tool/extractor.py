"""DICOM metadata extraction API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pydicom


def _safe_get(ds: pydicom.Dataset, tag: str, default: Any = None) -> Any:
    try:
        val = getattr(ds, tag, None)
        if val is None:
            return default
        if hasattr(val, "value"):
            val = val.value
        return val
    except Exception:
        return default


@dataclass
class SeriesMetadata:
    # Spatial
    pixel_spacing: Optional[list[float]] = None
    slice_thickness: Optional[float] = None
    image_orientation_patient: Optional[list[float]] = None
    image_positions: list[list[float]] = field(default_factory=list)
    num_slices: int = 0
    rows: Optional[int] = None
    columns: Optional[int] = None

    # Scanner / series
    manufacturer: Optional[str] = None
    manufacturer_model_name: Optional[str] = None
    convolution_kernel: Optional[str] = None
    kvp: Optional[float] = None
    modality: Optional[str] = None
    series_description: Optional[str] = None
    series_instance_uid: Optional[str] = None
    study_instance_uid: Optional[str] = None
    acquisition_date: Optional[str] = None

    # Source
    series_dir: Optional[str] = None


def _parse_float_seq(val: Any) -> Optional[list[float]]:
    if val is None:
        return None
    try:
        return [float(v) for v in val]
    except Exception:
        return None


def _load_slices(series_dir: Path) -> list[pydicom.Dataset]:
    slices = []
    for f in sorted(series_dir.iterdir()):
        if f.is_file():
            try:
                ds = pydicom.dcmread(str(f), stop_before_pixels=True)
                slices.append(ds)
            except Exception:
                pass
    return slices


def extract_series_metadata(series_dir: str | Path) -> SeriesMetadata:
    """Extract metadata from all DICOM files in a series directory."""
    series_dir = Path(series_dir)
    slices = _load_slices(series_dir)
    if not slices:
        return SeriesMetadata(series_dir=str(series_dir))

    # Use the first slice for scalar fields
    ds = slices[0]

    ps = _safe_get(ds, "PixelSpacing")
    orientation = _safe_get(ds, "ImageOrientationPatient")

    positions = []
    for s in slices:
        pos = _safe_get(s, "ImagePositionPatient")
        if pos is not None:
            p = _parse_float_seq(pos)
            if p:
                positions.append(p)

    kernel = _safe_get(ds, "ConvolutionKernel")
    if isinstance(kernel, pydicom.sequence.Sequence) or hasattr(kernel, "__iter__") and not isinstance(kernel, str):
        try:
            kernel = kernel[0] if len(kernel) > 0 else None
        except Exception:
            kernel = str(kernel)

    kvp = _safe_get(ds, "KVP")
    try:
        kvp = float(kvp) if kvp is not None else None
    except Exception:
        kvp = None

    thickness = _safe_get(ds, "SliceThickness")
    try:
        thickness = float(thickness) if thickness is not None else None
    except Exception:
        thickness = None

    return SeriesMetadata(
        pixel_spacing=_parse_float_seq(ps),
        slice_thickness=thickness,
        image_orientation_patient=_parse_float_seq(orientation),
        image_positions=positions,
        num_slices=len(slices),
        rows=_safe_get(ds, "Rows"),
        columns=_safe_get(ds, "Columns"),
        manufacturer=_safe_get(ds, "Manufacturer"),
        manufacturer_model_name=_safe_get(ds, "ManufacturerModelName"),
        convolution_kernel=str(kernel) if kernel is not None else None,
        kvp=kvp,
        modality=_safe_get(ds, "Modality"),
        series_description=_safe_get(ds, "SeriesDescription"),
        series_instance_uid=str(_safe_get(ds, "SeriesInstanceUID", "")),
        study_instance_uid=str(_safe_get(ds, "StudyInstanceUID", "")),
        acquisition_date=_safe_get(ds, "AcquisitionDate"),
        series_dir=str(series_dir),
    )


def extract_metadata(root_dir: str | Path) -> list[SeriesMetadata]:
    """Walk root_dir and extract metadata from every DICOM series found."""
    root_dir = Path(root_dir)
    results = []
    for dirpath, _, filenames in os.walk(root_dir):
        if any(f.endswith(".dcm") or "." not in f for f in filenames):
            meta = extract_series_metadata(dirpath)
            if meta.num_slices > 0:
                results.append(meta)
    return results
