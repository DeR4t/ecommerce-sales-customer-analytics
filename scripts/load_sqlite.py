"""Load and verify the unchanged UCI workbook in a local SQLite database."""

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "Online Retail.xlsx"
DATABASE = ROOT / "database" / "retail.sqlite3"
REPORT = ROOT / "data" / "processed" / "sqlite_import_validation.json"
SOURCE_COLUMNS = [
    "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
    "UnitPrice", "CustomerID", "Country",
]
SQL_COLUMNS = [
    "source_row_number", "invoice_no", "stock_code", "description", "quantity",
    "invoice_date", "unit_price", "customer_id", "country",
]


def nullable_text(value):
    return None if pd.isna(value) else str(value)


def source_records(frame):
    """Use Excel row numbers for lineage; only represent missing cells as NULL."""
    for row_number, row in enumerate(frame.itertuples(index=False, name=None), start=2):
        invoice, stock, description, quantity, date, price, customer, country = row
        if not pd.isna(quantity) and int(quantity) != quantity:
            raise ValueError(f"Non-integral source quantity at Excel row {row_number}.")
        yield (
            row_number, nullable_text(invoice), nullable_text(stock),
            nullable_text(description), None if pd.isna(quantity) else int(quantity),
            None if pd.isna(date) else pd.Timestamp(date).isoformat(sep=" "),
            None if pd.isna(price) else float(price), nullable_text(customer),
            nullable_text(country),
        )


def records_digest(records):
    """Hash row numbers, values, types and NULLs in deterministic source order."""
    digest = sha256()
    for record in records:
        encoded = json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        digest.update(encoded.encode("utf-8") + b"\n")
    return digest.hexdigest()


def source_summary(frame):
    return {
        "row_count": len(frame),
        "first_source_row": 2,
        "last_source_row": len(frame) + 1,
        "distinct_invoice_ids": int(frame["InvoiceNo"].nunique()),
        "distinct_known_customer_ids": int(frame["CustomerID"].nunique()),
        "first_invoice_timestamp": frame["InvoiceDate"].min().isoformat(sep=" "),
        "last_invoice_timestamp": frame["InvoiceDate"].max().isoformat(sep=" "),
        "missing_customer_ids": int(frame["CustomerID"].isna().sum()),
        "missing_descriptions": int(frame["Description"].isna().sum()),
        "negative_quantity_rows": int(frame["Quantity"].lt(0).sum()),
        "zero_price_rows": int(frame["UnitPrice"].eq(0).sum()),
        "negative_price_rows": int(frame["UnitPrice"].lt(0).sum()),
        "c_prefixed_rows": int(frame["InvoiceNo"].str.upper().str.startswith("C", na=False).sum()),
    }


def validate_database(connection, expected_summary, expected_digest, source_hash):
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed.")
    columns = [row[1] for row in connection.execute("PRAGMA table_info(raw_transactions)")]
    if columns != SQL_COLUMNS:
        raise ValueError("Unexpected raw transaction schema.")
    query = (ROOT / "sql" / "02_verify_raw_import.sql").read_text(encoding="utf-8")
    cursor = connection.execute(query)
    actual_summary = dict(zip((column[0] for column in cursor.description), cursor.fetchone()))
    if actual_summary != expected_summary:
        raise ValueError(f"Source and SQLite summaries differ: {actual_summary}")
    actual_digest = records_digest(connection.execute(
        f"SELECT {', '.join(SQL_COLUMNS)} FROM raw_transactions ORDER BY source_row_number"
    ))
    if actual_digest != expected_digest:
        raise ValueError("Full-record digest differs between source and SQLite.")
    metadata = connection.execute(
        "SELECT source_file, source_sheet, source_sha256, source_row_count, "
        "source_records_sha256, loaded_at_utc, schema_version FROM ingestion_metadata "
        "WHERE ingestion_id = 1"
    ).fetchone()
    if metadata is None or metadata[:5] != (
        SOURCE.name, "Online Retail", source_hash, expected_summary["row_count"], expected_digest
    ) or metadata[6] != 1:
        raise ValueError("Ingestion metadata does not match the source.")
    return actual_summary, actual_digest, metadata[5]


def main():
    manifest = json.loads((SOURCE.parent / "source_manifest.json").read_text(encoding="utf-8"))
    source_hash = sha256(SOURCE.read_bytes()).hexdigest()
    if source_hash != manifest["sha256"]:
        raise ValueError("Workbook checksum differs from its ingestion manifest.")
    print("Loading checksum-verified source workbook...", flush=True)
    frame = pd.read_excel(
        SOURCE, sheet_name="Online Retail", engine="openpyxl",
        dtype={"InvoiceNo": "string", "StockCode": "string", "CustomerID": "string"},
    )
    if frame.columns.tolist() != SOURCE_COLUMNS or frame.shape != (541_909, 8):
        raise ValueError("Unexpected source schema or dimensions.")
    if not pd.api.types.is_datetime64_any_dtype(frame["InvoiceDate"]):
        raise ValueError("Source invoice dates were not parsed as datetimes.")
    expected_summary = source_summary(frame)
    expected_digest = records_digest(source_records(frame))
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    if DATABASE.exists():
        print("Verifying existing database; no records will be appended...", flush=True)
        with closing(sqlite3.connect(f"{DATABASE.as_uri()}?mode=ro", uri=True)) as connection:
            summary, database_digest, loaded_at = validate_database(
                connection, expected_summary, expected_digest, source_hash
            )
        status = "existing_database_verified"
    else:
        # Publish only a fully validated database; preserve any existing target.
        with tempfile.NamedTemporaryFile(dir=DATABASE.parent, prefix=".retail-", suffix=".sqlite3", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            print("Importing all source rows into a temporary SQLite database...", flush=True)
            with closing(sqlite3.connect(temporary_path)) as connection:
                connection.executescript((ROOT / "sql" / "01_raw_schema.sql").read_text(encoding="utf-8"))
                loaded_at = datetime.now(timezone.utc).isoformat()
                with connection:
                    connection.executemany(
                        f"INSERT INTO raw_transactions ({', '.join(SQL_COLUMNS)}) VALUES ({', '.join(['?'] * 9)})",
                        source_records(frame),
                    )
                    connection.execute(
                        "INSERT INTO ingestion_metadata VALUES (1, ?, ?, ?, ?, ?, ?, 1)",
                        (SOURCE.name, "Online Retail", source_hash, len(frame), expected_digest, loaded_at),
                    )
                summary, database_digest, loaded_at = validate_database(
                    connection, expected_summary, expected_digest, source_hash
                )
            if sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
                raise ValueError("Source workbook changed during ingestion.")
            if DATABASE.exists():
                raise FileExistsError("A database appeared during ingestion; refusing to replace it.")
            # On Windows rename refuses an existing destination.
            temporary_path.rename(DATABASE)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        status = "created_and_verified"

    if sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise ValueError("Source workbook changed during verification.")
    report = {
        "status": status, "database": "database/retail.sqlite3",
        "source_sha256": source_hash, "source_records_sha256": expected_digest,
        "database_records_sha256": database_digest, "loaded_at_utc": loaded_at,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "sqlite_version": sqlite3.sqlite_version, "summary": summary,
        "integrity_check": "ok", "full_record_reconciliation": "passed",
        "source_workbook_unchanged": True,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
