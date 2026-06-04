-- A well-written stored procedure (should produce very few findings)
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetCustomerOrders
    @CustomerId INT,
    @StartDate  DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRANSACTION;

        SELECT
            o.OrderId,
            o.OrderDate,
            o.TotalAmount,
            c.CustomerName
        FROM dbo.Orders      o
        JOIN dbo.Customers   c ON c.CustomerId = o.CustomerId
        WHERE o.CustomerId = @CustomerId
          AND (@StartDate IS NULL OR o.OrderDate >= @StartDate);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END
GO
