# Analysis decisions

## Established at setup

- Preserve the raw workbook and record its SHA-256 checksum in `data/raw/source_manifest.json`.
- Treat rows as invoice line items, invoices as candidate orders, and customer IDs as identifiers.
- Use GBP throughout; no currency conversion is needed.
- Keep identifiers as strings when loading into pandas.
- Use the observed data window for analysis. December 2011 is partial; label or exclude it from full-month comparisons.
- Customer purchase frequency describes observed purchases in this window, not lifetime behavior or future retention.

## To decide in stage 2 after inspecting the data

- How to separate purchases, cancellations/credits, and other adjustments.
- Whether duplicate-looking rows represent data duplication or repeated line items; do not delete them automatically.
- How to retain anonymous sales for revenue analysis while restricting customer analysis to identified customers.
- How to handle zero/negative prices, unusual quantities, and non-merchandise codes.
- Definitions for gross purchase revenue, cancellation/credit value, and net recorded revenue. Do not call credit notes confirmed physical returns without evidence.
- Which eligible invoices enter average order value.
- Exact customer population, RFM reference date, scoring rules, and repeat-purchase denominator.

No cleaning rules or business KPI results have been finalized in stage 1.
