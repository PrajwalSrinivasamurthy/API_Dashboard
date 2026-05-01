-- Per-key budget, threshold flag, security events, spike-friendly index. Idempotent.

IF COL_LENGTH('dbo.project_keys', 'budget_usd') IS NULL
BEGIN
    ALTER TABLE dbo.project_keys ADD budget_usd DECIMAL(12, 2) NOT NULL CONSTRAINT DF_project_keys_budget DEFAULT (25.00);
END
GO

IF COL_LENGTH('dbo.project_keys', 'budget_warn_sent') IS NULL
BEGIN
    ALTER TABLE dbo.project_keys ADD budget_warn_sent BIT NOT NULL CONSTRAINT DF_project_keys_budget_warn DEFAULT (0);
END
GO

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

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE i.name = N'idx_usage_logs_key_created' AND t.name = N'usage_logs' AND s.name = N'dbo'
)
    CREATE NONCLUSTERED INDEX idx_usage_logs_key_created ON dbo.usage_logs (project_key_id, created_at);
GO
