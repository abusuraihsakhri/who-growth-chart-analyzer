#!/usr/bin/env python3
"""WHO 2006 growth standards: age-based LMS calculations, 0–60 months.

Uses sex-specific WHO reference parameters. This is not a diagnostic tool.
Weight-for-length/height (wasting) is not available in this dataset.
"""
import argparse
import csv
import json
import math
import os
import sys
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

MAX_CSV_FILE_SIZE = 50 * 1024 * 1024
GENESIS = "WHO Child Growth Standards 2006"


def _validate_safe_path(path):
    """Block explicit traversal and null bytes while allowing absolute local paths."""
    path = os.fspath(path)
    if "\x00" in path:
        raise ValueError("Path contains null bytes")
    if ".." in Path(path).parts:
        raise ValueError("Path traversal detected")
    return os.path.abspath(path)


@lru_cache(maxsize=1)
def _reference_rows():
    with files("agents").joinpath("data/who_lms.json").open("r", encoding="utf-8") as stream:
        reference = json.load(stream)
    return reference["rows"]


def _number(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _lms(age, sex, indicator):
    # WHO uses separate recumbent-length and standing-height standards at 24 months.
    if age < 24:
        points = [r for r in _reference_rows()
                  if r["age_months"] < 24 or
                  (r["age_months"] == 24 and r["stage"] == "length")]
    else:
        points = [r for r in _reference_rows()
                  if r["age_months"] > 24 or
                  (r["age_months"] == 24 and r["stage"] == "height")]
    for index, right in enumerate(points):
        if right["age_months"] >= age - 1e-8:
            if index == 0 or abs(right["age_months"] - age) < 1e-8:
                return right[sex][indicator]
            left = points[index - 1]
            fraction = (age - left["age_months"]) / (right["age_months"] - left["age_months"])
            return [a + fraction * (b - a) for a, b in
                    zip(left[sex][indicator], right[sex][indicator])]
    return points[-1][sex][indicator]


def lms_zscore(measurement, L, M, S):
    """Apply the LMS Box–Cox transform, including its L=0 limit."""
    measurement = _number(measurement, "measurement")
    if measurement <= 0 or M <= 0 or S <= 0:
        raise ValueError("measurement, M and S must be positive")
    ratio_log = math.log(measurement / M)
    return ratio_log / S if abs(L) < 1e-10 else math.expm1(L * ratio_log) / (L * S)


def z_to_percentile(z):
    return 50.0 * math.erfc(-z / math.sqrt(2))


def analyze_growth(weight_kg, height_cm, age_months, sex="M",
                   head_cm=None, measurement="auto"):
    """Analyze age-based WHO indicators. Age is expressed in decimal months.

    `measurement` is 'length', 'height' or 'auto' (age-appropriate assumption).
    A 0.7-cm adjustment is applied for non-age-appropriate measurement positions.
    """
    age = _number(age_months, "age_months")
    weight = _number(weight_kg, "weight_kg")
    height = _number(height_cm, "height_cm")
    sex = str(sex).upper()
    measurement = str(measurement).lower()
    if not 0 <= age <= 60:
        raise ValueError("WHO 2006 reference supports ages 0 to 60 months only")
    if sex not in ("M", "F"):
        raise ValueError("sex must be M or F")
    if measurement not in ("auto", "length", "height"):
        raise ValueError("measurement must be auto, length or height")
    if weight <= 0 or height <= 0:
        raise ValueError("weight_kg and height_cm must be positive")
    if head_cm is not None:
        head_cm = _number(head_cm, "head_cm")
        if head_cm <= 0:
            raise ValueError("head_cm must be positive")

    expected = "length" if age < 24 else "height"
    actual = expected if measurement == "auto" else measurement
    adjustment = 0.7 if expected == "length" and actual == "height" else (
        -0.7 if expected == "height" and actual == "length" else 0.0)
    reference_height = height + adjustment
    if reference_height <= 0:
        raise ValueError("adjusted height must be positive")
    bmi = weight / (reference_height / 100.0) ** 2
    inputs = {"weight": weight, "height": reference_height, "bmi": bmi}
    if head_cm is not None:
        inputs["head"] = head_cm

    calculated = {}
    for name, value in inputs.items():
        z = lms_zscore(value, *_lms(age, sex, name))
        calculated[name] = {
            "z": round(z, 4),
            "percentile": round(z_to_percentile(z), 4),
        }

    return {
        "reference": GENESIS,
        "age_months": age,
        "sex": sex,
        "measurement": actual,
        "height_adjustment_cm": adjustment,
        "height_for_reference_cm": round(reference_height, 3),
        "height_cm": height,
        "weight_kg": weight,
        "bmi": round(bmi, 2),
        "weight_for_age": calculated["weight"],
        "height_for_age": calculated["height"],
        "bmi_for_age": calculated["bmi"],
        "head_for_age": calculated.get("head"),
        "flags": {
            "underweight": calculated["weight"]["z"] < -2,
            "stunting_threshold": calculated["height"]["z"] < -2,
            "low_bmi_for_age": calculated["bmi"]["z"] < -2,
            "high_bmi_for_age": calculated["bmi"]["z"] > 2,
        },
        "note": "Age-based LMS only; no weight-for-length/height wasting assessment. "
                "WHO Anthro age-in-days and extreme-z methods may differ; review "
                "implausible anthropometry before clinical use.",
    }


def calculate_bmi_z(weight_kg, height_cm, age_months, sex="M"):
    """Backward-compatible interface returning BMI and WHO age-based indicators."""
    try:
        return analyze_growth(weight_kg, height_cm, age_months, sex)
    except ValueError as exc:
        return {"error": str(exc)}


def convert_hba1c(hba1c_percent=None, eag_mgdl=None):
    """Unrelated legacy conversion retained for backward compatibility."""
    try:
        if hba1c_percent is not None:
            h = _number(hba1c_percent, "hba1c_percent")
            if h < 0:
                raise ValueError("hba1c_percent cannot be negative")
            return {"hba1c_percent": round(h, 1), "eag_mgdl": round(28.7 * h - 46.7, 1)}
        if eag_mgdl is not None:
            e = _number(eag_mgdl, "eag_mgdl")
            if e < 0:
                raise ValueError("eag_mgdl cannot be negative")
            return {"hba1c_percent": round((e + 46.7) / 28.7, 1), "eag_mgdl": round(e, 1)}
        return {"error": "Either hba1c_percent or eag_mgdl required"}
    except ValueError as exc:
        return {"error": str(exc)}


def calculate_score(**kwargs):
    """Legacy generic weighted score (NOT a medical or growth score)."""
    vals = []
    for value in kwargs.values():
        try:
            if value is not None and str(value).strip():
                vals.append(_number(value, "value"))
        except ValueError:
            pass
    if not vals:
        vals = [1.0]
    h = sum(ord(c) for c in "who-growth-chart-analyzer") % 10
    return {"score": round(sum(vals) * (0.9 + h * 0.02) + math.log1p(len(vals)), 2),
            "inputs": len(vals)}


def assess_row(row):
    try:
        if "weight_kg" in row:
            return analyze_growth(
                row.get("weight_kg"), row.get("height_cm"),
                row.get("age_months", row.get("age")),
                row.get("sex", "M"), row.get("head_cm") or None,
                row.get("measurement") or "auto")
        if "hba1c_percent" in row or "eag_mgdl" in row:
            return convert_hba1c(row.get("hba1c_percent"), row.get("eag_mgdl"))
        return calculate_score(**row)
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}


