"""
Survival analysis for NHANES PhenoAge versus chronological age.

Tests whether PhenoAge predicts all-cause mortality better than chronological age,
which is the central claim of a biological-age clock. Produces:
  results/phenoage_vs_age.png   PhenoAge against chronological age
  results/km_by_accel.png       Kaplan-Meier survival by age-acceleration quartile
  results/cindex.png            Harrell C-index, PhenoAge vs age
  results/hr_forest.png         Cox hazard ratios with 95% CI
  results/metrics.json          headline numbers

Inputs (one row per person): phenoage, RIDAGEYR (age), RIAGENDR (sex 1/2),
MORTSTAT (1 dead, 0 alive at follow-up end), PERMTH_EXM (months from exam to
death or censoring). Time is analyzed in months. A 10-year (120-month) C-index is
also reported, to compare directly with Levine 2018.
"""

import json
import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.utils import concordance_index

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def add_accel(df):
    """PhenoAgeAccel = PhenoAge residual after regressing out chronological age."""
    d = df.dropna(subset=["phenoage", "RIDAGEYR"]).copy()
    slope, intercept = np.polyfit(d["RIDAGEYR"], d["phenoage"], 1)
    df = df.copy()
    df["phenoage_accel"] = df["phenoage"] - (slope * df["RIDAGEYR"] + intercept)
    return df, slope, intercept


def run_survival(df, results_dir=RESULTS):
    os.makedirs(results_dir, exist_ok=True)
    df, slope, intercept = add_accel(df)
    d = df.dropna(subset=["phenoage", "phenoage_accel", "RIDAGEYR",
                          "MORTSTAT", "PERMTH_EXM"]).copy()
    d = d[d["PERMTH_EXM"] > 0]
    d["event"] = d["MORTSTAT"].astype(int)
    d["time"] = d["PERMTH_EXM"].astype(float)

    # ---- PhenoAge vs chronological age ----
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(d["RIDAGEYR"], d["phenoage"], s=6, alpha=0.25,
               color="#2c7fb8", edgecolor="none")
    lims = [d["RIDAGEYR"].min(), d["RIDAGEYR"].max()]
    ax.plot(lims, lims, color="black", lw=0.8, ls="--", label="y = x")
    ax.set_xlabel("chronological age (years)")
    ax.set_ylabel("PhenoAge (years)")
    ax.set_title("PhenoAge vs chronological age")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(results_dir, "phenoage_vs_age.png"), dpi=150)
    plt.close(fig)

    # ---- Kaplan-Meier by acceleration quartile ----
    d["accel_q"] = pd.qcut(d["phenoage_accel"], 4,
                           labels=["Q1 youngest", "Q2", "Q3", "Q4 oldest"])
    fig, ax = plt.subplots(figsize=(6, 5))
    kmf = KaplanMeierFitter()
    for q in ["Q1 youngest", "Q2", "Q3", "Q4 oldest"]:
        m = d["accel_q"] == q
        kmf.fit(d.loc[m, "time"], d.loc[m, "event"], label=q)
        kmf.plot_survival_function(ax=ax, ci_show=False)
    ax.set_xlabel("months from exam")
    ax.set_ylabel("survival probability")
    ax.set_title("Survival by PhenoAge acceleration quartile")
    fig.tight_layout()
    fig.savefig(os.path.join(results_dir, "km_by_accel.png"), dpi=150)
    plt.close(fig)

    # ---- Cox proportional hazards ----
    cox_df = d[["time", "event", "phenoage_accel", "RIDAGEYR"]].copy()
    if "RIAGENDR" in d.columns:
        cox_df["male"] = (d["RIAGENDR"] == 1).astype(int)
    cph = CoxPHFitter()
    cph.fit(cox_df, duration_col="time", event_col="event")
    hr = np.exp(cph.params_)
    hr_lower = np.exp(cph.confidence_intervals_.iloc[:, 0])
    hr_upper = np.exp(cph.confidence_intervals_.iloc[:, 1])

    fig, ax = plt.subplots(figsize=(6, max(2.5, 0.7 * len(hr))))
    ypos = range(len(hr))
    ax.errorbar(hr.values, list(ypos),
                xerr=[hr.values - hr_lower.values, hr_upper.values - hr.values],
                fmt="o", color="#cb181d", capsize=3)
    ax.axvline(1.0, color="black", lw=0.8, ls="--")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(hr.index)
    ax.set_xlabel("hazard ratio (95% CI)")
    ax.set_title("Cox hazard ratios for all-cause mortality")
    fig.tight_layout()
    fig.savefig(os.path.join(results_dir, "hr_forest.png"), dpi=150)
    plt.close(fig)

    # ---- C-index: PhenoAge vs chronological age ----
    c_age = concordance_index(d["time"], -d["RIDAGEYR"], d["event"])
    c_pheno = concordance_index(d["time"], -d["phenoage"], d["event"])

    # 10-year (120-month) window, comparable to Levine 2018
    ev10 = ((d["event"] == 1) & (d["time"] <= 120)).astype(int)
    t10 = d["time"].clip(upper=120)
    c_age_10 = concordance_index(t10, -d["RIDAGEYR"], ev10)
    c_pheno_10 = concordance_index(t10, -d["phenoage"], ev10)

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(["chronological age", "PhenoAge"], [c_age, c_pheno],
           color=["#bdbdbd", "#cb181d"])
    ax.axhline(0.5, color="black", lw=0.8, ls="--")
    ax.set_ylim(0.5, max(0.75, c_pheno + 0.05))
    ax.set_ylabel("Harrell C-index")
    ax.set_title("Mortality discrimination")
    for i, v in enumerate([c_age, c_pheno]):
        ax.text(i, v + 0.005, "{:.3f}".format(v), ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(results_dir, "cindex.png"), dpi=150)
    plt.close(fig)

    metrics = {
        "n_people": int(len(d)),
        "n_deaths": int(d["event"].sum()),
        "median_followup_months": float(d["time"].median()),
        "accel_slope_phenoage_on_age": float(slope),
        "hr_per_year_accel": float(hr.get("phenoage_accel", np.nan)),
        "hr_accel_ci": [float(hr_lower.get("phenoage_accel", np.nan)),
                        float(hr_upper.get("phenoage_accel", np.nan))],
        "cindex_age": float(c_age),
        "cindex_phenoage": float(c_pheno),
        "cindex_gain": float(c_pheno - c_age),
        "cindex_age_10yr": float(c_age_10),
        "cindex_phenoage_10yr": float(c_pheno_10),
        "cindex_gain_10yr": float(c_pheno_10 - c_age_10),
    }
    with open(os.path.join(results_dir, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print("[survival] n={} deaths={} | full follow-up C(age)={:.3f} C(PhenoAge)={:.3f} "
          "gain={:+.3f} | 10yr C(age)={:.3f} C(PhenoAge)={:.3f} gain={:+.3f}".format(
              metrics["n_people"], metrics["n_deaths"], c_age, c_pheno, c_pheno - c_age,
              c_age_10, c_pheno_10, c_pheno_10 - c_age_10))
    return metrics


if __name__ == "__main__":
    import sys
    merged = os.path.join(os.path.dirname(RESULTS), "data", "merged.csv")
    if not os.path.exists(merged):
        print("[survival] no data/merged.csv. Run download_data.py and run_all.py first.")
        sys.exit(0)
    run_survival(pd.read_csv(merged))
