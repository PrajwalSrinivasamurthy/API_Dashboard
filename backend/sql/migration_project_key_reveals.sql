-- One-time virtual key reveal links (idempotent). Run on existing MSSQL DBs.
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
