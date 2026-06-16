# dicom-tool

`dicom-tool` is a Python toolkit for preparing DICOM imaging datasets for
machine learning and analysis workflows. It can extract series-level metadata,
run basic quality checks, convert DICOM series to NIfTI through `dcm2niix`, and
build cohort-level reports.

The package provides both a command line interface and an importable Python API.

## Features

- Recursive DICOM series discovery
- Metadata extraction for scanner, acquisition, image geometry, and series fields
- Slice spacing, reconstruction kernel, and orientation validation
- Vendor-aware reconstruction kernel normalisation
- NIfTI conversion using the external `dcm2niix` binary
- BIDS JSON sidecar enrichment with DICOM provenance
- Cohort reporting to stdout, CSV, or JSON

## Installation

Requires Python 3.9 or newer.

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -e .
```

NIfTI conversion also requires `dcm2niix` to be installed and available on your
`PATH`, or passed explicitly with `--dcm2niix`.

## Dependencies

| Library | Purpose |
| --- | --- |
| `pydicom` | Read DICOM files and tags |
| `nibabel` | NIfTI ecosystem support |
| `numpy` | Spacing and orientation math |
| `pandas` | Cohort-level tabular reports |
| `click` | Command line interface |
| `dcm2niix` | External DICOM-to-NIfTI converter |

## Command Line Usage

```bash
dicom-tool <command> <dicom_dir> [options]
```

### Extract Metadata

Print metadata for all discovered series:

```bash
dicom-tool extract /data/study_001
```

Write metadata as JSON:

```bash
dicom-tool extract /data/study_001 --format json --output metadata.json
```

### Validate Series

Run all quality checks:

```bash
dicom-tool validate /data/study_001
```

Treat warnings as a non-zero exit:

```bash
dicom-tool validate /data/study_001 --strict
```

Validation exit codes:

| Code | Meaning |
| --- | --- |
| `0` | No failures; warnings are allowed unless `--strict` is used |
| `1` | No series found, or warnings with `--strict` |
| `2` | At least one validation failure |

### Convert to NIfTI

Convert discovered DICOM series and enrich generated JSON sidecars:

```bash
dicom-tool convert /data/study_001 --output /out/nifti
```

Use a custom `dcm2niix` executable:

```bash
dicom-tool convert /data/study_001 --output /out/nifti --dcm2niix C:\tools\dcm2niix.exe
```

### Build a Cohort Report

Print a cohort summary:

```bash
dicom-tool report /data/cohort
```

Write CSV or JSON:

```bash
dicom-tool report /data/cohort --format csv --output cohort.csv
dicom-tool report /data/cohort --format json --output cohort.json
```

## Python API

```python
from dicom_tool import (
    extract_metadata,
    validate_series,
    convert_to_nifti,
    build_cohort_report,
    run_pipeline,
)
```

Extract metadata:

```python
series = extract_metadata("/data/cohort")

for item in series:
    print(item.series_dir, item.manufacturer, item.convolution_kernel)
```

Validate one series:

```python
results = validate_series(series[0])

for result in results:
    print(result.check, result.status, result.message)
```

Convert to NIfTI:

```python
conversion_results = convert_to_nifti(
    "/data/cohort",
    output_dir="/out/nifti",
    series_metadata=series,
)

for result in conversion_results:
    if not result.success:
        print(result.series_dir, result.error)
```

Build a report:

```python
df = build_cohort_report(series, output_path="cohort.csv", output_format="csv")
print(df[["manufacturer", "convolution_kernel", "num_slices", "any_fail"]])
```

Run the full pipeline:

```python
result = run_pipeline(
    "/data/cohort",
    output_dir="/out",
    run_conversion=True,
    output_format="csv",
)

print(result.cohort_report.head())
```

## Validation Checks

`dicom-tool` currently runs three checks for each series:

| Check | Behavior |
| --- | --- |
| Slice spacing | Computes inter-slice distances from `ImagePositionPatient` and compares them with `SliceThickness` |
| Kernel | Maps vendor-specific `ConvolutionKernel` values to common categories |
| Orientation | Verifies `ImageOrientationPatient` row and column cosines are unit length and orthogonal |

Kernel categories:

| Category | Siemens | GE | Philips | Canon |
| --- | --- | --- | --- | --- |
| `soft` | `B10`, `B20` | `SOFT` | `B` | `FC01`, `FC02` |
| `standard` | `B30`, `B31`, `B40`, `B41`, `B45` | `STANDARD` | `C`, `YA` | `FC03`, `FC04` |
| `sharp` | `B50`, `B60`, `B70` | `DETAIL`, `LUNG`, `EDGE` | `D`, `YB` | `FC05`, `FC06` |
| `bone` | `B80`, `B90` | `BONE` | `YC` | `FC07`, `FC08` |

## Project Layout

```text
dicom_tool/
  extractor.py    Metadata extraction and safe DICOM tag access
  validators.py   Slice spacing, kernel, and orientation checks
  converter.py    dcm2niix wrapper and sidecar enrichment
  report.py       Cohort DataFrame/report generation
  pipeline.py     End-to-end orchestration
  cli.py          Click command line interface
tests/
  conftest.py
  test_cli.py
  test_converter.py
  test_extractor.py
  test_report.py
  test_validators.py
```

## Testing

Install pytest in your environment, then run:

```bash
python -m pytest -q
```

Current coverage includes:

- Metadata extraction from synthetic DICOM files
- Missing and malformed metadata handling
- Slice spacing, kernel, and orientation validators
- Cohort report generation and CSV/JSON output
- `dcm2niix` success, failure, timeout, and missing-binary paths
- Batch conversion traversal
- BIDS sidecar provenance enrichment
- CLI behavior for `extract`, `validate`, `convert`, and `report`
- Pipeline orchestration

Latest local verification:

```text
84 passed
```
