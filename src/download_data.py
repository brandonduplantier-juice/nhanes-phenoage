"""
Download and merge NHANES biomarkers, demographics, and linked mortality.

Pulls the six continuous NHANES cycles from 1999 to 2010 (the window where serum
CRP is available, variable LBXCRP) and joins the NCHS Public-Use Linked Mortality
Files (2019 release, follow-up through 2019-12-31). Writes data/merged.csv with one
row per person: the nine PhenoAge biomarkers, age, sex, and mortality follow-up.

Needs internet. Run on your machine:
  python src/download_data.py
  python src/download_data.py --cycles 2005-2006 2007-2008 2009-2010

CDC reorganized the NHANES file URLs, so this tries the current path first and the
older path as a fallback, sends a browser User-Agent (the CDC CDN blocks bare
requests), and validates that each download is a real XPORT file before accepting it.
A redirect or error page can no longer masquerade as data.

TWO THINGS YOU MUST CONFIRM against current NCHS documentation:
  1. File names for the older cycles. The 2005-2010 names (DEMO_D/E/F, BIOPRO, CRP,
     CBC) are stable. The 1999-2004 names (LAB18, L40_B, L11_B, L25_B, ...) change
     between cycles. If a file is unavailable, this skips that whole cycle and says so.
  2. The mortality fixed-width layout (MORT_COLSPECS). After parsing, the script
     validates that MORTSTAT is 0/1 and ELIGSTAT is 1/2/3. If that check fails, the
     column positions are wrong for the file you downloaded.
"""

import argparse
import os
import sys
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "merged.csv")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# current CDC path first, legacy path second. {year} is the cycle start year.
XPT_URL_TEMPLATES = [
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}.xpt",
    "https://wwwn.cdc.gov/Nchs/Nhanes/{cycle}/{name}.XPT",
]
MORT_URL_TEMPLATES = [
    "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/"
    "NHANES_{m}_MORT_2019_PUBLIC.dat",
]

CYCLES = {
    "1999-2000": {"demo": "DEMO",   "biochem": "LAB18",    "crp": "LAB11", "cbc": "LAB25"},
    "2001-2002": {"demo": "DEMO_B", "biochem": "L40_B",    "crp": "L11_B", "cbc": "L25_B"},
    "2003-2004": {"demo": "DEMO_C", "biochem": "L40_C",    "crp": "L11_C", "cbc": "L25_C"},
    "2005-2006": {"demo": "DEMO_D", "biochem": "BIOPRO_D", "crp": "CRP_D", "cbc": "CBC_D"},
    "2007-2008": {"demo": "DEMO_E", "biochem": "BIOPRO_E", "crp": "CRP_E", "cbc": "CBC_E"},
    "2009-2010": {"demo": "DEMO_F", "biochem": "BIOPRO_F", "crp": "CRP_F", "cbc": "CBC_F"},
}
MORT_LABEL = {c: c.replace("-", "_") for c in CYCLES}

# Some cycles name the same analyte differently. Map canonical -> acceptable
# alternates (conventional units, not the SI columns), tried in order.
VAR_ALIASES = {
    "LBXSCR": ["LBXSCR", "LBDSCR"],      # creatinine, mg/dL (NOT LBDSCRSI, which is umol/L)
    "LBXSAPSI": ["LBXSAPSI", "LBDSAPSI"],  # alkaline phosphatase, U/L (IU/L is equivalent)
}

DEMO_VARS = ["SEQN", "RIDAGEYR", "RIAGENDR"]
BIOCHEM_VARS = ["SEQN", "LBXSAL", "LBXSCR", "LBXSGL", "LBXSAPSI"]
CRP_VARS = ["SEQN", "LBXCRP"]
CBC_VARS = ["SEQN", "LBXLYPCT", "LBXMCVSI", "LBXRDW", "LBXWBCSI"]

MORT_COLSPECS = [(0, 6), (14, 15), (15, 16), (16, 19), (19, 20), (20, 21), (42, 45), (45, 48)]
MORT_NAMES = ["SEQN", "ELIGSTAT", "MORTSTAT", "UCOD_LEADING",
              "DIABETES", "HYPERTEN", "PERMTH_INT", "PERMTH_EXM"]


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def _is_xport(data):
    # SAS XPORT files begin with a "HEADER RECORD...LIBRARY" ASCII banner.
    return data[:200].find(b"HEADER RECORD") != -1


