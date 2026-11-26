/* Apply after migrations. The application DB principal needs EXECUTE on sp_set_session_context. */
CREATE OR ALTER TRIGGER dbo.tr_journal_entries_posting_integrity
ON dbo.journal_entries
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted WHERE status = 'POSTED')
    BEGIN
        IF EXISTS (
            SELECT i.company_id, i.id
            FROM inserted AS i
            LEFT JOIN dbo.journal_lines AS jl
                ON jl.company_id = i.company_id AND jl.journal_id = i.id
            WHERE i.status = 'POSTED'
            GROUP BY i.company_id, i.id
            HAVING COUNT(jl.id) < 2
                OR ABS(COALESCE(SUM(jl.base_debit), 0) - COALESCE(SUM(jl.base_credit), 0)) >= 0.0001
        )
        BEGIN
            THROW 51001, 'A posted journal must have at least two lines and balance in functional currency.', 1;
        END;
    END;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_journal_entries_immutable
ON dbo.journal_entries
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE status = 'POSTED')
        THROW 51002, 'Posted journal entries are immutable. Create a reversing journal instead.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_journal_lines_immutable
ON dbo.journal_lines
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT company_id, journal_id FROM inserted
            UNION
            SELECT company_id, journal_id FROM deleted
        ) AS touched
        JOIN dbo.journal_entries AS je
          ON je.company_id = touched.company_id AND je.id = touched.journal_id
        WHERE je.status = 'POSTED'
    )
        THROW 51003, 'Lines on a posted journal are immutable. Create a reversing journal instead.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_posted_sales_documents_immutable
ON dbo.sales_invoices
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE status = 'POSTED')
        THROW 51004, 'Posted sales invoices are immutable. Use a credit note or reversal workflow.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_sales_invoice_post_integrity
ON dbo.sales_invoices
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM inserted AS invoice
        WHERE invoice.status = 'POSTED'
          AND (
              invoice.total_amount <> invoice.subtotal + invoice.tax_amount
              OR invoice.functional_total <> invoice.functional_subtotal + invoice.functional_tax
              OR NOT EXISTS (
                  SELECT 1 FROM dbo.journal_entries AS journal
                  WHERE journal.company_id = invoice.company_id
                    AND journal.source_type = 'SALES_INVOICE'
                    AND journal.source_id = CONVERT(nvarchar(80), invoice.id)
                    AND journal.status = 'POSTED'
              )
              OR NOT EXISTS (SELECT 1 FROM dbo.sales_invoice_lines AS line
                             WHERE line.company_id = invoice.company_id AND line.invoice_id = invoice.id)
          )
    ) THROW 51010, 'A sales invoice needs lines, consistent totals, and a posted journal before posting.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_posted_sales_lines_immutable
ON dbo.sales_invoice_lines
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1
        FROM (SELECT company_id, invoice_id FROM inserted UNION SELECT company_id, invoice_id FROM deleted) AS touched
        JOIN dbo.sales_invoices AS invoice
          ON invoice.company_id = touched.company_id AND invoice.id = touched.invoice_id
        WHERE invoice.status = 'POSTED'
    ) THROW 51005, 'Lines on a posted sales invoice are immutable.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_posted_purchase_documents_immutable
ON dbo.purchase_bills
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE status = 'POSTED')
        THROW 51006, 'Posted purchase bills are immutable. Use a supplier credit or reversal workflow.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_purchase_bill_post_integrity
ON dbo.purchase_bills
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM inserted AS bill
        WHERE bill.status = 'POSTED'
          AND NOT EXISTS (
              SELECT 1 FROM dbo.journal_entries AS journal
              WHERE journal.company_id = bill.company_id
                AND journal.source_type = 'PURCHASE_BILL'
                AND journal.source_id = CONVERT(nvarchar(80), bill.id)
                AND journal.status = 'POSTED'
          )
    ) THROW 51011, 'A posted purchase bill needs a posted journal.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_posted_purchase_lines_immutable
ON dbo.purchase_bill_lines
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1
        FROM (SELECT company_id, bill_id FROM inserted UNION SELECT company_id, bill_id FROM deleted) AS touched
        JOIN dbo.purchase_bills AS bill
          ON bill.company_id = touched.company_id AND bill.id = touched.bill_id
        WHERE bill.status = 'POSTED'
    ) THROW 51007, 'Lines on a posted purchase bill are immutable.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_posted_expenses_immutable
ON dbo.expenses
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE status = 'POSTED')
        THROW 51008, 'Posted expenses are immutable. Record a correcting journal instead.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_expense_post_integrity
ON dbo.expenses
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM inserted AS expense
        WHERE expense.status = 'POSTED'
          AND NOT EXISTS (
              SELECT 1 FROM dbo.journal_entries AS journal
              WHERE journal.company_id = expense.company_id
                AND journal.source_type = 'EXPENSE'
                AND journal.source_id = CONVERT(nvarchar(80), expense.id)
                AND journal.status = 'POSTED'
          )
    ) THROW 51012, 'A posted expense needs a posted journal.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.tr_stock_movements_append_only
ON dbo.stock_movements
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted)
        THROW 51009, 'Stock movements are append-only. Record a correcting movement.', 1;
END;
GO

/* The API sets company_id in SQL Server SESSION_CONTEXT after it validates membership.
   Companies, memberships, users, currencies and date dimensions are deliberately global. */
IF EXISTS (SELECT 1 FROM sys.security_policies WHERE name = N'tenant_policy' AND schema_id = SCHEMA_ID(N'dbo'))
    DROP SECURITY POLICY dbo.tenant_policy;
GO

CREATE OR ALTER FUNCTION dbo.fn_tenant_access(@company_id int)
RETURNS TABLE WITH SCHEMABINDING
AS
RETURN SELECT 1 AS fn_tenant_access_result
WHERE @company_id = TRY_CONVERT(int, SESSION_CONTEXT(N'company_id'));
GO

DECLARE @clauses nvarchar(max) = N'';
DECLARE @table sysname;
DECLARE tenant_tables CURSOR LOCAL FAST_FORWARD FOR
    SELECT DISTINCT t.name
    FROM sys.tables AS t
    JOIN sys.columns AS c ON c.object_id = t.object_id
    WHERE SCHEMA_NAME(t.schema_id) = N'dbo'
      AND c.name = N'company_id'
      AND t.name NOT IN (N'companies', N'company_memberships');
OPEN tenant_tables;
FETCH NEXT FROM tenant_tables INTO @table;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @clauses += N'ADD FILTER PREDICATE dbo.fn_tenant_access(company_id) ON dbo.' + QUOTENAME(@table)
        + N', ADD BLOCK PREDICATE dbo.fn_tenant_access(company_id) ON dbo.' + QUOTENAME(@table) + N' AFTER INSERT'
        + N', ADD BLOCK PREDICATE dbo.fn_tenant_access(company_id) ON dbo.' + QUOTENAME(@table) + N' AFTER UPDATE, ';
    FETCH NEXT FROM tenant_tables INTO @table;
END;
CLOSE tenant_tables;
DEALLOCATE tenant_tables;
IF LEN(@clauses) > 0
BEGIN
    SET @clauses = LEFT(@clauses, LEN(@clauses) - 2);
    EXEC(N'CREATE SECURITY POLICY dbo.tenant_policy ' + @clauses + N' WITH (STATE = ON);');
END;
GO
