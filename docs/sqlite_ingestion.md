# SQLite source ingestion

## Purpose and scope

The complete original workbook is stored in `database/retail.sqlite3` as the raw source layer. Ingestion preserves all records, including missing customer IDs, cancellations, negative quantities, zero or negative prices, and repeated invoice lines. No transaction cleaning or business-metric filtering is applied.

The database and machine-generated validation JSON are local artifacts excluded from Git. Source code, schema, reconciliation SQL, and this ingestion record are versioned.

## Reproduce

After downloading the source and installing the project dependencies:

```powershell
.\.venv\Scripts\python.exe scripts\load_sqlite.py
```

The importer verifies the workbook against `data/raw/source_manifest.json`, builds a temporary database, validates it, and publishes it only after all checks pass. A subsequent run opens the existing database in read-only mode and verifies it against the source; it does not append records or replace a mismatched database.

Validation results are saved to `data/processed/sqlite_import_validation.json`. Ingestion metadata within the database records the source filename and worksheet, source checksum, record count, canonical record digest, UTC load timestamp, and schema version.

## Raw transaction schema

| Column | SQLite type | Representation |
| --- | --- | --- |
| `source_row_number` | INTEGER, primary key | Original Excel row number, starting at 2 after the header |
| `invoice_no` | TEXT | Source invoice identifier; cancellation prefixes retained |
| `stock_code` | TEXT | Source product or adjustment code |
| `description` | TEXT | Source description; missing values remain NULL |
| `quantity` | INTEGER | Original signed quantity |
| `invoice_date` | TEXT | ISO datetime representation of the original timestamp; no timezone inferred |
| `unit_price` | REAL | Original numeric unit price in GBP |
| `customer_id` | TEXT | Source customer identifier; missing values remain NULL |
| `country` | TEXT | Source country label |

Invoice IDs and invoice/product pairs are not unique line keys. `source_row_number` preserves lineage and permits identical source entries to coexist. SQLite REAL uses binary floating-point; currency aggregation and rounding rules remain part of the subsequent analytical-population definitions.

Schema: [`sql/01_raw_schema.sql`](../sql/01_raw_schema.sql). Reconciliation query: [`sql/02_verify_raw_import.sql`](../sql/02_verify_raw_import.sql).

## Source reconciliation

| Check | Workbook / SQLite result |
| --- | --- |
| Source records | 541,909 |
| Source row range | 2–541,910 |
| Distinct invoice IDs, including cancellations | 25,900 |
| Distinct known customer IDs | 4,372 |
| First timestamp | 2010-12-01 08:26:00 |
| Last timestamp | 2011-12-09 12:50:00 |
| Missing customer IDs | 135,080 |
| Missing descriptions | 1,454 |
| Negative quantities | 10,624 |
| Zero prices | 2,515 |
| Negative prices | 2 |
| C-prefixed invoice lines | 9,288 |
| SQLite integrity check | `ok` |

Beyond these summary checks, every source row is represented in a deterministic serialization containing the Excel row number and all eight source values. The SHA-256 digest of that sequence matches the SQLite rows in source order. This verifies values, NULLs, types as represented by the declared schema, row ordering, and retained repeated records.

Source and database record digest: `4bf3dc993048be11b3cf64755381fb9a9f2a31763bfd63a1e4162da50d929568`.

The original workbook checksum is checked again after ingestion to confirm source preservation. These checks establish import fidelity; they do not establish that every entry is an eligible purchase.

## Rerun verification

A second execution returned `existing_database_verified`, retained 541,909 records and the original load timestamp, and passed the same full-record comparison. The database file SHA-256 was identical before and after the rerun, confirming that the existing source layer was not modified or duplicated.
