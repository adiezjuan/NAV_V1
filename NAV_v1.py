# app.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="NAVIGATOR v1.0 (Demo)", layout="wide")

# -----------------------------
# Scoring utilities (v1.0, rule-based)
# -----------------------------
def clamp01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))

def score_systemic(age: float, bmi: float) -> float:
    """
    NAVIGATOR v1.0 demo: Systemic Biology Score (SBS), 0(best)-100(worst)
    Using only age + BMI (as requested).
    """
    age_r = clamp01((age - 30.0) / 15.0)     # starts increasing >30, saturates ~45
    bmi_r = clamp01((bmi - 22.0) / 18.0)     # starts increasing >22, saturates ~40
    sbs = 100.0 * (0.55 * age_r + 0.45 * bmi_r)
    return float(np.clip(sbs, 0, 100))

def score_endometrial(emt_mm: float, prog_ng_ml: float) -> float:
    """
    Endometrial Phenotype Score (EPS), 0(best)-100(worst)
    - EMT risk increases when <7mm
    - Progesterone risk increases when <9.5 ng/mL (demo threshold; centers vary)
    """
    emt_r = clamp01((7.0 - emt_mm) / 3.0)      # risk if <7; ~0 at >=7; high at <=4
    prog_r = clamp01((9.5 - prog_ng_ml) / 6.0) # risk if <9.5; high at very low values
    eps = 100.0 * (0.60 * emt_r + 0.40 * prog_r)
    return float(np.clip(eps, 0, 100))

def score_embryo(euploid: bool, good_grade: bool) -> float:
    """
    Embryo Genetics/Competence Score (EGS), 0(best)-100(worst)
    """
    # simple competence proxy
    competence = 0.70 * (1.0 if euploid else 0.0) + 0.30 * (1.0 if good_grade else 0.0)
    emb_r = 1.0 - clamp01(competence)
    egs = 100.0 * emb_r
    return float(np.clip(egs, 0, 100))

def navigator_index(age, bmi, emt_mm, prog_ng_ml, euploid, good_grade):
    sbs = score_systemic(age, bmi)
    eps = score_endometrial(emt_mm, prog_ng_ml)
    egs = score_embryo(euploid, good_grade)

    # Global NAVIGATOR Index (GNI) weighting for this minimal input set
    # (Embryo 45%, Endometrium 35%, Systemic 20%)
    gni = 0.45 * egs + 0.35 * eps + 0.20 * sbs
    return sbs, eps, egs, float(np.clip(gni, 0, 100))

def bucket(score: float) -> str:
    if score < 30:
        return "Low"
    if score < 60:
        return "Moderate"
    return "High"

def primary_limiting_domain(sbs, eps, egs):
    d = {"Embryo": egs, "Endometrium": eps, "Systemic": sbs}
    return max(d, key=d.get)

# -----------------------------
# Decision-tree style guidance (non-drug, standard clinic actions)
# -----------------------------
def suggest_path(age, bmi, emt_mm, prog_ng_ml, euploid, good_grade, sbs, eps, egs, gni):
    """
    Outputs an IVF path suggestion as short, clinic-friendly bullets.
    Keeps actions within standard practice and avoids experimental add-ons.
    """
    suggestions = []

    # 1) Embryo-first gate
    if not euploid:
        suggestions.append(("Primary focus: Embryo competence",
            [
                "If PGT-A is available/appropriate, prioritize transferring a euploid embryo to reduce embryo-related uncertainty.",
                "If no euploid embryos are available, focus on optimizing stimulation strategy and embryo selection (lab + morphology).",
                "Consider deferring endometrial optimization steps until embryo competence is addressed."
            ]))
        # still add endometrial/systemic notes if clearly high
    else:
        suggestions.append(("Embryo gate passed (euploid = Yes)",
            ["Proceed to endometrial and systemic optimization checks before transfer."]))

    # 2) Endometrial readiness
    endo_actions = []
    if emt_mm < 7.0:
        endo_actions.append(f"Endometrium thickness is low (EMT {emt_mm:.1f} mm). Optimize endometrial preparation (standard protocol adjustments) before transfer.")
        endo_actions.append("If thin endometrium persists, consider uterine cavity evaluation (e.g., sonohysterography/hysteroscopy) per clinic practice.")
    if prog_ng_ml < 9.5:
        endo_actions.append(f"Progesterone appears low (P4 {prog_ng_ml:.1f} ng/mL). Consider confirming progesterone on the day of transfer (or mid-luteal depending on protocol) and adjusting luteal support per clinic standards.")
    if not endo_actions:
        endo_actions.append("Endometrial readiness markers (EMT and progesterone) look acceptable for proceeding within standard workflows.")

    suggestions.append(("Endometrial phenotype actions", endo_actions))

    # 3) Systemic optimization (standard lifestyle / endocrine checks)
    sys_actions = []
    if bmi >= 30:
        sys_actions.append(f"BMI is elevated (BMI {bmi:.1f}). Consider a pre-transfer optimization window focusing on weight, sleep, and activity—especially if repeated failures.")
    elif bmi >= 27:
        sys_actions.append(f"BMI is moderately elevated (BMI {bmi:.1f}). Lifestyle optimization may improve systemic environment before transfer.")
    if age >= 38:
        sys_actions.append(f"Age is {age:.0f}. Consider prioritizing embryo genetics/selection and minimizing delays to transfer once readiness is confirmed.")
    if not sys_actions:
        sys_actions.append("Systemic risk signals (age/BMI) are not strongly elevated; proceed with standard preparation.")

    suggestions.append(("Systemic biology actions", sys_actions))

    # 4) NAVIGATOR summary path
    dom = primary_limiting_domain(sbs, eps, egs)
    suggestions.append(("NAVIGATOR summary path",
        [
            f"Global NAVIGATOR Index (0–100): {gni:.1f} → {bucket(gni)} overall risk",
            f"Primary limiting domain: {dom}",
            "Suggested sequence: Address the primary limiting domain first, then re-check readiness and proceed to transfer."
        ]))

    return suggestions

