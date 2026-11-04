import io
import re
from typing import List, Optional

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill


class CustomerExportService:
    """
    Service to handle Excel and file exports for customer data.
    """

    @staticmethod
    def clean_phone_number(raw_phone: Optional[str]) -> Optional[str]:
        """
        Cleans and normalizes phone numbers:
        - Extracts digits.
        - Strips Nepal country code prefix '977'.
        - Removes leading '0' if total length is 11.
        - Ensures valid 10-digit phone format.
        """
        if not raw_phone:
            return None

        raw_str = str(raw_phone).strip()
        if raw_str.upper() in ("N/A", "NONE", "NULL", ""):
            return None

        digits = re.sub(r"\D", "", raw_str)
        if digits.startswith("977"):
            digits = digits[3:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]

        if len(digits) == 10:
            return digits

        return digits if digits else None

    @classmethod
    def generate_phone_numbers_excel(
        cls, phone_numbers: List[str], sheet_title: str = "Customer Phones"
    ) -> io.BytesIO:
        """
        Generates an Excel (.xlsx) file in-memory with a single 'phone' column.
        Formatted with text cells to preserve leading zeroes and clean presentation.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_title

        # Header cell: phone
        header_cell = ws.cell(row=1, column=1, value="phone")
        header_cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_cell.fill = PatternFill(
            start_color="1F497D", end_color="1F497D", fill_type="solid"
        )
        header_cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.column_dimensions["A"].width = 20

        # Data rows
        for row_idx, phone in enumerate(phone_numbers, start=2):
            cell = ws.cell(row=row_idx, column=1, value=str(phone))
            cell.number_format = "@"  # Text format
            cell.alignment = Alignment(horizontal="left", vertical="center")

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
