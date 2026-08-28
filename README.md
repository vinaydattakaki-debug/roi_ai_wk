# AI Investment Decision Agent — Final Take-Home Project

## What this project answers

**If a company deploys an AI agent, does the investment create incremental financial value?**

The project uses Wolters Kluwer's CCH Axcess Expert AI as the worked example.

The key idea is simple:

**AI operating assumptions → incremental revenue/cost → EBIT → free cash flow → NPV / IRR / payback → investment decision**

## Why the existing financial model matters

The detailed Wolters Kluwer workbook is the **finance foundation**. It establishes the company's baseline revenue, margins, cash flow, WACC, enterprise value and shares outstanding.

This app does not try to replicate the entire workbook. Instead it isolates the incremental cash flows of one AI initiative. That avoids incorrectly claiming that all company growth is caused by AI.

The original model architecture also separates:
- **Deterministic math** — calculations must be auditable and reproducible.
- **Judgment** — the analyst interprets the already-computed results and highlights the weakest assumption.

## Main user inputs

The four inputs visible by default are:

1. 2031 AI adoption
2. AI module ARPU
3. AI benefit realization
4. Platform & governance cost

Advanced assumptions and tokenomics are available in expandable sections.

## Main outputs

- Incremental AI NPV
- IRR
- Discounted payback
- Cumulative ROI
- Benefit / cost
- Incremental value per share
- AI NPV as % of enterprise value
- Cash-flow graph
- Adoption × ARPU sensitivity
- Fund / Pilot / Do Not Scale recommendation

## Tokenomics

Tokenomics is intentionally a supporting cost driver, not the whole case.

The app uses:

`cost per call = input tokens × input price + output tokens × output price`

and then:

`annual inference cost = subscribed firms × workflows per firm × calls per workflow × cost per call`

This cost flows into the same AI P&L and DCF as the other operating costs.

## How to run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The command opens the app in your browser at http://localhost:8501.
Running `python app.py` will not work: Streamlit scripts need the Streamlit runtime to start the web server.