from typing import Any, Dict

# Standard ESC/POS Control Byte Constants
ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"  # Reset and initialize printer
ALIGN_LEFT = ESC + b"a\x00"  # Left justification
ALIGN_CENTER = ESC + b"a\x01"  # Centered text
ALIGN_RIGHT = ESC + b"a\x02"  # Right justification

BOLD_ON = ESC + b"E\x01"  # Bold text enabled
BOLD_OFF = ESC + b"E\x00"  # Bold text disabled

TXT_NORMAL = GS + b"!\x00"  # Standard font size
TXT_DOUBLE_HEIGHT = GS + b"!\x01"  # 2x height
TXT_DOUBLE_WIDTH = GS + b"!\x10"  # 2x width
TXT_TITLE = GS + b"!\x11"  # 2x height + 2x width

FEED_3 = b"\n\n\n"  # Feed paper 3 lines
CUT_PAPER = GS + b"VA\x03"  # Partial cut with 3-dot feed


def _get_columns(width_mm: int) -> int:
    """Returns character width of line based on thermal paper roll size."""
    return 32 if width_mm == 58 else 48


def _line_sep(width: int, char: str = "=") -> bytes:
    return (char * width + "\n").encode("latin1", errors="replace")


def _fmt_amount(val: Any) -> str:
    """Formats amount cleanly: 1380.00 -> 1380, 1380.50 -> 1380.50"""
    try:
        f = float(str(val).replace(",", "").strip())
        return str(int(f)) if f.is_integer() else f"{f:.2f}"
    except Exception:
        return str(val)


def _clean_text(s: str) -> str:
    """Strips non-ASCII characters and emojis that thermal printers cannot render."""
    if not s:
        return ""
    return "".join(c for c in s if ord(c) < 128).strip()


def _two_cols(left: str, right: str, width: int) -> str:
    """Formats two text columns justified left and right to fill line width."""
    left = str(left)
    right = str(right)
    gap = width - len(left) - len(right)
    if gap < 0:
        left = left[: max(0, width - len(right) - 1)] + " "
        gap = 0
    return left + (" " * max(gap, 0)) + right + "\n"


def _three_cols(col1: str, col2: str, col3: str, width: int) -> str:
    """Formats three columns: Item name (left), Qty (middle), Total (right)."""
    # Allocate: qty = 5 cols, total = 9 cols, item = remaining
    c2 = str(col2).center(5)
    c3 = str(col3).rjust(9)
    item_width = width - len(c2) - len(c3)
    c1 = str(col1)
    if len(c1) > item_width:
        c1 = c1[: item_width - 1] + " "
    else:
        c1 = c1.ljust(item_width)
    return c1 + c2 + c3 + "\n"


