# DICOM tool build plan

## Overview

A Python-based preprocessing tool for medical imaging pipelines, targeting ML/AI engineers and medical imaging researchers. The tool extracts DICOM metadata, validates data quality, converts to NIfTI, and reports cohort-level statistics — packaged as both a CLI and an importable Python API.

---

## File structure

```
dicom_tool/
├── extractor.py       # metadata extraction API
├── validators.py      # spacing, kernel, manufacturer checks
├── converter.py       # NIfTI conversion wrapper
├── report.py          # dataset-level cohort summary
├── pipeline.py        # orchestrates the above into a full workflow
└── cli.py             # click entry point, thin wrapper over pipeline.py
```

---

## Phase 1 — Core foundation

**Module:** `extractor.py`

Everything else depends on this. Build the central metadata extraction API first.

### Safe tag access helper

DICOM tags are frequently absent or malformed in real-world data despite being mandatory per the standard. All tag reads must go through a safe-get helper that returns a default rather than raising. This prevents silent failures downstream.

### Spatial field extraction

Fields required for resampling validation and model input consistency:

- Pixel spacing
- Slice thickness
- Image orientation (patient)
- Image position (patient)
- Number of slices
- Rows and columns

### Scanner and series field extraction

Fields required for dataset stratification and scanner-confound auditing:

- Manufacturer
- Manufacturer model name
- Reconstruction kernel (convolution kernel)
- kVp
- Modality
- Series description
- Series instance UID
- Study instance UID
- Acquisition date

---

## Phase 2 — Validation checks

**Module:** `validators.py`

Consumers of the extractor. Each validator returns a structured result — `pass`, `warn`, or `fail` — with a message, not just a boolean.

### Slice spacing checker

Computes the actual inter-slice distance from image position vectors and compares it against the declared slice thickness. Flags irregular spacing, missing slices, and mismatches beyond a configurable tolerance. This is the most critical check for ML pipelines — inconsistent spacing is a common silent failure.

### Kernel and vendor parser

Normalises manufacturer-specific kernel naming into comparable categories (e.g. soft, standard, sharp, bone). Siemens, GE, Philips, and Canon each use different naming conventions for equivalent kernels. The parser maps these to a common schema so cross-scanner datasets can be stratified correctly.

### Orientation validator

Checks that the image orientation cosines are consistent across all slices in a series and that the affine matrix is well-formed before NIfTI conversion. Catches studies where patient orientation is inconsistent — a common issue with localiser series mixed into volumetric studies.

---

## Phase 3 — Conversion and reporting

**Modules:** `converter.py`, `report.py`

### NIfTI conversion wrapper (`converter.py`)

Wraps `dcm2niix` via subprocess with:

- Batch handling across multiple series
- Error recovery with per-study failure logging
- Consistent output naming conventions
- Sidecar JSON enrichment — fields extracted in Phase 1 are written into the `.json` sidecar alongside the standard BIDS fields, preserving provenance through conversion

### Cohort summary report (`report.py`)

Aggregates metadata across N studies into a pandas DataFrame. Output includes:

- Scanner and kernel distribution across the dataset
- Slice spacing statistics (mean, std, min, max)
- Flagged studies from Phase 2 validators
- Series counts per modality
- Export to CSV or JSON

---

## Phase 4 — Dual packaging

**Modules:** `pipeline.py`, `cli.py`

### Orchestrator (`pipeline.py`)

Wires Phases 1–3 into a full end-to-end workflow. Accepts a directory of DICOM studies, runs extraction → validation → conversion → reporting in sequence, and returns a structured result object. Both the CLI and the Python API call this directly.

### CLI (`cli.py`)

Built with `click`. Four commands, each a thin wrapper over `pipeline.py`:

| Command | Description |
|---|---|
| `dicom-tool extract <dir>` | Extract and print metadata for all series |
| `dicom-tool validate <dir>` | Run all validators and report pass/warn/fail |
| `dicom-tool convert <dir>` | Convert to NIfTI with enriched sidecars |
| `dicom-tool report <dir>` | Generate cohort-level summary |

Shared flags: `--output <path>`, `--format [csv\|json\|stdout]`, `--strict` (fail on warn).

### Python API

The same underlying pipeline, directly importable:

```python
from dicom_tool import (
    extract_metadata,
    validate_series,
    convert_to_nifti,
    build_cohort_report,
)
```

Designed to embed cleanly into PyTorch or other ML data loading pipelines. Each function accepts a path and returns a typed result object.

---

## Key dependencies

| Library | Purpose |
|---|---|
| `pydicom` | DICOM file reading and tag access |
| `nibabel` | NIfTI read/write |
| `dcm2niix` | NIfTI conversion (called via subprocess) |
| `numpy` | Spacing and affine math |
| `pandas` | Cohort-level metadata aggregation |
| `click` | CLI framework |

---

## Packaging

Distribute as a single PyPI-publishable package with both the Python API and the CLI entry point declared in `pyproject.toml`. The CLI is registered as a console script so `dicom-tool` is available on the path after `pip install`.
