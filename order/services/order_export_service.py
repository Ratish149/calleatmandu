import io
import re
from typing import List, Optional

import openpyxl
from django.db.models import QuerySet
from openpyxl.styles import Alignment, Font, PatternFill

from order.models import Order


class OrderExportService:
    @staticmethod
    def clean_phone_number(raw_phone: Optional[str]) -> Optional[str]:
        """
        Cleans and formats a phone number:
        - Strips any non-digit characters.
        - Removes '+977' or '977' Nepal country code prefix.
        - Removes leading zero if 11 digits (e.g. 098...).
        - Returns only valid 10-digit phone numbers.
        """
        if not raw_phone:
            return None

        # Extract only digits
        digits = re.sub(r"\D", "", str(raw_phone))

        # Remove 977 country code prefix
        if digits.startswith("977"):
            digits = digits[3:]

        # Remove leading zero if present and total length is 11
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]

        # Ensure exactly 10 digits
        if len(digits) == 10:
            return digits

        return None

    @classmethod
    def get_order_phone_numbers(
        cls, queryset: QuerySet[Order], distinct: bool = True
    ) -> List[str]:
        """
        Extracts cleaned 10-digit phone numbers from the given Order queryset.
        Optimized with .values_list('phone_number', flat=True) and .exclude(phone_number__isnull=True).
        """
        raw_phones = (
            queryset.exclude(phone_number__isnull=True)
            .exclude(phone_number="")
            .order_by("-created_at")
            .values_list("phone_number", flat=True)
        )

        seen = set()
        cleaned_numbers = []
        for raw in raw_phones:
            cleaned = cls.clean_phone_number(raw)
            if cleaned:
                if distinct:
                    if cleaned not in seen:
                        seen.add(cleaned)
                        cleaned_numbers.append(cleaned)
                else:
                    cleaned_numbers.append(cleaned)

        return cleaned_numbers

    @classmethod
    def generate_phone_numbers_excel(cls, phone_numbers: List[str]) -> io.BytesIO:
        """
        Generates an Excel workbook with a single 'phone' column containing the phone numbers.
        Formatted with text cells to preserve leading zeroes and clean formatting.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Phone Numbers"

        # Header
        header_cell = ws.cell(row=1, column=1, value="phone")
        header_cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_cell.fill = PatternFill(
            start_color="1F497D", end_color="1F497D", fill_type="solid"
        )
        header_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Column width
        ws.column_dimensions["A"].width = 20

        # Data rows
        for row_idx, phone in enumerate(phone_numbers, start=2):
            cell = ws.cell(row=row_idx, column=1, value=str(phone))
            cell.number_format = "@"  # Explicit text formatting
            cell.alignment = Alignment(horizontal="left", vertical="center")

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
