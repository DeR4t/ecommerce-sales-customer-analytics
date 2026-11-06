-- Raw source layer: retain every workbook row, including repeated records.
CREATE TABLE raw_transactions (
    source_row_number INTEGER PRIMARY KEY CHECK (source_row_number >= 2),
    invoice_no TEXT,
    stock_code TEXT,
    description TEXT,
    quantity INTEGER,
    invoice_date TEXT,
    unit_price REAL,
    customer_id TEXT,
    country TEXT
);

CREATE TABLE ingestion_metadata (
    ingestion_id INTEGER PRIMARY KEY CHECK (ingestion_id = 1),
    source_file TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_row_count INTEGER NOT NULL,
    source_records_sha256 TEXT NOT NULL,
    loaded_at_utc TEXT NOT NULL,
    schema_version INTEGER NOT NULL
);
