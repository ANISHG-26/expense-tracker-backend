import os
import tempfile

from app import create_app


def setup_app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app(database_path=path)
    app.config.update({"TESTING": True})
    client = app.test_client()
    return app, client, path


def test_create_and_list_expenses():
    app, client, path = setup_app()
    with app.app_context():
        response = client.post(
            "/expenses",
            json={
                "amount": 25.5,
                "currency": "USD",
                "categoryId": "cat-food",
                "merchant": "Corner Cafe",
                "note": "Lunch",
                "date": "2026-01-12"
            }
        )
        assert response.status_code == 201
        body = response.get_json()
        assert body["id"]
        assert body["merchant"] == "Corner Cafe"

        list_response = client.get("/expenses")
        assert list_response.status_code == 200
        items = list_response.get_json()
        assert len(items) == 1
        assert items[0]["note"] == "Lunch"

    os.remove(path)


def test_update_and_delete_expense():
    app, client, path = setup_app()
    with app.app_context():
        create_response = client.post(
            "/expenses",
            json={
                "amount": 10,
                "currency": "USD",
                "categoryId": "cat-transport",
                "merchant": "Metro",
                "note": "Bus",
                "date": "2026-01-12"
            }
        )
        expense_id = create_response.get_json()["id"]

        update_response = client.put(
            f"/expenses/{expense_id}",
            json={"note": "Train", "amount": 12, "merchant": "Rail"}
        )
        assert update_response.status_code == 200
        updated = update_response.get_json()
        assert updated["note"] == "Train"
        assert updated["amount"] == 12
        assert updated["merchant"] == "Rail"

        delete_response = client.delete(f"/expenses/{expense_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/expenses/{expense_id}")
        assert get_response.status_code == 404

    os.remove(path)


def test_list_categories():
    app, client, path = setup_app()
    with app.app_context():
        response = client.get("/categories")
        assert response.status_code == 200
        items = response.get_json()
        assert len(items) >= 1

    os.remove(path)


def test_download_report_pdf():
    app, client, path = setup_app()
    with app.app_context():
        client.post(
            "/expenses",
            json={
                "amount": 20,
                "currency": "USD",
                "categoryId": "cat-food",
                "merchant": "Cafe",
                "note": "Latte",
                "date": "2026-01-10"
            }
        )
        client.post(
            "/expenses",
            json={
                "amount": 45,
                "currency": "USD",
                "categoryId": "cat-utilities",
                "merchant": "Power Co",
                "note": "Electric",
                "date": "2026-01-15"
            }
        )
        response = client.get(
            "/reports/expenses.pdf?from=2026-01-01&to=2026-01-31&groupBy=week"
        )
        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.data.startswith(b"%PDF")

    os.remove(path)


def test_download_report_invalid_range():
    app, client, path = setup_app()
    with app.app_context():
        response = client.get("/reports/expenses.pdf?from=2026-02-01&to=2026-01-01")
        assert response.status_code == 400

    os.remove(path)

