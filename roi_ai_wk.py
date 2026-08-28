from pathlib import Path
import textwrap, zipfile, json, math, os

out = Path(__file__).resolve().parent / "Wolters_Kluwer_AI_ROI"
out.mkdir(parents=True, exist_ok=True)

model_py = r'''
import math

ACCOUNT = {
    "entity": "Wolters Kluwer — Tax & Accounting",
    "initiative": "CCH Axcess Expert AI",
    "first_year": 2026,
    "horizon": 6,
    "shares": 228.0,              # million
    "enterprise_value": 30162.0,  # € million
    "wacc": 8.0,
    "tax_rate": 23.6,
    "sunk_cost": 17.6,            # € million
    "base_revenue": 1660.0,       # € million, T&A 2025A
    "base_growth": 7.0,
}

BASE_DRIVERS = {
    "firms": 10000.0,
    "firm_growth": 3.0,
    "adoption_start": 4.0,
    "adoption_end": 34.0,
    "arpu": 25000.0,
    "expansion_pct": 15.0,
    "churn_bps": 100.0,
    "price_bps": 50.0,
    "attribution": 50.0,
    "dev_intensity": 12.0,
    "ai_share_of_dev": 8.0,
    "delivery_pct": 15.0,
    "sm_pct": 20.0,
    "platform": 5.0,
    "include_sunk": True,
    "benefit_realization": 100.0,

    # Optional tokenomics extension.
    "include_token_cost": False,
    "workflows_per_firm": 500.0,
    "calls_per_workflow": 4.0,
    "input_tokens_per_call": 10000.0,
    "output_tokens_per_call": 2000.0,
    "input_price_per_m": 2.0,
    "output_price_per_m": 10.0,
}


def token_cost_per_firm(d):
    per_call = (
        d["input_tokens_per_call"] * d["input_price_per_m"]
        + d["output_tokens_per_call"] * d["output_price_per_m"]
    ) / 1_000_000.0
    return d["workflows_per_firm"] * max(1.0, d["calls_per_workflow"]) * per_call


def _npv_at(rate, flows):
    return sum(f / ((1.0 + rate) ** i) for i, f in enumerate(flows))


def _irr(flows):
    lo, hi = -0.5, 3.0
    if _npv_at(lo, flows) * _npv_at(hi, flows) >= 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _npv_at(lo, flows) * _npv_at(mid, flows) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def compute_model(drivers=None, account=None):
    a = dict(ACCOUNT if account is None else account)
    d = dict(BASE_DRIVERS)
    if drivers:
        d.update(drivers)

    N = int(a["horizon"])
    rows = []
    prev_year_end = 0.0
    token_per_firm = token_cost_per_firm(d)

    for i in range(N):
        t = i + 1
        year = int(a["first_year"] + i)

        firms = d["firms"] * ((1 + d["firm_growth"] / 100.0) ** i)
        start = max(d["adoption_start"], 0.01)
        adoption = (d["adoption_start"] / 100.0) * (
            d["adoption_end"] / start
        ) ** (i / max(N - 1, 1))

        year_end = firms * adoption
        avg_subscribed = (prev_year_end + year_end) / 2.0
        prev_year_end = year_end

        recurring_base = a["base_revenue"] * ((1 + a["base_growth"] / 100.0) ** t)

        module_revenue = avg_subscribed * d["arpu"] / 1_000_000.0
        advisory_expansion = module_revenue * d["expansion_pct"] / 100.0
        retention = (
            recurring_base
            * d["churn_bps"] / 10000.0
            * t
            * d["attribution"] / 100.0
        )
        pricing = (
            recurring_base
            * d["price_bps"] / 10000.0
            * d["attribution"] / 100.0
        )

        potential_benefit = module_revenue + advisory_expansion + retention + pricing
        benefit = potential_benefit * d["benefit_realization"] / 100.0

        ai_dev = (
            recurring_base
            * d["dev_intensity"] / 100.0
            * d["ai_share_of_dev"] / 100.0
        )
        delivery = module_revenue * d["delivery_pct"] / 100.0
        sales_marketing = module_revenue * d["sm_pct"] / 100.0
        platform = d["platform"] * (1.03 ** i)

        token_cost = 0.0
        if d["include_token_cost"]:
            token_cost = avg_subscribed * token_per_firm / 1_000_000.0

        total_cost = ai_dev + delivery + sales_marketing + platform + token_cost
        ebit = benefit - total_cost
        tax = ebit * a["tax_rate"] / 100.0 if ebit > 0 else 0.0
        fcf = ebit - tax

        rows.append({
            "year": year,
            "firms": firms,
            "adoption": adoption,
            "avg_subscribed": avg_subscribed,
            "module_revenue": module_revenue,
            "advisory_expansion": advisory_expansion,
            "retention": retention,
            "pricing": pricing,
            "potential_benefit": potential_benefit,
            "benefit": benefit,
            "ai_dev": ai_dev,
            "delivery": delivery,
            "sales_marketing": sales_marketing,
            "platform": platform,
            "token_cost": token_cost,
            "cost": total_cost,
            "ebit": ebit,
            "tax": tax,
            "fcf": fcf,
        })

    sunk = -a["sunk_cost"] if d["include_sunk"] else 0.0
    flows = [sunk] + [r["fcf"] for r in rows]
    wacc = a["wacc"] / 100.0

    npv = sum(f / ((1 + wacc) ** i) for i, f in enumerate(flows))
    irr = _irr(flows)

    discounted_cumulative = sunk
    payback = None
    for i, row in enumerate(rows):
        discounted_fcf = row["fcf"] / ((1 + wacc) ** (i + 1))
        start_cum = discounted_cumulative
        discounted_cumulative += discounted_fcf
        row["discounted_fcf"] = discounted_fcf
        row["discounted_cumulative_fcf"] = discounted_cumulative

        if payback is None and start_cum < 0 <= discounted_cumulative and discounted_fcf > 0:
            fraction = (-start_cum) / discounted_fcf
            payback = row["year"] - 1 + fraction

    sum_benefit = sum(r["benefit"] for r in rows)
    sum_cost = sum(r["cost"] for r in rows) + (a["sunk_cost"] if d["include_sunk"] else 0.0)

    return {
        "account": a,
        "drivers": d,
        "rows": rows,
        "npv": npv,
        "irr": irr,
        "payback": payback,
        "roi": (sum_benefit - sum_cost) / sum_cost if sum_cost else 0.0,
        "bcr": sum_benefit / sum_cost if sum_cost else 0.0,
        "per_share": npv / a["shares"],
        "pct_ev": npv / a["enterprise_value"],
        "token_cost_per_firm": token_per_firm,
    }


def break_even(driver_name, low, high, fixed_drivers=None, iterations=80, account=None):
    base = {} if fixed_drivers is None else dict(fixed_drivers)
    low_result = compute_model({**base, driver_name: low}, account)["npv"]
    high_result = compute_model({**base, driver_name: high}, account)["npv"]

    if high_result < 0:
        return None
    if low_result >= 0:
        return low

    lo, hi = low, high
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        result = compute_model({**base, driver_name: mid}, account)["npv"]
        if result >= 0:
            hi = mid
        else:
            lo = mid
    return hi
'''

