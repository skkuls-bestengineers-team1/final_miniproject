CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT NOT NULL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
    store_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    address     TEXT,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_code   TEXT PRIMARY KEY,
    product_name   TEXT NOT NULL,
    category_code  TEXT NOT NULL,
    price          INTEGER
);

CREATE TABLE IF NOT EXISTS inventory (
    store_id      TEXT NOT NULL REFERENCES stores(store_id),
    product_code  TEXT NOT NULL REFERENCES products(product_code),
    quantity      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (store_id, product_code)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id         TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES users(user_id),
    product_code     TEXT NOT NULL REFERENCES products(product_code),
    option           TEXT,
    order_date       TEXT NOT NULL,
    delivery_status  TEXT NOT NULL CHECK (delivery_status IN ('PREPARING','SHIPPED','IN_TRANSIT','DELIVERED')),
    expected_date    TEXT,
    delivered_date   TEXT,
    ship_address     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    request_type    TEXT NOT NULL CHECK (request_type IN ('ADDRESS_CHANGE','EXCHANGE','REFUND')),
    method          TEXT CHECK (method IN ('STORE_VISIT','PICKUP')),
    new_address     TEXT,
    pickup_address  TEXT,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','DONE')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS inquiries (
    inquiry_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    product_code        TEXT REFERENCES products(product_code),
    inquiry_type_code   TEXT,
    inquiry_text        TEXT NOT NULL,
    handled_by          TEXT,
    priority_level      INTEGER CHECK (priority_level BETWEEN 1 AND 4),
    answer_status_code  TEXT NOT NULL DEFAULT 'WAITING' CHECK (answer_status_code IN ('WAITING','IN_PROGRESS','ANSWERED')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
