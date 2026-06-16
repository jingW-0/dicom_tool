"""Shared fixtures for dicom_tool tests."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, UID

from dicom_tool.extractor import SeriesMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ds(
    *,
    rows: int = 512,
    cols: int = 512,
    pixel_spacing: tuple[float, float] = (0.75, 0.75),
    slice_thickness: float = 1.0,
    iop: tuple = (1, 0, 0, 0, 1, 0),
    ipp: tuple[float, float, float] = (0.0, 0.0, 0.0),
    manufacturer: str = "Siemens",
    model: str = "SOMATOM Force",
    kernel: str = "B31f",
    kvp: float = 120.0,
    modality: str = "CT",
    series_desc: str = "CHEST",
    series_uid: str = "1.2.3.4.5",
    study_uid: str = "1.2.3.4",
    acq_date: str = "20240101",
) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ds.Rows = rows
    ds.Columns = cols
    ds.PixelSpacing = list(pixel_spacing)
    ds.SliceThickness = slice_thickness
    ds.ImageOrientationPatient = list(iop)
    ds.ImagePositionPatient = list(ipp)
    ds.Manufacturer = manufacturer
    ds.ManufacturerModelName = model
    ds.ConvolutionKernel = kernel
    ds.KVP = kvp
    ds.Modality = modality
    ds.SeriesDescription = series_desc
    ds.SeriesInstanceUID = series_uid
    ds.StudyInstanceUID = study_uid
    ds.AcquisitionDate = acq_date
    return ds


def _write_dicom(path: Path, ds: Dataset) -> None:
    """Write a minimal valid DICOM file (no pixel data needed for metadata tests)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fds = FileDataset(str(path), dataset=ds, file_meta=ds.file_meta, preamble=b"\x00" * 128)
    fds.is_implicit_VR = False
    fds.is_little_endian = True
    pydicom.dcmwrite(str(path), fds)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def base_ds():
    """A well-formed single-slice dataset."""
    return _make_ds()


@pytest.fixture()
def series_dir(tmp_path):
    """A temporary directory with 5 well-spaced DICOM slices."""
    for i in range(5):
        ds = _make_ds(ipp=(0.0, 0.0, float(i)), series_uid="1.2.3.4.5.6")
        _write_dicom(tmp_path / f"slice_{i:03d}.dcm", ds)
    return tmp_path


@pytest.fixture()
def irregular_series_dir(tmp_path):
    """A temporary directory with irregular inter-slice spacing."""
    positions = [0.0, 1.0, 2.5, 4.5, 5.0]
    for i, z in enumerate(positions):
        ds = _make_ds(ipp=(0.0, 0.0, z), series_uid="1.2.3.4.5.7")
        _write_dicom(tmp_path / f"slice_{i:03d}.dcm", ds)
    return tmp_path


@pytest.fixture()
def well_formed_meta() -> SeriesMetadata:
    """Pre-built SeriesMetadata for a clean 5-slice series."""
    return SeriesMetadata(
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
