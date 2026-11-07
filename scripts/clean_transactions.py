"""Create lineage-preserving purchase populations from verified raw SQLite rows."""

from contextlib import closing
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
import tempfile

import pandas as pd

from load_sqlite import DATABASE, ROOT, SOURCE, SQL_COLUMNS, records_digest

OUTPUT = ROOT / "data" / "processed"
CLASSIFICATIONS = ROOT / "docs" / "item_code_classification.csv"
TEXT_COLUMNS = ["invoice_no", "stock_code", "description", "invoice_date", "customer_id", "country"]
CLEAN_TEXT_COLUMNS = ["invoice_no_key", "stock_code_key", "description_clean", "customer_id_key", "country_clean"]
SOURCE_START = pd.Timestamp("2010-12-01")
SOURCE_END_EXCLUSIVE = pd.Timestamp("2011-12-10")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def price_in_millipounds(price):
    scaled = Decimal(str(price)) * 1000
    require(scaled.is_finite() and scaled == scaled.to_integral_value(),
            f"Unit price exceeds supported precision: {price}")
    return int(scaled)


def classify(raw, rules):
    """Preserve raw columns; add independent flags and a mutually exclusive status."""
    frame = raw.copy()
    require(frame.columns.tolist() == SQL_COLUMNS, "Unexpected source columns or order.")
    for column in TEXT_COLUMNS:
        require(pd.api.types.is_string_dtype(frame[column]) and
                frame[column].dropna().map(lambda value: isinstance(value, str)).all(),
                f"Source field {column} must contain text or NULL.")
    for column in ["source_row_number", "quantity", "unit_price"]:
        require(pd.api.types.is_numeric_dtype(frame[column]) and
                not pd.api.types.is_bool_dtype(frame[column]), f"Source field {column} must be numeric.")
        require(frame[column].map(lambda value: pd.notna(value) and math.isfinite(value)).all(),
                f"Source field {column} must contain finite values.")
    required = [column for column in SQL_COLUMNS if column not in {"description", "customer_id"}]
    require(not frame[required].isna().any().any(), "Required source fields contain NULLs.")
    require(not frame[["invoice_no", "stock_code", "country"]].apply(
        lambda column: column.str.strip().eq("")).any().any(), "Required identifiers contain blanks.")
    require(frame.source_row_number.is_unique, "Source-row lineage is not unique.")
    require(frame.source_row_number.ge(2).all() and frame.source_row_number.mod(1).eq(0).all(),
            "Source-row lineage must contain integer Excel row numbers starting at 2.")
    require(pd.api.types.is_integer_dtype(frame.source_row_number), "Source-row lineage must use an integer type.")
    timestamps = pd.to_datetime(frame.invoice_date.str.strip(), format="%Y-%m-%d %H:%M:%S", errors="coerce")
    require(timestamps.notna().all(), "Invalid source dates.")
    require((timestamps.ge(SOURCE_START) & timestamps.lt(SOURCE_END_EXCLUSIVE)).all(),
            "Source dates fall outside the documented extract window.")
    frame["invoice_timestamp"] = timestamps.astype("datetime64[ns]")
    require(frame.quantity.mod(1).eq(0).all(), "Non-integral quantities.")
    require(pd.api.types.is_integer_dtype(frame.quantity), "Source quantities must use an integer type.")
    for source_column, clean_column in [
        ("invoice_no", "invoice_no_key"), ("description", "description_clean"),
        ("customer_id", "customer_id_key"), ("country", "country_clean"),
    ]:
        trimmed = frame[source_column].str.strip()
        frame[clean_column] = trimmed.mask(trimmed.eq(""), pd.NA).astype("string")
    frame["stock_code_key"] = frame.stock_code.str.strip().str.upper()
    require(rules.stock_code_key.is_unique, "Duplicate item-code classification rules.")
    require(rules.item_class.isin(["merchandise", "non_merchandise", "unresolved"]).all(),
            "Unknown item class.")
    frame["item_class"] = frame.stock_code_key.map(rules.set_index("stock_code_key").item_class).astype("string")
    conventional = frame.stock_code_key.str.fullmatch(r"[0-9]{5}[A-Z]*")
    frame.loc[frame.item_class.isna() & conventional, "item_class"] = "merchandise"
    unknown = frame.loc[frame.item_class.isna(), "stock_code_key"].unique().tolist()
    require(not unknown, f"Unreviewed item codes: {unknown}")
    frame["is_cancellation"] = frame.invoice_no_key.str.upper().str.startswith("C").astype("bool")
    frame["has_customer_id"] = frame.customer_id_key.notna().astype("bool")
    frame["is_exact_copy_beyond_first"] = frame.duplicated(subset=SQL_COLUMNS[1:], keep="first")
    frame["unit_price_millipounds"] = frame.unit_price.map(price_in_millipounds).astype("int64")
    # Python integers avoid silent overflow before converting to a compact column.
    frame["line_value_millipounds"] = pd.Series([
        int(quantity) * int(price)
        for quantity, price in zip(frame.quantity, frame.unit_price_millipounds)
    ], index=frame.index, dtype="int64")
    frame["row_status"] = pd.Series("eligible_purchase", index=frame.index, dtype="string")
    # Apply in reverse order: cancellation has highest reporting precedence.
    frame.loc[frame.item_class.eq("unresolved"), "row_status"] = "unresolved_item"
    frame.loc[frame.item_class.eq("non_merchandise"), "row_status"] = "non_merchandise"
    frame.loc[frame.unit_price.le(0), "row_status"] = "nonpositive_price"
    frame.loc[frame.quantity.le(0), "row_status"] = "nonpositive_quantity"
    frame.loc[frame.is_cancellation, "row_status"] = "cancellation"
    frame["is_sales_eligible"] = frame.row_status.eq("eligible_purchase").astype("bool")
    frame["is_customer_eligible"] = (frame.is_sales_eligible & frame.has_customer_id).astype("bool")
    return frame


