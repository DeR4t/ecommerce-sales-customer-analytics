-- Gross merchandise purchases before credits; anonymous purchases included.
SELECT COUNT(*) AS purchase_lines, COUNT(DISTINCT invoice_no_key) AS purchase_orders,
       COUNT(DISTINCT customer_id_key) AS identified_customers,
       SUM(quantity) AS units, SUM(line_value_millipounds) AS gross_purchase_millipounds,
       SUM(CASE WHEN customer_id_key IS NOT NULL THEN line_value_millipounds ELSE 0 END)
           AS identified_purchase_millipounds,
       SUM(CASE WHEN customer_id_key IS NULL THEN line_value_millipounds ELSE 0 END)
           AS anonymous_purchase_millipounds,
       SUM(line_value_millipounds) / (1000.0 * COUNT(DISTINCT invoice_no_key)) AS gross_aov_gbp
FROM sales_transactions;
