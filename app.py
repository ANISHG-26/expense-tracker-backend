from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import uuid

from db import close_db, get_db, init_db, row_to_expense
from reporting import build_pdf_bytes, build_report_lines, parse_iso_date


def create_app(database_path=None):
    app = Flask(__name__)
    CORS(app)
    base_dir = os.path.dirname(__file__)
    app.config["DATABASE_PATH"] = database_path or os.environ.get(
        "DATABASE_PATH", os.path.join(base_dir, "expenses.db")
    )

    init_db(app.config["DATABASE_PATH"])
    app.teardown_appcontext(close_db)

    @app.get("/expenses")
    def expenses_list():
        db = get_db()
        rows = db.execute(
            "SELECT id, amount, currency, category_id, merchant, note, date FROM expenses"
        ).fetchall()
        return jsonify([row_to_expense(row) for row in rows])

    @app.post("/expenses")
    def expenses_create():
        payload = request.get_json(silent=True) or {}
        required = ["amount", "currency", "categoryId", "date"]
        missing = [field for field in required if payload.get(field) is None]
        if missing:
            return jsonify({"error": "Missing required fields: amount, currency, categoryId, date"}), 400

        expense = {
            "id": str(uuid.uuid4()),
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "categoryId": payload.get("categoryId"),
            "merchant": payload.get("merchant"),
            "note": payload.get("note"),
            "date": payload.get("date")
        }

        db = get_db()
        db.execute(
            """
            INSERT INTO expenses (id, amount, currency, category_id, merchant, note, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense["id"],
                expense["amount"],
                expense["currency"],
                expense["categoryId"],
                expense["merchant"],
                expense["note"],
                expense["date"]
            )
        )
        db.commit()
        return jsonify(expense), 201

    @app.get("/expenses/<expense_id>")
    def expenses_get(expense_id):
        db = get_db()
        row = db.execute(
            "SELECT id, amount, currency, category_id, merchant, note, date FROM expenses WHERE id = ?",
            (expense_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Expense not found"}), 404
        return jsonify(row_to_expense(row))

    @app.put("/expenses/<expense_id>")
    def expenses_update(expense_id):
        payload = request.get_json(silent=True) or {}
        db = get_db()
        row = db.execute(
            "SELECT id, amount, currency, category_id, merchant, note, date FROM expenses WHERE id = ?",
            (expense_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Expense not found"}), 404

        current = row_to_expense(row)
        updated = {**current, **payload}

        db.execute(
            """
            UPDATE expenses
            SET amount = ?, currency = ?, category_id = ?, merchant = ?, note = ?, date = ?
            WHERE id = ?
            """,
            (
                updated["amount"],
                updated["currency"],
                updated["categoryId"],
                updated.get("merchant"),
                updated.get("note"),
                updated["date"],
                expense_id
            )
        )
        db.commit()
        return jsonify(updated)

    @app.delete("/expenses/<expense_id>")
    def expenses_delete(expense_id):
        db = get_db()
        cur = db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Expense not found"}), 404
        return "", 204

    @app.get("/categories")
    def categories_list():
        db = get_db()
        rows = db.execute("SELECT id, name FROM categories").fetchall()
        return jsonify([{"id": row["id"], "name": row["name"]} for row in rows])

    @app.get("/reports/expenses.pdf")
    def expenses_report_pdf():
        from_value = request.args.get("from")
        to_value = request.args.get("to")
        group_by = request.args.get("groupBy")
        if not from_value or not to_value:
            return jsonify({"error": "from and to are required"}), 400
        try:
            from_date = parse_iso_date(from_value)
            to_date = parse_iso_date(to_value)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
        if from_date > to_date:
            return jsonify({"error": "Invalid date range"}), 400
        if group_by not in (None, "", "week", "month"):
            return jsonify({"error": "Invalid groupBy value"}), 400

        db = get_db()
        rows = db.execute(
            "SELECT id, amount, currency, category_id, merchant, note, date "
            "FROM expenses "
            "WHERE date >= ? AND date <= ? "
            "ORDER BY date ASC",
            (from_value, to_value)
        ).fetchall()
        expenses = [row_to_expense(row) for row in rows]
        lines = build_report_lines(expenses, from_value, to_value, group_by)
        pdf_bytes = build_pdf_bytes(lines)
        response = Response(pdf_bytes, mimetype="application/pdf")
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port)
