# E-commerce Sales & Customer Analytics

A guided Python and SQL project using the UCI Online Retail dataset. We will build it one stage at a time, explaining each decision before moving on.

## Current stage: 2 — Data quality investigation

The first notebook loads the original data and inspects its structure. The second investigates missing IDs, cancellations, unusual values, duplicate-looking rows, invoice consistency, and monthly coverage. No source rows have been removed and business KPI definitions are still to be finalized.

## Roadmap

1. **Setup and first look** — environment, source download, columns, row grain, and initial checks.
2. **Data quality and cleaning** — investigate missing customer IDs, cancellations, unusual prices/quantities, and duplicate-looking rows; document decisions.
3. **SQLite and SQL** — load reviewed data, define invoice/order grain, and practice aggregations and joins.
4. **Sales analysis** — products, countries, monthly revenue, and average order value.
5. **Customer analysis** — repeat purchasing, purchase intervals, and RFM (recency, frequency, monetary value) segmentation.
6. **Business report** — supported findings, visualizations, recommendations, and limitations.

## Setup (Windows PowerShell)

Run these commands from this project folder. The environment is local to this project; no activation or PowerShell policy change is needed.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\download_data.py
.\.venv\Scripts\python.exe -m jupyterlab
```

In JupyterLab, open `notebooks/01_first_look.ipynb`. Use **Run → Run All Cells** to rerun it. The notebook uses the environment that launched JupyterLab.

Then open `notebooks/02_data_quality.ipynb`. Both notebooks are standalone: each reads and verifies the original workbook. The second lesson saves technical findings in `docs/stage_02_notes.md` and its completeness chart in `reports/figures/`.

To execute a notebook and generate a read-only HTML lesson preview from PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\02_data_quality.ipynb
```

The preview is saved as `reports/02_data_quality.html`. Generated quality-count summaries in `data/processed/` are ignored by Git; they are not cleaned transaction data. Register the kernel below before using this command in a rebuilt environment.

The first notebook also has a project-specific kernel. Register it locally if rebuilding the environment:

```powershell
.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name ecommerce-analytics --display-name "E-commerce Analytics (.venv)"
```

If Python reports a certificate error while downloading, use Windows certificate validation to download the same archive, then run the downloader again. Do not disable certificate verification.

```powershell
Invoke-WebRequest -Uri 'https://archive.ics.uci.edu/static/public/352/online+retail.zip' -OutFile 'data\raw\online_retail.zip'
.\.venv\Scripts\python.exe scripts\download_data.py
```

`requirements-lock.txt` records the exact installed versions from the verified setup. Use `-r requirements-lock.txt` instead of `-r requirements.txt` to reproduce that environment on a compatible Python/Windows installation.

## Folder guide

```text
data/raw/          Original source files; never edit in place
data/processed/    Reviewed datasets (stage 2)
database/          SQLite database (stage 3)
notebooks/         Guided notebooks
sql/               Saved SQL queries (stage 3)
reports/figures/   Exported charts (later stages)
docs/              Source notes, definitions, and decisions
scripts/           Reusable project utilities
```

## Questions we will answer

- Which products generate the most revenue?
- Which countries contribute the most sales?
- Who are the most valuable customers?
- How does revenue change by month?
- How frequently do customers purchase again?
- What is the average order value?

## Source and scope

Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5BW33>. License: CC BY 4.0.

Source page: <https://archive.ics.uci.edu/dataset/352/online+retail>.

This is historical data for a UK-based retailer, covering 1 December 2010–9 December 2011, with prices in GBP. A row is an invoice line item, not a complete order. One invoice can span multiple rows. The final month is partial, so a raw month-to-month comparison would be misleading.

The screenshot is a project brief and visual reference. Its dashboard values are not results from our dataset. Discount, acquisition-channel, age, and profit analyses require fields that this source does not provide.

See `docs/data_dictionary.md` for columns and `docs/analysis_decisions.md` for the decisions we will make together.
