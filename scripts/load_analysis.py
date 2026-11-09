"""Load verified cleaning outputs into a separate, fully reconciled SQLite database."""

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile

import pandas as pd

from clean_transactions import read_export, require
from load_sqlite import ROOT, SOURCE, records_digest
from validate_cleaning import BOOLEANS, EXPECTED_COLUMNS

ANALYSIS_DB = ROOT / "database" / "retail_analysis.sqlite3"
SCHEMA = ROOT / "sql" / "04_analysis_schema.sql"


def sql_records(frame):
    """Canonical SQL representation: NULL, 0/1 booleans, and ISO timestamps."""
    for row in frame.itertuples(index=False, name=None):
        yield tuple(None if pd.isna(value) else int(value) if column in BOOLEANS
                    else value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, pd.Timestamp)
                    else value for column, value in zip(EXPECTED_COLUMNS, row))


def validate_invoice_dimensions(connection):
    conflicts = connection.execute(
        "SELECT invoice_no_key FROM sales_transactions GROUP BY invoice_no_key "
        "HAVING COUNT(DISTINCT country_clean) != 1 OR COUNT(DISTINCT customer_id_key) > 1 "
        "OR (COUNT(customer_id_key) > 0 AND COUNT(customer_id_key) < COUNT(*)) LIMIT 1"
    ).fetchone()
    require(conflicts is None, f"An invoice has conflicting customer/country dimensions: {conflicts}")


def validate_database(connection, provenance, expected_digest):
    require(connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "Analysis DB integrity failed.")
    columns = [row[1] for row in connection.execute("PRAGMA table_info(transaction_ledger)")]
    require(columns == EXPECTED_COLUMNS, "Unexpected analytical ledger schema.")
    metadata = connection.execute(
        "SELECT provenance_json, ledger_records_sha256, loaded_at_utc FROM analysis_metadata WHERE metadata_id = 1"
    ).fetchone()
    require(metadata is not None and json.loads(metadata[0]) == provenance and metadata[1] == expected_digest,
            "Analysis DB provenance differs from current cleaning inputs; preserve it and rebuild separately.")
    actual_digest = records_digest(connection.execute(
        f"SELECT {', '.join(EXPECTED_COLUMNS)} FROM transaction_ledger ORDER BY source_row_number"))
    require(actual_digest == expected_digest, "Full SQL ledger values differ from verified cleaning export.")
    validate_invoice_dimensions(connection)
    for table, population in [("transaction_ledger", "all_recorded_lines"),
                              ("sales_transactions", "merchandise_purchases"),
                              ("customer_transactions", "identified_customer_purchases")]:
        counts = connection.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT invoice_no_key), COUNT(DISTINCT customer_id_key), "
            f"SUM(quantity), SUM(line_value_millipounds) FROM {table}"
        ).fetchone()
        expected = provenance["populations"][population]
        require(counts == tuple(expected[key] for key in ["rows", "invoice_ids", "known_customer_ids",
                                                          "quantity", "line_value_millipounds"]),
                f"SQL population does not reconcile: {table}")
    return metadata[2]


def main():
    summary = json.loads((ROOT / "reports" / "03_cleaning_summary.json").read_text(encoding="utf-8"))
    qa = json.loads((ROOT / "data" / "processed" / "cleaning_qa_results.json").read_text(encoding="utf-8"))
    require(qa["hard_failure_groups"] == 0 and not qa["blocked_checks"], "Cleaning QA has failures or incomplete checks.")
    require(qa["export_sha256"] == summary["export_sha256"] and
            qa["raw_records_sha256"] == summary["raw_records_sha256"], "Cleaning QA is stale; rerun validate_cleaning.py.")
    for name, expected_hash in summary["export_sha256"].items():
        require(sha256((ROOT / "data" / "processed" / name).read_bytes()).hexdigest() == expected_hash,
                f"Cleaning export changed: {name}")
    require(sha256(SOURCE.read_bytes()).hexdigest() == summary["source_sha256"], "Original workbook changed.")
    require(sha256((ROOT / "docs" / "item_code_classification.csv").read_bytes()).hexdigest() ==
            summary["classification_sha256"], "Item-code classification changed; rerun cleaning/QA.")
    ledger = read_export(ROOT / "data" / "processed" / "transaction_ledger.csv.gz")
    require(ledger.columns.tolist() == EXPECTED_COLUMNS and ledger.source_row_number.is_monotonic_increasing,
            "Unexpected cleaning export schema or order.")
    expected_digest = records_digest(sql_records(ledger))
    provenance = {key: summary[key] for key in ["rules_version", "source_sha256", "raw_records_sha256",
        "classification_sha256", "export_sha256", "populations"]}
    provenance["schema_sha256"] = sha256(SCHEMA.read_bytes()).hexdigest()
    ANALYSIS_DB.parent.mkdir(parents=True, exist_ok=True)
    if ANALYSIS_DB.exists():
        with closing(sqlite3.connect(f"{ANALYSIS_DB.as_uri()}?mode=ro", uri=True)) as connection:
            loaded_at = validate_database(connection, provenance, expected_digest)
        status = "existing_database_verified"
    else:
        with tempfile.NamedTemporaryFile(dir=ANALYSIS_DB.parent, prefix=".analysis-", suffix=".sqlite3", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with closing(sqlite3.connect(temporary)) as connection:
                connection.executescript(SCHEMA.read_text(encoding="utf-8"))
                loaded_at = datetime.now(timezone.utc).isoformat()
                with connection:
                    connection.executemany(
                        f"INSERT INTO transaction_ledger VALUES ({','.join('?' for _ in EXPECTED_COLUMNS)})",
                        sql_records(ledger))
                    connection.execute("INSERT INTO analysis_metadata VALUES (1, ?, ?, ?)",
                        (json.dumps(provenance, sort_keys=True), expected_digest, loaded_at))
                validate_database(connection, provenance, expected_digest)
            temporary.rename(ANALYSIS_DB)
        finally:
            if temporary.exists():
                temporary.unlink()
        status = "created_and_verified"
    report = {"status": status, "database": "database/retail_analysis.sqlite3", "loaded_at_utc": loaded_at,
              "ledger_records_sha256": expected_digest, "full_record_reconciliation": "passed",
              "invoice_dimensions": "passed", "provenance": provenance}
    (ROOT / "data" / "processed" / "analysis_import_validation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{status}: {len(ledger):,} ledger rows; every field and all purchase populations reconciled.")
    return report


if __name__ == "__main__":
    main()
