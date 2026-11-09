-- One row per eligible invoice, before credits. Amount is exact integer thousandths GBP.
SELECT invoice_no_key, order_timestamp, country, customer_id, line_count, units,
       gross_purchase_millipounds
FROM purchase_orders ORDER BY invoice_no_key;
