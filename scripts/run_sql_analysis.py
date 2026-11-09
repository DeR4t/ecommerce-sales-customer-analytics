"""Execute saved business SQL and reconcile complete results against pandas."""

from contextlib import closing
from hashlib import sha256
import json
import sqlite3

import pandas as pd

from clean_transactions import read_export, require
from load_analysis import ANALYSIS_DB, main as load_analysis
from load_sqlite import ROOT

QUERIES = {
    "sales_summary": "05_sales_summary.sql", "products": "06_product_performance.sql",
    "countries": "07_country_performance.sql", "monthly_sales": "08_monthly_sales.sql",
    "orders": "09_order_value.sql", "customers": "10_customer_purchases.sql",
}


def same(sql, python, columns, sort_by, name):
    pd.testing.assert_frame_equal(sql[columns].sort_values(sort_by).reset_index(drop=True),
        python[columns].sort_values(sort_by).reset_index(drop=True), check_dtype=False,
        check_exact=True, obj=name)


def reconcile(results, sales):
    """Independent pandas grouping at line, invoice, product, country and customer grain."""
    orders = sales.groupby("invoice_no_key", sort=True).agg(
        order_timestamp=("invoice_timestamp", "min"), country=("country_clean", "first"),
        customer_id=("customer_id_key", "first"), line_count=("quantity", "size"),
        units=("quantity", "sum"), gross_purchase_millipounds=("line_value_millipounds", "sum")).reset_index()
    orders["order_timestamp"] = orders.order_timestamp.dt.strftime("%Y-%m-%d %H:%M:%S")
    same(results["orders"], orders, orders.columns.tolist(), ["invoice_no_key"], "orders")
    value = int(sales.line_value_millipounds.sum())
    summary = results["sales_summary"].iloc[0]
    expected = {"purchase_lines": len(sales), "purchase_orders": len(orders),
                "identified_customers": sales.customer_id_key.nunique(), "units": int(sales.quantity.sum()),
                "gross_purchase_millipounds": value,
                "identified_purchase_millipounds": int(sales.loc[sales.has_customer_id, "line_value_millipounds"].sum()),
                "anonymous_purchase_millipounds": int(sales.loc[~sales.has_customer_id, "line_value_millipounds"].sum())}
    for key, expected_value in expected.items():
        require(summary[key] == expected_value, f"Sales summary differs: {key}")
    require(abs(summary.gross_aov_gbp - value / (1000 * len(orders))) < 1e-9, "AOV does not reconcile.")

    products = sales.groupby("stock_code_key").agg(purchase_lines=("quantity", "size"),
        purchase_orders=("invoice_no_key", "nunique"), units=("quantity", "sum"),
        gross_purchase_millipounds=("line_value_millipounds", "sum")).reset_index()
    latest = sales.dropna(subset=["description_clean"]).sort_values(
        ["invoice_timestamp", "source_row_number"]).drop_duplicates("stock_code_key", keep="last")
    products["product_description"] = products.stock_code_key.map(latest.set_index("stock_code_key").description_clean).fillna(products.stock_code_key)
    products["value_rank"] = products.gross_purchase_millipounds.rank(method="dense", ascending=False).astype("int64")
    same(results["products"], products, products.columns.tolist(), ["stock_code_key"], "products")

    countries = orders.groupby("country").agg(purchase_orders=("invoice_no_key", "size"),
        purchase_lines=("line_count", "sum"), identified_customers=("customer_id", "nunique"),
        units=("units", "sum"), gross_purchase_millipounds=("gross_purchase_millipounds", "sum")).reset_index()
    same(results["countries"], countries, countries.columns.tolist(), ["country"], "countries")
    for _, row in results["countries"].iterrows():
        require(abs(row.gross_aov_gbp - row.gross_purchase_millipounds / (1000 * row.purchase_orders)) < 1e-9,
                "Country AOV differs.")
        require(abs(row.value_share_percent - 100 * row.gross_purchase_millipounds / value) < 1e-9,
                "Country share differs.")

    orders["month"] = orders.order_timestamp.str[:7]
    months = orders.groupby("month").agg(purchase_orders=("invoice_no_key", "size"),
        purchase_lines=("line_count", "sum"), units=("units", "sum"),
        gross_purchase_millipounds=("gross_purchase_millipounds", "sum")).reset_index()
    same(results["monthly_sales"], months, months.columns.tolist(), ["month"], "monthly_sales")
    previous = None
    for _, row in results["monthly_sales"].iterrows():
        complete = row.month != "2011-12"
        require(row.is_complete_month == int(complete), "Partial-month flag differs.")
        require(abs(row.gross_aov_gbp - row.gross_purchase_millipounds / (1000 * row.purchase_orders)) < 1e-9,
                "Monthly AOV differs.")
        adjacent = previous is not None and (pd.Period(row.month, freq="M") - 1 == pd.Period(previous.month, freq="M"))
        if previous is None or not complete or not previous.is_complete_month or not adjacent:
            require(pd.isna(row.full_month_growth_percent), "Invalid full-month growth comparison.")
        else:
            growth = 100 * (row.gross_purchase_millipounds / previous.gross_purchase_millipounds - 1)
            require(abs(growth - row.full_month_growth_percent) < 1e-9, "Monthly growth differs.")
        previous = row

    customers = orders.dropna(subset=["customer_id"]).groupby("customer_id").agg(
        purchase_orders=("invoice_no_key", "size"), purchase_lines=("line_count", "sum"), units=("units", "sum"),
        gross_purchase_millipounds=("gross_purchase_millipounds", "sum"),
        first_purchase_timestamp=("order_timestamp", "min"), last_purchase_timestamp=("order_timestamp", "max")).reset_index()
    same(results["customers"], customers, customers.columns.tolist(), ["customer_id"], "customers")
    aov = results["customers"].gross_purchase_millipounds / (1000 * results["customers"].purchase_orders)
    require((aov - results["customers"].gross_aov_gbp).abs().lt(1e-9).all(), "Customer AOV differs.")
    for name in ["products", "countries", "monthly_sales", "orders"]:
        require(int(results[name].gross_purchase_millipounds.sum()) == value, f"Non-additive value totals: {name}")
    require(int(results["customers"].gross_purchase_millipounds.sum()) == expected["identified_purchase_millipounds"],
            "Customer purchase values do not reconcile.")
    return {name: "all_rows_and_measures_passed" for name in QUERIES}


