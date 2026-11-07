# Data quality findings

Source: Chen, D. (2015), [UCI Online Retail](https://doi.org/10.24432/C5BW33), CC BY 4.0. Workbook: `data/raw/Online Retail.xlsx`, sheet `Online Retail`. SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.

Scope: 541,909 original invoice line items, eight columns, 01 December 2010–09 December 2011. Prices are GBP. No source rows were deleted or changed. Evidence and code: `notebooks/02_data_quality.ipynb`.

| Observation | Risk and proposed treatment | Priority / evidence confidence |
| --- | --- | --- |
| 135,080 missing customer IDs (24.93% of all raw rows); 3,710 raw invoice groups have no known customer | High risk for customer history. Retain otherwise eligible anonymous sales for sales analysis; use known IDs for customer analysis and disclose coverage. Never group all missing IDs into one customer. Cause is not established. | High / high for counts |
| 9,288 C-prefixed rows; 10,624 negative-quantity rows, including 1,336 without a C prefix | Separate cancellation/credit entries from purchases and other adjustments. A negative quantity alone does not establish a physical return. | High / high for counts; business causes unresolved |
| 2,515 zero-price rows and 2 negative-price rows | Review descriptions and item codes before setting purchase eligibility. Do not silently include adjustments in average order value. | High / high for counts |
| 5,268 exact copies beyond the first (0.97%); 10,147 total rows in exact duplicate groups | Deletion could remove legitimate repeated lines; retention could overstate value if they are duplicated records. Preserve them pending an explicit baseline and sensitivity comparison. No true line identifier is supplied. | Medium / high for equality, unresolved for cause |
| 5,268 copies beyond first after whitespace/case normalization | Cosmetic normalization is not sufficient evidence that a row is duplicated. Raw strings remain unchanged. | Medium / high |
| Invoice IDs with multiple known customers: 0; multiple countries: 0; multiple timestamps: 43 | Review these groups before imposing one-to-one invoice dimension rules in SQLite. Do not infer that an invoice uniquely identifies a customer or timestamp without a rule. | Medium / high for counts |
| Item-code heuristic flags 2,995 rows | Review candidate service/adjustment codes before calling the product ranking merchandise revenue. Format alone is not an invalidity rule. | Medium / high for flag, unresolved for classification |
| December 2011 ends on 09 December, not month end | Mark this month partial. Exclude it from full-month comparisons or compare matching date windows. | High / high |

## Temporal and coverage notes

The chart and monthly table show missing-customer shares together with raw row denominators. Variation does not establish an ingestion failure or its cause. This is a static historical extract, so a modern freshness SLA does not apply. Missing IDs constrain observable customer coverage; date gaps may reflect trading patterns. There is no documented ingestion timestamp or timezone.

## Checks completed

Source checksum and expected schema/shape; nulls and blank text; overlapping review flags; cancellation-by-quantity cross-tab; exact and normalized duplicate comparisons; numeric quantiles and extreme samples; item-code review candidates; invoice consistency; monthly completeness and volume; count reconciliations and independent Python recounts for missing customer IDs and C prefixes; unchanged source/DataFrame checks.

## Recommended analytical treatment

1. Define positive purchase lines, cancellation/credit entries, and other adjustments, retaining source row lineage.
2. Keep anonymous eligible purchases for overall sales; restrict customer history to known IDs.
3. Decide a duplicate baseline and calculate a with/without-exact-copy sensitivity, rather than asserting an unproven source error.
4. Review the item-code candidates before defining merchandise rankings.
5. Record order eligibility, average order value, and revenue definitions before aggregation. Net recorded line value is not profit.

This assessment itself does not change any rows. Stage 2 subsequently implemented the reviewed rules and saved lineage-preserving populations; see [transaction cleaning](data_cleaning.md) for the applied decisions, counts, and limitations. The original observations above remain the pre-cleaning baseline.
