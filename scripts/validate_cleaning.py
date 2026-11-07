"""Independently verify cleaned retail exports and log row-level quality findings."""

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pandas as pd

from clean_transactions import read_export
from load_sqlite import DATABASE, ROOT, SOURCE, SQL_COLUMNS, records_digest

OUTPUT = ROOT / "data" / "processed"
EXPORTS = {
    "ledger": "transaction_ledger.csv.gz",
    "sales": "sales_transactions.csv.gz",
    "customers": "customer_transactions.csv.gz",
}
TEXT = ["invoice_no", "stock_code", "description", "invoice_date", "customer_id", "country",
        "invoice_no_key", "description_clean", "customer_id_key", "country_clean", "stock_code_key",
        "item_class", "row_status"]
INTEGERS = ["source_row_number", "quantity", "unit_price_millipounds", "line_value_millipounds"]
BOOLEANS = ["is_cancellation", "has_customer_id", "is_exact_copy_beyond_first",
            "is_sales_eligible", "is_customer_eligible"]
EXPECTED_COLUMNS = SQL_COLUMNS + ["invoice_timestamp", "invoice_no_key", "description_clean",
    "customer_id_key", "country_clean", "stock_code_key", "item_class", "is_cancellation",
    "has_customer_id", "is_exact_copy_beyond_first", "unit_price_millipounds",
    "line_value_millipounds", "row_status", "is_sales_eligible", "is_customer_eligible"]
CATEGORIES = ["schema", "null_empty", "boundaries_outliers", "duplicates_keys", "business_logic"]


def independent_expectations(raw, rules):
    """Recompute policy directly from raw fields; never invoke the cleaning classifier."""
    if not rules.stock_code_key.is_unique or not rules.item_class.isin(
            ["merchandise", "non_merchandise", "unresolved"]).all():
        raise ValueError("Invalid or duplicate reviewed item-code classifications")
    expected = raw.copy()
    for column in SQL_COLUMNS:
        if column not in {"source_row_number", "quantity", "unit_price"}:
            expected[column] = expected[column].astype("string")
    for source, target in [("invoice_no", "invoice_no_key"), ("stock_code", "stock_code_key"),
                           ("description", "description_clean"), ("customer_id", "customer_id_key"),
                           ("country", "country_clean")]:
        value = expected[source].str.strip()
        expected[target] = value.mask(value.eq(""), pd.NA)
    expected["stock_code_key"] = expected.stock_code_key.str.upper()
    expected["invoice_timestamp"] = pd.to_datetime(expected.invoice_date.str.strip(),
        format="%Y-%m-%d %H:%M:%S", errors="coerce").astype("datetime64[ns]")
    registry = dict(zip(rules.stock_code_key, rules.item_class))
    expected["item_class"] = expected.stock_code_key.map(registry).astype("string")
    ordinary = expected.stock_code_key.str.fullmatch(r"[0-9]{5}[A-Z]*", na=False)
    expected.loc[ordinary & expected.item_class.isna(), "item_class"] = "merchandise"
    if expected.item_class.isna().any():
        raise ValueError("Raw source includes unreviewed item codes")
    expected["is_cancellation"] = expected.invoice_no_key.str.upper().str.startswith("C", na=False)
    expected["has_customer_id"] = expected.customer_id_key.notna()
    expected["is_exact_copy_beyond_first"] = expected.duplicated(SQL_COLUMNS[1:], keep="first")
    def exact_price(value):
        scaled = Decimal(str(value)) * 1000
        if not scaled.is_finite() or scaled != scaled.to_integral_value():
            raise ValueError("Raw unit price has non-finite or unsupported precision")
        return int(scaled)
    expected["unit_price_millipounds"] = expected.unit_price.map(exact_price)
    expected["line_value_millipounds"] = [int(q) * int(p) for q, p in
        zip(expected.quantity, expected.unit_price_millipounds)]
    # A separate first-match implementation of the documented precedence.
    expected["row_status"] = pd.Series(pd.NA, index=expected.index, dtype="string")
    conditions = [(expected.is_cancellation, "cancellation"),
                  (expected.quantity.le(0), "nonpositive_quantity"),
                  (expected.unit_price.le(0), "nonpositive_price"),
                  (expected.item_class.eq("non_merchandise"), "non_merchandise"),
                  (expected.item_class.eq("unresolved"), "unresolved_item")]
    for condition, status in conditions:
        expected.loc[expected.row_status.isna() & condition.fillna(False), "row_status"] = status
    expected["row_status"] = expected.row_status.fillna("eligible_purchase")
    expected["is_sales_eligible"] = expected.row_status.eq("eligible_purchase")
    expected["is_customer_eligible"] = expected.is_sales_eligible & expected.has_customer_id
    return expected


