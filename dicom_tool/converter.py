"""NIfTI conversion wrapper around dcm2niix."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .extractor import SeriesMetadata

log = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    series_dir: str
    success: bool
    output_files: list[str] = field(default_factory=list)
    error: Optional[str] = None


def _enrich_sidecar(json_path: Path, meta: SeriesMetadata) -> None:
    """Write Phase-1 fields into an existing BIDS JSON sidecar."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
    except Exception:
        data = {}

    provenance = {
        "PixelSpacing": meta.pixel_spacing,
        "SliceThickness": meta.slice_thickness,
        "ImageOrientationPatient": meta.image_orientation_patient,
        "NumSlices": meta.num_slices,
        "Rows": meta.rows,
        "Columns": meta.columns,
        "Manufacturer": meta.manufacturer,
        "ManufacturerModelName": meta.manufacturer_model_name,
        "ConvolutionKernel": meta.convolution_kernel,
        "KVP": meta.kvp,
        "Modality": meta.modality,
        "SeriesDescription": meta.series_description,
        "SeriesInstanceUID": meta.series_instance_uid,
        "StudyInstanceUID": meta.study_instance_uid,
        "AcquisitionDate": meta.acquisition_date,
    }
    data["dicom_tool_provenance"] = {k: v for k, v in provenance.items() if v is not None}

    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def convert_series(
    series_dir: str | Path,
    output_dir: str | Path,
    meta: Optional[SeriesMetadata] = None,
    dcm2niix_path: str = "dcm2niix",
) -> ConversionResult:
    """Convert a single DICOM series to NIfTI using dcm2niix."""
    series_dir = Path(series_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        dcm2niix_path,
        "-z", "y",          # gzip output
        "-b", "y",          # BIDS sidecar
        "-o", str(output_dir),
        str(series_dir),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            return ConversionResult(
                series_dir=str(series_dir),
                success=False,
                error=proc.stderr.strip() or proc.stdout.strip(),
            )
    except FileNotFoundError:
        return ConversionResult(
            series_dir=str(series_dir),
            success=False,
            error="dcm2niix not found on PATH. Install it from https://github.com/rordenlab/dcm2niix",
        )
    except subprocess.TimeoutExpired:
        return ConversionResult(
            series_dir=str(series_dir),
            success=False,
            error="dcm2niix timed out after 300 s.",
        )

    output_files = [str(p) for p in output_dir.iterdir() if p.suffix in (".gz", ".nii", ".json")]

    if meta is not None:
        for p in output_dir.glob("*.json"):
            _enrich_sidecar(p, meta)

    return ConversionResult(
        series_dir=str(series_dir),
        success=True,
        output_files=output_files,
    )


def convert_to_nifti(
    root_dir: str | Path,
    output_dir: str | Path,
    series_metadata: Optional[list[SeriesMetadata]] = None,
    dcm2niix_path: str = "dcm2niix",
) -> list[ConversionResult]:
    """Batch-convert all series under root_dir to NIfTI."""
    root_dir = Path(root_dir)
    output_dir = Path(output_dir)

    meta_map: dict[str, SeriesMetadata] = {}
    if series_metadata:
        for m in series_metadata:
            if m.series_dir:
                meta_map[m.series_dir] = m

    results = []
    for series_path in sorted(root_dir.rglob("*")):
        if not series_path.is_dir():
            continue
        if not any(True for _ in series_path.iterdir() if _.is_file()):
            continue

        rel = series_path.relative_to(root_dir)
        out = output_dir / rel
        meta = meta_map.get(str(series_path))

        log.info("Converting %s", series_path)
        result = convert_series(series_path, out, meta=meta, dcm2niix_path=dcm2niix_path)
        if not result.success:
            log.warning("Conversion failed for %s: %s", series_path, result.error)
        results.append(result)

    return results