def format_kot(order: Dict[str, Any], width_mm: int = 80) -> bytes:
    """
    Formats a Kitchen Order Ticket (KOT) as raw ESC/POS printer bytes.
    KOT focuses strictly on kitchen requirements: Order #, Order Type, Item Qty, and Notes.
    Omits payment / pricing details.
    """
    import datetime

    width = _get_columns(width_mm)
    buf = bytearray()

    order_num = str(order.get("order_number", "N/A"))
    order_type = str(order.get("order_type", "DELIVERY")).upper()
    created_at = str(order.get("created_at", ""))
    notes = str(
        order.get("special_note")
        or order.get("notes")
        or order.get("kitchen_notes")
        or ""
    ).strip()

    # Branch and customer info
    branch_name = (
        str(
            order.get("branch_name")
            or (order.get("branch") or {}).get("name", "")
            or order.get("restaurant_name", "")
            or "RESTAURANT"
        )
        .strip()
        .upper()
    )
    customer = order.get("customer") or {}
    cust_name = str(
        (customer.get("name") if isinstance(customer, dict) else None)
        or order.get("customer_name")
        or ""
    ).strip()
    if cust_name.lower() in ("none", "null"):
        cust_name = ""

    cust_phone = str(
        (customer.get("phone") if isinstance(customer, dict) else None)
        or order.get("phone_number")
        or ""
    ).strip()
    if cust_phone.lower() in ("none", "null"):
        cust_phone = ""

    # Time parts
    time_str = ""
    if created_at:
        time_str = created_at.replace("T", " ")[11:16]  # HH:MM

    # ── Initialize ────────────────────────────────────────────────
    buf.extend(INIT)

    # ── Header: "** KITCHEN TICKET **" ───────────────────────────
    buf.extend(ALIGN_CENTER)
    buf.extend(_line_sep(width, "-"))

    # App name — normal bold (same size as branch name)
    buf.extend(BOLD_ON + b"CallEatMandu\n" + BOLD_OFF)

    # Kitchen ticket title — reduced from TXT_TITLE to double height (cleaner, not stretched)
    buf.extend(
        BOLD_ON + TXT_DOUBLE_HEIGHT + b"** KITCHEN TICKET **\n" + TXT_NORMAL + BOLD_OFF
    )

    # Branch name below header (bold, centered)
    buf.extend(BOLD_ON + branch_name.encode("latin1", "replace") + b"\n" + BOLD_OFF)

    buf.extend(_line_sep(width, "-"))

    # ── Order meta row: "Order: #xxx | Time: HH:MM | Type: DINE" ─
    buf.extend(ALIGN_LEFT)
    buf.extend(f"Order: #{order_num}\n".encode("latin1", "replace"))

    if time_str:
        row = _two_cols(f"Time: {time_str}", f"Type: {order_type}", width)
        buf.extend(row.encode("latin1", "replace"))
    else:
        buf.extend(f"Type: {order_type}\n".encode("latin1", "replace"))

    buf.extend(_line_sep(width, "-"))

    # ── CUSTOMER section (only print if name or phone exists) ──────
    if cust_name or cust_phone:
        buf.extend(ALIGN_LEFT)
        buf.extend(BOLD_ON + b"CUSTOMER\n" + BOLD_OFF)
        if cust_name:
            buf.extend(f"  Name : {cust_name}\n".encode("latin1", "replace"))
        if cust_phone:
            buf.extend(f"  Phone: {cust_phone}\n".encode("latin1", "replace"))
        buf.extend(_line_sep(width, "-"))

    # ── ITEMS section ─────────────────────────────────────────────
    items = order.get("items", [])
    buf.extend(
        BOLD_ON + f"ITEMS ({len(items)})\n".encode("latin1", "replace") + BOLD_OFF
    )
    buf.extend(_line_sep(width, "-"))

    for idx, item in enumerate(items):
        name = _clean_text(
            str(item.get("product_name") or item.get("name", "Unknown Item"))
        )
        qty = item.get("quantity", 1)
        item_note = _clean_text(
            str(item.get("notes", "") or item.get("special_note", ""))
        )

        # Product name LEFT, quantity RIGHT in standard bold font
        buf.extend(BOLD_ON)
        row_text = _two_cols(name, f"x{qty}", width)
        buf.extend(row_text.encode("latin1", "replace"))
        buf.extend(BOLD_OFF)

        # Extras (selected add-ons) — normal size, indented
        extras = item.get("selected_extras", [])
        for extra in extras:
            extra_name = _clean_text(str(extra.get("extra_name", "")))
            extra_price = extra.get("additional_price", 0)
            if extra_name:
                price_val = _fmt_amount(extra_price)
                if extra_price and float(str(extra_price).replace(",", "")) > 0:
                    buf.extend(
                        f"  + {extra_name} (+{price_val})\n".encode("latin1", "replace")
                    )
                else:
                    buf.extend(f"  + {extra_name}\n".encode("latin1", "replace"))

        if item_note:
            buf.extend(f"  * {item_note}\n".encode("latin1", "replace"))

        # Clean vertical spacing between items
        if idx < len(items) - 1:
            buf.extend(b"\n")

    buf.extend(_line_sep(width, "-"))

    # ── Special Instructions / Notes ──────────────────────────────
    if notes:
        buf.extend(b"\n")
        buf.extend(BOLD_ON + b"Special Instructions:\n" + BOLD_OFF)
        buf.extend(notes.encode("latin1", "replace") + b"\n")
        buf.extend(_line_sep(width, "-"))

    # ── Footer: "Printed at: HH:MM:SS" ───────────────────────────
    buf.extend(ALIGN_CENTER)
    printed_at = datetime.datetime.now().strftime("%H:%M:%S")
    buf.extend(f"Printed at: {printed_at}\n".encode("latin1", "replace"))
    buf.extend(_line_sep(width, "-"))

    buf.extend(FEED_3)
    buf.extend(CUT_PAPER)

    return bytes(buf)