def download_xpt(cycle, name, dest):
    if os.path.exists(dest) and _is_xport(open(dest, "rb").read(200)):
        return True
    year = cycle.split("-")[0]
    last_preview = ""
    for tmpl in XPT_URL_TEMPLATES:
        url = tmpl.format(year=year, cycle=cycle, name=name)
        try:
            data = _fetch(url)
        except Exception as exc:
            last_preview = "request failed: {}".format(exc)
            continue
        if _is_xport(data):
            with open(dest, "wb") as fh:
                fh.write(data)
            return True
        last_preview = data[:80].decode("latin-1", "replace").replace("\n", " ")
    print("  [skip] {} {}: no valid XPORT file. Last response began: {!r}".format(
        cycle, name, last_preview))
    return False


def download_mort(cycle, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    for tmpl in MORT_URL_TEMPLATES:
        url = tmpl.format(m=MORT_LABEL[cycle])
        try:
            data = _fetch(url)
        except Exception as exc:
            print("  [skip mortality] {}: {}".format(cycle, exc))
            continue
        with open(dest, "wb") as fh:
            fh.write(data)
        return True
    return False


def read_xpt(path, cols):
    df = pd.read_sas(path, format="xport")
    df.columns = [c.upper() for c in df.columns]
    keep, missing, rename = [], [], {}
    for c in cols:
        if c in df.columns:
            keep.append(c)
            continue
        found = next((a for a in VAR_ALIASES.get(c, []) if a in df.columns), None)
        if found:
            keep.append(found)
            rename[found] = c
        else:
            missing.append(c)
    if missing:
        print("  [warn] {} missing vars {}".format(os.path.basename(path), missing))
    df = df[keep].rename(columns=rename).copy()
    df["SEQN"] = df["SEQN"].astype("Int64")
    return df


def parse_mortality(path_or_buffer):
    m = pd.read_fwf(path_or_buffer, colspecs=MORT_COLSPECS, names=MORT_NAMES,
                    na_values=[".", ""])
    m["SEQN"] = pd.to_numeric(m["SEQN"], errors="coerce").astype("Int64")
    for c in ["MORTSTAT", "PERMTH_EXM", "PERMTH_INT", "ELIGSTAT"]:
        m[c] = pd.to_numeric(m[c], errors="coerce")
    ms = set(m["MORTSTAT"].dropna().unique())
    es = set(m["ELIGSTAT"].dropna().unique())
    if not ms.issubset({0, 1}) or not es.issubset({1, 2, 3}):
        raise ValueError("mortality layout looks wrong: MORTSTAT={} ELIGSTAT={}. "
                         "Confirm MORT_COLSPECS against the NCHS readme.".format(ms, es))
    return m[["SEQN", "ELIGSTAT", "MORTSTAT", "PERMTH_EXM", "UCOD_LEADING"]]


def build(cycles):
    os.makedirs(RAW, exist_ok=True)
    frames = []
    for cyc in cycles:
        files = CYCLES[cyc]
        print("[{}]".format(cyc))
        paths = {}
        ok = True
        for kind, name in files.items():
            dest = os.path.join(RAW, "{}.XPT".format(name))
            if not download_xpt(cyc, name, dest):
                ok = False
                break
            paths[kind] = dest
        if not ok:
            print("  [skip cycle] a file was unavailable, confirm names at wwwn.cdc.gov")
            continue
        demo = read_xpt(paths["demo"], DEMO_VARS)
        bio = read_xpt(paths["biochem"], BIOCHEM_VARS)
        crp = read_xpt(paths["crp"], CRP_VARS)
        cbc = read_xpt(paths["cbc"], CBC_VARS)
        lab = demo.merge(bio, on="SEQN", how="inner") \
                  .merge(crp, on="SEQN", how="inner") \
                  .merge(cbc, on="SEQN", how="inner")

        mort_dest = os.path.join(RAW, "MORT_{}.dat".format(MORT_LABEL[cyc]))
        if not download_mort(cyc, mort_dest):
            print("  [skip cycle] mortality file unavailable")
            continue
        mort = parse_mortality(mort_dest)
        merged = lab.merge(mort, on="SEQN", how="inner")
        merged["cycle"] = cyc
        print("  rows: {}".format(len(merged)))
        frames.append(merged)

    if not frames:
        print("[build] no cycles merged. Confirm file names and network.")
        sys.exit(1)
    out = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False)
    print("[build] wrote {} ({} rows, {} cycles)".format(OUT, len(out), len(frames)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", nargs="*", default=list(CYCLES))
    args = ap.parse_args()
    bad = [c for c in args.cycles if c not in CYCLES]
    if bad:
        print("unknown cycles: {}. Valid: {}".format(bad, list(CYCLES)))
        sys.exit(1)
    build(args.cycles)


if __name__ == "__main__":
    main()
