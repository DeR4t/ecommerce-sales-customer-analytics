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

## Population and metric definitions pending review

- Separate positive purchase lines, cancellation/credit entries, and other adjustments. A negative quantity alone does not prove a physical return.
- Preserve otherwise eligible anonymous purchases for overall sales; restrict customer-history calculations to known customer IDs and disclose coverage.
- Choose and document a duplicate baseline with a sensitivity comparison before removing exact copies.
- Review non-merchandise and adjustment codes before defining product rankings.
- Define gross purchase value, credit value, net recorded revenue, and eligible purchase invoices before computing average order value. Recorded revenue is not profit.
- Define the RFM reference date, customer population, scoring rules, and repeat-purchase denominator.

## Interpretation

December 2011 requires exclusion from full-month comparisons or a matching-window comparison. Customer purchase frequency describes only observed activity within the source window. No transaction rows have been removed and no business KPI has yet been finalized.
