# Source data dictionary

Source: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33).

| Column | Meaning | Analytical considerations |
| --- | --- | --- |
| InvoiceNo | Invoice identifier; a leading C indicates a cancellation | Store as text; an invoice contains multiple rows |
| StockCode | Product/item identifier | Store as text; investigate service and adjustment codes |
| Description | Item description | Check missing values and different descriptions for the same code |
| Quantity | Units on this invoice line | Investigate negative and zero values |
| InvoiceDate | Invoice date and time | Use a datetime; source timezone is unspecified |
| UnitPrice | Price per unit in pounds sterling (GBP) | Investigate zero and negative values |
| CustomerID | Customer identifier | Store as text; check missing values before customer analysis |
| Country | Customer's country | Does not establish delivery location or nationality |

The dataset contains 541,909 invoice line items and eight columns. UCI's feature count excludes ID columns. Inspect the downloaded workbook directly for missingness even where the source metadata says no missing values.

Do not infer cost, profit, discount amounts, demographics, acquisition channel, or website conversion rates: these fields are unavailable.

SQLite preserves these source fields in `raw_transactions` using snake_case names, with `source_row_number` added for Excel-row lineage. See [SQLite ingestion](sqlite_ingestion.md) for types, NULL handling, and reconciliation results.