def format_bill(order: Dict[str, Any], width_mm: int = 80) -> bytes:
    """
    Formats a Customer Bill / Receipt as raw ESC/POS printer bytes.
    Matches receipt design from image: centered branch header, order metadata,
    items table with add-on extras, subtotal/total, CODE128 barcode, and footer.
    """
    import datetime

    width = _get_columns(width_mm)
    buf = bytearray()

    # ── Extract fields ────────────────────────────────────────────
    branch_name = (
        str(
            order.get("branch_name")
            or (order.get("branch") or {}).get("name", "")
            or order.get("restaurant_name", "")
            or "RESTAURANT"
        )
        .strip()
        .upper()
    )

    order_num = str(order.get("order_number", "N/A")).lstrip("#")
    barcode_num = str(order.get("barcode_number", "")).strip()
    if not barcode_num:
        clean_digits = "".join(filter(str.isdigit, order_num))
        barcode_num = clean_digits if clean_digits else order_num

    order_type = str(order.get("order_type", "DELIVERY")).upper()
    created_at = str(order.get("created_at", ""))
    special_note = str(order.get("special_note") or order.get("notes") or "").strip()

    subtotal = order.get("subtotal", "0")
    delivery_fee = order.get("delivery_fee", "0")
    discount = order.get("discount_amount") or order.get("discount", "0")
    total = order.get("total_amount") or order.get("total", "0")

    # ── Format date: e.g. "28 Sept 2026, 13:15" ──────────────────
    date_str = ""
    if created_at:
        try:
            dt = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            month = dt.strftime("%b")
            if month == "Sep":
                month = "Sept"
            date_str = f"{dt.day} {month} {dt.year}, {dt.strftime('%H:%M')}"
        except Exception:
            date_str = created_at.replace("T", " ")[:16]

    # ── Initialize printer ────────────────────────────────────────
    buf.extend(INIT)

    # ── Header: Centered Branch Name ──────────────────────────────
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + branch_name.encode("latin1", "replace") + b"\n\n" + BOLD_OFF)

    # ── Order meta ────────────────────────────────────────────────
    buf.extend(ALIGN_LEFT)
    buf.extend(f"Order: #{order_num}\n".encode("latin1", "replace"))
    buf.extend(f"Type: {order_type}\n".encode("latin1", "replace"))
    if date_str:
        buf.extend(f"Date: {date_str}\n".encode("latin1", "replace"))
    buf.extend(_line_sep(width, "-"))

    # ── Items table header ────────────────────────────────────────
    if width <= 32:
        header_right = "QtyTotal"
    else:
        header_right = "Qty   Total"

    buf.extend(BOLD_ON)
    buf.extend(_two_cols("Item", header_right, width).encode("latin1", "replace"))
    buf.extend(BOLD_OFF)
    buf.extend(_line_sep(width, "-"))

    # ── Item lines ────────────────────────────────────────────────
    items = order.get("items", [])
    for item in items:
        name = _clean_text(str(item.get("product_name") or item.get("name", "Item")))
        qty = str(item.get("quantity", 1))
        item_total = (
            item.get("subtotal") or item.get("total") or item.get("unit_price", 0)
        )
        amt_str = _fmt_amount(item_total)

        if width <= 32:
            right_col = f"{qty}Rs {amt_str}"
        else:
            right_col = f"{qty}   Rs {amt_str}"

        buf.extend(_two_cols(name, right_col, width).encode("latin1", "replace"))

        # Extras (add-ons)
        extras = item.get("selected_extras", [])
        for extra in extras:
            extra_name = _clean_text(str(extra.get("extra_name", "")))
            extra_price = extra.get("additional_price", 0)
            if extra_name:
                price_val = _fmt_amount(extra_price)
                if extra_price and float(str(extra_price).replace(",", "")) > 0:
                    price_str = f"+Rs {price_val}"
                    buf.extend(
                        _two_cols(f"+ {extra_name}", price_str, width).encode(
                            "latin1", "replace"
                        )
                    )
                else:
                    buf.extend(f"+ {extra_name}\n".encode("latin1", "replace"))

        # Item-level note
        item_note = _clean_text(
            str(item.get("notes") or item.get("special_note") or "")
        )
        if item_note:
            buf.extend(f"  * {item_note}\n".encode("latin1", "replace"))

    buf.extend(_line_sep(width, "-"))

    # ── Subtotal and Financial Breakdown ──────────────────────────
    buf.extend(
        _two_cols("Subtotal", f"Rs {_fmt_amount(subtotal)}", width).encode(
            "latin1", "replace"
        )
    )

    try:
        del_fee_num = float(str(delivery_fee).replace(",", ""))
    except Exception:
        del_fee_num = 0.0
    if del_fee_num > 0:
        buf.extend(
            _two_cols("Delivery Fee", f"Rs {_fmt_amount(delivery_fee)}", width).encode(
                "latin1", "replace"
            )
        )

    try:
        disc_num = float(str(discount).replace(",", ""))
    except Exception:
        disc_num = 0.0
    if disc_num > 0:
        buf.extend(
            _two_cols("Discount", f"-Rs {_fmt_amount(discount)}", width).encode(
                "latin1", "replace"
            )
        )

    # ── Special note ──────────────────────────────────────────────
    if special_note:
        buf.extend(BOLD_ON + b"Note:\n" + BOLD_OFF)
        buf.extend(f"  {special_note}\n".encode("latin1", "replace"))

    buf.extend(_line_sep(width, "-"))

    # ── TOTAL ─────────────────────────────────────────────────────
    buf.extend(BOLD_ON)
    buf.extend(
        _two_cols("TOTAL", f"Rs {_fmt_amount(total)}", width).encode(
            "latin1", "replace"
        )
    )
    buf.extend(BOLD_OFF)

    # ── Barcode ───────────────────────────────────────────────────
    if barcode_num:
        buf.extend(ALIGN_CENTER)
        # Set barcode height: 60 dots
        buf.extend(GS + b"h" + bytes([60]))
        # Barcode module width: 2 (narrow)
        buf.extend(GS + b"w" + bytes([2]))
        # HRI font: Font A (0)
        buf.extend(GS + b"f" + bytes([0]))
        # Print HRI text below barcode (2)
        buf.extend(GS + b"H" + bytes([2]))

        clean_barcode = "".join(c for c in barcode_num if c.isalnum() or c in "-_")
        if clean_barcode:
            # CODE128 Function B (m=73) with Code Set B prefix '{B'
            code128_data = b"{B" + clean_barcode.encode("ascii", "replace")
            buf.extend(GS + b"k" + bytes([73, len(code128_data)]) + code128_data)
            buf.extend(b"\n")

    # ── Footer ────────────────────────────────────────────────────
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + b"THANK YOU\n" + BOLD_OFF)
    buf.extend(b"calleatmandu.com\n")

    buf.extend(FEED_3)
    buf.extend(CUT_PAPER)

    return bytes(buf)


def format_test(branch_id: Any, printer_name: str, width_mm: int = 80) -> bytes:
    """Generates a diagnostic self-test printout to confirm printer operation."""
    width = _get_columns(width_mm)
    buf = bytearray()

    buf.extend(INIT)
    buf.extend(ALIGN_CENTER)
    buf.extend(_line_sep(width, "="))
    buf.extend(
        BOLD_ON + TXT_TITLE + b"RESTAURANT PRINT AGENT\n" + TXT_NORMAL + BOLD_OFF
    )
    buf.extend(_line_sep(width, "="))
    buf.extend(b"\n")

    buf.extend(BOLD_ON + b"Printer Test Successful\n\n" + BOLD_OFF)

    buf.extend(ALIGN_LEFT)
    buf.extend(_two_cols("Branch:", str(branch_id), width).encode("latin1", "replace"))
    buf.extend(
        _two_cols("Printer:", str(printer_name), width).encode("latin1", "replace")
    )
    buf.extend(
        _two_cols("Paper Width:", f"{width_mm}mm ({width} cols)", width).encode(
            "latin1", "replace"
        )
    )

    buf.extend(_line_sep(width, "="))
    buf.extend(FEED_3)
    buf.extend(CUT_PAPER)

    return bytes(buf)
