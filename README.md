# NHANES PhenoAge and Mortality Dashboard

Biological age (Levine PhenoAge) from routine NHANES blood labs, tested against
all-cause mortality, with an interactive population-level dashboard.

Version 1.0.0

## Result

PhenoAge, a biological-age score built from nine routine biomarkers plus age,
is tested for whether it predicts all-cause mortality better than chronological
age alone in the NHANES 1999-2010 cohort with linked mortality follow-up through
2019. After you run the pipeline, the headline numbers land in
results/metrics.json:

- People analyzed: n_people
- Deaths: n_deaths
- Harrell C-index, chronological age: cindex_age
- Harrell C-index, PhenoAge: cindex_phenoage (expected to be higher)
- Hazard ratio per year of PhenoAge acceleration: hr_per_year_accel

For reference, Levine 2018 reported PhenoAge out-discriminating chronological age
for 10-year mortality (C-index roughly 0.74 vs 0.71) in NHANES III. Your numbers
will differ with cohort and follow-up window, but PhenoAge beating age is the
expected direction. Paste your actual metrics here once you have them.

![C-index](results/cindex.png)
![Survival by acceleration quartile](results/km_by_accel.png)

## Explore it

    pip install -r requirements.txt
    python -m streamlit run app.py

A population-level dashboard with age and sex filters, Kaplan-Meier survival by
PhenoAge acceleration quartile, biomarker distributions, and a PhenoAge versus
chronological age view. It is not a personal calculator: it does not take your own
labs and does not estimate any individual's biological age.

## What this is

PhenoAge converts nine standard blood biomarkers plus age into an estimated
biological age. The residual after removing chronological age (PhenoAge
acceleration) measures whether someone is aging faster or slower than peers of the
same age. This project computes it on a large public cohort and tests whether it
tracks mortality.

## Data

NHANES continuous cycles 1999-2010 (the window where serum CRP is available),
public domain, joined to the NCHS Public-Use Linked Mortality Files (2019 release,
follow-up to 2019-12-31) on SEQN. Only mortality-eligible respondents (ELIGSTAT 1)
are analyzed. Raw downloads are gitignored; the derived, de-identified analysis
cohort (data/analysis.csv) is committed so the dashboard deploys without a download.

## Method

PhenoAge uses the published Levine 2018 equation: a parametric mortality model over
nine biomarkers and age, mapped onto an age scale. See src/phenoage.py for the exact
coefficients and the unit conversions, which are the main source of error. Survival
analysis uses Kaplan-Meier by acceleration quartile, Cox proportional hazards for the
hazard ratio, and the Harrell C-index to compare PhenoAge against chronological age
for mortality discrimination.

## Reproduce (Windows)

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe run_all.py
    .venv\Scripts\python.exe -m streamlit run app.py

run_all.py downloads NHANES and mortality, scores PhenoAge, writes data/analysis.csv,
and produces the figures and metrics. Reruns skip the download.

## Three things to verify before trusting the numbers

1. PhenoAge units. src/phenoage.py converts NHANES units to Levine units. Confirm
   the result against a reference implementation (for example the BioAge R package)
   on a handful of rows. The CRP unit is the most error-prone term.
2. NHANES file names. The 1999-2004 lab file names vary by cycle. If a cycle is
   skipped during download, confirm names at wwwn.cdc.gov/nchs/nhanes and update
   src/download_data.py. The 2005-2010 cycles are the reliable core.
3. Mortality layout. src/download_data.py validates the fixed-width parse (MORTSTAT
   in 0/1, ELIGSTAT in 1/2/3). If it raises, confirm column positions against the
   NCHS public-use linked mortality file readme.

## Outputs

results/phenoage_vs_age.png, results/km_by_accel.png, results/cindex.png,
results/hr_forest.png, results/metrics.json

## Limitations

PhenoAge is built on US NHANES and may transfer poorly to other populations.
Single-timepoint biomarkers, no repeated measures. Observational data, so hazard
ratios are associations, not causal effects. Unmeasured confounders (smoking,
socioeconomic status, comorbidity) are not adjusted by default. This is a
population-level research analysis, not a diagnostic or personal risk tool.

## Citation

PhenoAge: Levine ME, Lu AT, Quach A, et al. An epigenetic biomarker of aging for
lifespan and healthspan. Aging (Albany NY), 2018.

Data: NHANES (CDC/NCHS) and the NCHS Public-Use Linked Mortality Files, 2019 release.
