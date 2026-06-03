> **EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are unverified and may be wrong. Consult a qualified clinician.**

# Lab report review (DRAFT — for clinician verification)

- **Source:** sample_lab_report.png  |  **OCR engine:** transcript-fallback  |  **Reasoning model:** meditron-mock
- **Generated:** 2026-06-03 22:17
- **Status:** UNVERIFIED. Every item below must be checked by a qualified clinician.

## 1. Extracted results
_Reference ranges are taken from the report itself, exactly as printed._

| Test | Value | Unit | Reference range | Report flag | Deterministic flag |
| --- | --- | --- | --- | --- | --- |
| Haemoglobin | 9.8 | g/dL | 13.0-17.0 | L | low |
| Red Cell Count | 4.1 | 10^12/L | 4.5-5.9 | L | low |
| Haematocrit | 0.31 | L/L | 0.40-0.54 | L | low |
| Mean Cell Volume | 78 | fL | 80-100 | L | low |
| White Cell Count | 12.6 | 10^9/L | 4.0-11.0 | H | high |
| Neutrophils | 9.1 | 10^9/L | 2.0-7.5 | H | high |
| Lymphocytes | 2.3 | 10^9/L | 1.0-4.0 | — | normal |
| Platelets | 178 | 10^9/L | 150-400 | — | normal |
| C-Reactive Protein | 48 | mg/L | — | — | cannot_assess — no range provided |
| Ferritin | -- | ug/L | 30-400 | — | unparsed |

## 2. Flagged abnormalities (deterministic — no AI)
Computed by arithmetic against the printed ranges:

- **Haemoglobin** = 9.8 g/dL — **LOW** (reference 13.0-17.0)
- **Red Cell Count** = 4.1 10^12/L — **LOW** (reference 4.5-5.9)
- **Haematocrit** = 0.31 L/L — **LOW** (reference 0.40-0.54)
- **Mean Cell Volume** = 78 fL — **LOW** (reference 80-100)
- **White Cell Count** = 12.6 10^9/L — **HIGH** (reference 4.0-11.0)
- **Neutrophils** = 9.1 10^9/L — **HIGH** (reference 2.0-7.5)

## 3. Possible considerations (for clinician review)
> The following is an **unverified, AI-generated draft** of *possibilities to discuss with a clinician* — not a diagnosis, not exhaustive, and possibly wrong. A qualified clinician must verify or discard each point.

For clinician review only — possibilities, not a diagnosis; non-exhaustive, requires clinical correlation.

- Low Hb/MCV/Hct/RBC: a microcytic picture; possible categories include iron-deficiency states, thalassaemia trait, anaemia of chronic disease. Uncertainty HIGH; NON-SPECIFIC. Correlate clinically (e.g. iron studies).
- High WCC/neutrophils: reactive/inflammatory or many benign causes; the CRP had no printed range so was not assessed. Uncertainty HIGH; NON-SPECIFIC. Correlate clinically.

## 4. Limitations & coverage
- **Could not be parsed (value unreadable):** Ferritin
- **No reference range on report (not assessed):** C-Reactive Protein
- Reference ranges were used **as printed**; none were guessed or substituted.
- The considerations are **AI-generated and unverified**. Educational prototype, not a medical device, and may be wrong.

---
_EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are unverified and may be wrong. Consult a qualified clinician._
