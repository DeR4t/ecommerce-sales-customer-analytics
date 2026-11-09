# SQL analysis baseline

## Population and database

Stage 3 uses the verified Stage 2 merchandise-purchase population. Gross merchandise purchase value is measured **before credits**, with anonymous purchases included and exact source copies retained. Customer analysis uses identified purchases only. No source rows, cleaning rules, or monetary totals are changed.

`scripts/load_analysis.py` loads all 541,909 cleaning-ledger records into the separate, untracked `database/retail_analysis.sqlite3`. The original `database/retail.sqlite3` remains unchanged. The loader verifies current source/classification/export fingerprints against the successful full-data QA receipt, then checks every stored ledger field with a deterministic record digest. It checks counts, distinct invoices/customers, units, and integer monetary totals for all three populations. SQLite integrity and invoice-dimension checks must pass before publication. Repeated imports verify the existing database without appending rows; a provenance mismatch stops rather than replacing an existing database.

The analytical schema uses SQLite STRICT tables, requiring SQLite 3.37 or newer. The verified project Python environment provides SQLite 3.50.4. Boolean flags are constrained integers 0/1, timestamps are canonical ISO text, identifiers are text, and monetary values are signed integer thousandths of GBP. SQLite itself has no native timestamp type; `invoice_timestamp` retains its typed datetime representation in Python.

| SQL object | Grain and eligibility |
| --- | --- |
| `transaction_ledger` | Every original source line, its normalized fields, classification, flags, and Excel-row lineage |
| `sales_transactions` | View restricted to eligible positive merchandise purchases |
| `customer_transactions` | View restricted to eligible purchases with known customer IDs |
| `purchase_orders` | One row per eligible invoice, summing every eligible line and using the earliest eligible timestamp |

Before using one country/customer per invoice, the loader rejects invoices with conflicting country labels, multiple known customer IDs, or a mixture of known and missing customer IDs. A repeated invoice ID is expected at line grain and is not a duplicate primary key.

## Saved queries and definitions

| File | Analytical result |
| --- | --- |
| `sql/04_analysis_schema.sql` | Analytical tables, constraints, indexes, and views |
| `sql/05_sales_summary.sql` | Purchase lines, distinct orders/customers, units, exact gross value, identified/anonymous value, and gross average order value |
| `sql/06_product_performance.sql` | All item codes ranked by gross value, with line/order counts and units |
| `sql/07_country_performance.sql` | Customer-country value, orders, units, identified customers, share, and order value |
| `sql/08_monthly_sales.sql` | Order-month totals, partial-month flag, average order value, and eligible month-on-month growth |
| `sql/09_order_value.sql` | All eligible invoice totals with order timestamp, country, and nullable customer ID |
| `sql/10_customer_purchases.sql` | All identified customers with purchase counts, units, gross value, first/last purchase, and average order value |

Gross average order value is total eligible purchase value divided by distinct eligible invoices, converted to GBP. It is not a mean of line values or an unweighted average of monthly/country averages.

Product identity is the normalized stock code. Descriptions are display labels: select the latest non-missing eligible description by timestamp, breaking ties by highest source-row number. That single label joins once to each product aggregate, preventing value multiplication from description variants. The label does not imply that all historical lines had that exact description. Distinct product-level order counts overlap and must not be summed into the overall order count.

Country labels are taken from the source customer country and do not establish shipping destinations. Invoice counts and values partition by country after dimension checks. Distinct customer counts across countries are not guaranteed additive.

Monthly attribution follows the earliest eligible timestamp for each invoice. Every eligible line in that invoice belongs to that order month, even if another line has a later timestamp. December 2011 is partial through 9 December: preserve its observed value and suppress full-month growth. The first observed month and comparisons across a missing month also have NULL growth. Other observed months cover the full calendar period in the extract; this does not establish that unobserved source events never occurred.

Repeat-purchase share is identified customers with at least two distinct eligible invoices divided by all identified customers with at least one eligible purchase. It describes the observed extract window, not retention, lifetime behavior, or refund-adjusted customer value. RFM scoring remains for Stage 5.

## Executed baseline findings

Source period: 1 December 2010–9 December 2011. Currency: GBP. Original source: Chen, D. (2015), [UCI Online Retail](https://doi.org/10.24432/C5BW33), CC BY 4.0.

| Measure | Verified result |
| --- | ---: |
| Eligible purchase lines | 527,761 |
| Eligible purchase invoices | 19,773 |
| Gross purchase value before credits (GBP) | 10,271,433.063 |
| Gross average order value (GBP, displayed to pennies) | 519.47 |
| Identified customers | 4,334 |
| Customers with one eligible invoice | 1,505 |
| Customers with at least two eligible invoices | 2,829 |
| Observed repeat-purchase share | 65.27% |

- The United Kingdom contributes 85.16% of gross merchandise purchase value. The Netherlands and source label EIRE follow at 2.76% and 2.64%.
- Item 22423, latest label **REGENCY CAKESTAND 3 TIER**, leads gross product value at GBP 174,484.740 across 1,988 eligible invoices.
- Item 23843 ranks second at GBP 168,469.600 from **one** eligible invoice and 80,995 units. Separate credit entries exist in the source ledger. The gross ranking alone does not establish broad customer demand or retained spending.
- November 2011 is the highest complete month by gross value, GBP 1,457,745.530. December 2011 is partial and is not ranked as a comparable full month.

These are descriptive SQL baseline findings. Distribution analysis, visual comparisons, seasonality interpretation, and business recommendations remain for later stages.

## Reconciliation and reproduction

From the prepared project environment, after raw ingestion and cleaning:

```powershell
.\.venv\Scripts\python.exe scripts\validate_cleaning.py
.\.venv\Scripts\python.exe scripts\run_sql_analysis.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\04_sql_analysis.ipynb
```

The analysis runner verifies or creates its database automatically. The notebook invokes the same runner, so either entry point can reproduce the saved outputs. An existing successful cleaning-QA receipt is required; rerun `validate_cleaning.py` when source/export fingerprints change.

The runner independently rebuilds invoice, product, country, month, and customer aggregates in pandas. It compares every returned row and measure for all six queries, checks exact additive integer-value totals, and reconciles customer values to the identified population. Ratio differences must be below 1e-9. It checks product labels/ranks, NULL growth rules, country shares, first/last purchase timestamps, and average order values. Dedicated synthetic tests cover cross-month invoices, anonymous purchases, retained exact copies, cancellation/service exclusion, product-label joins, missing-month comparisons, partial December, and conflicting invoice dimensions.

Complete query results, including invoice/customer-level outputs, are written only to the ignored `data/processed/sql_analysis/` folder. The tracked `reports/04_sql_summary.json` contains bounded product/country leaders, monthly aggregates, customer-population summaries, query fingerprints, and reconciliation status. Query fingerprints tie the summary to the exact SQL used. The executed notebook is `notebooks/04_sql_analysis.ipynb`, with its standard HTML export under `reports/`.

Verification on 9 November 2026: all six full-data query reconciliations and all 20 regression tests passed. A second import verified the existing database without appending records; the seven-cell notebook executed top-to-bottom. Saved outputs were checked for expected tables, values, source labels, and absent execution errors. Visual layout inspection of the HTML export was not performed at this checkpoint; no new figures are part of the SQL stage.
