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

## Derived cleaning fields

The cleaning ledger and its purchase subsets retain all source fields and add:

| Field | Type and meaning |
| --- | --- |
| `invoice_timestamp` | Timezone-naive datetime parsed from the original invoice date text; source timezone is unknown |
| `invoice_no_key`, `customer_id_key` | Trimmed text identifiers; a blank optional customer identifier becomes missing |
| `stock_code_key` | Trimmed uppercase item code used for reviewed classification |
| `description_clean`, `country_clean` | Trimmed text labels; missing descriptions remain missing |
| `item_class` | Reviewed merchandise, non-merchandise, or unresolved classification |
| `is_cancellation`, `has_customer_id` | Boolean indicators derived from normalized identifiers |
| `is_exact_copy_beyond_first` | Boolean equality flag over all eight original source fields, retaining the first source row |
| `unit_price_millipounds`, `line_value_millipounds` | Signed 64-bit integer monetary values in thousandths of GBP |
| `row_status` | Exclusive status assigned using documented exclusion precedence |
| `is_sales_eligible`, `is_customer_eligible` | Boolean purchase and identified-customer eligibility flags |

Use the cleaning module's `read_export` loader to restore text identifiers, missing values, and the analytical timestamp type from compressed CSV. See [transaction cleaning](data_cleaning.md) for eligibility and monetary definitions.
