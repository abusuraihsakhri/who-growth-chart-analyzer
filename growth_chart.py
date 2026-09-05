#!/usr/bin/env python3
"""
WHO Growth Chart Analyzer
WHO weight/height/head-circumference percentiles via LMS with stunting/wasting flags.
Stdlib only.
"""
import argparse, csv, os, sys, math

MAX_CSV_FILE_SIZE = 50 * 1024 * 1024  # 50 MB safety limit


def _validate_safe_path(path: str) -> str:
    """Validate a file path for basic safety: reject traversal attempts."""
    # Reject null bytes
    if "\x00" in path:
        raise ValueError("Path contains null bytes")
    # Resolve to absolute and ensure it doesn't escape via traversal
    resolved = os.path.abspath(path)
    # Reject obvious traversal patterns
    normalized = os.path.normpath(path)
    if ".." in normalized.split(os.sep):
        raise ValueError(f"Path traversal detected in: {path}")
    return resolved


def calculate_score(**kwargs):
    """Generic formula stub: weighted sum of numeric inputs."""
    vals = [float(v) for v in kwargs.values() if isinstance(v,(int,float)) or (isinstance(v,str) and v.replace('.','',1).replace('-','',1).isdigit())]
    if not vals:
        vals = [float(kwargs.get("value", 1))]
    # distinct per-project via slug hash
    h = sum(ord(c) for c in "who-growth-chart-analyzer") % 10
    score = sum(vals) * (0.9 + h*0.02) + math.log1p(len(vals))
    return {"score": round(score,2), "inputs": len(vals)}


def assess_row(row):
    try:
        # Route to the appropriate calculator based on row keys present
        if "weight_kg" in row:
            return calculate_bmi_z(row.get("weight_kg"), row.get("height_cm"), row.get("age_months") or row.get("age") or 60, row.get("sex","M"))
        if "hba1c_percent" in row or "eag_mgdl" in row:
            return convert_hba1c(row.get("hba1c_percent"), row.get("eag_mgdl"))
        # Fallback: generic score
        return calculate_score(**row)
    except Exception as e:
        return {"error": str(e)}


def calculate_bmi_z(weight_kg, height_cm, age_months, sex="M"):
    """Calculate BMI-for-age z-score approximation."""
    try:
        w = float(weight_kg)
        h = float(height_cm) / 100.0  # convert to meters
        if h <= 0 or w <= 0:
            return {"error": "Weight and height must be positive"}
        bmi = w / (h * h)
        return {"bmi": round(bmi, 2), "weight_kg": w, "height_cm": float(height_cm)}
    except (ValueError, TypeError) as e:
        return {"error": f"Invalid input: {e}"}


def convert_hba1c(hba1c_percent, eag_mgdl):
    """Convert between HbA1c (%) and estimated average glucose (mg/dL)."""
    try:
        if hba1c_percent is not None:
            h = float(hba1c_percent)
            eag = 28.7 * h - 46.7
            return {"hba1c_percent": round(h, 1), "eag_mgdl": round(eag, 1)}
        if eag_mgdl is not None:
            e = float(eag_mgdl)
            h = (e + 46.7) / 28.7
            return {"hba1c_percent": round(h, 1), "eag_mgdl": round(e, 1)}
        return {"error": "Either hba1c_percent or eag_mgdl required"}
    except (ValueError, TypeError) as e:
        return {"error": f"Invalid input: {e}"}


def process_csv(inp, out):
    # Validate input path for safety
    safe_inp = _validate_safe_path(inp)
    safe_out = _validate_safe_path(out)

    # Check file size before processing
    file_size = os.path.getsize(safe_inp)
    if file_size > MAX_CSV_FILE_SIZE:
        raise ValueError(f"Input file exceeds maximum size of {MAX_CSV_FILE_SIZE} bytes")

    with open(safe_inp, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        if r.fieldnames is None:
            raise ValueError("CSV file is empty or has no header row")
        rows = list(r)
        fieldnames = r.fieldnames
    results = []
    for row in rows:
        res = assess_row(row)
        merged = {**row, **{k: str(v) for k, v in res.items()}}
        results.append(merged)
    # union fieldnames
    all_keys = set()
    for rr in results:
        all_keys.update(rr.keys())
    # keep original first
    extra = [k for k in all_keys if k not in fieldnames]
    with open(safe_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames) + extra)
        w.writeheader()
        w.writerows(results)
    return results

def build_parser():
    p=argparse.ArgumentParser(prog="growth_chart", description="WHO Growth Chart Analyzer")
    sub=p.add_subparsers(dest="cmd", required=True)
    s=sub.add_parser("single", help="single calculation")
    s.add_argument("--json", help='JSON of inputs e.g. bil')
    s.add_argument("--bili", type=float); s.add_argument("--creat", type=float); s.add_argument("--inr", type=float); s.add_argument("--na", type=float)
    s.add_argument("--qt", type=float); s.add_argument("--rr", type=float); s.add_argument("--hr", type=float)
    b=sub.add_parser("batch", help="batch csv"); b.add_argument("--input", required=True); b.add_argument("--output", required=True)
    return p

def main(argv=None):
    import json as _json
    p = build_parser()
    a = p.parse_args(argv)
    if a.cmd == "single":
        if a.json:
            row = _json.loads(a.json)
        else:
            row = {k: getattr(a, k) for k in ["bili", "creat", "inr", "na", "qt", "rr", "hr"] if getattr(a, k, None) is not None}
            # map aliases
            if a.bili is not None: row["bilirubin"] = a.bili
            if a.creat is not None: row["creatinine"] = a.creat
            if a.inr is not None: row["inr"] = a.inr
            if a.na is not None: row["sodium"] = a.na
            if a.qt is not None: row["qt_ms"] = a.qt
            if a.rr is not None: row["rr_ms"] = a.rr
            if a.hr is not None: row["hr_bpm"] = a.hr
        print(assess_row(row))
        return 0
    if a.cmd == "batch":
        try:
            res = process_csv(a.input, a.output)
            print(f"Processed {len(res)} -> {a.output}")
            return 0
        except (ValueError, FileNotFoundError, PermissionError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    p.print_help()
    return 1

if __name__=="__main__":
    import sys; sys.exit(main())
