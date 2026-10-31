-- V1.4 additional PostgreSQL schema (REFERENCE ONLY).
-- The application creates these new tables through SQLAlchemy Base.metadata.create_all
-- on initial startup; do NOT run this script blindly against an existing production DB.

CREATE TABLE IF NOT EXISTS publish_tasks_v14 (
 id SERIAL PRIMARY KEY,
 order_id INTEGER NOT NULL REFERENCES business_orders(id) ON DELETE RESTRICT,
 merchant_id INTEGER NOT NULL REFERENCES merchants(id) ON DELETE RESTRICT,
 title VARCHAR(200) NOT NULL,
 platform VARCHAR(40) NOT NULL DEFAULT 'TikTok',
 account_label VARCHAR(120) NOT NULL DEFAULT '',
 publish_date DATE,
 instructions TEXT NOT NULL DEFAULT '',
 status VARCHAR(32) NOT NULL DEFAULT 'draft',
 published_url VARCHAR(500) NOT NULL DEFAULT '',
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_task_videos_v14 (
 id SERIAL PRIMARY KEY,
 task_id INTEGER NOT NULL REFERENCES publish_tasks_v14(id) ON DELETE RESTRICT,
 video_id VARCHAR(36) NOT NULL REFERENCES videos(id) ON DELETE RESTRICT,
 active BOOLEAN NOT NULL DEFAULT true,
 review_status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
 review_note VARCHAR(2000) NOT NULL DEFAULT '',
 reviewed_by INTEGER REFERENCES users(id),
 reviewed_at TIMESTAMPTZ,
 submitted_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_review_events_v14 (
 id SERIAL PRIMARY KEY,
 task_id INTEGER NOT NULL REFERENCES publish_tasks_v14(id),
 link_id INTEGER NOT NULL REFERENCES publish_task_videos_v14(id),
 reviewer_id INTEGER NOT NULL REFERENCES users(id),
 decision VARCHAR(32) NOT NULL,
 note VARCHAR(2000) NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
