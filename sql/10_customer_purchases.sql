-- Identified customers only. Frequency is distinct eligible invoices in this extract.
SELECT customer_id, COUNT(*) AS purchase_orders, SUM(line_count) AS purchase_lines,
       SUM(units) AS units, SUM(gross_purchase_millipounds) AS gross_purchase_millipounds,
       MIN(order_timestamp) AS first_purchase_timestamp,
       MAX(order_timestamp) AS last_purchase_timestamp,
       SUM(gross_purchase_millipounds) / (1000.0 * COUNT(*)) AS gross_aov_gbp
FROM purchase_orders WHERE customer_id IS NOT NULL
GROUP BY customer_id ORDER BY gross_purchase_millipounds DESC, customer_id;
