import asyncio
import logging
import sys
import threading
from pathlib import Path

from config import Config
from agent import setup_logging
from websocket_client import WebSocketPrintClient

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class RestaurantPrintService(win32serviceutil.ServiceFramework):
        """
        Native Windows Service framework wrapper for Restaurant Thermal Print Agent.
        Runs silently in the background on system boot without user login.
        """
        _svc_name_ = "RestaurantPrintAgent"
        _svc_display_name_ = "Restaurant Thermal Print Agent"
        _svc_description_ = (
            "Background thermal printing agent for CallEatMandu food delivery platform. "
            "Automatically prints KOTs and Bills directly to the local receipt printer."
        )

        def __init__(self, args):
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.is_running = True
            self.client = None
            self.loop = None
            self.worker_thread = None

        def SvcStop(self):
            """Triggered when Windows requests service shutdown or stop."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.is_running = False

            if self.client:
                self.client.stop()

            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)

            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self):
            """Main entry point executed by Windows Service Control Manager."""
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )

            logger = setup_logging(foreground=False)
            logger.info("=== Windows Service: RestaurantPrintAgent Started ===")

            try:
                config = Config()
                self.client = WebSocketPrintClient(config)

                # Run asyncio loop in background thread
                def run_loop():
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)
                    try:
                        self.loop.run_until_complete(self.client.start())
                    finally:
                        self.loop.close()

                self.worker_thread = threading.Thread(target=run_loop, daemon=True)
                self.worker_thread.start()

                # Wait for Windows stop signal
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

            except Exception as e:
                logger.critical(f"Fatal error in Windows Service execution: {e}", exc_info=True)
            finally:
                logger.info("=== Windows Service: RestaurantPrintAgent Stopped ===")

    if __name__ == "__main__":
        win32serviceutil.HandleCommandLine(RestaurantPrintService)

else:
    # Non-Windows stub
    def main():
        print("service.py is designed for Windows Services using pywin32.")
        print("To run the agent on macOS/Linux in background or terminal, run:")
        print("  python agent.py --foreground")

    if __name__ == "__main__":
        main()
