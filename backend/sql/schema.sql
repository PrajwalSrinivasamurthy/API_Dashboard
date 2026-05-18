

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* project_keys */
IF OBJECT_ID(N'dbo.project_keys', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.project_keys (
        id                  INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [key]               NVARCHAR(255) NOT NULL,
        [name]              NVARCHAR(255) NOT NULL,
        budget_usd          DECIMAL(12, 2) NOT NULL CONSTRAINT DF_project_keys_budget DEFAULT (25.00),
        budget_warn_sent    BIT NOT NULL CONSTRAINT DF_project_keys_budget_warn DEFAULT (0),
        active              BIT NOT NULL CONSTRAINT DF_project_keys_active DEFAULT (1),
        used_tokens   BIGINT NOT NULL CONSTRAINT DF_project_keys_used_tokens DEFAULT (0),
        created_at    DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_project_keys_created DEFAULT (SYSUTCDATETIME()),
        updated_at    DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_project_keys_updated DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_project_keys_key UNIQUE ([key])
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_project_keys_active' AND t.name = N'project_keys' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_project_keys_active ON dbo.project_keys (active);
GO

/* usage_logs */
IF OBJECT_ID(N'dbo.usage_logs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.usage_logs (
        id                  INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        project_key_id      INT NOT NULL,
        prompt_tokens       INT NOT NULL CONSTRAINT DF_usage_logs_prompt DEFAULT (0),
        completion_tokens   INT NOT NULL CONSTRAINT DF_usage_logs_completion DEFAULT (0),
        total_tokens        INT NOT NULL CONSTRAINT DF_usage_logs_total DEFAULT (0),
        cost                DECIMAL(14, 6) NOT NULL CONSTRAINT DF_usage_logs_cost DEFAULT (0),
        model               NVARCHAR(128) NULL,
        created_at          DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_usage_logs_created DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_usage_logs_project_key
            FOREIGN KEY (project_key_id) REFERENCES dbo.project_keys (id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_usage_logs_project_key_id' AND t.name = N'usage_logs' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_usage_logs_project_key_id ON dbo.usage_logs (project_key_id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_usage_logs_created_at' AND t.name = N'usage_logs' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_usage_logs_created_at ON dbo.usage_logs (created_at);
GO

/* dashboard_users */
IF OBJECT_ID(N'dbo.dashboard_users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dashboard_users (
        id              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        email           NVARCHAR(255) NOT NULL,
        password_hash   NVARCHAR(255) NOT NULL,
        project         NVARCHAR(255) NOT NULL CONSTRAINT DF_dashboard_users_project DEFAULT (''),
        permissions     NVARCHAR(255) NULL,
        token_version   INT NOT NULL CONSTRAINT DF_dashboard_users_token_version DEFAULT (1),
        created_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_dashboard_users_created DEFAULT (SYSUTCDATETIME()),
        updated_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_dashboard_users_updated DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_dashboard_users_email UNIQUE (email)
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_dashboard_users_email' AND t.name = N'dashboard_users' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_dashboard_users_email ON dbo.dashboard_users (email);
GO

/* One-time share links for newly created virtual keys */
IF OBJECT_ID(N'dbo.project_key_reveals', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.project_key_reveals (
        id              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        token           NVARCHAR(64) NOT NULL,
        project_key_id  INT NOT NULL,
        expires_at      DATETIMEOFFSET(7) NOT NULL,
        consumed_at     DATETIMEOFFSET(7) NULL,
        created_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_project_key_reveals_created DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_project_key_reveals_token UNIQUE (token),
        CONSTRAINT FK_project_key_reveals_project
            FOREIGN KEY (project_key_id) REFERENCES dbo.project_keys (id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_project_key_reveals_token' AND t.name = N'project_key_reveals' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_project_key_reveals_token ON dbo.project_key_reveals (token);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_project_key_reveals_project_key_id' AND t.name = N'project_key_reveals' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_project_key_reveals_project_key_id ON dbo.project_key_reveals (project_key_id);
GO

/* Security / limit audit trail */
IF OBJECT_ID(N'dbo.project_key_security_events', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.project_key_security_events (
        id              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        project_key_id  INT NOT NULL,
        event_type      NVARCHAR(64) NOT NULL,
        client_ip       NVARCHAR(45) NULL,
        detail          NVARCHAR(2000) NULL,
        created_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_project_key_security_events_created DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_project_key_security_events_project
            FOREIGN KEY (project_key_id) REFERENCES dbo.project_keys (id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_project_key_security_events_key_time' AND t.name = N'project_key_security_events' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_project_key_security_events_key_time
        ON dbo.project_key_security_events (project_key_id, created_at);
GO

/* HMAC nonce replay protection */
IF OBJECT_ID(N'dbo.hmac_nonces', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.hmac_nonces (
        id              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        project_key_id  INT NOT NULL,
        nonce           NVARCHAR(128) NOT NULL,
        expires_at      DATETIMEOFFSET(7) NOT NULL,
        created_at      DATETIMEOFFSET(7) NOT NULL CONSTRAINT DF_hmac_nonces_created DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_hmac_nonces_project
            FOREIGN KEY (project_key_id) REFERENCES dbo.project_keys (id) ON DELETE CASCADE,
        CONSTRAINT UQ_hmac_nonces_key_nonce UNIQUE (project_key_id, nonce)
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_hmac_nonces_expires_at' AND t.name = N'hmac_nonces' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_hmac_nonces_expires_at ON dbo.hmac_nonces (expires_at);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_usage_logs_key_created' AND t.name = N'usage_logs' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_usage_logs_key_created ON dbo.usage_logs (project_key_id, created_at);
GO