app_py = r'''
import re
import pandas as pd
import streamlit as st

from model import ACCOUNT, BASE_DRIVERS, compute_model, break_even, token_cost_per_firm

st.set_page_config(
    page_title="AI Investment Decision Agent",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background: #f7f9fb; color: #172033; }
    [data-testid="stHeader"] { background: rgba(247,249,251,.95); }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e4e9ee; }
    h1,h2,h3 { color: #142033 !important; }
    .subtle { color: #667085; font-size: 0.92rem; }
    .eyebrow { color:#60736f; text-transform:uppercase; letter-spacing:.12em; font-size:.74rem; font-weight:700; }
    .decision {
        background:#ffffff; border:1px solid #e1e7ec; border-radius:16px;
        padding:20px 22px; margin-bottom:14px;
    }
    .decision-good { border-left:5px solid #2f766f; }
    .decision-watch { border-left:5px solid #9a6b2f; }
    .decision-bad { border-left:5px solid #9b4b4b; }
    div[data-testid="stMetric"] {
        background:#ffffff; border:1px solid #e1e7ec; border-radius:14px;
        padding:14px 16px;
    }
    div[data-testid="stMetric"] label { color:#667085 !important; }
    div[data-testid="stMetricValue"] { color:#174f49 !important; }
    .stButton > button[kind="primary"] {
        background:#2f766f; border-color:#2f766f; color:white; border-radius:10px;
    }
    .stButton > button { border-radius:10px; }
    .small-note {
        background:#f1f5f4; border-radius:12px; padding:12px 14px; color:#53635f;
        font-size:.88rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def euro_m(x):
    return f"€{x:,.1f}m"

def pct(x):
    return "N/M" if x is None else f"{x*100:.1f}%"

def decision_for(result):
    hurdle = result["account"]["wacc"] / 100.0
    if result["npv"] > 0 and result["irr"] is not None and result["irr"] > hurdle:
        return (
            "FUND WITH STAGE GATE",
            "good",
            "The investment creates positive incremental value and clears the hurdle rate. "
            "Validate adoption, monetization and realized AI performance before releasing the next tranche of capital.",
        )
    if result["npv"] > 0:
        return (
            "PILOT / VALIDATE",
            "watch",
            "The project is NPV-positive, but the return profile does not clearly clear the hurdle. "
            "Use a controlled pilot to validate the weakest operating assumptions.",
        )
    return (
        "DO NOT SCALE",
        "bad",
        "The current scenario does not create positive incremental value within the modeled horizon. "
        "Improve adoption, monetization, benefit realization or the cost structure before scaling.",
    )

st.markdown("<div class='eyebrow'>Wolters Kluwer · CCH Axcess Expert AI</div>", unsafe_allow_html=True)
st.title("AI Investment Decision Agent")
st.markdown(
    "<div class='subtle'>A simple investment-underwriting tool that connects AI operating assumptions to "
    "incremental cash flow, ROI and corporate value.</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Investment assumptions")
    st.caption("Change the few assumptions that matter most and run the investment case.")

    adoption_end = st.slider("2031 AI adoption (%)", 10.0, 60.0, 34.0, 1.0)
    st.caption("Base assumption: 34%")

    arpu = st.number_input("AI module ARPU (€ / firm-year)", 5_000.0, 60_000.0, 25_000.0, 500.0)
    st.caption("Annual AI revenue per subscribed firm")

    benefit_realization = st.slider(
        "AI benefit realization (%)", 50.0, 100.0, 100.0, 1.0,
        help="A simple stress factor for technical effectiveness, accuracy and real-world benefit capture."
    )
    st.caption("Stress technical effectiveness and real-world benefit capture")

    platform = st.number_input("Platform & governance cost (€m / year)", 0.0, 30.0, 5.0, 0.5)
    st.caption("Annual run cost of the AI platform, security and oversight")

    with st.expander("Advanced assumptions", expanded=True):
        a1, a2 = st.columns(2)
        wacc = a1.number_input(
            "WACC (%)", 3.0, 20.0, float(ACCOUNT["wacc"]), 0.5,
            help="Discount rate and investment hurdle. Feeds NPV, discounted payback and the fund / pilot verdict."
        )
        expansion = a2.number_input("Advisory expansion (%)", 0.0, 40.0, 15.0, 1.0)

        a3, a4 = st.columns(2)
        churn_bps = a3.number_input("Churn reduction (bps)", 0.0, 250.0, 100.0, 5.0)
        price_bps = a4.number_input("Price uplift (bps)", 0.0, 200.0, 50.0, 5.0)

        attribution = st.number_input("Benefits credited to AI (%)", 0.0, 100.0, 50.0, 5.0)

        a5, a6 = st.columns(2)
        adoption_start = a5.number_input("2026 adoption (%)", 0.5, 25.0, 4.0, 0.5)
        firms = a6.number_input("Addressable firms", 100.0, 50_000.0, 10_000.0, 100.0)

        firm_growth = st.number_input("Addressable-firm growth (%)", 0.0, 10.0, 3.0, 0.5)

    with st.expander("Cost assumptions", expanded=True):
        c1, c2 = st.columns(2)
        dev_intensity = c1.number_input("Product development (% revenue)", 5.0, 20.0, 12.0, 0.5)
        ai_share_dev = c2.number_input("AI share of development (%)", 0.0, 50.0, 8.0, 1.0)

        c3, c4 = st.columns(2)
        delivery_pct = c3.number_input("Delivery cost (% module revenue)", 0.0, 50.0, 15.0, 1.0)
        sm_pct = c4.number_input("Sales & marketing (% module revenue)", 0.0, 60.0, 20.0, 1.0)

        include_sunk = st.checkbox("Include €17.6m sunk cost", value=True)

    with st.expander("Tokenomics", expanded=True):
        st.caption(
            "Optional. Token usage is treated as one operating-cost driver inside the same DCF."
        )
        include_token_cost = st.checkbox("Include inference cost", value=False)

        t1, t2 = st.columns(2)
        workflows_per_firm = t1.number_input("Workflows / firm / year", 0.0, 100_000.0, 500.0, 100.0)
        calls_per_workflow = t2.number_input("Model calls / workflow", 1.0, 50.0, 4.0, 1.0)

        t3, t4 = st.columns(2)
        input_tokens = t3.number_input("Input tokens / call", 0.0, 1_000_000.0, 10_000.0, 1_000.0)
        output_tokens = t4.number_input("Output tokens / call", 0.0, 1_000_000.0, 2_000.0, 500.0)

        t5, t6 = st.columns(2)
        input_price = t5.number_input("Input € / 1M tokens", 0.0, 100.0, 2.0, 0.5)
        output_price = t6.number_input("Output € / 1M tokens", 0.0, 500.0, 10.0, 1.0)

        preview_cost = token_cost_per_firm({
            "workflows_per_firm": workflows_per_firm,
            "calls_per_workflow": calls_per_workflow,
            "input_tokens_per_call": input_tokens,
            "output_tokens_per_call": output_tokens,
            "input_price_per_m": input_price,
            "output_price_per_m": output_price,
        })
        st.caption(
            f"Estimated inference cost is €{preview_cost:,.2f} per subscribed firm-year. "
            + ("Currently included in the DCF." if include_token_cost
               else "Currently excluded from the DCF.")
        )

top1, top2, top3 = st.columns(3)
top1.metric("T&A revenue, 2025A", "€1,660m")
top2.metric("Enterprise value anchor", "€30.16bn")
top3.metric("WACC / investment hurdle", f"{wacc:.1f}%")

st.divider()

drivers = {
    "adoption_start": adoption_start,
    "adoption_end": adoption_end,
    "firms": firms,
    "firm_growth": firm_growth,
    "arpu": arpu,
    "expansion_pct": expansion,
    "churn_bps": churn_bps,
    "price_bps": price_bps,
    "attribution": attribution,
    "dev_intensity": dev_intensity,
    "ai_share_of_dev": ai_share_dev,
    "delivery_pct": delivery_pct,
    "sm_pct": sm_pct,
    "platform": platform,
    "include_sunk": include_sunk,
    "benefit_realization": benefit_realization,
    "include_token_cost": include_token_cost,
    "workflows_per_firm": workflows_per_firm,
    "calls_per_workflow": calls_per_workflow,
    "input_tokens_per_call": input_tokens,
    "output_tokens_per_call": output_tokens,
    "input_price_per_m": input_price,
    "output_price_per_m": output_price,
}

account = dict(ACCOUNT)
account["wacc"] = wacc

result = compute_model(drivers, account)
verdict, tone, headline = decision_for(result)

tab1, tab2, tab3, tab4 = st.tabs(
    ["Decision", "Financial model", "Scenario analyst", "Evidence & method"]
)

with tab1:
    st.markdown(
        f"""
        <div class="decision decision-{tone}">
          <div class="eyebrow">Investment recommendation</div>
          <h2 style="margin:.25rem 0 .35rem 0">{verdict}</h2>
          <div class="subtle">{headline}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Incremental AI NPV", euro_m(result["npv"]))
    c2.metric("IRR", pct(result["irr"]))
    c3.metric("Discounted payback", "> horizon" if result["payback"] is None else f"{result['payback']:.1f}")
    c4.metric("Value / share", f"€{result['per_share']:.3f}")

    st.subheader("Cash-flow profile")
    chart_df = pd.DataFrame(
        {
            "Year": [r["year"] for r in result["rows"]],
            "Free cash flow": [r["fcf"] for r in result["rows"]],
            "Cumulative discounted FCF": [r["discounted_cumulative_fcf"] for r in result["rows"]],
        }
    ).set_index("Year")
    st.line_chart(chart_df, height=320)

    st.markdown(
        f"""
        <div class="small-note">
        <b>Interpretation:</b> The model values only the incremental cash flows of this AI initiative.
        Its NPV equals {result['pct_ev']*100:.3f}% of the enterprise-value anchor, so this is a
        materiality check — not a claim that all Wolters Kluwer value creation is caused by AI.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("What creates the value?")
    d1, d2, d3 = st.columns(3)
    d1.metric("2031 adoption", f"{adoption_end:.0f}%")
    d2.metric("Module ARPU", f"€{arpu:,.0f}")
    d3.metric("Benefit realization", f"{benefit_realization:.0f}%")

with tab2:
    st.subheader("Incremental AI cash-flow build")
    rows = pd.DataFrame(result["rows"])
    table = rows[
        ["year", "module_revenue", "advisory_expansion", "retention", "pricing",
         "benefit", "ai_dev", "delivery", "sales_marketing", "platform",
         "token_cost", "cost", "ebit", "fcf"]
    ].copy()
    table.columns = [
        "Year", "Module revenue", "Expansion", "Retention", "Pricing",
        "Total benefit", "AI development", "Delivery", "Sales & marketing",
        "Platform", "Token cost", "Total cost", "EBIT", "FCF"
    ]
    st.dataframe(table.round(2), use_container_width=True, hide_index=True)

    s1, s2 = st.columns([1, 1])
    with s1:
        st.subheader("Return metrics")
        metrics = pd.DataFrame(
            [
                ["NPV", euro_m(result["npv"])],
                ["IRR", pct(result["irr"])],
                ["Discounted payback", "> horizon" if result["payback"] is None else f"{result['payback']:.1f}"],
                ["Cumulative ROI", f"{result['roi']*100:.1f}%"],
                ["Benefit / cost", f"{result['bcr']:.2f}x"],
                ["Value / share", f"€{result['per_share']:.3f}"],
                ["NPV / enterprise value", f"{result['pct_ev']*100:.3f}%"],
            ],
            columns=["Metric", "Result"],
        )
        st.dataframe(metrics, use_container_width=True, hide_index=True)

    with s2:
        st.subheader("Tokenomics")
        st.metric("Inference cost / firm-year", f"€{result['token_cost_per_firm']:,.2f}")
        st.caption(
            "Tokenomics is treated as one operating-cost driver. It does not replace the broader "
            "development, delivery, sales, platform and governance cost structure."
        )

    st.subheader("NPV sensitivity — adoption × ARPU")
    adoption_multipliers = [0.70, 0.85, 1.00, 1.15, 1.30]
    arpus = [17_500.0, 25_000.0, 32_500.0]
    sens_rows = []
    for mult in adoption_multipliers:
        row = {"Adoption vs base": f"{mult*100:.0f}%"}
        for a in arpus:
            scenario = dict(drivers)
            scenario["adoption_end"] = 34.0 * mult
            scenario["arpu"] = a
            row[f"€{a/1000:.1f}K ARPU"] = compute_model(scenario, account)["npv"]
        sens_rows.append(row)
    sens_df = pd.DataFrame(sens_rows)
    st.dataframe(sens_df.style.format({c: "{:.1f}" for c in sens_df.columns[1:]}), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Scenario analyst")
    st.caption(
        "Ask a simple investment question. The analyst changes the scenario, calls the deterministic "
        "financial engine, and explains the result."
    )

    examples = st.columns(4)
    if examples[0].button("Adoption = 20%"):
        st.session_state["agent_q"] = "What if adoption is 20%?"
    if examples[1].button("Break-even ARPU"):
        st.session_state["agent_q"] = "What is the break-even ARPU?"
    if examples[2].button("Benefit realization = 80%"):
        st.session_state["agent_q"] = "What if benefit realization is 80%?"
    if examples[3].button("Token prices double"):
        st.session_state["agent_q"] = "What if token prices double?"

    q = st.text_input(
        "Ask the analyst",
        value=st.session_state.get("agent_q", ""),
        placeholder="Example: What if adoption is 25%?",
    )

    if q:
        ql = q.lower()
        scenario = dict(drivers)
        answer = None

        if "break-even" in ql and "arpu" in ql:
            fixed = dict(drivers)
            be = break_even("arpu", 5_000.0, 100_000.0, fixed_drivers=fixed, account=account)
            if be is None:
                answer = "The model does not reach positive NPV within the tested ARPU range."
            else:
                answer = (
                    f"Break-even ARPU is approximately €{be:,.0f} per firm-year under the current "
                    f"adoption, benefit-realization and cost assumptions."
                )

        elif ("minimum" in ql or "break-even" in ql) and "adoption" in ql:
            fixed = dict(drivers)
            be = break_even("adoption_end", 1.0, 90.0, fixed_drivers=fixed, account=account)
            if be is None:
                answer = "The model does not reach positive NPV within the tested adoption range."
            else:
                answer = (
                    f"Break-even 2031 adoption is approximately {be:.1f}% under the current ARPU "
                    f"and cost assumptions."
                )

        else:
            adoption_match = re.search(r"adoption[^0-9]*(\d+(?:\.\d+)?)\s*%", ql)
            arpu_match = re.search(r"arpu[^0-9]*(\d[\d,]*)", ql)
            realization_match = re.search(
                r"(?:benefit realization|realization|success|accuracy)[^0-9]*(\d+(?:\.\d+)?)\s*%",
                ql,
            )

            if adoption_match:
                scenario["adoption_end"] = float(adoption_match.group(1))
            if arpu_match:
                scenario["arpu"] = float(arpu_match.group(1).replace(",", ""))
            if realization_match:
                scenario["benefit_realization"] = float(realization_match.group(1))
            if "token" in ql and "double" in ql:
                scenario["include_token_cost"] = True
                scenario["input_price_per_m"] *= 2
                scenario["output_price_per_m"] *= 2

            scenario_result = compute_model(scenario, account)
            sv, _, _ = decision_for(scenario_result)
            payback_txt = (
                "> horizon"
                if scenario_result["payback"] is None
                else f"{scenario_result['payback']:.1f}"
            )
            answer = (
                f"{sv}. Under this scenario, NPV is {euro_m(scenario_result['npv'])}, "
                f"IRR is {pct(scenario_result['irr'])}, and discounted payback is "
                f"{payback_txt}. "
                "The result is computed by the deterministic financial engine; the analyst layer only interprets it."
            )

        st.info(answer)

with tab4:
    st.subheader("Evidence used to anchor the case")
    evidence = pd.DataFrame(
        [
            ["T&A revenue 2025A", "€1,660m", "2025 Annual Report"],
            ["T&A organic growth", "+7%", "2025 Annual Report"],
            ["T&A H1 2026", "€847m / +6% organic", "2026 Half-Year Results"],
            ["Recurring revenue share", "93% in T&A H1 2026", "2026 Half-Year Results"],
            ["Renewal rate", ">90%", "2025 Annual Report"],
            ["CCH Axcess native-cloud growth", "+19%", "2025 Annual Report"],
            ["Firms using AI modules", "≈250", "2026 Half-Year Results"],
            ["Product development intensity", "12–13%", "2025 AR / 2026 H1"],
            ["Investment hurdle", "8%", "AI M&A / investment references used in source model"],
            ["Enterprise value anchor", "€30,162m", "Integrated DCF"],
            ["Diluted shares", "228m", "Integrated DCF"],
        ],
        columns=["Anchor", "Value", "Source"],
    )
    st.dataframe(evidence, use_container_width=True, hide_index=True)

    st.subheader("Why the financial model matters")
    st.markdown(
        """
        1. **Baseline:** the full company model establishes Wolters Kluwer's revenue growth, margins,
           free cash flow, WACC, enterprise value and shares outstanding.
        2. **Isolation:** this app separately models the incremental economics of one AI initiative,
           rather than attributing all company growth to AI.
        3. **Conversion:** adoption, ARPU, retention, pricing and AI costs flow into EBIT and after-tax
           free cash flow.
        4. **Valuation:** those incremental cash flows are discounted to NPV and compared with the
           company's hurdle rate and enterprise value.
        """
    )

    st.subheader("Deterministic vs non-deterministic")
    st.markdown(
        """
        - **Deterministic engine:** formulas for revenue, costs, EBIT, tax, FCF, NPV, IRR and payback.
          The same inputs always return the same result.
        - **Uncertain inputs:** adoption, ARPU, benefit realization, churn benefit, pricing benefit,
          model usage and token cost. These are scenario assumptions, not guaranteed outcomes.
        - **Decision layer:** the analyst interprets the computed figures and identifies what needs to
          be validated before more capital is committed.
        """
    )

    st.warning(
        "Limitation: this is an incremental AI investment appraisal, not a claim that AI caused "
        "Wolters Kluwer's historical share-price or enterprise-value movements."
    )


'''

requirements = """streamlit>=1.40
pandas>=2.0
"""

readme = r"""
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
"""

# --- the step that was missing: actually write the files to disk ---
config_toml = """[theme]
base = "light"
primaryColor = "#2f766f"
backgroundColor = "#f7f9fb"
secondaryBackgroundColor = "#ffffff"
textColor = "#172033"
"""

files = {
    ".streamlit/config.toml": config_toml,
    "model.py": model_py.lstrip(),
    "app.py": app_py.lstrip(),
    "requirements.txt": requirements,
    "README.md": readme.lstrip(),
}

for name, text in files.items():
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

with zipfile.ZipFile(out.parent / "AI_Investment_Decision_Agent_Final.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    for name in files:
        zf.write(out / name, arcname=f"{out.name}/{name}")

print("Wrote:")
for name in files:
    print("  ", (out / name).resolve())
print()
print("Run it with:")
print(f"  pip install -r {(out / 'requirements.txt')}")
print(f"  streamlit run {(out / 'app.py')}")
