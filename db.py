import sqlite3
from flask import current_app, g

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
