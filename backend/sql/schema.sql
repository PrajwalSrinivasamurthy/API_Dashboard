

CREATE TABLE IF NOT EXISTS project_keys (
    id              SERIAL PRIMARY KEY,
    key             VARCHAR(255) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    used_tokens     BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_project_keys_active ON project_keys (active);

CREATE TABLE IF NOT EXISTS usage_logs (
    id                  SERIAL PRIMARY KEY,
    project_key_id      INTEGER NOT NULL REFERENCES project_keys (id) ON DELETE CASCADE,
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens        INTEGER NOT NULL DEFAULT 0,
    cost                NUMERIC(14, 6) NOT NULL DEFAULT 0,
    model               VARCHAR(128) NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_project_key_id ON usage_logs (project_key_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs (created_at);

-- Whitelisted dashboard logins (email + bcrypt password_hash). No public signup.
CREATE TABLE IF NOT EXISTS dashboard_users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dashboard_users_email ON dashboard_users (email);
