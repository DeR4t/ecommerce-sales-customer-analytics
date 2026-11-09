-- Source customer country, not an independently verified shipping destination.
SELECT country, COUNT(*) AS purchase_orders, SUM(line_count) AS purchase_lines,
       COUNT(DISTINCT customer_id) AS identified_customers, SUM(units) AS units,
       SUM(gross_purchase_millipounds) AS gross_purchase_millipounds,
       SUM(gross_purchase_millipounds) / (1000.0 * COUNT(*)) AS gross_aov_gbp,
       100.0 * SUM(gross_purchase_millipounds) /
           (SELECT SUM(gross_purchase_millipounds) FROM purchase_orders) AS value_share_percent
FROM purchase_orders GROUP BY country
ORDER BY gross_purchase_millipounds DESC, country;
