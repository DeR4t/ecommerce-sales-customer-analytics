"""Mutation checks prove each full-data QA category detects corrupted outputs."""

from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from load_sqlite import SQL_COLUMNS
from validate_cleaning import BOOLEANS, EXPECTED_COLUMNS, INTEGERS, QualityReview, independent_expectations


class CleaningQualityTests(unittest.TestCase):
    def setUp(self):
        raw = pd.DataFrame([
            (2, "1", "12345", " Item ", 2, "2011-01-01 12:00:00", 1.5, "10", "UK"),
            (3, "2", "12345", None, 1, "2011-01-02 12:00:00", 0.001, None, "UK"),
        ], columns=SQL_COLUMNS)
        rules = pd.DataFrame(columns=["stock_code_key", "item_class"])
        self.expected = independent_expectations(raw, rules)
        self.raw = raw
        self.rules = rules
        self.valid = self.expected[EXPECTED_COLUMNS].copy()
        for column in BOOLEANS:
            self.valid[column] = self.valid[column].astype("bool")
        for column in INTEGERS:
            self.valid[column] = self.valid[column].astype("int64")

    def inspect(self, frame):
        review = QualityReview()
        review.inspect("sales", frame, self.expected)
        return review

    def test_valid_population_has_no_failures(self):
        self.assertEqual(self.inspect(self.valid).failures, [])

    def test_schema_corruption_is_detected(self):
        changed = self.valid.copy()
        changed["quantity"] = changed.quantity.astype("float64")
        review = self.inspect(changed)
        self.assertTrue(any(f["category"] == "schema" and f["field"] == "quantity" for f in review.failures))

    def test_numeric_text_and_timezone_schema_fail_without_crashing(self):
        changed = self.valid.copy()
        changed["invoice_no_key"] = pd.Series([1, 2], dtype="int64")
        review = self.inspect(changed)
        self.assertTrue(any(f["category"] == "schema" and f["field"] == "invoice_no_key" for f in review.failures))
        changed = self.valid.copy()
        changed["invoice_timestamp"] = changed.invoice_timestamp.dt.tz_localize("UTC")
        review = self.inspect(changed)
        self.assertTrue(any(f["category"] == "schema" and f["field"] == "invoice_timestamp" for f in review.failures))
        self.assertTrue(any(f["category"] == "boundaries_outliers" for f in review.failures))

    def test_missing_schema_does_not_claim_other_checks_passed(self):
        review = self.inspect(self.valid.drop(columns="country_clean"))
        result = review.summary()
        self.assertEqual(result["categories"]["schema"]["status"], "FAIL")
        self.assertEqual(result["categories"]["business_logic"]["status"], "INCOMPLETE")

    def test_source_precision_and_unreviewed_codes_fail_closed(self):
        raw = self.raw.copy()
        raw.loc[0, "unit_price"] = 0.0001
        with self.assertRaisesRegex(ValueError, "precision"):
            independent_expectations(raw, self.rules)
        raw = self.raw.copy()
        raw.loc[0, "stock_code"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            independent_expectations(raw, self.rules)

    def test_required_null_and_whitespace_sentinel_are_detected(self):
        for value in [pd.NA, " \t "]:
            with self.subTest(value=value):
                changed = self.valid.copy()
                changed.loc[0, "invoice_no_key"] = value
                review = self.inspect(changed)
                self.assertTrue(any(f["category"] == "null_empty" for f in review.failures))

    def test_impossible_date_and_nonpositive_purchase_are_detected(self):
        for column, value in [("invoice_timestamp", pd.Timestamp("2099-01-01")), ("quantity", -1), ("unit_price", float("inf"))]:
            with self.subTest(column=column):
                changed = self.valid.copy()
                changed.loc[0, column] = value
                review = self.inspect(changed)
                self.assertTrue(any(f["category"] == "boundaries_outliers" for f in review.failures))

    def test_duplicate_source_key_is_detected(self):
        changed = pd.concat([self.valid, self.valid.iloc[[0]]], ignore_index=True)
        review = self.inspect(changed)
        self.assertTrue(any(f["category"] == "duplicates_keys" and "Duplicate" in f["reason"] for f in review.failures))
        self.assertEqual(review.summary()["categories"]["business_logic"]["status"], "INCOMPLETE")

    def test_business_value_and_missing_membership_are_detected(self):
        changed = self.valid.copy()
        changed.loc[0, "line_value_millipounds"] += 1
        review = self.inspect(changed)
        self.assertTrue(any(f["category"] == "business_logic" and f["field"] == "line_value_millipounds" for f in review.failures))
        review = self.inspect(self.valid.iloc[[0]])
        self.assertTrue(any("missing from analytical population" in f["reason"] for f in review.failures))


if __name__ == "__main__":
    unittest.main()
