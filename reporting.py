from datetime import datetime, timedelta, timezone


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


def build_report_lines(expenses, from_value, to_value, group_by):
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
                f"{bucket['label']}: {currency} {bucket['total']:.2f} "
                f"({bucket['count']} entries)"
            )
    else:
        for expense in expenses:
            lines.append(
                f"{expense['date']} - {expense.get('merchant') or 'Unknown'} "
                f"{currency} {float(expense.get('amount') or 0):.2f}"
            )

    return lines
