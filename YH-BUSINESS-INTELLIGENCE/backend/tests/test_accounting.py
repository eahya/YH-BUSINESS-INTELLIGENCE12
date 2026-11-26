from sqlalchemy import select

from app.models import JournalEntry, JournalLine


def test_unbalanced_draft_cannot_be_posted(auth):
    client, headers, _ = auth
    draft = client.post("/api/v1/finance/journals", headers=headers, json={
        "journal_number": "J-UNBALANCED", "journal_date": "2025-01-15", "description": "Bad entry",
        "lines": [
            {"account_code": "1000", "currency_code": "USD", "debit": "10.00"},
            {"account_code": "4000", "currency_code": "USD", "credit": "9.00"},
        ],
    })
    assert draft.status_code == 201
    journal_id = draft.json()["id"]
    posted = client.post(f"/api/v1/finance/journals/{journal_id}/post", headers=headers)
    assert posted.status_code == 422
    assert client.get("/api/v1/finance/journals", headers=headers).json()[0]["status"] == "DRAFT"


def test_sales_posting_is_balanced_and_immutable(auth, client):
    api, headers, company_id = auth
    factory = client[1]
    customer = api.post("/api/v1/customers", headers=headers, json={"code": "C-01", "name": "Acme"})
    warehouse = api.post("/api/v1/warehouses", headers=headers, json={"code": "WH-01", "name": "Main"})
    product = api.post("/api/v1/products", headers=headers, json={
        "sku": "SKU-01", "name": "Widget", "unit_cost": "5", "selling_price": "10",
    })
    assert customer.status_code == warehouse.status_code == product.status_code == 201
    stock = api.post("/api/v1/inventory/movements", headers=headers, json={
        "product_id": product.json()["id"], "warehouse_id": warehouse.json()["id"],
        "movement_date": "2025-01-01", "movement_type": "RECEIPT", "quantity": "10", "unit_cost": "5",
    })
    assert stock.status_code == 201
    invoice = api.post("/api/v1/sales/invoices", headers=headers, json={
        "customer_id": customer.json()["id"], "invoice_number": "INV-100",
        "invoice_date": "2025-01-15", "currency_code": "USD", "tax_amount": "4",
        "lines": [{"product_id": product.json()["id"], "warehouse_id": warehouse.json()["id"],
                   "quantity": "2", "unit_price": "10"}],
    })
    assert invoice.status_code == 201
    posted = api.post(f"/api/v1/sales/invoices/{invoice.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "POSTED"
    with factory() as db:
        entry = db.scalar(select(JournalEntry).where(JournalEntry.company_id == company_id,
                                                      JournalEntry.source_type == "SALES_INVOICE"))
        lines = db.scalars(select(JournalLine).where(JournalLine.journal_id == entry.id)).all()
        assert sum(line.base_debit for line in lines) == sum(line.base_credit for line in lines)
        assert entry.status == "POSTED"
    assert api.post(f"/api/v1/sales/invoices/{invoice.json()['id']}/post", headers=headers).status_code == 409
    balance = api.get("/api/v1/inventory/balances", headers=headers).json()[0]
    assert float(balance["quantity"]) == 8.0
    overview = api.get("/api/v1/analytics/overview?start=2025-01-01&end=2025-01-31", headers=headers).json()
    assert float(overview["revenue"]) == 20.0
    assert float(overview["cost_of_goods_sold"]) == 10.0
    assert float(overview["net_profit_estimate"]) == 10.0


def test_purchase_expense_and_warehouse_refresh(auth):
    api, headers, _ = auth
    supplier = api.post("/api/v1/suppliers", headers=headers, json={"code": "S-01", "name": "Supply Co"})
    warehouse = api.post("/api/v1/warehouses", headers=headers, json={"code": "WH-01", "name": "Main"})
    product = api.post("/api/v1/products", headers=headers, json={"sku": "SKU-02", "name": "Part"})
    bill = api.post("/api/v1/purchases/bills", headers=headers, json={
        "supplier_id": supplier.json()["id"], "bill_number": "B-20", "bill_date": "2025-02-01",
        "currency_code": "USD", "lines": [{"product_id": product.json()["id"],
            "warehouse_id": warehouse.json()["id"], "quantity": "3", "unit_cost": "7.50"}],
    })
    assert bill.status_code == 201
    assert api.post(f"/api/v1/purchases/bills/{bill.json()['id']}/post", headers=headers).status_code == 200
    rate = api.post("/api/v1/finance/fx-rates", headers=headers, json={
        "currency_code": "EUR", "rate_date": "2025-02-01", "functional_per_unit": "0.9",
    })
    assert rate.status_code == 201
    expense = api.post("/api/v1/expenses", headers=headers, json={
        "expense_date": "2025-02-02", "category": "Travel", "description": "Taxi",
        "currency_code": "EUR", "amount": "100",
    })
    assert expense.status_code == 201
    assert float(expense.json()["functional_amount"]) == 90.0
    posted_expense = api.post(f"/api/v1/expenses/{expense.json()['id']}/post", headers=headers)
    assert posted_expense.status_code == 200
    assert api.get("/api/v1/analytics/insights?start=2025-02-01&end=2025-02-28", headers=headers).json()["external_llm"] is False
    first = api.post("/api/v1/analytics/warehouse/refresh", headers=headers).json()
    second = api.post("/api/v1/analytics/warehouse/refresh", headers=headers).json()
    assert first["fact_rows_inserted"] >= 2
    assert second["fact_rows_inserted"] == 0
