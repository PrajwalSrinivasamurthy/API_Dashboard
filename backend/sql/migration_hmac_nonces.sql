SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

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