def main():
    imported = load_analysis()
    with closing(sqlite3.connect(f"{ANALYSIS_DB.as_uri()}?mode=ro", uri=True)) as connection:
        results = {name: pd.read_sql_query((ROOT / "sql" / filename).read_text(encoding="utf-8"), connection)
                   for name, filename in QUERIES.items()}
    sales = read_export(ROOT / "data" / "processed" / "sales_transactions.csv.gz")
    checks = reconcile(results, sales)
    output = ROOT / "data" / "processed" / "sql_analysis"
    output.mkdir(exist_ok=True)
    for name, frame in results.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    customers = results["customers"]
    report = {
        "currency": "GBP", "integer_value_scale": 1000, "measure": "gross_merchandise_purchases_before_credits",
        "duplicate_baseline": "retain_all_source_rows", "source_window": ["2010-12-01", "2011-12-09"],
        "analysis_records_sha256": imported["ledger_records_sha256"],
        "query_sha256": {name: sha256((ROOT / "sql" / filename).read_bytes()).hexdigest() for name, filename in QUERIES.items()},
        "reconciliation": checks, "sales_summary": results["sales_summary"].to_dict(orient="records")[0],
        "leading_products": results["products"].head(10).to_dict(orient="records"),
        "leading_countries": results["countries"].head(10).to_dict(orient="records"),
        "monthly_sales": json.loads(results["monthly_sales"].to_json(orient="records", double_precision=15)),
        "customer_purchase_summary": {"identified_customers": len(customers),
            "one_order_customers": int(customers.purchase_orders.eq(1).sum()),
            "repeat_customers": int(customers.purchase_orders.ge(2).sum()),
            "repeat_customer_share_percent": 100 * float(customers.purchase_orders.ge(2).mean())},
    }
    (ROOT / "reports" / "04_sql_summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"reconciliation": checks, "sales_summary": report["sales_summary"],
                      "customer_purchase_summary": report["customer_purchase_summary"]}, indent=2))
    return report


if __name__ == "__main__":
    main()
