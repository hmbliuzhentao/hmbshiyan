-- VideoHub PostgreSQL reference schema.
-- NOTE: This is documentation, NOT an auto-executed migration.
-- The running MVP creates the first three tables using SQLAlchemy.
-- Upgrade production databases with versioned Alembic migrations.

-- MVP core
CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(80) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(16) NOT NULL DEFAULT 'viewer',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT users_role_ck CHECK (role IN ('admin','viewer'))
);
CREATE TABLE IF NOT EXISTS videos (
  id VARCHAR(36) PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  storage_key VARCHAR(100) NOT NULL UNIQUE,
  mime VARCHAR(100) NOT NULL,
  size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
  status VARCHAR(20) NOT NULL DEFAULT 'ready',
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS videos_created_at_idx ON videos(created_at DESC);
CREATE TABLE IF NOT EXISTS tasks (
  id BIGSERIAL PRIMARY KEY,
  type VARCHAR(32) NOT NULL,
  status VARCHAR(20) NOT NULL,
  detail VARCHAR(255) NOT NULL,
  video_id VARCHAR(36) REFERENCES videos(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- V2 roadmap tables: do not assume these APIs are already implemented.
CREATE TABLE IF NOT EXISTS platform_accounts (
  id BIGSERIAL PRIMARY KEY,
  owner_id BIGINT NOT NULL REFERENCES users(id),
  provider VARCHAR(32) NOT NULL,
  platform_user_id VARCHAR(255) NOT NULL,
  display_name VARCHAR(255),
  credential_ref VARCHAR(255), -- reference to encrypted credentials in a secrets store
  linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, platform_user_id)
);
CREATE TABLE IF NOT EXISTS video_metrics_daily (
  id BIGSERIAL PRIMARY KEY,
  video_id VARCHAR(36) NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  platform_account_id BIGINT REFERENCES platform_accounts(id),
  metric_date DATE NOT NULL,
  views BIGINT NOT NULL DEFAULT 0,
  likes BIGINT NOT NULL DEFAULT 0,
  comments BIGINT NOT NULL DEFAULT 0,
  shares BIGINT NOT NULL DEFAULT 0,
  source VARCHAR(32) NOT NULL DEFAULT 'own_platform',
  UNIQUE(video_id, platform_account_id, metric_date)
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  actor_id BIGINT REFERENCES users(id),
  action VARCHAR(100) NOT NULL,
  target_type VARCHAR(50),
  target_id VARCHAR(100),
  detail JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS audit_logs_created_idx ON audit_logs(created_at DESC);
