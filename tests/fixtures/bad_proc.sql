-- A poorly written stored procedure (should trigger multiple rule findings)
CREATE PROCEDURE sp_GetData
AS
BEGIN
    -- Missing SET ANSI_NULLS ON
    -- Missing SET QUOTED_IDENTIFIER ON
    -- Missing SET NOCOUNT ON
    -- No TRY/CATCH
    -- sp_ prefix
    -- SELECT *
    -- Unqualified table references
    -- NOLOCK hint
    -- ORDER BY without TOP
    -- PRINT statement
    -- NULL comparison with =

    PRINT 'Starting GetData'

    SELECT * FROM Orders WITH (NOLOCK)
    WHERE CustomerId = NULL

    SELECT * FROM Customers
    ORDER BY CustomerName

    EXEC(@sql)

    -- Hardcoded credential
    DECLARE @pwd VARCHAR(50) = 'MyPassword123'

    DECLARE cur CURSOR FOR
        SELECT OrderId FROM Orders

    OPEN cur
    FETCH NEXT FROM cur INTO @id
    WHILE @@FETCH_STATUS = 0
    BEGIN
        FETCH NEXT FROM cur INTO @id
    END
    CLOSE cur
    DEALLOCATE cur
END
GO
