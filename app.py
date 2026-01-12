from flask import Flask, request, jsonify, g, current_app
from flask_cors import CORS
import os
import sqlite3
import uuid

DEFAULT_CATEGORIES = [
    {"id": "cat-food", "name": "Food"},
    {"id": "cat-transport", "name": "Transport"},
    {"id": "cat-utilities", "name": "Utilities"},
    {"id": "cat-fun", "name": "Entertainment"}
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_column(db, table, column, column_def):
    columns = [row["name"] for row in db.execute(f"PRAGMA table_info({table})")]
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")


def init_db(database_path):
    db = sqlite3.connect(database_path)
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            category_id TEXT NOT NULL,
            merchant TEXT,
            note TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
        """
    )

    ensure_column(db, "expenses", "merchant", "TEXT")

    cur = db.execute("SELECT COUNT(*) as count FROM categories")
    count = cur.fetchone()["count"]
    if count == 0:
        db.executemany(
            "INSERT INTO categories (id, name) VALUES (?, ?)",
            [(c["id"], c["name"]) for c in DEFAULT_CATEGORIES]
        )
    db.commit()
    db.close()


def row_to_expense(row):
    return {
        "id": row["id"],
        "amount": row["amount"],
        "currency": row["currency"],
        "categoryId": row["category_id"],
        "merchant": row["merchant"],
        "note": row["note"],
        "date": row["date"]
    }


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

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port)