def population_summary(frame):
    return {
        "rows": len(frame), "invoice_ids": int(frame.invoice_no_key.nunique()),
        "known_customer_ids": int(frame.customer_id_key.nunique()),
        "quantity": sum(int(value) for value in frame.quantity),
        "line_value_millipounds": sum(int(value) for value in frame.line_value_millipounds),
    }


def read_export(path):
    frame = pd.read_csv(path, dtype={column: "string" for column in TEXT_COLUMNS + CLEAN_TEXT_COLUMNS + [
        "stock_code_key", "item_class", "row_status"]}, keep_default_na=False,
        na_values={column: [""] for column in ["description", "customer_id", "description_clean", "customer_id_key"]},
        converters={"unit_price": float})
    if "invoice_timestamp" in frame:
        frame["invoice_timestamp"] = pd.to_datetime(
            frame.invoice_timestamp, format="%Y-%m-%d %H:%M:%S", errors="raise").astype("datetime64[ns]")
    return frame


def main():
    source_hash = sha256(SOURCE.read_bytes()).hexdigest()
    manifest = json.loads((SOURCE.parent / "source_manifest.json").read_text(encoding="utf-8"))
    require(source_hash == manifest["sha256"], "Source checksum mismatch.")
    rules = pd.read_csv(CLASSIFICATIONS, keep_default_na=False)
    with closing(sqlite3.connect(f"{DATABASE.as_uri()}?mode=ro", uri=True)) as connection:
        require(connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)],
                "SQLite integrity check failed.")
        raw = pd.read_sql_query("SELECT * FROM raw_transactions ORDER BY source_row_number", connection)
        metadata = connection.execute(
            "SELECT source_sha256, source_records_sha256, source_row_count FROM ingestion_metadata "
            "WHERE ingestion_id = 1").fetchone()
        raw_digest = records_digest(connection.execute(
            f"SELECT {', '.join(SQL_COLUMNS)} FROM raw_transactions ORDER BY source_row_number"))
        connection.execute("CREATE TEMP TABLE reviewed_item_codes (stock_code_key TEXT PRIMARY KEY, item_class TEXT)")
        connection.executemany("INSERT INTO reviewed_item_codes VALUES (?, ?)",
                               rules[["stock_code_key", "item_class"]].itertuples(index=False, name=None))
        sql_reconciliation = connection.execute(
            (ROOT / "sql" / "03_verify_cleaning.sql").read_text(encoding="utf-8")).fetchall()
    require(metadata == (source_hash, raw_digest, len(raw)), "Raw database provenance mismatch.")
    require(raw.columns.tolist() == SQL_COLUMNS and len(raw) == 541_909, "Unexpected raw schema/size.")
    for column in TEXT_COLUMNS:
        raw[column] = raw[column].astype("string")
    ledger = classify(raw, rules)
    sales = ledger.loc[ledger.is_sales_eligible].copy()
    customers = ledger.loc[ledger.is_customer_eligible].copy()
    anonymous = sales.loc[~sales.has_customer_id]
    statuses = {str(key): int(value) for key, value in ledger.row_status.value_counts().items()}
    require(sum(statuses.values()) == len(raw), "Status counts do not reconcile.")
    python_reconciliation = [
        (str(status), len(group), sum(int(value) for value in group.line_value_millipounds))
        for status, group in ledger.groupby("row_status", sort=True)
    ]
    require(sql_reconciliation == python_reconciliation, "Independent SQL reconciliation failed.")
    require(len(sales) == len(customers) + len(anonymous), "Customer population does not reconcile.")
    require(population_summary(sales)["line_value_millipounds"] ==
            population_summary(customers)["line_value_millipounds"] +
            population_summary(anonymous)["line_value_millipounds"], "Customer values do not reconcile.")
    require((~sales.is_cancellation & sales.quantity.gt(0) & sales.unit_price.gt(0) &
             sales.item_class.eq("merchandise")).all(), "Ineligible sales row.")
    pd.testing.assert_frame_equal(raw, ledger[SQL_COLUMNS], check_exact=True)
    summary = {
        "rules_version": 2, "source_sha256": source_hash, "raw_records_sha256": raw_digest,
        "classification_sha256": sha256(CLASSIFICATIONS.read_bytes()).hexdigest(),
        "currency": "GBP", "integer_value_scale": 1000,
        "duplicate_baseline": "retain_all_source_rows",
        "source_rows": len(raw), "status_counts": statuses,
        "populations": {name: population_summary(frame) for name, frame in [
            ("all_recorded_lines", ledger), ("merchandise_purchases", sales),
            ("identified_customer_purchases", customers), ("anonymous_purchases", anonymous)]},
        "duplicate_sensitivity": {
            name: {"baseline": population_summary(frame),
                   "without_exact_copies": population_summary(frame.loc[~frame.is_exact_copy_beyond_first])}
            for name, frame in [("merchandise_purchases", sales), ("identified_customer_purchases", customers)]
        },
        "raw_exact_copies_beyond_first": int(ledger.is_exact_copy_beyond_first.sum()),
        "item_class_counts": {str(key): int(value) for key, value in ledger.item_class.value_counts().items()},
        "checks": {"raw_columns_unchanged": True, "raw_digest_verified": True,
                   "unique_source_lineage": True, "status_partition": True,
                   "independent_sql_status_rows_and_value": True,
                   "customer_partition_rows_and_value": True, "exports_round_trip": True},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Validate every export before publishing the completed set; summary is written last.
    with tempfile.TemporaryDirectory(dir=OUTPUT, prefix=".cleaning-") as temporary:
        temporary_path = Path(temporary)
        exports = {"transaction_ledger.csv.gz": ledger, "sales_transactions.csv.gz": sales,
                   "customer_transactions.csv.gz": customers}
        hashes = {}
        for name, frame in exports.items():
            path = temporary_path / name
            frame.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
            restored = read_export(path)
            pd.testing.assert_frame_equal(frame.reset_index(drop=True), restored,
                                          check_exact=True, check_dtype=True)
            hashes[name] = sha256(path.read_bytes()).hexdigest()
        summary["export_sha256"] = hashes
        require(sha256(SOURCE.read_bytes()).hexdigest() == source_hash, "Source changed during cleaning.")
        for name in exports:
            (temporary_path / name).replace(OUTPUT / name)
    summary_path = ROOT / "reports" / "03_cleaning_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
