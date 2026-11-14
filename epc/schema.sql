CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE source_files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    record_size INTEGER NOT NULL,
    xor_mask INTEGER NOT NULL
);

CREATE TABLE catalogs (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    local_code TEXT NOT NULL,
    region TEXT NOT NULL,
    name TEXT NOT NULL,
    model_codes TEXT NOT NULL,
    production_from TEXT,
    production_to TEXT,
    revision TEXT,
    imported INTEGER NOT NULL,
    application_count INTEGER NOT NULL,
    record_count INTEGER NOT NULL,
    hnb_path TEXT NOT NULL,
    UNIQUE (region, local_code)
);

CREATE TABLE part_names (
    region TEXT NOT NULL,
    pnc TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (region, pnc)
) WITHOUT ROWID;

CREATE VIRTUAL TABLE names_search USING fts5(
    region UNINDEXED,
    pnc UNINDEXED,
    name,
    tokenize = 'unicode61'
);

CREATE TABLE figures (
    region TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (region, code)
) WITHOUT ROWID;

CREATE TABLE bindings (
    number TEXT NOT NULL,
    catalog_id INTEGER NOT NULL,
    pnc TEXT NOT NULL,
    figure TEXT NOT NULL
);

CREATE TABLE parts (
    number TEXT PRIMARY KEY,
    catalog_count INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE catalog_figures (
    catalog_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    part_count INTEGER NOT NULL,
    PRIMARY KEY (catalog_id, code)
) WITHOUT ROWID;

CREATE TABLE variants (
    id INTEGER PRIMARY KEY,
    catalog_id INTEGER NOT NULL,
    vin_prefix TEXT NOT NULL,
    model TEXT NOT NULL,
    frame TEXT NOT NULL,
    source_group TEXT NOT NULL,
    variant_code TEXT NOT NULL,
    production_from TEXT,
    production_to TEXT,
    engine TEXT NOT NULL,
    attributes TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_offset INTEGER NOT NULL
);

CREATE TABLE import_issues (
    source_path TEXT NOT NULL,
    source_offset INTEGER,
    reason TEXT NOT NULL,
    raw_hex TEXT
);

CREATE TABLE accessories (
    id INTEGER PRIMARY KEY,
    group_code TEXT NOT NULL,
    document TEXT NOT NULL,
    title TEXT NOT NULL,
    production_from TEXT,
    production_to TEXT,
    name TEXT NOT NULL,
    number TEXT NOT NULL,
    destination TEXT NOT NULL,
    quantity TEXT NOT NULL,
    notes TEXT NOT NULL,
    model_codes TEXT NOT NULL,
    image TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    raw_fields TEXT NOT NULL
);

CREATE VIRTUAL TABLE accessories_search USING fts5(
    name,
    number,
    title,
    model_codes,
    content = 'accessories',
    content_rowid = 'id'
);
