"""Exercise invoice grain, label joins, partial months, and exact SQL accounting."""

from pathlib import Path
import sqlite3
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from clean_transactions import classify
from load_analysis import sql_records, validate_invoice_dimensions
from load_sqlite import ROOT, SQL_COLUMNS
from run_sql_analysis import QUERIES, reconcile


class BusinessSQLTests(unittest.TestCase):
    def setUp(self):
        # Invoice 1 spans months; invoice 2 contains an intentional exact copy.
        rows = [
            ("1", "12345", "Older label", 2, "2011-01-31 23:59:00", 1.0, "10", "UK"),
            ("1", "12345", "New label", 1, "2011-02-01 00:01:00", 3.0, "10", "UK"),
            ("2", "12345", "Latest label", 1, "2011-02-02 12:00:00", 5.0, None, "France"),
            ("2", "12345", "Latest label", 1, "2011-02-02 12:00:00", 5.0, None, "France"),
            ("3", "22222", "Other product", 1, "2011-12-09 12:00:00", 7.0, "20", "UK"),
            ("4", "22222", "Other product", 1, "2011-11-15 12:00:00", 11.0, "20", "UK"),
            ("C2", "12345", "Credit", -2, "2011-02-03 12:00:00", 1.0, "10", "UK"),
            ("5", "POST", "Postage", 1, "2011-02-04 12:00:00", 10.0, "10", "UK"),
        ]
        raw = pd.DataFrame([(index + 2, *row) for index, row in enumerate(rows)], columns=SQL_COLUMNS)
        for column in ["invoice_no", "stock_code", "description", "invoice_date", "customer_id", "country"]:
            raw[column] = raw[column].astype("string")
        rules = pd.DataFrame([("POST", "non_merchandise")], columns=["stock_code_key", "item_class"])
        self.ledger = classify(raw, rules)
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript((ROOT / "sql" / "04_analysis_schema.sql").read_text(encoding="utf-8"))
        self.connection.executemany("INSERT INTO transaction_ledger VALUES (" + ",".join("?" for _ in self.ledger.columns) + ")",
                                    sql_records(self.ledger))
        self.results = {name: pd.read_sql_query((ROOT / "sql" / filename).read_text(encoding="utf-8"), self.connection)
                        for name, filename in QUERIES.items()}

    def test_full_sql_and_python_reconciliation(self):
        validate_invoice_dimensions(self.connection)
        self.assertEqual(len(reconcile(self.results, self.ledger.loc[self.ledger.is_sales_eligible])), 6)

    def test_invoice_grain_and_anonymous_sales(self):
        row = self.results["sales_summary"].iloc[0]
        self.assertEqual(row.purchase_lines, 6)
        self.assertEqual(row.purchase_orders, 4)
        self.assertEqual(row.gross_purchase_millipounds, 33_000)
        self.assertEqual(row.anonymous_purchase_millipounds, 10_000)
        self.assertEqual(row.gross_aov_gbp, 8.25)
        self.assertEqual(len(self.results["customers"]), 2)
        self.assertEqual(int(self.results["customers"].gross_purchase_millipounds.sum()), 23_000)

    def test_product_join_does_not_multiply_values(self):
        product = self.results["products"].set_index("stock_code_key").loc["12345"]
        self.assertEqual(product.product_description, "Latest label")
        self.assertEqual(product.gross_purchase_millipounds, 15_000)
        self.assertEqual(product.purchase_orders, 2)

    def test_order_month_and_incomplete_comparisons(self):
        monthly = self.results["monthly_sales"].set_index("month")
        self.assertEqual(monthly.loc["2011-01", "gross_purchase_millipounds"], 5_000)
        self.assertEqual(monthly.loc["2011-02", "gross_purchase_millipounds"], 10_000)
        self.assertEqual(monthly.loc["2011-02", "full_month_growth_percent"], 100.0)
        self.assertTrue(pd.isna(monthly.loc["2011-11", "full_month_growth_percent"]))
        self.assertEqual(monthly.loc["2011-12", "is_complete_month"], 0)
        self.assertTrue(pd.isna(monthly.loc["2011-12", "full_month_growth_percent"]))

    def test_conflicting_order_dimensions_stop_import(self):
        self.connection.execute("UPDATE transaction_ledger SET country_clean = 'France' WHERE source_row_number = 2")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            validate_invoice_dimensions(self.connection)


if __name__ == "__main__":
    unittest.main()
