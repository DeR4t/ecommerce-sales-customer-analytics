-- Source-level reconciliation; counts include purchases, credits and adjustments.
SELECT
    COUNT(*) AS row_count,
    MIN(source_row_number) AS first_source_row,
    MAX(source_row_number) AS last_source_row,
    COUNT(DISTINCT invoice_no) AS distinct_invoice_ids,
    COUNT(DISTINCT customer_id) AS distinct_known_customer_ids,
    MIN(invoice_date) AS first_invoice_timestamp,
    MAX(invoice_date) AS last_invoice_timestamp,
    SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS missing_customer_ids,
    SUM(CASE WHEN description IS NULL THEN 1 ELSE 0 END) AS missing_descriptions,
    SUM(CASE WHEN quantity < 0 THEN 1 ELSE 0 END) AS negative_quantity_rows,
    SUM(CASE WHEN unit_price = 0 THEN 1 ELSE 0 END) AS zero_price_rows,
    SUM(CASE WHEN unit_price < 0 THEN 1 ELSE 0 END) AS negative_price_rows,
    SUM(CASE WHEN UPPER(SUBSTR(invoice_no, 1, 1)) = 'C' THEN 1 ELSE 0 END) AS c_prefixed_rows
FROM raw_transactions;
