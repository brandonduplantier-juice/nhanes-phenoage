"""
Run the full NHANES PhenoAge mortality pipeline: download, score, survival.

Usage:
  python run_all.py                  download if needed, then analyze
  python run_all.py --force-download refetch all NHANES and mortality files

Restricts to adults (age >= 20), the range in which PhenoAge was developed and
validated (Levine 2018). Writes data/analysis.csv and the figures and metrics in
results/.
"""

import argparse
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

import download_data as dd          # noqa: E402
from phenoage import phenoage_from_frame  # noqa: E402
import survival                     # noqa: E402

__version__ = "1.0.4"
ADULT_MIN_AGE = 20  # PhenoAge is an adult clock; younger ages inflate the C-index

MERGED = os.path.join(HERE, "data", "merged.csv")
ANALYSIS = os.path.join(HERE, "data", "analysis.csv")
KEEP = ["SEQN", "cycle", "RIDAGEYR", "RIAGENDR", "phenoage", "phenoage_accel",
        "MORTSTAT", "PERMTH_EXM", "LBXSAL", "LBXSCR", "LBXSGL", "LBXCRP",
        "LBXLYPCT", "LBXMCVSI", "LBXRDW", "LBXSAPSI", "LBXWBCSI"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-download", action="store_true")
    args = ap.parse_args()
    print("[run_all] nhanes-phenoage v{}".format(__version__))

    if args.force_download or not os.path.exists(MERGED):
        if args.force_download and os.path.exists(MERGED):
            os.remove(MERGED)
        dd.build(list(dd.CYCLES))
    else:
        print("[run_all] data/merged.csv exists, skipping download "
              "(pass --force-download to refetch)")

    df = pd.read_csv(MERGED)
    df["phenoage"] = phenoage_from_frame(df)

    elig = df[df["ELIGSTAT"] == 1].copy()
    before = len(elig)
    elig = elig[elig["RIDAGEYR"] >= ADULT_MIN_AGE]
    print("[run_all] adult filter (age >= {}): {} -> {} people".format(
        ADULT_MIN_AGE, before, len(elig)))
    elig = elig.dropna(subset=["phenoage", "MORTSTAT", "PERMTH_EXM", "RIDAGEYR"])
    elig = elig[elig["PERMTH_EXM"] > 0]
    print("[run_all] scored adult cohort: {} people".format(len(elig)))

    elig, slope, intercept = survival.add_accel(elig)
    elig[[c for c in KEEP if c in elig.columns]].to_csv(ANALYSIS, index=False)
    print("[run_all] wrote data/analysis.csv")

    survival.run_survival(elig)
    print("[run_all] done. See results/ for figures and metrics, "
          "and run: python -m streamlit run app.py")


if __name__ == "__main__":
    main()
