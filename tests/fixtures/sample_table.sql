-- Sample table DDL — missing PK to trigger DS / schema checks
CREATE TABLE dbo.AuditLog (
    LogId        INT           NOT NULL,
    EventType    VARCHAR(50)   NOT NULL,
    EventDate    DATETIME      NOT NULL DEFAULT GETDATE(),
    UserId       INT,
    Description  VARCHAR(MAX),   -- triggers DS006 unbounded varchar
    IpAddress    VARCHAR(15),
    SessionId    NVARCHAR(MAX)   -- another unbounded column
);
-- No PRIMARY KEY → triggers tables_without_pk check
