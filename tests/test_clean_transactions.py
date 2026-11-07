"""Boundary checks for population membership and exact monetary arithmetic."""

from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from clean_transactions import classify, price_in_millipounds
from load_sqlite import SQL_COLUMNS


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


if __name__ == "__main__":
    unittest.main()
