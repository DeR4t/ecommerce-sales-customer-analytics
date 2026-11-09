# Project delivery plan

## Time budget

- Estimated duration: **12–15 workdays**, with **1–2 hours of project work per day**.
- Planning ceiling: **15 workdays and 30 hours**. Each stage has its own maximum allocation below.
- A workday means a day with active project work, not an automatically assigned calendar date. No dated deadline has been set.
- Completed setup and inspection work counts toward the project; the schedule does not restart those activities.
- The allocations are limits, not waiting periods. A completed milestone can close early.

## Milestones and completion criteria

The day ranges show a maximum-duration sequence. The three flexible days sit within segmentation, recommendations, and final presentation; they are not an additional allowance.

| Stage | Allocation | Maximum-duration sequence | Hour ceiling | Completion criteria |
| --- | --- | --- | --- | --- |
| 1. Setup and data understanding | 1 day | Day 1 | 2 hours | Original dataset downloaded and fingerprinted; Python and SQLite loads reconciled to the source; schema, record grain, and initial quality findings documented. |
| 2. Data cleaning | 2 days | Days 2–3 | 4 hours | Reproducible cleaning process; documented handling of missing IDs, cancellations, quantities, prices, product-code exceptions, and duplicate sensitivity; sales and identified-customer populations saved with source-row lineage and reconciliation checks. |
| 3. SQL analysis | 2 days | Days 4–5 | 4 hours | Saved SQLite queries for revenue, leading products, country performance, monthly sales, order value, and customer purchases; totals reconciled with the reviewed Python populations. |
| 4. Exploratory data analysis | 3 days | Days 6–8 | 6 hours | Focused analysis of the agreed sales and customer questions; readable figures using pandas, Matplotlib, and Seaborn; dates, units, eligible populations, and partial-month treatment disclosed. |
| 5. Customer segmentation | 2–3 days | Days 9–11 | 6 hours | RFM reference date, eligibility, and scoring rules documented; identified customers classified; segment sizes and monetary totals reconciled; a concise segment profile produced. |
| 6. Insights and recommendations | 1–2 days | Days 12–13 | 4 hours | Business findings supported by executed outputs; prioritized recommendations tied to evidence; material coverage limits and interpretation risks stated. |
| 7. Final presentation | 1–2 days | Days 14–15 | 4 hours | Notebooks execute from a clean environment; README, report, figures, queries, and setup instructions agree; repository presentation reviewed and final changes pushed. |
| **Total** | **12–15 days** | **Maximum 15 workdays** | **30 hours maximum** | Reproducible source-to-report project with professional repository outputs. |

## Scope control

The core deliverables are reproducible Python notebooks and utilities, SQLite ingestion and analytical SQL, documented cleaning and metric rules, source-backed figures, RFM customer segments, a concise business report, and a professional README.

Interactive dashboards, predictive models, elaborate data-platform architecture, custom websites, and additional analyses require a separate scope decision. Optional enhancements are deferred when they threaten the core delivery budget.

At the end of an allocation, record completed outputs, unresolved issues, and remaining work. Reduce optional scope first. Any extension beyond a stage allocation or the overall ceiling must be explicitly agreed; it is not assumed. Validation remains part of each allocation, and an unverified result is not marked complete to meet a time limit.

## Session practice

Each active work session has a defined objective and a stopping point. The daily target is one hour, with a two-hour daily ceiling unless an extension is explicitly agreed. Record only observed work time; time between messages or work completed before tracking began is not estimated retrospectively.

Completed, verified changes are committed and pushed throughout the project. Repository publication is maintained incrementally, with the final stage reserved for integration and presentation review.

## Current position

- **Stage 1 is complete:** dataset download, environment setup, Python loading, source documentation, quality inspection, and verified SQLite ingestion are finished.
- SQLite retains all 541,909 original records. Source summaries and a comparison covering every row and field passed; a repeat import verified the existing database without changing it. See [SQLite ingestion](sqlite_ingestion.md).
- **Stage 2 is complete:** the reproducible cleaning pipeline preserves all 541,909 source rows in an audit ledger and saves 527,761 eligible merchandise-purchase rows plus a 396,340-row identified-customer subset. Item-code review, exact-copy sensitivity, independent SQL reconciliation, and exact export read-back checks passed. See [transaction cleaning](data_cleaning.md).
- Follow-up verification added trimmed analytical labels/keys and a typed timestamp without changing analytical populations or values. All 15 regression tests and independent full-data checks across schema, missingness, boundaries/outliers, duplicates/keys, and business rules passed with disclosed warnings and no blocked checks.
- **Stage 3 is complete:** the separate analytical SQLite database reconciles every ledger field and reviewed population. Six saved business queries reconcile every output row and measure with pandas. The seven-cell SQL notebook executed successfully, the import was verified again without appending, and all 20 regression tests passed. See [SQL analysis](sql_analysis.md).
- The cleaning notebook executed top-to-bottom and its HTML export was generated. Visual inspection of that export remains uncompleted because the preview browser blocks local-file URLs; this presentation gap does not affect the executed data reconciliation.
- Historical effort before timed session tracking has not been measured, so no retrospective consumed-hour estimate is asserted.

The next implementation milestone is Stage 4: focused exploratory data analysis and figures. Stage 1 closed on 6 November 2026; Stage 2 closed on 7 November 2026; Stage 3 closed on 9 November 2026 within its allocation. Stage 4 has not started.
