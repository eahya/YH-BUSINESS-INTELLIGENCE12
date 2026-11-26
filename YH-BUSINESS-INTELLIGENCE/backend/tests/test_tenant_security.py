
def test_company_membership_is_required_and_data_is_scoped(auth):
    client, headers, _ = auth
    forbidden = {**headers, "X-Company-ID": "2"}
    response = client.get("/api/v1/customers", headers=forbidden)
    assert response.status_code == 403
    own = client.get("/api/v1/customers", headers=headers)
    assert own.status_code == 200
    assert all(row["name"] != "Private Customer" for row in own.json())


def test_company_admin_can_create_another_company(auth):
    client, headers, _ = auth
    added = client.post("/api/v1/admin/users", headers=headers, json={
        "email": "analyst@example.test", "full_name": "Demo Analyst",
        "temporary_password": "another-correct-horse", "role_code": "ADMIN",
    })
    assert added.status_code == 201, added.text
    response = client.post("/api/v1/admin/companies", headers=headers, json={
        "name": "YH Secondary", "functional_currency_code": "EUR", "country_code": "DE",
    })
    assert response.status_code == 201, response.text
    company_id = response.json()["id"]
    companies = client.get("/api/v1/companies", headers={"Authorization": headers["Authorization"]})
    assert len(companies.json()) == 2
    second_company_headers = {**headers, "X-Company-ID": str(company_id)}
    attached = client.post("/api/v1/admin/users", headers=second_company_headers, json={
        "email": "analyst@example.test", "full_name": "Demo Analyst", "role_code": "ADMIN",
    })
    assert attached.status_code == 201, attached.text
    analyst_token = client.post("/api/v1/auth/token", json={
        "email": "analyst@example.test", "password": "another-correct-horse",
    }).json()["access_token"]
    analyst_companies = client.get("/api/v1/companies", headers={"Authorization": f"Bearer {analyst_token}"})
    assert len(analyst_companies.json()) == 2
    accounts = client.get("/api/v1/finance/accounts", headers=second_company_headers)
    assert accounts.status_code == 200
    assert any(account["code"] == "4000" for account in accounts.json())


def test_inventory_cannot_go_below_zero(auth):
    client, headers, _ = auth
    product = client.post("/api/v1/products", headers=headers, json={"sku": "EMPTY", "name": "Empty"}).json()
    warehouse = client.post("/api/v1/warehouses", headers=headers, json={"code": "ZERO", "name": "Empty"}).json()
    response = client.post("/api/v1/inventory/movements", headers=headers, json={
        "product_id": product["id"], "warehouse_id": warehouse["id"], "movement_date": "2025-02-01",
        "movement_type": "ISSUE", "quantity": "1",
    })
    assert response.status_code == 409