# -----------------------------
# UI
# -----------------------------
st.title("NAVIGATOR v1.0 — Demo Streamlit App (Rule-based)")
st.caption("Inputs: standard clinic/patient variables only. Outputs: domain scores, global index, and a suggested IVF path (non-experimental).")

left, right = st.columns([1, 1])

with left:
    st.subheader("Patient & Cycle Inputs")

    age = st.number_input("Age (years)", min_value=18, max_value=55, value=34, step=1)
    bmi = st.number_input("BMI", min_value=15.0, max_value=50.0, value=25.0, step=0.1)
    emt_mm = st.number_input("Endometrial thickness (EMT, mm)", min_value=3.0, max_value=20.0, value=9.0, step=0.1)
    prog_ng_ml = st.number_input("Progesterone (ng/mL) around transfer", min_value=0.0, max_value=40.0, value=10.5, step=0.1)

    euploid = st.selectbox("Euploid embryo available?", options=["Yes", "No"], index=0) == "Yes"
    good_grade = st.selectbox("Good embryo grade?", options=["Yes", "No"], index=0) == "Yes"

    st.markdown("---")
    st.caption("Note: Progesterone thresholds vary by clinic protocol; this demo uses 9.5 ng/mL as an example.")

# compute
sbs, eps, egs, gni = navigator_index(age, bmi, emt_mm, prog_ng_ml, euploid, good_grade)

with right:
    st.subheader("NAVIGATOR Outputs")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Systemic (SBS)", f"{sbs:.1f}", bucket(sbs))
    c2.metric("Endometrium (EPS)", f"{eps:.1f}", bucket(eps))
    c3.metric("Embryo (EGS)", f"{egs:.1f}", bucket(egs))
    c4.metric("Global (GNI)", f"{gni:.1f}", bucket(gni))

    # Radar-ish bar chart (simple, clear)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    labels = ["Systemic", "Endometrium", "Embryo", "Global"]
    values = [sbs, eps, egs, gni]
    ax.bar(labels, values)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Risk score (0 best → 100 worst)")
    ax.set_title("NAVIGATOR v1.0 Scores")
    st.pyplot(fig, clear_figure=True)

st.markdown("---")

# Suggested path
st.subheader("Suggested Patient IVF Path (Decision Tree Output)")
suggestions = suggest_path(age, bmi, emt_mm, prog_ng_ml, euploid, good_grade, sbs, eps, egs, gni)

for title, bullets in suggestions:
    with st.expander(title, expanded=True):
        for b in bullets:
            st.write(f"- {b}")

# Optional: show the underlying record (for exports later)
st.markdown("---")
st.subheader("Export-ready Record (for future audit trails)")
row = pd.DataFrame([{
    "age": age,
    "bmi": bmi,
    "emt_mm": emt_mm,
    "prog_ng_ml": prog_ng_ml,
    "euploid": int(euploid),
    "good_grade": int(good_grade),
    "SBS": round(sbs, 2),
    "EPS": round(eps, 2),
    "EGS": round(egs, 2),
    "GNI": round(gni, 2),
    "overall_bucket": bucket(gni),
    "primary_limiting_domain": primary_limiting_domain(sbs, eps, egs)
}])

st.dataframe(row, use_container_width=True)
