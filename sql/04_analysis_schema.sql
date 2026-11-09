-- Separate analytical database; the original raw database remains unchanged.
CREATE TABLE transaction_ledger (
    source_row_number INTEGER PRIMARY KEY CHECK (source_row_number >= 2),
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL,
    invoice_date TEXT NOT NULL,
    unit_price REAL NOT NULL,
    customer_id TEXT,
    country TEXT NOT NULL,
    invoice_timestamp TEXT NOT NULL,
    invoice_no_key TEXT NOT NULL,
    description_clean TEXT,
    customer_id_key TEXT,
    country_clean TEXT NOT NULL,
    stock_code_key TEXT NOT NULL,
    item_class TEXT NOT NULL CHECK (item_class IN ('merchandise', 'non_merchandise', 'unresolved')),
    is_cancellation INTEGER NOT NULL CHECK (is_cancellation IN (0, 1)),
    has_customer_id INTEGER NOT NULL CHECK (has_customer_id IN (0, 1)),
    is_exact_copy_beyond_first INTEGER NOT NULL CHECK (is_exact_copy_beyond_first IN (0, 1)),
    unit_price_millipounds INTEGER NOT NULL,
    line_value_millipounds INTEGER NOT NULL,
    row_status TEXT NOT NULL CHECK (row_status IN ('eligible_purchase', 'cancellation',
        'nonpositive_quantity', 'nonpositive_price', 'non_merchandise', 'unresolved_item')),
    is_sales_eligible INTEGER NOT NULL CHECK (is_sales_eligible IN (0, 1)),
    is_customer_eligible INTEGER NOT NULL CHECK (is_customer_eligible IN (0, 1)),
    CHECK (line_value_millipounds = quantity * unit_price_millipounds),
    CHECK (has_customer_id = (customer_id_key IS NOT NULL)),
    CHECK (is_sales_eligible = (row_status = 'eligible_purchase')),
    CHECK (is_customer_eligible = (is_sales_eligible AND has_customer_id)),
    CHECK (NOT is_sales_eligible OR
        (quantity > 0 AND unit_price_millipounds > 0 AND NOT is_cancellation AND item_class = 'merchandise'))
) STRICT;

CREATE TABLE analysis_metadata (
    metadata_id INTEGER PRIMARY KEY CHECK (metadata_id = 1),
    provenance_json TEXT NOT NULL,
    ledger_records_sha256 TEXT NOT NULL,
    loaded_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX ledger_invoice ON transaction_ledger(invoice_no_key);
CREATE INDEX ledger_product ON transaction_ledger(stock_code_key);
CREATE INDEX ledger_customer ON transaction_ledger(customer_id_key);

CREATE VIEW sales_transactions AS
SELECT * FROM transaction_ledger WHERE is_sales_eligible = 1;

CREATE VIEW customer_transactions AS
SELECT * FROM transaction_ledger WHERE is_customer_eligible = 1;

-- The loader checks that each eligible invoice has at most one country/customer.
-- Allocate every eligible line of an invoice to its earliest eligible timestamp.
CREATE VIEW purchase_orders AS
SELECT invoice_no_key, MIN(invoice_timestamp) AS order_timestamp,
       MIN(country_clean) AS country, MIN(customer_id_key) AS customer_id,
       COUNT(*) AS line_count, SUM(quantity) AS units,
       SUM(line_value_millipounds) AS gross_purchase_millipounds
FROM sales_transactions
GROUP BY invoice_no_key;
