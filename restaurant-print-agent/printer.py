import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from config import get_base_dir

logger = logging.getLogger("RestaurantPrintAgent.Printer")

# Try importing pywin32 on Windows platforms
IS_WINDOWS = sys.platform == "win32"
win32print = None

if IS_WINDOWS:
    try:
        import win32print
    except ImportError:
        logger.error("pywin32 (win32print) is not installed. Required for Windows raw thermal printing.")


def get_available_printers() -> List[str]:
    """
    Returns a list of all installed printer names detected by the OS.
    Uses Win32 spooler enumeration on Windows.
    """
    if IS_WINDOWS and win32print:
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            return [p[2] for p in printers]
        except Exception as e:
            logger.error(f"Error enumerating Windows printers: {e}")
            return []

    # Non-Windows development fallback
    return ["XP-80C (Simulated)", "POS-58 (Simulated)", "Mock Thermal Printer"]


def print_raw(printer_name: str, data: bytes, doc_name: str = "OrderPrintJob") -> Tuple[bool, Optional[str]]:
    """
    Sends raw ESC/POS binary data directly to the local Windows print spooler.
    Completely silent: NO print dialogs, NO browser windows, NO user popups.
    """
    if not printer_name or not printer_name.strip():
        return False, "No printer name configured in config.json"

    if IS_WINDOWS:
        if not win32print:
            return False, "win32print module unavailable on this system."

        h_printer = None
        try:
            # 1. Open the printer handle
            h_printer = win32print.OpenPrinter(printer_name)

            # 2. Begin document with RAW data type (bypasses Windows GDI formatting)
            job_info = (doc_name, None, "RAW")
            win32print.StartDocPrinter(h_printer, 1, job_info)

            try:
                win32print.StartPagePrinter(h_printer)
                win32print.WritePrinter(h_printer, data)
                win32print.EndPagePrinter(h_printer)
            finally:
                win32print.EndDocPrinter(h_printer)

            logger.info(f"Direct raw bytes ({len(data)} B) sent to '{printer_name}' [Doc: {doc_name}]")
            return True, None

        except Exception as e:
            err_msg = f"Printer unavailable or error sending to '{printer_name}': {e}"
            logger.error(err_msg)
            return False, err_msg

        finally:
            if h_printer:
                try:
                    win32print.ClosePrinter(h_printer)
                except Exception:
                    pass

    else:
        # Development / macOS / Linux simulation fallback
        try:
            logs_dir = get_base_dir() / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

            bin_file = logs_dir / "simulated_print.bin"
            with open(bin_file, "wb") as f:
                f.write(data)

            txt_file = logs_dir / "simulated_print.txt"
            with open(txt_file, "w", encoding="utf-8", errors="replace") as f:
                f.write(data.decode("latin1", errors="replace"))

            logger.info(
                f"[SIMULATION] Saved {len(data)} bytes to {bin_file} and preview to {txt_file} for '{printer_name}'"
            )
            return True, None
        except Exception as e:
            return False, f"Simulation write failed: {e}"
