-- Order-cohort month, using earliest eligible invoice timestamp.
-- The known extract ends 9 December 2011: suppress its full-month growth comparison.
WITH monthly AS (
    SELECT SUBSTR(order_timestamp, 1, 7) AS month, COUNT(*) AS purchase_orders,
           SUM(line_count) AS purchase_lines, SUM(units) AS units,
           SUM(gross_purchase_millipounds) AS gross_purchase_millipounds,
           CASE WHEN SUBSTR(order_timestamp, 1, 7) = '2011-12' THEN 0 ELSE 1 END AS is_complete_month
    FROM purchase_orders GROUP BY SUBSTR(order_timestamp, 1, 7)
), comparisons AS (
    SELECT *, LAG(gross_purchase_millipounds) OVER (ORDER BY month) AS previous_value,
           LAG(is_complete_month) OVER (ORDER BY month) AS previous_complete,
           LAG(month) OVER (ORDER BY month) AS previous_month
    FROM monthly
)
SELECT month, purchase_orders, purchase_lines, units, gross_purchase_millipounds, is_complete_month,
       gross_purchase_millipounds / (1000.0 * purchase_orders) AS gross_aov_gbp,
       CASE WHEN is_complete_month = 1 AND previous_complete = 1 AND previous_value > 0
                 AND date(month || '-01', '-1 month') = date(previous_month || '-01')
            THEN 100.0 * (gross_purchase_millipounds - previous_value) / previous_value
            ELSE NULL END AS full_month_growth_percent
FROM comparisons ORDER BY month;
