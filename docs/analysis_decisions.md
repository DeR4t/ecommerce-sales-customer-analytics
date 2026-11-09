# Analytical methodology

## Source and record grain

- The original workbook is immutable; ingestion records its SHA-256 checksum.
- Each source row is an invoice line item. Invoice IDs are candidate order identifiers, not unique line keys.
- Invoice, product, and customer identifiers are stored as text.
- Monetary values use GBP; no currency conversion is applied.
- Source timestamps have no documented timezone.

## Quality assessment

- Profiling retains all original rows, including anonymous entries, cancellations, and adjustments.
- Quality flags overlap; their counts must not be added as mutually exclusive defects.
- Exact copies beyond the first occurrence are distinguished from all members of duplicate groups. Equality alone does not establish a source error.
- Whitespace/case normalization is evaluated on a temporary copy without altering source strings.
- Item-code format exceptions and numeric extremes are review candidates, not automatic exclusions.
- Invoice-level customer, country, and timestamp consistency is checked before defining relational constraints.
- Monthly missing-customer shares retain their raw row denominators. December 2011 is labeled partial.

Evidence: [data quality notebook](../notebooks/02_data_quality.ipynb) and [quality findings](data_quality.md).

## Reviewed purchase populations

- Merchandise purchases require positive quantity and price, a reviewed merchandise code, and no cancellation prefix. Retain otherwise eligible anonymous purchases in sales; identified purchases form a separate customer population.
- Retain exact copies in the baseline; publish a sensitivity excluding copies beyond the first. Preserve cancellations, nonpositive values, non-merchandise, and unresolved manual entries in the complete ledger.
- Store monetary calculations in integer thousandths of GBP to retain the observed £0.001 price precision. Gross purchase value excludes credits and is not net revenue or profit. Signed all-source value includes adjustments and is not net merchandise revenue.
- Eligible orders are distinct invoice IDs containing eligible purchase lines. Gross merchandise average order value divides purchase value by that order count. Use the earliest eligible line timestamp per invoice for later invoice-level date aggregation.
- Keep source strings unchanged; derive trimmed identifiers and labels, an uppercase item-code key for classification, and a typed analytical timestamp. Preserve unusual merchandise codes and numeric extremes. Required fields and supported types must pass validation; optional missing customer IDs and descriptions remain missing.

Rules, classification assumptions, reconciliation results, and duplicate sensitivity: [transaction cleaning](data_cleaning.md). The reproducible outputs retain source-row lineage.

## Decisions deferred to later stages

- Credit matching or a refund-adjusted metric requires a separate documented method; none is assumed.
- Define the RFM reference date and scoring rules during segmentation.

## SQL baseline definitions

The [SQL analysis](sql_analysis.md) applies the reviewed populations in a separate analytical SQLite database. Monthly totals use earliest eligible invoice timestamps, product labels use one latest eligible description per item code, and full-month growth is suppressed for partial December 2011 or non-adjacent periods. Observed repeat-purchase share uses identified customers with at least two eligible invoices divided by all identified customers with purchases; this is not a retention measure. RFM reference date and scoring remain deferred.

## Interpretation

December 2011 requires exclusion from full-month comparisons or a matching-window comparison. Customer purchase frequency describes only observed activity within the source window. All source rows remain in the raw table and cleaning ledger; analytical populations filter eligibility without deleting source records. Business KPI analyses remain for the next stages.
