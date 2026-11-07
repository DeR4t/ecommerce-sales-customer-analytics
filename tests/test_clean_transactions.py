"""Boundary checks for population membership and exact monetary arithmetic."""

from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from clean_transactions import classify, price_in_millipounds, read_export
from load_sqlite import ROOT, SQL_COLUMNS


class CleaningRulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = pd.DataFrame([
            ("POST", "non_merchandise"), ("M", "unresolved"), ("PADS", "merchandise")
        ], columns=["stock_code_key", "item_class"])

    def frame(self, rows):
        result = pd.DataFrame([
            (index + 2, invoice, code, "Item", quantity, "2011-01-01 12:00:00", price, customer, "UK")
            for index, (invoice, code, quantity, price, customer) in enumerate(rows)
        ], columns=SQL_COLUMNS)
        for column in ["invoice_no", "stock_code", "description", "invoice_date", "customer_id", "country"]:
            result[column] = result[column].astype("string")
        return result

    def test_populations_duplicates_and_precedence(self):
        raw = self.frame([
            ("1", "12345", 2, 1.5, None), ("1", "12345", 2, 1.5, None),
            ("2", "15056bl", 1, 2.0, "10"), ("C3", "12345", -1, 0.0, "10"),
            ("4", "12345", -1, 2.0, "10"), ("5", "12345", 1, 0.0, "10"),
            ("6", "POST", 1, 2.0, "10"), ("7", "M", 1, 2.0, "10"),
            ("8", "PADS", 1, 0.001, "10"), ("C9", "12345", 1, 2.0, "10"),
            ("10", "12345", 0, 2.0, "10"), ("11", "12345", 1, -2.0, "10"),
        ])
        result = classify(raw, self.rules)
        self.assertEqual(result.row_status.tolist(), [
            "eligible_purchase", "eligible_purchase", "eligible_purchase", "cancellation",
            "nonpositive_quantity", "nonpositive_price", "non_merchandise", "unresolved_item",
            "eligible_purchase", "cancellation", "nonpositive_quantity", "nonpositive_price"])
        self.assertEqual(result.is_sales_eligible.sum(), 4)
        self.assertEqual(result.is_customer_eligible.sum(), 2)
        self.assertEqual(result.is_exact_copy_beyond_first.sum(), 1)
        self.assertEqual(result.loc[8, "line_value_millipounds"], 1)
        pd.testing.assert_frame_equal(raw, result[SQL_COLUMNS])

    def test_unknown_codes_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unreviewed item codes"):
            classify(self.frame([("1", "NEWCODE", 1, 1.0, "10")]), self.rules)

    def test_precision_is_not_silently_rounded(self):
        self.assertEqual(price_in_millipounds(0.001), 1)
        self.assertEqual(price_in_millipounds(-11062.06), -11062060)
        with self.assertRaisesRegex(ValueError, "precision"):
            price_in_millipounds(0.0001)

    def test_clean_fields_preserve_raw_values_and_blank_nulls(self):
        raw = self.frame([(" 1 ", " 15056bl ", 1, 1.5, " 10 "),
                          ("2", "12345", 1, 1.5, " \t ")])
        raw.loc[0, "description"] = "  Item label \t"
        raw.loc[1, "description"] = " \t "
        raw.loc[0, "country"] = " UK "
        raw.loc[0, "invoice_date"] = " 2011-01-01 12:00:00 "
        result = classify(raw, self.rules)
        self.assertEqual(result.loc[0, "description_clean"], "Item label")
        self.assertTrue(pd.isna(result.loc[1, "description_clean"]))
        self.assertEqual(result.loc[0, "invoice_no_key"], "1")
        self.assertEqual(result.loc[0, "stock_code_key"], "15056BL")
        self.assertEqual(result.loc[0, "customer_id_key"], "10")
        self.assertTrue(pd.isna(result.loc[1, "customer_id_key"]))
        self.assertEqual(result.loc[0, "country_clean"], "UK")
        self.assertEqual(str(result.invoice_timestamp.dtype), "datetime64[ns]")
        self.assertIsNone(result.invoice_timestamp.dt.tz)
        self.assertFalse(result.loc[1, "is_customer_eligible"])
        pd.testing.assert_frame_equal(raw, result[SQL_COLUMNS])

    def test_invalid_schema_numbers_dates_and_lineage_fail_clearly(self):
        baseline = self.frame([("1", "12345", 1, 1.0, "10")])
        cases = [
            ("quantity", "wrong", "must be numeric"),
            ("unit_price", float("inf"), "finite"),
            ("unit_price", float("nan"), "finite"),
            ("quantity", float("inf"), "finite"),
            ("quantity", 1.5, "Non-integral"),
            ("invoice_date", "2011-02-30 12:00:00", "Invalid source dates"),
            ("invoice_date", "2099-01-01 12:00:00", "extract window"),
            ("invoice_date", "2011-01-01T12:00:00+05:30", "Invalid source dates"),
            ("source_row_number", 1, "Excel row numbers"),
            ("source_row_number", 2.5, "Excel row numbers"),
        ]
        for column, value, error in cases:
            with self.subTest(column=column, value=value):
                raw = baseline.copy()
                if isinstance(value, str) and column in {"quantity", "unit_price"}:
                    raw[column] = raw[column].astype("object")
                elif isinstance(value, float) and column in {"quantity", "source_row_number"}:
                    raw[column] = raw[column].astype("float64")
                raw.loc[0, column] = value
                with self.assertRaisesRegex(ValueError, error):
                    classify(raw, self.rules)
        for column in ["invoice_no", "customer_id"]:
            with self.subTest(column=column):
                raw = baseline.copy()
                raw[column] = pd.Series([123], dtype="int64")
                with self.assertRaisesRegex(ValueError, "must contain text"):
                    classify(raw, self.rules)
        duplicate = pd.concat([baseline, baseline], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "lineage is not unique"):
            classify(duplicate, self.rules)
        for column, dtype in [("quantity", "Int64"), ("unit_price", "Float64")]:
            with self.subTest(nullable_numeric=column):
                raw = baseline.copy()
                raw[column] = pd.Series([pd.NA], dtype=dtype)
                with self.assertRaisesRegex(ValueError, "finite"):
                    classify(raw, self.rules)

    def test_export_round_trip_preserves_types_and_nulls(self):
        raw = self.frame([("1", "PADS", 1, 0.001, None), ("2", "12345", 2, 1.5, "10")])
        raw.loc[0, "description"] = pd.NA
        result = classify(raw, self.rules)
        with tempfile.TemporaryDirectory(dir=ROOT / "data" / "processed") as temporary:
            path = Path(temporary) / "round_trip.csv.gz"
            result.to_csv(path, index=False, compression="gzip")
            restored = read_export(path)
            pd.testing.assert_frame_equal(result, restored, check_dtype=True, check_exact=True)


if __name__ == "__main__":
    unittest.main()
