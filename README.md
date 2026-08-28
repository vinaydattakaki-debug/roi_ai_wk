# AI Investment Decision Agent

## Project Overview

The **AI Investment Decision Agent** is a financial decision-support tool built to answer a simple question:

**Can an AI investment create incremental financial value for a company?**

The project uses **Wolters Kluwer and CCH Axcess Expert AI** as the case study.

The project was completed in two stages.

### 1. Financial Modeling

The first step was to build a detailed financial model for Wolters Kluwer.

The model was used to:

* Analyze historical financial performance
* Forecast future revenue and profitability
* Forecast the income statement, balance sheet, and cash flow statement
* Estimate free cash flow
* Calculate WACC
* Perform a DCF valuation
* Estimate enterprise value and value per share

This created the financial baseline needed to evaluate the AI investment.

### 2. AI Investment Analysis

After establishing the company baseline, the model separately evaluates the incremental financial impact of **CCH Axcess Expert AI**.

The application looks at assumptions such as:

* AI customer adoption
* AI module ARPU
* AI benefit realization
* Customer retention improvement
* Pricing improvement
* AI development costs
* Delivery and sales costs
* Platform and governance costs
* AI inference and token costs

These assumptions are converted into:

**AI assumptions → incremental revenue and costs → EBIT → free cash flow → NPV / IRR / payback → investment decision**

The purpose is not to assume that all Wolters Kluwer growth was caused by AI.

Instead, the project asks:

**If the expected benefits of this AI initiative are achieved, how much additional value could it create?**

## Main User Inputs

The four main inputs shown in the application are:

1. **2031 AI adoption**
2. **AI module ARPU**
3. **AI benefit realization**
4. **Platform and governance cost**

Additional assumptions are available under advanced settings, including:

* Starting adoption
* Addressable customers
* Customer growth
* Churn reduction
* Pricing uplift
* AI development costs
* Delivery costs
* Sales and marketing costs
* Token usage and inference costs

## Main Outputs

The application calculates:

* Incremental AI NPV
* IRR
* Discounted payback
* Cumulative ROI
* Benefit-to-cost ratio
* Incremental value per share
* AI NPV as a percentage of enterprise value
* Free cash flow over time
* Adoption × ARPU sensitivity
* Break-even scenarios
* **Fund / Pilot / Do Not Scale** recommendation

## Scenario Analysis

The application also allows the user to test simple questions such as:

* What if AI adoption is only 20%?
* What if AI benefit realization falls to 80%?
* What is the minimum ARPU required for positive NPV?
* What level of adoption is required to break even?
* What happens if AI inference costs increase?

The financial calculations are performed by the deterministic model, while the decision layer helps interpret the results.

## Tokenomics

Token costs are included as one part of the overall AI cost structure.

The model estimates:

`cost per call = input token cost + output token cost`

and:

`annual inference cost = subscribed firms × workflows per firm × model calls per workflow × cost per call`

These costs flow into the same AI financial model as development, platform, delivery, and other operating costs.

## Overall Objective

The project combines traditional financial modeling with AI investment analysis.

The main question is:

**Under what operating and commercial assumptions does an AI investment create incremental shareholder value?**

## How to Run the Project

Install the required packages:

```bash
pip install -r requirements.txt
```

Then start the Streamlit application:

```bash
streamlit run app.py
```

The application will open in your browser, usually at:

`http://localhost:8501`

Do not run:

```bash
python app.py
```

The project should be started with the Streamlit command because Streamlit runs the web interface and local server.
