
IF OBJECT_ID(N'dbo.dashboard_users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dashboard_users (
        id              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        email           NVARCHAR(255) NOT NULL,
        password_hash   NVARCHAR(255) NOT NULL,
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
