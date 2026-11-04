-- V2.1.0 PostgreSQL reference fragment only; NOT an auto-executed migration.
-- Canonical schema is defined by backend/app/*.py SQLAlchemy models.
-- Existing deployments must use the additive migration in main.apply_v21_migrations().

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE,
  phone VARCHAR(40) UNIQUE,
  name VARCHAR(80) NOT NULL,
  password_hash VARCHAR(255),
  role VARCHAR(16) NOT NULL DEFAULT 'producer',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT users_role_ck CHECK (role IN ('admin','producer','merchant'))
);

CREATE TABLE IF NOT EXISTS oauth_states (
  id BIGSERIAL PRIMARY KEY,
  nonce_hash VARCHAR(64) NOT NULL UNIQUE,
  mode VARCHAR(16) NOT NULL,
  role VARCHAR(16) NOT NULL DEFAULT 'merchant',
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Existing publish_tasks_v14 rows are preserved. V2.1 adds nullable assignment columns.
ALTER TABLE publish_tasks_v14 ADD COLUMN IF NOT EXISTS assigned_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE publish_tasks_v14 ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ;
ALTER TABLE publish_tasks_v14 ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_publish_tasks_v14_assigned_user_id ON publish_tasks_v14(assigned_user_id);