class QualityReview:
    def __init__(self):
        self.failures = []
        self.warnings = []
        self.logs = []
        self.null_profiles = {}
        self.outlier_fences = {}
        self.blocked = []

    def finding(self, category, dataset, frame, mask, field, reason, severity="FAIL"):
        mask = pd.Series(mask, index=frame.index).fillna(True).astype(bool)
        affected = frame.loc[mask]
        if affected.empty:
            return
        entry = {"category": category, "dataset": dataset, "field": field,
                 "reason": reason, "rows": len(affected),
                 "example_source_rows": [None if pd.isna(value) else value if
                     isinstance(value, (str, int, float, bool)) else str(value)
                     for value in affected.source_row_number.head(10).tolist()]}
        (self.failures if severity == "FAIL" else self.warnings).append(entry)
        log = affected[["source_row_number", "invoice_no", "stock_code"]].copy()
        log["dataset"] = dataset
        log["category"] = category
        log["severity"] = severity
        log["field"] = field
        log["value"] = affected[field].astype("string").fillna("<NULL>") if field in affected else "<ROW>"
        log["reason"] = reason
        self.logs.append(log)

    def global_failure(self, category, dataset, field, reason):
        self.failures.append({"category": category, "dataset": dataset, "field": field,
                              "reason": reason, "rows": None, "example_source_rows": []})

    def inspect(self, name, frame, expected):
        """Run all five checks on one export; expected rows are source-derived."""
        if frame.columns.tolist() != EXPECTED_COLUMNS:
            self.global_failure("schema", name, "columns", "Missing, extra, or reordered export columns")
            self.blocked.extend({"category": category, "dataset": name,
                                 "reason": "Cannot run meaningful check without the required schema"}
                                for category in CATEGORIES if category != "schema")
            return
        for column in TEXT:
            if str(frame[column].dtype) != "string":
                self.global_failure("schema", name, column, f"Expected string dtype, observed {frame[column].dtype}")
        for column in INTEGERS:
            if str(frame[column].dtype) != "int64":
                self.global_failure("schema", name, column, f"Expected int64, observed {frame[column].dtype}")
        if str(frame.unit_price.dtype) != "float64":
            self.global_failure("schema", name, "unit_price", f"Expected float64, observed {frame.unit_price.dtype}")
        if str(frame.invoice_timestamp.dtype) != "datetime64[ns]":
            self.global_failure("schema", name, "invoice_timestamp", f"Expected timezone-naive datetime64[ns], observed {frame.invoice_timestamp.dtype}")
        for column in BOOLEANS:
            if str(frame[column].dtype) != "bool":
                self.global_failure("schema", name, column, f"Expected bool, observed {frame[column].dtype}")

        optional = {"description", "description_clean"}
        if name != "customers":
            optional |= {"customer_id", "customer_id_key"}
        profile = {}
        for column in frame.columns:
            missing = frame[column].isna()
            empty = frame[column].astype("string").str.strip().eq("").fillna(False)
            profile[column] = {"nulls": int(missing.sum()), "empty": int(empty.sum()),
                "null_or_empty_percent": float((missing | empty).mean() * 100),
                "required": column not in optional}
            if column not in optional:
                self.finding("null_empty", name, frame, missing | empty, column, "Required field is null or empty")
            if column in {"invoice_no_key", "stock_code_key", "description_clean", "customer_id_key", "country_clean"}:
                text = frame[column].astype("string")
                whitespace = text.ne(text.str.strip()).fillna(False)
                self.finding("null_empty", name, frame, whitespace | empty, column, "Analytical text contains surrounding whitespace or an empty sentinel")
        self.null_profiles[name] = profile

        # Dates and arithmetic are guarded for malformed schema mutations.
        dates = pd.to_datetime(frame.invoice_timestamp, errors="coerce")
        if dates.dt.tz is not None:
            date_bad = pd.Series(True, index=frame.index)
        else:
            date_bad = dates.isna() | dates.lt(pd.Timestamp("2010-12-01")) | dates.ge(pd.Timestamp("2011-12-10"))
        self.finding("boundaries_outliers", name, frame, date_bad, "invoice_timestamp", "Invalid, timezone-bearing, or out-of-window date")
        for column in ["quantity", "unit_price"]:
            values = pd.to_numeric(frame[column], errors="coerce")
            invalid = values.isna() | values.isin([float("inf"), -float("inf")])
            if column == "quantity":
                invalid |= values.mod(1).ne(0)
            if name != "ledger":
                invalid |= values.le(0)
            self.finding("boundaries_outliers", name, frame, invalid, column, "Non-finite, fractional quantity, or nonpositive purchase value")

        key = pd.to_numeric(frame.source_row_number, errors="coerce")
        self.finding("duplicates_keys", name, frame, key.isna() | key.lt(2) | key.mod(1).ne(0),
                     "source_row_number", "Invalid Excel source-row key")
        self.finding("duplicates_keys", name, frame, frame.source_row_number.duplicated(keep=False),
                     "source_row_number", "Duplicate source-row primary key")
        actual_ids = set(frame.source_row_number)
        expected_ids = set(expected.source_row_number)
        self.finding("business_logic", name, frame, ~frame.source_row_number.isin(expected_ids),
                     "source_row_number", "Unexpected row in analytical population")
        absent = expected.loc[~expected.source_row_number.isin(actual_ids)]
        self.finding("business_logic", name, absent, pd.Series(True, index=absent.index),
                     "source_row_number", "Required source row missing from analytical population")
        if not frame.source_row_number.is_unique:
            self.blocked.append({"category": "business_logic", "dataset": name,
                                 "reason": "Duplicate source keys prevent unambiguous field-by-field alignment"})
            return
        aligned = expected.set_index("source_row_number").reindex(frame.source_row_number)
        aligned.index = frame.index
        for column in EXPECTED_COLUMNS:
            if column == "source_row_number":
                continue
            equal = frame[column].eq(aligned[column]) | (frame[column].isna() & aligned[column].isna())
            self.finding("business_logic", name, frame, ~equal.fillna(False), column,
                         "Value differs from independent source-derived expectation")

    def record_source_anomalies(self, expected):
        for column in ["customer_id", "description"]:
            self.finding("null_empty", "raw", expected, expected[column].isna(), column,
                         "Disclosed optional source field missing", "WARN")
        whitespace = expected.description.notna() & expected.description.ne(expected.description.str.strip())
        self.finding("null_empty", "raw", expected, whitespace, "description",
                     "Source description whitespace preserved; trimmed analytical label available", "WARN")
        for mask, field, reason in [
            (expected.is_cancellation, "invoice_no", "Cancellation retained in ledger and excluded from purchases"),
            (expected.quantity.le(0), "quantity", "Nonpositive source quantity retained outside purchases"),
            (expected.unit_price.le(0), "unit_price", "Nonpositive source price retained outside purchases"),
            (expected.item_class.eq("unresolved"), "stock_code", "Unresolved item retained outside purchases"),
        ]:
            self.finding("boundaries_outliers", "raw", expected, mask, field, reason, "WARN")
        self.finding("duplicates_keys", "raw", expected, expected.is_exact_copy_beyond_first,
                     "source_row_number", "Exact source copy beyond first retained by baseline policy", "WARN")
        purchases = expected.loc[expected.is_sales_eligible]
        for column in ["quantity", "unit_price"]:
            q1, q3 = purchases[column].quantile([0.25, 0.75])
            fence = float(q3 + 3 * (q3 - q1))
            self.outlier_fences[column] = {"method": "upper Tukey outer fence Q3 + 3*IQR", "threshold": fence}
            self.finding("boundaries_outliers", "eligible_purchases", purchases, purchases[column].gt(fence),
                         column, f"High-value review flag above Q3 + 3*IQR ({fence:g}); not proof of error", "WARN")

    def summary(self):
        return {"categories": {category: {
                    "status": "FAIL" if any(f["category"] == category for f in self.failures)
                              else "INCOMPLETE" if any(f["category"] == category for f in self.blocked)
                              else "PASS_WITH_WARNINGS" if any(f["category"] == category for f in self.warnings) else "PASS",
                    "failures": [f for f in self.failures if f["category"] == category],
                    "warnings": [f for f in self.warnings if f["category"] == category]}
                for category in CATEGORIES},
                "hard_failure_groups": len(self.failures), "null_profiles": self.null_profiles,
                "blocked_checks": self.blocked,
                "outlier_fences": self.outlier_fences,
                "readiness": "Needs revision" if self.failures else "Verification incomplete" if self.blocked
                             else "Ready for defined gross-purchase analysis with disclosed caveats"}


