# Transaction cleaning and analytical populations

## Scope and source

The cleaning process reads the verified `raw_transactions` table in `database/retail.sqlite3` without modifying it. The [UCI Online Retail](https://doi.org/10.24432/C5BW33) workbook contains 541,909 invoice line items from 1 December 2010 to 9 December 2011. The workbook fingerprint, raw-record digest, and ingestion metadata must agree before outputs are produced.

Implementation: `scripts/clean_transactions.py`. Executed evidence: [cleaning notebook](../notebooks/03_data_cleaning.ipynb) and [machine-readable summary](../reports/03_cleaning_summary.json). The source fields remain unchanged; `source_row_number` identifies the original Excel row, including the header offset.

## Eligibility rules

| Rule | Treatment and rationale |
| --- | --- |
| Cancellation prefix | Invoice IDs beginning with C, ignoring case and surrounding whitespace, are excluded from purchases and retained in the ledger. A cancellation flag does not establish a physical return or match a particular original purchase. |
| Quantity | Purchase lines require quantity greater than zero. Negative quantities without a C prefix remain separate adjustments. No arbitrary upper cutoff is applied. |
| Price | Purchase lines require a price greater than zero. Zero-price records are not assumed to be mistakes or imputed. Negative prices remain adjustments. |
| Item code | Conventional five-digit codes with optional letter suffixes are treated as merchandise. Exceptions are reviewed by source description in the [classification registry](item_code_classification.csv). Postage, carriage, fees, discounts, samples, bad-debt entries, and vouchers are excluded; ambiguous manual entries are unresolved and excluded. New unreviewed codes halt the process. |
| Customer ID | Otherwise eligible anonymous purchases remain in sales; only identified purchases enter customer analysis. Missing IDs are never imputed or combined into one customer. |
| Exact copies | Retain all source rows in the baseline. Mark copies beyond the first across all eight source fields, ordered by Excel row, and calculate a separate sensitivity excluding them. No source line key exists to establish whether repeated lines are errors. |
| Missing descriptions | Preserve missingness without inferring a description. Eligibility is based on the reviewed item code, quantity, price, and cancellation rules. Descriptions are labels, not product identifiers. |
| Numeric extremes | Preserve observed values. Large purchases may have associated credits; gross purchases do not represent retained customer spending. No unsupported cancellation matching or outlier trimming is performed. |

`stock_code_key` is a derived uppercase, trimmed key; original item codes and descriptions are preserved. Two-letter suffixes such as `15056BL` remain merchandise. Descriptive `DCGS` codes include real merchandise and are reviewed individually. The classification is an analytical assumption based on source descriptions, not an independently verified product catalog.

### Typed analytical fields

The original source columns remain unchanged. Derived `invoice_no_key`, `customer_id_key`, `country_clean`, and `description_clean` fields strip surrounding whitespace; empty optional labels and IDs become missing values rather than invented replacements. `stock_code_key` also converts letter case to uppercase. The source contains 113,452 descriptions with surrounding whitespace, so `description_clean` provides consistent display labels while preserving the original evidence.

`invoice_timestamp` is a timezone-naive `datetime64[ns]` analytical field parsed from the original ISO date text. The export loader restores its datetime type. Source dates must parse and fall within the documented extract dates, 1 December 2010 through 9 December 2011. Schema validation rejects incorrect source types, non-finite numeric values, fractional quantities, and invalid Excel-row lineage. Export read-back verification compares both values and dtypes.

## Exclusive status and overlapping flags

For a count bridge, assign the first applicable status in this order: cancellation, nonpositive quantity, nonpositive price, non-merchandise, unresolved item, eligible purchase. This precedence prevents double counting; the status does not enumerate every issue on the row. Original fields and independent flags preserve overlapping conditions.

| Status | Source rows |
| --- | ---: |
| Eligible purchase | 527,761 |
| Cancellation | 9,288 |
| Non-merchandise | 2,021 |
| Nonpositive quantity, after cancellation exclusion | 1,336 |
| Nonpositive price, after preceding exclusions | 1,181 |
| Unresolved item, after preceding exclusions | 322 |
| **Total** | **541,909** |

The 2,021 non-merchandise status rows differ from the 2,374 rows classified as non-merchandise: some of the latter are assigned a higher-priority cancellation, quantity, or price status. Likewise, 581 rows have unresolved item classifications, but only 322 reach that exclusive status.

## Saved populations

All three files are gzip-compressed CSVs under `data/processed/`, excluded from Git. Identifiers must be loaded as text; use `read_export` from the cleaning module to preserve types and missing values.

| Output | Rows | Contents |
| --- | ---: | --- |
| `transaction_ledger.csv.gz` | 541,909 | Every source row, original fields, derived key, item class, eligibility flags, exact-copy flag, status, and integer monetary values |
| `sales_transactions.csv.gz` | 527,761 | Positive-price, positive-quantity merchandise purchases without cancellation prefixes; anonymous lines included |
| `customer_transactions.csv.gz` | 396,340 | The sales subset with known customer IDs; 4,334 distinct identified customers |

Anonymous purchases account for 131,421 sales rows. Sales contain 19,773 distinct eligible invoice IDs; the identified-customer population contains 18,402. These are population counts, not a finalized monthly KPI readout.

## Monetary and order definitions

- Preserve source price precision using integer **millipounds**: `unit_price_millipounds = UnitPrice × 1,000`; `line_value_millipounds = Quantity × unit_price_millipounds`. Source prices have up to three decimal places, including £0.001. New unsupported precision fails instead of being rounded. Sum integers and divide by 1,000 for GBP presentation; round only at display time.
- Gross merchandise purchase value is the sum over eligible sales lines, before credits: **£10,271,433.063**. Identified purchases contribute £8,761,066.653 and anonymous purchases £1,510,366.410. These values reconcile exactly in integer units.
- Signed value over **all raw lines** is £9,747,747.934. It includes fees, bad-debt entries, and ambiguous adjustments, so it is not labeled net merchandise revenue or profit.
- Merchandise credits can be studied separately using the ledger, but they have not been matched to original purchases. No refund-adjusted customer measure is claimed.
- An eligible purchase invoice contains at least one eligible merchandise line. Gross merchandise average order value uses eligible purchase value divided by distinct eligible invoice IDs. Do not use line count as order count.
- For later invoice-date aggregation, use the earliest eligible line timestamp for each invoice and disclose that rule: the raw source contains 43 invoice groups with multiple timestamps. Do not impose a unique timestamp constraint on invoice IDs.

## Duplicate sensitivity

| Population | Baseline rows | Rows without exact copies | Value reduction (GBP) |
| --- | ---: | ---: | ---: |
| Merchandise purchases | 527,761 | 522,540 | 24,213.740 |
| Identified-customer purchases | 396,340 | 391,153 | 23,839.010 |

The merchandise value reduction is approximately 0.236% of the retained-row baseline. Neither scenario proves the true transaction count. Report baseline retention and revisit sensitivity where conclusions depend on small differences.

## Verification and reproduction

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\clean_transactions.py
.\.venv\Scripts\python.exe scripts\validate_cleaning.py
.\.venv\Scripts\python.exe scripts\run_notebook.py notebooks\03_data_cleaning.ipynb
```

The notebook also runs the pipeline, so the standalone cleaning command is optional when running the notebook. Prerequisites are the verified workbook and SQLite ingestion described in the README.

`scripts/validate_cleaning.py` independently recomputes expected results from the raw SQLite records and classification registry, then checks every row of all three saved populations in five categories: schema/types, nulls/empty values, numeric/date boundaries and outliers, duplicates/keys, and business rules. It verifies source/export fingerprints, normalized fields, source lineage, population membership, flags, and exact integer monetary values without calling the cleaning classifier. Mutation tests deliberately corrupt representative inputs to verify that the checks detect errors. A schema-blocked check is recorded as incomplete rather than passed.

Validation results and full per-column missingness profiles are saved locally in `data/processed/cleaning_qa_results.json`. Row-level findings are saved in `data/processed/cleaning_qa_anomalies.csv.gz`, including source Excel row, invoice, item, field, value, reason, and severity. These files remain excluded from Git. Warnings can overlap on the same source row; their counts must not be summed as distinct records. Optional source nulls, retained exact copies, and positive purchase extremes are disclosed review conditions rather than automatic evidence of invalid purchases. High purchase quantities and prices are flagged using the upper outer Tukey fence, Q3 + 3 × IQR, calculated separately for each field over eligible purchases; flags do not trigger deletion.

Checks cover source fingerprint and raw-record digest, SQLite integrity, immutable raw columns, unique lineage, required fields, date parsing, supported price precision, item-code coverage, membership boundary cases, count and monetary reconciliation by status using independent SQL, customer/anonymous reconciliation, and an exact read-back comparison of every exported field. A repeated run checks deterministic export hashes. Exports are validated in a temporary directory before replacement; the summary is published last and its hashes identify the completed file set. Consumers should verify those hashes if a run is interrupted during publication.

Initial verification on 7 November 2026: three focused tests passed; the six-cell notebook executed top-to-bottom; all three export hashes matched the earlier full run. The HTML export was generated and checked structurally for expected content and saved table outputs. **Visual layout inspection remains uncompleted:** the preview browser rejects local-file URLs. No visual acceptance is claimed.

### Follow-up quality verification

Follow-up verification on 7 November 2026 added typed analytical fields, strict dtype reconciliation, input guards, and independent full-data QA. All 15 regression test methods passed, including deliberately corrupted schema, nulls, dates, numeric boundaries, primary keys, monetary values, and population membership. All original source columns, population counts, status counts, purchase values, and duplicate sensitivity results remained unchanged.

The independent audit compared every field in the ledger, sales, and customer exports against expectations derived directly from all 541,909 raw records. Source and export fingerprints matched. There were **zero hard failures and zero blocked checks**.

| Check | Final result |
| --- | --- |
| Exact 24-column schema and types | Passed |
| Null and empty values | Passed with optional-source missingness warnings; no missing required fields |
| Numeric/date boundaries and outliers | Passed with disclosed source adjustments and positive-extreme review flags; no invalid purchase boundaries or dates |
| Duplicate rows and keys | Passed with retained exact-copy warnings; no duplicate source-row primary keys |
| Business rules and source reconciliation | Passed for normalized fields, eligibility, flags, memberships, original fields, and exact monetary values |

The ledger retains 135,080 missing customer IDs and 1,454 missing descriptions. Sales retain 131,421 anonymous purchase lines (24.90% of eligible purchase rows); the customer dataset contains no missing values. The source's 113,452 whitespace-affected descriptions are preserved with trimmed analytical labels. Exact copies remain under the baseline policy.

The outlier review flagged 19,320 eligible quantities above 41 and 10,143 eligible unit prices above GBP 12.77 using the documented outer-fence method. These are review flags, not verified errors, and no rows were removed on this basis. The anomaly log contains 307,727 overlapping warning records across 250,138 distinct source rows; those totals must not be interpreted as defective-record counts.

The final datasets are suitable for the defined gross-merchandise-purchase analysis with disclosed coverage and sensitivity limitations. This verification does not establish refund-adjusted customer spending or accounting revenue.

## Remaining limits

Missing customer IDs constrain customer coverage. Item classification depends on descriptions, duplicate origin is unknown, and credits are not matched to purchases. Customer analysis will describe gross observed purchasing unless a different measure is explicitly introduced. December 2011 is partial. RFM reference date, scoring, and segmentation rules remain for Stage 5. Business SQL queries and database publication of the cleaned populations belong to Stage 3.
