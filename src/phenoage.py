"""
Levine PhenoAge from NHANES biomarkers.

Implements the published PhenoAge biological-age score (Levine et al., 2018) from
9 clinical biomarkers plus chronological age. The single most error-prone part is
units: NHANES reports biomarkers in different units than Levine's equation expects,
so every conversion is explicit and documented below. Validate against a reference
implementation (for example the BioAge R package) on a few rows before trusting the
absolute numbers.

Levine units expected by the linear predictor:
  albumin      g/L        NHANES LBXSAL is g/dL     -> multiply by 10
  creatinine   umol/L     NHANES LBXSCR is mg/dL    -> multiply by 88.4017
  glucose      mmol/L     NHANES LBXSGL is mg/dL    -> multiply by 0.0555
  CRP          mg/dL      NHANES LBXCRP is mg/dL    -> use as is, then ln()
  lymphocyte   percent    NHANES LBXLYPCT           -> as is
  MCV          fL         NHANES LBXMCVSI           -> as is
  RDW          percent    NHANES LBXRDW             -> as is
  ALP          U/L        NHANES LBXSAPSI           -> as is
  WBC          1000/uL    NHANES LBXWBCSI           -> as is
  age          years      NHANES RIDAGEYR           -> as is

CRP caveat: NHANES 1999-2010 reports CRP in mg/dL (variable LBXCRP), which matches
Levine. Later cycles switched to high-sensitivity CRP in mg/L (LBXHSCRP); if you
ever extend past 2010 you must divide by 10 before ln(). This module assumes mg/dL.

Reference: Levine ME et al. An epigenetic biomarker of aging for lifespan and
healthspan. Aging (Albany NY), 2018.
"""

import numpy as np
import pandas as pd

# linear-predictor coefficients, in Levine units (see header)
INTERCEPT = -19.907
COEF = {
    "albumin_gL": -0.0336,
    "creatinine_umol": 0.0095,
    "glucose_mmol": 0.1953,
    "ln_crp": 0.0954,
    "lymph_pct": -0.0120,
    "mcv_fL": 0.0268,
    "rdw_pct": 0.3306,
    "alp_U": 0.00188,
    "wbc_k": 0.0554,
    "age_yr": 0.0804,
}
# survival-to-age transform constants (Levine 2018)
GAMMA = 0.0076927
LAMBDA = 1.51714
A0 = 141.50225
A1 = 0.090165
A2 = 0.00553


def compute_phenoage(
    albumin_gdl, creatinine_mgdl, glucose_mgdl, crp_mgdl,
    lymph_pct, mcv_fl, rdw_pct, alp_ul, wbc_k, age_yr,
):
    """Return PhenoAge in years from NHANES-native biomarker units."""
    alb = np.asarray(albumin_gdl, float) * 10.0
    creat = np.asarray(creatinine_mgdl, float) * 88.4017
    gluc = np.asarray(glucose_mgdl, float) * 0.0555
    crp = np.asarray(crp_mgdl, float)
    ln_crp = np.log(np.clip(crp, 1e-4, None))
    lymph = np.asarray(lymph_pct, float)
    mcv = np.asarray(mcv_fl, float)
    rdw = np.asarray(rdw_pct, float)
    alp = np.asarray(alp_ul, float)
    wbc = np.asarray(wbc_k, float)
    age = np.asarray(age_yr, float)

    xb = (
        INTERCEPT
        + COEF["albumin_gL"] * alb
        + COEF["creatinine_umol"] * creat
        + COEF["glucose_mmol"] * gluc
        + COEF["ln_crp"] * ln_crp
        + COEF["lymph_pct"] * lymph
        + COEF["mcv_fL"] * mcv
        + COEF["rdw_pct"] * rdw
        + COEF["alp_U"] * alp
        + COEF["wbc_k"] * wbc
        + COEF["age_yr"] * age
    )
    mort = 1.0 - np.exp(-LAMBDA * np.exp(xb) / GAMMA)
    one_minus_m = np.clip(1.0 - mort, 1e-12, 1.0)
    phenoage = A0 + np.log(-A2 * np.log(one_minus_m)) / A1
    return phenoage


def phenoage_from_frame(df):
    """Vectorized PhenoAge for a dataframe carrying the 9 NHANES lab columns plus age.

    Expected columns: LBXSAL, LBXSCR, LBXSGL, LBXCRP, LBXLYPCT, LBXMCVSI, LBXRDW,
    LBXSAPSI, LBXWBCSI, RIDAGEYR. Rows with any missing input return NaN.
    """
    cols = ["LBXSAL", "LBXSCR", "LBXSGL", "LBXCRP", "LBXLYPCT",
            "LBXMCVSI", "LBXRDW", "LBXSAPSI", "LBXWBCSI", "RIDAGEYR"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError("missing required columns: {}".format(missing))
    out = compute_phenoage(
        df["LBXSAL"], df["LBXSCR"], df["LBXSGL"], df["LBXCRP"],
        df["LBXLYPCT"], df["LBXMCVSI"], df["LBXRDW"], df["LBXSAPSI"],
        df["LBXWBCSI"], df["RIDAGEYR"],
    )
    return pd.Series(out, index=df.index, name="phenoage")


def _selftest():
    # Healthy-ish 50 year old, biomarkers near reference. Hand-checked xb ~ -8.86.
    pa = float(compute_phenoage(4.3, 0.9, 95, 0.2, 30, 90, 13, 70, 6.5, 50))
    print("healthy 50yo PhenoAge = {:.2f}".format(pa))
    assert 35 < pa < 55, "out of plausible range"

    # Monotonicity: worsening inflammation, glucose, RDW must raise PhenoAge.
    sick = float(compute_phenoage(3.6, 1.3, 150, 5.0, 18, 95, 16, 140, 9.5, 50))
    print("unhealthy 50yo PhenoAge = {:.2f}".format(sick))
    assert sick > pa + 5, "worse biomarkers should raise PhenoAge clearly"

    # Aging: same biomarkers, older age must raise PhenoAge.
    older = float(compute_phenoage(4.3, 0.9, 95, 0.2, 30, 90, 13, 70, 6.5, 70))
    print("healthy 70yo PhenoAge = {:.2f}".format(older))
    assert older > pa + 10, "older age should raise PhenoAge"
    print("phenoage selftest OK")


if __name__ == "__main__":
    _selftest()
