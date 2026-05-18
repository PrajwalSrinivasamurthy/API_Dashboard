
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

IF COL_LENGTH('dbo.dashboard_users', 'project') IS NULL
BEGIN
    ALTER TABLE dbo.dashboard_users
    ADD project NVARCHAR(255) NOT NULL CONSTRAINT DF_dashboard_users_project DEFAULT ('');
END
GO

IF COL_LENGTH('dbo.dashboard_users', 'permissions') IS NULL
BEGIN
    ALTER TABLE dbo.dashboard_users
    ADD permissions NVARCHAR(255) NULL;
END
GO

IF COL_LENGTH('dbo.dashboard_users', 'token_version') IS NULL
BEGIN
    ALTER TABLE dbo.dashboard_users
    ADD token_version INT NOT NULL CONSTRAINT DF_dashboard_users_token_version DEFAULT (1);
END
GO
