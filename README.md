# E-commerce Sales & Customer Analytics

Reproducible analysis of transaction records from a UK online retailer, focused on sales performance, purchasing behavior, and customer segmentation.

## Objectives

- Identify leading products and countries by revenue.
- Evaluate monthly sales trends and average order value.
- Measure repeat purchasing and customer value.
- Segment identified customers using recency, frequency, and monetary value (RFM).

## Delivery plan

The project is timeboxed to 12–15 workdays at 1–2 hours per day, with a maximum planned effort of 30 hours. The [delivery plan](docs/project_plan.md) defines stage allocations, scope limits, completion criteria, and current progress.

## Available outputs

| Artifact | Contents |
| --- | --- |
| [Dataset overview](notebooks/01_data_overview.ipynb) | Source verification, schema, coverage, and record grain |
| [Data quality assessment](notebooks/02_data_quality.ipynb) | Missing values, cancellations, duplicate records, numeric exceptions, and invoice consistency |
| [Quality findings](docs/data_quality.md) | Observed issues, analytical implications, and proposed treatment |
| [Completeness chart](reports/figures/02_customer_id_completeness.png) | Monthly customer-ID coverage and source row counts |
| [Methodology](docs/analysis_decisions.md) | Population definitions, assumptions, and outstanding decisions |
| [SQLite ingestion](docs/sqlite_ingestion.md) | Raw schema, reproducible loading, and complete source reconciliation |
| [Transaction cleaning](docs/data_cleaning.md) | Reviewed eligibility rules, lineage-preserving populations, and duplicate sensitivity |
| [Cleaning notebook](notebooks/03_data_cleaning.ipynb) | Executed cleaning pipeline, count bridge, population coverage, and validation results |

Executed notebooks and HTML exports are included. Original records are reconciled in SQLite; cleaning produces a complete audit ledger plus separate merchandise-purchase and identified-customer populations. Business SQL queries, revenue KPI analysis, and customer segmentation remain pending.

## Data

[UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) contains 541,909 invoice line items from 1 December 2010 to 9 December 2011. Prices are in GBP. An invoice can contain multiple line items, so row counts are not order counts.

The raw workbook is preserved and verified against a recorded SHA-256 checksum. Source files, intermediate datasets, and local databases are excluded from version control. See the [data dictionary](docs/data_dictionary.md) for field definitions.

## Reproduce

From the project root in Windows PowerShell, using Python 3.14:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Invoke-WebRequest -Uri 'https://archive.ics.uci.edu/static/public/352/online+retail.zip' -OutFile 'data\raw\online_retail.zip'
.\.venv\Scripts\python.exe scripts\download_data.py
.\.venv\Scripts\python.exe scripts\load_sqlite.py
.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name ecommerce-analytics --display-name "E-commerce Analytics (.venv)"
.\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\01_data_overview.ipynb
.\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\02_data_quality.ipynb
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\03_data_cleaning.ipynb
```

`requirements-lock.txt` records the verified environment; `requirements.txt` defines supported dependency ranges. The runner saves executed notebooks and HTML exports under `reports/`. Launch JupyterLab with `.\.venv\Scripts\python.exe -m jupyterlab` for interactive use.

## Structure

```text
data/raw/          Original workbook and source manifest (untracked)
data/processed/    Derived datasets and profiling summaries (untracked)
database/          Local SQLite databases (untracked)
docs/              Field definitions, methodology, and quality findings
notebooks/         Reproducible analytical notebooks
reports/           HTML exports and figures
scripts/           Download and execution utilities
sql/               SQL models and analytical queries
```

## Analytical limitations

- Missing customer IDs constrain customer-level coverage; anonymous sales require separate treatment.
- Cancellations, adjustments, non-merchandise codes, and duplicate-looking rows require documented eligibility rules before revenue aggregation.
- The cleaned sales population measures gross merchandise purchases before credits, retains exact copies as a disclosed baseline, and excludes ambiguous manual entries. It is not net revenue.
- December 2011 is partial and is not directly comparable with full months.
- The source does not provide costs, customer demographics, acquisition channels, or website traffic. Profit and conversion metrics cannot be established from this dataset.
- Purchase frequency describes the observed historical window, not customer lifetime behavior.

## Attribution

Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. [DOI: 10.24432/C5BW33](https://doi.org/10.24432/C5BW33). Dataset license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
