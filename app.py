from flask import Flask, request, jsonify, g, current_app, Response
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
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




def parse_iso_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_week_start(value):
    return value - timedelta(days=value.weekday())


def build_pdf_bytes(lines):
    def escape_text(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = [
        "BT",
        "/F1 12 Tf",
        "72 720 Td",
        "16 TL"
    ]
    for index, line in enumerate(lines):
        escaped = escape_text(line)
        if index == 0:
            content_lines.append(f"({escaped}) Tj")
        else:
            content_lines.append(f"T* ({escaped}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1")

    objects = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    )
    objects.append(f"<< /Length {len(content)} >>\nstream\n{content.decode('latin-1')}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = bytearray()
    output.extend(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1"))

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )
    return bytes(output)


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

        lines = ["Expense report"]
        lines.append(f"Range: {from_value} to {to_value}")
        lines.append(f"Grouping: {group_by or 'none'}")
        lines.append(
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"
        )
        lines.append("")

        total = sum(float(expense.get("amount") or 0) for expense in expenses)
        currency = expenses[0]["currency"] if expenses else ""
        lines.append(f"Total: {currency} {total:.2f}")
        lines.append(f"Entries: {len(expenses)}")
        lines.append("")

        if group_by:
            buckets = {}
            for expense in expenses:
                try:
                    expense_date = parse_iso_date(expense["date"])
                except (TypeError, ValueError):
                    continue
                if group_by == "month":
                    bucket_date = expense_date.replace(day=1)
                    label = f"{bucket_date.year}-{bucket_date.month:02d}"
                else:
                    bucket_date = get_week_start(expense_date)
                    label = f"Week of {bucket_date.strftime('%Y-%m-%d')}"
                key = bucket_date.isoformat()
                buckets.setdefault(key, {"label": label, "total": 0, "count": 0})
                buckets[key]["total"] += float(expense.get("amount") or 0)
                buckets[key]["count"] += 1
            for key in sorted(buckets.keys()):
                bucket = buckets[key]
                lines.append(
                    f"{bucket['label']}: {currency} {bucket['total']:.2f} ({bucket['count']} entries)"
                )
        else:
            for expense in expenses:
                lines.append(
                    f"{expense['date']} - {expense.get('merchant') or 'Unknown'} "
                    f"{currency} {float(expense.get('amount') or 0):.2f}"
                )

        pdf_bytes = build_pdf_bytes(lines)
        response = Response(pdf_bytes, mimetype="application/pdf")
        response.headers["Cache-Control"] = "no-store"
        return response
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port)