def _csv_safe(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    cell = str(value) if value is not None else ""
    if cell.startswith(("=", "+", "@", "\t", "\r")) or (
            cell.startswith("-") and not _looks_numeric(cell)):
        return "'" + cell
    return cell


def _looks_numeric(text):
    try:
        return math.isfinite(float(text))
    except ValueError:
        return False


def process_csv(inp, out):
    safe_inp, safe_out = _validate_safe_path(inp), _validate_safe_path(out)
    if os.path.realpath(safe_inp) == os.path.realpath(safe_out):
        raise ValueError("Input and output CSV paths must differ")
    if os.path.getsize(safe_inp) > MAX_CSV_FILE_SIZE:
        raise ValueError("Input CSV exceeds 50 MB")
    with open(safe_inp, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        if not fields or any(not x for x in fields) or len(set(fields)) != len(fields):
            raise ValueError("CSV requires unique, nonempty header names")
        rows = list(reader)
    results = []
    keys = list(fields)
    for row in rows:
        result = assess_row(row)
        merged = {**row, **result}
        results.append(merged)
        for k in merged:
            if k not in keys:
                keys.append(k)
    with open(safe_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for result in results:
            writer.writerow({k: _csv_safe(v) for k, v in result.items()})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="WHO 2006 growth indicators (0–60 months)")
    sub = parser.add_subparsers(dest="command", required=True)
    single = sub.add_parser("single")
    single.add_argument("--json", help="JSON object with growth measurements")
    single.add_argument("--weight-kg", type=float)
    single.add_argument("--height-cm", type=float)
    single.add_argument("--age-months", type=float)
    single.add_argument("--head-cm", type=float)
    single.add_argument("--sex", default="M", choices=["M", "F"])
    single.add_argument("--measurement", default="auto", choices=["auto", "length", "height"])
    for legacy in ("bili", "creat", "inr", "na", "qt", "rr", "hr"):
        single.add_argument("--" + legacy, type=float, help=argparse.SUPPRESS)
    batch = sub.add_parser("batch")
    batch.add_argument("--input", required=True)
    batch.add_argument("--output", required=True)
    a = parser.parse_args(argv)
    if a.command == "batch":
        try:
            print(f"Processed {len(process_csv(a.input, a.output))} rows to {a.output}")
            return 0
        except (ValueError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    try:
        if a.json:
            row = json.loads(a.json)
            if not isinstance(row, dict):
                raise ValueError("--json must be a JSON object")
        elif a.weight_kg is not None:
            row = dict(weight_kg=a.weight_kg, height_cm=a.height_cm,
                       age_months=a.age_months, head_cm=a.head_cm,
                       sex=a.sex, measurement=a.measurement)
        else:
            row = {k: getattr(a, k) for k in ("bili", "creat", "inr", "na", "qt", "rr", "hr")
                   if getattr(a, k) is not None}
        result = assess_row(row)
        print(json.dumps(result, indent=2))
        return 1 if "error" in result else 0
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
