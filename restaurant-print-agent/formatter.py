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


def _two_cols(left: str, right: str, width: int) -> str:
    """Formats two text columns justified left and right to fill line width."""
    left = str(left)
    right = str(right)
    gap = width - len(left) - len(right)
    if gap < 1:
        # If left text is too long, truncate it
        left = left[: width - len(right) - 2] + " "
        gap = width - len(left) - len(right)
    return left + (" " * max(gap, 1)) + right + "\n"


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
    width = _get_columns(width_mm)
    buf = bytearray()

    order_num = str(order.get("order_number", "N/A"))
    resto_name = str(order.get("restaurant_name", "RESTAURANT"))
    order_type = str(order.get("order_type", "DELIVERY")).upper()
    created_at = str(order.get("created_at", ""))
    notes = str(
        order.get("notes")
        or order.get("special_note")
        or order.get("kitchen_notes")
        or ""
    ).strip()

    # Initialize
    buf.extend(INIT)

    # Header
    buf.extend(ALIGN_CENTER)
    buf.extend(_line_sep(width, "="))
    buf.extend(BOLD_ON + TXT_TITLE + b"KITCHEN ORDER\n" + TXT_NORMAL + BOLD_OFF)
    buf.extend(_line_sep(width, "="))
    buf.extend(b"\n")

    buf.extend(BOLD_ON + resto_name.encode("latin1", "replace") + b"\n\n" + BOLD_OFF)

    # Order details
    buf.extend(ALIGN_LEFT)
    buf.extend(f"Order: {order_num}\n".encode("latin1", "replace"))
    buf.extend(f"Type:  {order_type}\n".encode("latin1", "replace"))
    if created_at:
        time_part = created_at.replace("T", " ")[:19]
        buf.extend(f"Time:  {time_part}\n".encode("latin1", "replace"))

    buf.extend(_line_sep(width, "-"))
    buf.extend(b"\n")

    # Item List
    items = order.get("items", [])
    buf.extend(BOLD_ON + TXT_DOUBLE_HEIGHT)
    for item in items:
        name = str(item.get("product_name") or item.get("name", "Unknown Item"))
        qty = item.get("quantity", 1)
        item_note = str(item.get("notes", "") or item.get("special_note", "")).strip()

        row_text = _two_cols(name, f"x{qty}", width)
        buf.extend(row_text.encode("latin1", "replace"))

        if item_note:
            buf.extend(f"  * {item_note}\n".encode("latin1", "replace"))

    buf.extend(TXT_NORMAL + BOLD_OFF)
    buf.extend(b"\n")
    buf.extend(_line_sep(width, "-"))

    # Order Special Instructions / Notes
    if notes:
        buf.extend(b"\n")
        buf.extend(BOLD_ON + b"Special Instructions:\n" + BOLD_OFF)
        buf.extend(notes.encode("latin1", "replace") + b"\n\n")

    buf.extend(_line_sep(width, "="))
    buf.extend(FEED_3)
    buf.extend(CUT_PAPER)

    return bytes(buf)


def format_bill(order: Dict[str, Any], width_mm: int = 80) -> bytes:
    """
    Formats a Customer Bill / Receipt as raw ESC/POS printer bytes.
    Includes item breakdown, pricing, subtotals, delivery fee, discounts, and total.
    """
    width = _get_columns(width_mm)
    buf = bytearray()

    resto_name = str(order.get("restaurant_name", "RESTAURANT")).upper()
    order_num = str(order.get("order_number", "N/A"))
    order_type = str(order.get("order_type", "DELIVERY")).upper()
    created_at = str(order.get("created_at", ""))

    subtotal = str(order.get("subtotal", "0.00"))
    delivery_fee = str(order.get("delivery_fee", "0.00"))
    discount = str(order.get("discount_amount") or order.get("discount", "0.00"))
    total = str(order.get("total_amount") or order.get("total", "0.00"))

    customer = order.get("customer", {})
    # OrderResponseSerializer sends flat fields: customer_name, phone_number
    cust_name = str(
        (customer.get("name") if customer else None) or order.get("customer_name", "")
    ).strip()
    cust_phone = str(
        (customer.get("phone") if customer else None) or order.get("phone_number", "")
    ).strip()

    # Initialize
    buf.extend(INIT)

    # Header
    buf.extend(ALIGN_CENTER)
    buf.extend(_line_sep(width, "="))
    buf.extend(
        BOLD_ON
        + TXT_TITLE
        + resto_name.encode("latin1", "replace")
        + b"\n"
        + TXT_NORMAL
        + BOLD_OFF
    )
    buf.extend(_line_sep(width, "="))
    buf.extend(b"\n")

    buf.extend(ALIGN_LEFT)
    buf.extend(f"Order: {order_num}\n".encode("latin1", "replace"))
    buf.extend(f"Type:  {order_type}\n".encode("latin1", "replace"))
    if created_at:
        time_part = created_at.replace("T", " ")[:19]
        buf.extend(f"Date:  {time_part}\n".encode("latin1", "replace"))

    if cust_name or cust_phone:
        info = f"{cust_name} ({cust_phone})".strip(" ()")
        buf.extend(f"Cust:  {info}\n".encode("latin1", "replace"))

    buf.extend(_line_sep(width, "-"))

    # Table Header
    buf.extend(BOLD_ON)
    buf.extend(_three_cols("Item", "Qty", "Total", width).encode("latin1", "replace"))
    buf.extend(BOLD_OFF)
    buf.extend(_line_sep(width, "-"))

    # Table Items
    items = order.get("items", [])
    for item in items:
        name = str(item.get("product_name") or item.get("name", "Item"))
        qty = str(item.get("quantity", "1"))
        item_total = str(
            item.get("subtotal") or item.get("total") or item.get("unit_price", "0.00")
        )
        buf.extend(
            _three_cols(name, qty, item_total, width).encode("latin1", "replace")
        )

    buf.extend(_line_sep(width, "-"))

    # Financial Breakdown
    buf.extend(_two_cols("Subtotal", subtotal, width).encode("latin1", "replace"))
    if delivery_fee and float(str(delivery_fee).replace(",", "")) > 0:
        buf.extend(
            _two_cols("Delivery Fee", delivery_fee, width).encode("latin1", "replace")
        )
    if discount and float(str(discount).replace(",", "")) > 0:
        buf.extend(
            _two_cols("Discount", f"-{discount}", width).encode("latin1", "replace")
        )

    buf.extend(_line_sep(width, "-"))

    # Total with double height
    buf.extend(BOLD_ON + TXT_DOUBLE_HEIGHT)
    buf.extend(_two_cols("TOTAL", total, width).encode("latin1", "replace"))
    buf.extend(TXT_NORMAL + BOLD_OFF)

    # Footer
    buf.extend(_line_sep(width, "="))
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + b"THANK YOU\n" + BOLD_OFF)
    buf.extend(_line_sep(width, "="))

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
