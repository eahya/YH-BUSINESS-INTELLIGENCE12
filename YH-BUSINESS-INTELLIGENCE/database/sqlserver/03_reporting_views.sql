CREATE OR ALTER VIEW dbo.vw_trial_balance_functional
AS
SELECT je.company_id, a.code AS account_code, a.name AS account_name, a.account_type,
       je.journal_date, SUM(jl.base_debit) AS debit_functional,
       SUM(jl.base_credit) AS credit_functional
FROM dbo.journal_entries AS je
JOIN dbo.journal_lines AS jl
  ON jl.company_id = je.company_id AND jl.journal_id = je.id
JOIN dbo.accounts AS a
  ON a.company_id = jl.company_id AND a.id = jl.account_id
WHERE je.status = 'POSTED'
GROUP BY je.company_id, a.code, a.name, a.account_type, je.journal_date;
GO

CREATE OR ALTER VIEW dbo.vw_inventory_on_hand
AS
SELECT sm.company_id, sm.product_id, sm.warehouse_id,
       SUM(CASE WHEN sm.movement_type IN ('RECEIPT','ADJUSTMENT_IN')
                THEN sm.quantity ELSE -sm.quantity END) AS quantity_on_hand,
       SUM(CASE WHEN sm.movement_type IN ('RECEIPT','ADJUSTMENT_IN')
                THEN sm.quantity * sm.unit_cost ELSE -sm.quantity * sm.unit_cost END) AS inventory_value_functional
FROM dbo.stock_movements AS sm
GROUP BY sm.company_id, sm.product_id, sm.warehouse_id;
GO
