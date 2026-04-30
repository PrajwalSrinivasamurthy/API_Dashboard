-- Bind project keys to client IP (set when reveal link is opened). Idempotent.
IF COL_LENGTH('dbo.project_keys', 'allowed_client_ip') IS NULL
BEGIN
    ALTER TABLE dbo.project_keys ADD allowed_client_ip NVARCHAR(45) NULL;
END
GO
