-- Independent status and exact-value reconciliation against raw source rows.
-- The caller supplies temp.reviewed_item_codes from the reviewed CSV rules.
WITH classified AS (
    SELECT
        CASE
            WHEN UPPER(TRIM(r.invoice_no)) LIKE 'C%' THEN 'cancellation'
            WHEN r.quantity <= 0 THEN 'nonpositive_quantity'
            WHEN r.unit_price <= 0 THEN 'nonpositive_price'
            WHEN c.item_class = 'non_merchandise' THEN 'non_merchandise'
            WHEN c.item_class = 'unresolved' THEN 'unresolved_item'
            ELSE 'eligible_purchase'
        END AS row_status,
        r.quantity * CAST(ROUND(r.unit_price * 1000) AS INTEGER) AS line_value_millipounds
    FROM raw_transactions AS r
    LEFT JOIN temp.reviewed_item_codes AS c
        ON UPPER(TRIM(r.stock_code)) = c.stock_code_key
)
SELECT row_status, COUNT(*) AS rows, SUM(line_value_millipounds) AS line_value_millipounds
FROM classified
GROUP BY row_status
ORDER BY row_status;
