-- One row per normalized item code; latest eligible non-null description is a label.
WITH labels AS (
    SELECT stock_code_key, description_clean,
           ROW_NUMBER() OVER (PARTITION BY stock_code_key
               ORDER BY invoice_timestamp DESC, source_row_number DESC) AS label_rank
    FROM sales_transactions WHERE description_clean IS NOT NULL
), products AS (
    SELECT stock_code_key, COUNT(*) AS purchase_lines,
           COUNT(DISTINCT invoice_no_key) AS purchase_orders, SUM(quantity) AS units,
           SUM(line_value_millipounds) AS gross_purchase_millipounds
    FROM sales_transactions GROUP BY stock_code_key
)
SELECT p.*, COALESCE(l.description_clean, p.stock_code_key) AS product_description,
       DENSE_RANK() OVER (ORDER BY p.gross_purchase_millipounds DESC) AS value_rank
FROM products AS p
LEFT JOIN labels AS l ON p.stock_code_key = l.stock_code_key AND l.label_rank = 1
ORDER BY p.gross_purchase_millipounds DESC, p.stock_code_key;
