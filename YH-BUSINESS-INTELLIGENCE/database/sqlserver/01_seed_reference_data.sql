/* Run after `alembic upgrade head` while connected to YH_BusinessIntelligence. */
MERGE dbo.currencies AS target
USING (VALUES
    ('AED', N'UAE Dirham', 2), ('AUD', N'Australian Dollar', 2),
    ('CAD', N'Canadian Dollar', 2), ('EGP', N'Egyptian Pound', 2),
    ('EUR', N'Euro', 2), ('GBP', N'Pound Sterling', 2),
    ('JPY', N'Japanese Yen', 0), ('SAR', N'Saudi Riyal', 2),
    ('USD', N'US Dollar', 2)
) AS source(code, name, minor_units)
ON target.code = source.code
WHEN NOT MATCHED THEN INSERT (code, name, minor_units, is_active)
    VALUES (source.code, source.name, source.minor_units, 1);
GO
