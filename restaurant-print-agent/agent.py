import argparse
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import sys
from pathlib import Path

from config import Config, get_base_dir
from formatter import format_test
from printer import get_available_printers, print_raw


def setup_logging(foreground: bool = False) -> logging.Logger:
    """Configures rotating file logging with 5MB max size and 5 backups."""
    base_dir = get_base_dir()
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "agent.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Rotating File Handler
    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 2. Console Handler (for dev/debugging)
    if foreground or sys.stderr.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    return logging.getLogger("RestaurantPrintAgent")


def run_test_printer(config: Config) -> None:
    """Sends a diagnostic test receipt to verify local thermal printer communication."""
    print(f"Detected Windows / System Printers: {get_available_printers()}")
    print(f"Target Configured Printer: '{config.printer_name}'")

    raw_bytes = format_test(
        branch_id=config.branch_id,
        printer_name=config.printer_name,
        width_mm=config.paper_width_mm,
    )
    success, err = print_raw(config.printer_name, raw_bytes, doc_name="SelfTestReceipt")
    if success:
        print("[SUCCESS] Test receipt printed successfully!")
    else:
        print(f"[FAILED] Could not print test receipt: {err}")
        sys.exit(1)


def run_test_config(config: Config) -> None:
    """Validates configuration file and lists system printers."""
    print("=" * 60)
    print(" Restaurant Print Agent - Configuration Diagnostics")
    print("=" * 60)
    print(f"Config File:     {config.config_path}")
    print(f"Server URL:      {config.server_url}")
    print(f"WebSocket URL:   {config.get_websocket_url()}")
    print(f"Branch ID:       {config.branch_id}")
    print(f"Target Printer:  {config.printer_name}")
    print(f"Paper Width:     {config.paper_width_mm}mm")
    print("-" * 60)

    printers = get_available_printers()
    print("Available Printers on this System:")
    if printers:
        for p in printers:
            mark = "  [*MATCH*]" if p.lower() == config.printer_name.lower() else "  [ ]"
            print(f"{mark} {p}")
    else:
        print("  (No printers detected. Ensure printer USB is connected and driver is installed.)")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="CallEatMandu Restaurant Background Thermal Print Agent")
    parser.add_argument("--config", type=str, default=None, help="Path to custom config.json")
    parser.add_argument("--test-printer", action="store_true", help="Send a test receipt to the configured printer")
    parser.add_argument("--test-config", action="store_true", help="Validate config and check detected printers")
    parser.add_argument("--foreground", action="store_true", help="Run with standard output console logging")
    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config) if args.config else None
    try:
        config = Config(config_path=config_path)
    except Exception as e:
        print(f"[FATAL CONFIG ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if args.test_config:
        run_test_config(config)
        return

    if args.test_printer:
        run_test_printer(config)
        return

    # Normal Background Agent Execution
    logger = setup_logging(foreground=args.foreground)
    logger.info("==================================================")
    logger.info("Restaurant Thermal Print Agent starting...")
    logger.info(f"Target: Branch #{config.branch_id}, Printer: '{config.printer_name}'")
    logger.info(f"Target WebSocket: {config.get_websocket_url()}")
    logger.info("==================================================")

    from websocket_client import WebSocketPrintClient
    client = WebSocketPrintClient(config)

    # Signal handling for graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown_signal():
        logger.info("Shutdown signal received. Stopping client...")
        client.stop()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, shutdown_signal)
            except NotImplementedError:
                # Windows event loop doesn't always support add_signal_handler
                pass
    except Exception:
        pass

    try:
        loop.run_until_complete(client.start())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
    finally:
        client.stop()
        loop.close()
        logger.info("Restaurant Thermal Print Agent stopped cleanly.")


if __name__ == "__main__":
    main()