def main():
    summary = json.loads((ROOT / "reports" / "03_cleaning_summary.json").read_text(encoding="utf-8"))
    rules = pd.read_csv(ROOT / "docs" / "item_code_classification.csv", keep_default_na=False)
    with closing(sqlite3.connect(f"{DATABASE.as_uri()}?mode=ro", uri=True)) as connection:
        raw = pd.read_sql_query("SELECT * FROM raw_transactions ORDER BY source_row_number", connection)
        digest = records_digest(connection.execute(
            f"SELECT {', '.join(SQL_COLUMNS)} FROM raw_transactions ORDER BY source_row_number"))
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
    review = QualityReview()
    try:
        expected = independent_expectations(raw, rules)
    except (ValueError, TypeError, KeyError) as error:
        review.global_failure("business_logic", "raw", "source", f"Source policy cannot be evaluated: {error}")
        review.blocked.extend({"category": category, "dataset": "all",
                               "reason": "Independent source expectations could not be established"}
                              for category in CATEGORIES if category != "business_logic")
        result = review.summary()
        result["readiness"] = "Needs revision; source policy could not be evaluated"
        (OUTPUT / "cleaning_qa_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 1
    if integrity != [("ok",)]:
        review.global_failure("business_logic", "raw", "sqlite_integrity", "Raw SQLite integrity check failed")
    if digest != summary["raw_records_sha256"]:
        review.global_failure("business_logic", "raw", "raw_records_sha256", "Raw source-record digest differs from cleaning provenance")
    if sha256(SOURCE.read_bytes()).hexdigest() != summary["source_sha256"]:
        review.global_failure("business_logic", "raw", "source_sha256", "Workbook fingerprint differs from cleaning provenance")
    if sha256((ROOT / "docs" / "item_code_classification.csv").read_bytes()).hexdigest() != summary["classification_sha256"]:
        review.global_failure("business_logic", "raw", "classification_sha256", "Reviewed classification registry differs from cleaning provenance")
    review.record_source_anomalies(expected)
    hashes = {}
    for name, filename in EXPORTS.items():
        path = OUTPUT / filename
        hashes[filename] = sha256(path.read_bytes()).hexdigest()
        if hashes[filename] != summary["export_sha256"][filename]:
            review.global_failure("business_logic", name, "export_sha256", "Export hash differs from cleaning summary")
        target = expected if name == "ledger" else expected.loc[
            expected.is_sales_eligible if name == "sales" else expected.is_customer_eligible]
        try:
            frame = read_export(path)
            review.inspect(name, frame, target)
        except (ValueError, TypeError, KeyError) as error:
            review.global_failure("schema", name, "export", f"Export cannot be validated: {error}")
            review.blocked.extend({"category": category, "dataset": name,
                                   "reason": "Export could not be loaded or fully validated"}
                                  for category in CATEGORIES if category != "schema")
    result = review.summary()
    result.update({"verified_at_utc": datetime.now(timezone.utc).isoformat(),
                   "coverage": {"source_rows": len(raw), "datasets": list(EXPORTS), "sampling": "none"},
                   "raw_records_sha256": digest,
                   "export_sha256": hashes})
    anomalies = pd.concat(review.logs, ignore_index=True) if review.logs else pd.DataFrame()
    anomalies.to_csv(OUTPUT / "cleaning_qa_anomalies.csv.gz", index=False,
                     compression={"method": "gzip", "mtime": 0})
    (OUTPUT / "cleaning_qa_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"categories": {key: value["status"] for key, value in result["categories"].items()},
                      "hard_failure_groups": result["hard_failure_groups"], "readiness": result["readiness"],
                      "logged_anomaly_records": len(anomalies)}, indent=2))
    return 1 if review.failures or review.blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
