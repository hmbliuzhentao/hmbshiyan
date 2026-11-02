-- Business tables reference SQL. Actual installation uses SQLAlchemy create_all()
-- and will CREATE ONLY MISSING TABLES; do not execute this manually on your server.
CREATE TABLE IF NOT EXISTS business_orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(40) UNIQUE NOT NULL,
    client_name VARCHAR(120) NOT NULL,
    contact VARCHAR(120) NOT NULL DEFAULT '',
    title VARCHAR(200) NOT NULL,
    service_type VARCHAR(80) NOT NULL DEFAULT '视频剪辑',
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    amount_cents INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
    order_date DATE NOT NULL,
    due_date DATE,
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS order_payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES business_orders(id) ON DELETE RESTRICT,
    amount_cents INTEGER NOT NULL,
    received_on DATE NOT NULL,
    method VARCHAR(40) NOT NULL DEFAULT '银行转账',
    remark VARCHAR(300) NOT NULL DEFAULT '',
    is_void BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS order_events (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES business_orders(id) ON DELETE RESTRICT,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(40) NOT NULL,
    detail VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
