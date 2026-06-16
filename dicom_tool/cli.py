"""CLI entry point for dicom-tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .extractor import extract_metadata
from .pipeline import run_pipeline
from .report import build_cohort_report, print_summary
from .validators import validate_series


@click.group()
def cli():
    """DICOM preprocessing tool for ML/AI pipelines."""


@cli.command("extract")
@click.argument("dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", default=None, help="Output file path.")
@click.option("--format", "-f", "fmt", default="stdout", type=click.Choice(["csv", "json", "stdout"]))
def cmd_extract(dir, output, fmt):
    """Extract and print metadata for all series in DIR."""
    series = extract_metadata(dir)
    if not series:
        click.echo("No DICOM series found.", err=True)
        sys.exit(1)

    if fmt == "json":
        data = [s.__dict__ for s in series]
        text = json.dumps(data, indent=2, default=str)
        if output:
            Path(output).write_text(text, encoding="utf-8")
        else:
            click.echo(text)
    else:
        for s in series:
            click.echo(f"\n--- {s.series_dir} ---")
            for k, v in s.__dict__.items():
                if v is not None:
                    click.echo(f"  {k}: {v}")


@cli.command("validate")
@click.argument("dir", type=click.Path(exists=True, file_okay=False))
@click.option("--strict", is_flag=True, help="Exit 1 on any warn or fail.")
def cmd_validate(dir, strict):
    """Run all validators and report pass/warn/fail for each series."""
    series = extract_metadata(dir)
    if not series:
        click.echo("No DICOM series found.", err=True)
        sys.exit(1)

    any_fail = False
    any_warn = False
    for meta in series:
        click.echo(f"\n{meta.series_dir}")
        results = validate_series(meta)
        for r in results:
            symbol = {"pass": "✓", "warn": "⚠", "fail": "✗"}.get(r.status, "?")
            click.echo(f"  [{r.status.upper():4}] {symbol} {r.check}: {r.message}")
            if r.status == "fail":
                any_fail = True
            if r.status == "warn":
                any_warn = True

    if any_fail:
        sys.exit(2)
    if strict and any_warn:
        sys.exit(1)


@cli.command("convert")
@click.argument("dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", required=True, help="Output directory for NIfTI files.")
@click.option("--dcm2niix", default="dcm2niix", help="Path to dcm2niix executable.")
def cmd_convert(dir, output, dcm2niix):
    """Convert DICOM series in DIR to NIfTI with enriched sidecars."""
    result = run_pipeline(
        dir,
        output_dir=output,
        run_conversion=True,
        output_format="stdout",
        dcm2niix_path=dcm2niix,
    )
    for cr in result.conversion_results:
        status = "OK" if cr.success else "FAIL"
        click.echo(f"[{status}] {cr.series_dir}")
        if not cr.success:
            click.echo(f"       {cr.error}", err=True)


@cli.command("report")
@click.argument("dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", default=None, help="Output file path.")
@click.option("--format", "-f", "fmt", default="stdout", type=click.Choice(["csv", "json", "stdout"]))
@click.option("--strict", is_flag=True, help="Exit 1 on any warn or fail.")
def cmd_report(dir, output, fmt, strict):
    """Generate a cohort-level summary report for DIR."""
    series = extract_metadata(dir)
    if not series:
        click.echo("No DICOM series found.", err=True)
        sys.exit(1)

    df = build_cohort_report(series, output_path=output, output_format=fmt)
    if fmt == "stdout":
        print_summary(df)

    if strict and (df["any_fail"].any() or df["any_warn"].any()):
        sys.exit(1)


def main():
    cli()
