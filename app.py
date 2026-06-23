"""
NHANES PhenoAge mortality dashboard.

Written for a general audience: plain-language explainers on every chart and hover
tooltips on every number. Population-level research over a public cohort. It is NOT
a personal health calculator: it does not take your labs and does not estimate any
individual's biological age or risk.

Run locally:
  pip install -r requirements.txt
  python -m streamlit run app.py

Reads data/analysis.csv and results/metrics.json, produced by run_all.py.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from lifelines import KaplanMeierFitter

APP_VERSION = "1.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "data", "analysis.csv")
METRICS = os.path.join(HERE, "results", "metrics.json")

BIOMARKERS = {
    "LBXSAL": "Albumin (g/dL)", "LBXSCR": "Creatinine (mg/dL)",
    "LBXSGL": "Glucose (mg/dL)", "LBXCRP": "CRP (mg/dL)",
    "LBXLYPCT": "Lymphocyte %", "LBXMCVSI": "MCV (fL)",
    "LBXRDW": "RDW %", "LBXSAPSI": "Alk phosphatase (U/L)",
    "LBXWBCSI": "WBC (1000/uL)",
}
BIOMARKER_PLAIN = {
    "LBXSAL": "a liver and nutrition protein", "LBXSCR": "a kidney-function marker",
    "LBXSGL": "blood sugar", "LBXCRP": "an inflammation marker",
    "LBXLYPCT": "a type of immune cell, as a percent", "LBXMCVSI": "average red blood cell size",
    "LBXRDW": "variation in red blood cell size", "LBXSAPSI": "a liver and bone enzyme",
    "LBXWBCSI": "white blood cell count",
}


@st.cache_data
def load():
    df = pd.read_csv(ANALYSIS)
    meta = {}
    if os.path.exists(METRICS):
        with open(METRICS) as fh:
            meta = json.load(fh)
    return df, meta


if not os.path.exists(ANALYSIS):
    st.error("data/analysis.csv not found. Run: python run_all.py")
    st.stop()

df, meta = load()

st.title("Biological age and survival")
st.caption("How a blood-based estimate of biological age tracks with lifespan, in a "
           "large US health survey (NHANES 1999-2010). Research only, not medical advice.")

with st.expander("New here? How to read this", expanded=False):
    st.markdown(
        "- **Biological age (PhenoAge)** is an estimate of how old your body seems "
        "based on nine routine blood tests, which can differ from your age in years.\n"
        "- **Age acceleration** is the gap: positive means your body looks older than "
        "your actual age, negative means younger.\n"
        "- **Survival curve** shows the share of a group still alive over time. A lower "
        "curve means more deaths.\n"
        "- **C-index** scores how well a number sorts who lives longer, from 0.5 (a coin "
        "flip) to 1.0 (perfect). The question here is whether biological age beats plain "
        "age in years.\n"
        "- **Hazard ratio** is how much the risk of dying changes per unit. Above 1 means "
        "higher risk.\n\n"
        "This dashboard describes groups of people, not any one person. It cannot tell "
        "you your own biological age."
    )

if meta:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("People", "{:,}".format(meta.get("n_people", len(df))),
              help="Number of survey participants analyzed.")
    c2.metric("Deaths", "{:,}".format(meta.get("n_deaths", 0)),
              help="Participants who died during follow-up (through 2019).")
    c3.metric("Score: age in years", "{:.3f}".format(meta.get("cindex_age", float("nan"))),
              help="How well plain age in years sorts who lives longer. 0.5 is chance.")
    c4.metric("Score: biological age", "{:.3f}".format(meta.get("cindex_phenoage", float("nan"))),
              delta="{:+.3f}".format(meta.get("cindex_gain", 0.0)),
              help="Same score for biological age. Higher than the age-in-years score means it predicts lifespan better.")

st.sidebar.header("Filter the group")
st.sidebar.caption("Narrow the people shown in the charts.")
amin, amax = int(df["RIDAGEYR"].min()), int(df["RIDAGEYR"].max())
age_lo, age_hi = st.sidebar.slider("Age range (years)", amin, amax, (amin, amax))
sex_opt = st.sidebar.multiselect("Sex", ["Male", "Female"], ["Male", "Female"])
sex_codes = [c for c, lbl in [(1, "Male"), (2, "Female")] if lbl in sex_opt]

f = df[(df["RIDAGEYR"] >= age_lo) & (df["RIDAGEYR"] <= age_hi)]
if sex_codes and "RIAGENDR" in f.columns:
    f = f[f["RIAGENDR"].isin(sex_codes)]
st.write("Showing {:,} people, {:,} of whom died during follow-up.".format(
    len(f), int(f["MORTSTAT"].sum())))

st.subheader("Biological age vs age in years")
st.caption("Each dot is a person. The dashed line is where the two match. Dots above "
           "the line are biologically older than their years; dots below are younger.")
fig = px.scatter(f, x="RIDAGEYR", y="phenoage", opacity=0.3,
                 custom_data=["phenoage_accel"],
                 labels={"RIDAGEYR": "age in years", "phenoage": "biological age (PhenoAge)"})
fig.update_traces(hovertemplate="age in years: %{x:.0f}<br>biological age: %{y:.0f}<br>"
                  "gap: %{customdata[0]:+.1f} years<extra></extra>")
lim = [f["RIDAGEYR"].min(), f["RIDAGEYR"].max()]
fig.add_trace(go.Scatter(x=lim, y=lim, mode="lines", name="same age",
                         line=dict(color="black", dash="dash"),
                         hovertemplate="biological age equals age in years<extra></extra>"))
fig.update_layout(height=430)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Do faster agers die sooner?")
st.caption("People are split into four equal groups by how fast they are aging. Each "
           "line is a group; lower means more deaths over time. If biological age "
           "matters, the fastest agers (red) should sit lowest.")
if len(f) > 50 and f["MORTSTAT"].sum() > 5:
    g = f.dropna(subset=["phenoage_accel"]).copy()
    g["q"] = pd.qcut(g["phenoage_accel"], 4,
                     labels=["slowest agers", "slower", "faster", "fastest agers"])
    kmf = KaplanMeierFitter()
    km_fig = go.Figure()
    for q in ["slowest agers", "slower", "faster", "fastest agers"]:
        m = g["q"] == q
        if m.sum() < 5:
            continue
        kmf.fit(g.loc[m, "PERMTH_EXM"], g.loc[m, "MORTSTAT"], label=str(q))
        sf = kmf.survival_function_
        km_fig.add_trace(go.Scatter(
            x=sf.index / 12.0, y=sf.iloc[:, 0].values, mode="lines", name=str(q),
            hovertemplate="%{y:.0%} still alive at %{x:.1f} years<extra>" + str(q) + "</extra>"))
    km_fig.update_layout(height=430, xaxis_title="years after the survey",
                         yaxis_title="share still alive",
                         yaxis_tickformat=".0%")
    st.plotly_chart(km_fig, use_container_width=True)
else:
    st.info("Too few people or deaths in this filter to draw the survival curves.")

st.subheader("What drives the biological-age gap?")
st.caption("Compare a single blood test between people aging faster vs slower than "
           "their age. Differences hint at what pushes biological age up.")
bm = st.selectbox("Blood test", list(BIOMARKERS),
                  format_func=lambda k: "{} ({})".format(BIOMARKERS[k], BIOMARKER_PLAIN[k]),
                  help="Pick one of the nine routine tests behind the biological-age score.")
if bm in f.columns:
    h = f.dropna(subset=[bm, "phenoage_accel"]).copy()
    h["group"] = np.where(h["phenoage_accel"] > 0,
                          "aging faster than their age", "aging slower than their age")
    hist = px.histogram(h, x=bm, color="group", barmode="overlay", opacity=0.6,
                        labels={bm: "{} ({})".format(BIOMARKERS[bm], BIOMARKER_PLAIN[bm])})
    hist.update_layout(height=380, legend_title_text="")
    st.plotly_chart(hist, use_container_width=True)

st.caption("Aging speed here is the biological-age gap after removing age in years. "
           "Positive means older than peers of the same age. Research use only, not a "
           "personal risk tool. App v{}.".format(APP_VERSION))
