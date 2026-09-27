import json
import tempfile
import unittest
from pathlib import Path

from config import Config
from database import Database
from formatter import format_bill, format_kot, format_test, ESC, GS
from printer import get_available_printers, print_raw

SAMPLE_ORDER = {
    "order_number": "ORD-1025",
    "restaurant_name": "ABC Restaurant",
    "order_type": "DELIVERY",
    "created_at": "2026-09-27T14:20:00",
    "notes": "Spicy, extra chutney",
    "customer": {
        "name": "John",
        "phone": "9800000000",
    },
    "items": [
        {
            "name": "Chicken Momo",
            "quantity": 2,
            "price": "150.00",
            "total": "300.00",
        },
        {
            "name": "Chowmein",
            "quantity": 1,
            "price": "200.00",
            "total": "200.00",
        },
    ],
    "subtotal": "500.00",
    "delivery_fee": "50.00",
    "discount": "0.00",
    "total": "550.00",
}


class TestPrintAgent(unittest.TestCase):

    def test_config_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = Path(tmpdir) / "config.json"
            cfg_data = {
                "server_url": "wss://api.example.com/ws/printer/15/",
                "branch_id": 15,
                "printer_name": "XP-80C",
            }
            with open(cfg_file, "w") as f:
                json.dump(cfg_data, f)

            cfg = Config(config_path=cfg_file)
            self.assertEqual(cfg.branch_id, 15)
            self.assertEqual(cfg.printer_name, "XP-80C")
            self.assertEqual(cfg.get_websocket_url(), "wss://api.example.com/ws/printer/15/")
            self.assertEqual(cfg.paper_width_mm, 80)

    def test_database_duplicate_protection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test.db"
            db = Database(db_path=db_file)

            # Initially not printed
            self.assertFalse(db.already_printed("job_101"))

            # Record print
            db.record_print("job_101", order_number="ORD-1025", job_type="KOT")

            # Now should be detected as already printed
            self.assertTrue(db.already_printed("job_101"))
            self.assertFalse(db.already_printed("job_102"))

    def test_kot_formatting(self):
        kot_bytes = format_kot(SAMPLE_ORDER, width_mm=80)
        self.assertIsInstance(kot_bytes, bytes)
        self.assertIn(ESC + b"@", kot_bytes)   # Reset/Init command
        self.assertIn(GS + b"VA\x03", kot_bytes)  # Cut command

        text = kot_bytes.decode("latin1", errors="ignore")
        self.assertIn("KITCHEN ORDER", text)
        self.assertIn("ORD-1025", text)
        self.assertIn("Chicken Momo", text)
        self.assertIn("x2", text)
        self.assertIn("Chowmein", text)
        self.assertIn("x1", text)
        self.assertIn("Spicy, extra chutney", text)
        # Verify customer payment/delivery fees are omitted from KOT
        self.assertNotIn("550.00", text)

    def test_bill_formatting(self):
        bill_bytes = format_bill(SAMPLE_ORDER, width_mm=80)
        self.assertIsInstance(bill_bytes, bytes)

        text = bill_bytes.decode("latin1", errors="ignore")
        self.assertIn("ABC RESTAURANT", text)
        self.assertIn("ORD-1025", text)
        self.assertIn("Chicken Momo", text)
        self.assertIn("300.00", text)
        self.assertIn("Chowmein", text)
        self.assertIn("200.00", text)
        self.assertIn("Subtotal", text)
        self.assertIn("TOTAL", text)
        self.assertIn("550.00", text)
        self.assertIn("THANK YOU", text)

    def test_format_test(self):
        test_bytes = format_test(branch_id=15, printer_name="XP-80C", width_mm=80)
        self.assertIsInstance(test_bytes, bytes)
        text = test_bytes.decode("latin1", errors="ignore")
        self.assertIn("RESTAURANT PRINT AGENT", text)
        self.assertIn("Printer Test Successful", text)
        self.assertIn("15", text)
        self.assertIn("XP-80C", text)

    def test_simulated_print(self):
        test_bytes = format_test(branch_id=15, printer_name="XP-80C", width_mm=80)
        success, err = print_raw("XP-80C", test_bytes, doc_name="UnitTesting")
        self.assertTrue(success)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
