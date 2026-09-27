import asyncio
import json
import logging
from typing import Any, Dict, Optional

import websockets
from config import Config
from database import db
from formatter import format_bill, format_kot
from printer import print_raw

logger = logging.getLogger("RestaurantPrintAgent.WebSocket")


class WebSocketPrintClient:
    """
    Persistent asyncio WebSocket client for receiving print jobs from Django Channels.
    Maintains continuous connection with exponential backoff and direct job processing.
    """

    def __init__(self, config: Config):
        self.config = config
        self.is_running = True
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

    async def start(self) -> None:
        """Main connection and reconnection lifecycle loop."""
        backoff_delays = [1, 2, 4, 8, 16, 30]
        attempt = 0

        logger.info(
            f"Agent starting for Branch #{self.config.branch_id} on Printer '{self.config.printer_name}'"
        )

        while self.is_running:
            url = self.config.get_websocket_url()

            logger.info(f"Connecting to WebSocket: {url}")

            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=5,
                ) as ws:
                    self.ws = ws
                    attempt = 0  # Reset backoff on successful connect
                    logger.info("Connected to WebSocket printer stream.")

                    # Message Listening Loop
                    async for raw_msg in ws:
                        if not self.is_running:
                            break
                        await self._handle_message(raw_msg)

            except asyncio.CancelledError:
                logger.info("WebSocket listener task cancelled.")
                break

            except Exception as e:
                self.ws = None
                max_delay = self.config.reconnect_interval_max
                base_delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                delay = min(base_delay, max_delay)

                logger.warning(
                    f"WebSocket disconnected ({e}). Retrying in {delay} seconds..."
                )
                attempt += 1

                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    break

        logger.info("WebSocket client stopped.")

    def stop(self) -> None:
        """Signals the client to terminate cleanly."""
        self.is_running = False

    async def _handle_message(self, raw_msg: str) -> None:
        """Parses and routes inbound WebSocket payloads."""
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message from server: {raw_msg[:100]}")
            return

        msg_type = msg.get("type")

        # Handle connection confirmation or heartbeats
        if msg_type in ("connected", "pong"):
            logger.info(f"Server message: {msg.get('message', 'OK')}")
            return

        if msg_type == "ping":
            if self.ws:
                await self.ws.send(json.dumps({"type": "pong"}))
            return

        # Handle print jobs
        if msg_type == "print_order":
            await self._process_print_job(msg)

    async def _process_print_job(self, msg: Dict[str, Any]) -> None:
        """
        Executes print pipeline:
          Validation -> Duplicate check -> Format ESC/POS -> Spool -> Send ACK

        Backend payload structure:
          {
            "type": "print_order",
            "data": {
              "job_id": ...,
              "job_type": "KOT" | "BILL",
              "order": { ... }
            }
          }
        """
        # Fields are nested under "data" in the backend payload
        data = msg.get("data") or {}
        job_id = data.get("job_id") or msg.get(
            "job_id"
        )  # fallback to top-level for safety
        job_type = str(data.get("job_type") or msg.get("job_type", "KOT")).upper()
        order = data.get("order") or msg.get("order") or {}
        order_number = str(order.get("order_number", "UNKNOWN"))

        logger.info(
            f"[RECEIVE] print_order — job_id={job_id}, job_type={job_type}, order={order_number}"
        )

        if not job_id:
            logger.error("Invalid print message: missing 'job_id'")
            return

        logger.info(
            f"Received print job {job_id} ({job_type}) for Order #{order_number}"
        )

        # 1. Duplicate Protection Gate
        if db.already_printed(str(job_id)):
            logger.info(
                f"Job {job_id} already printed previously. Sending duplicate ACK."
            )
            await self._send_ack(job_id=job_id, success=True)
            return

        # 2. Format Ticket
        try:
            width_mm = self.config.paper_width_mm
            if job_type == "KOT":
                raw_bytes = format_kot(order, width_mm=width_mm)
            elif job_type == "BILL":
                raw_bytes = format_bill(order, width_mm=width_mm)
            else:
                err = f"Unsupported job_type: '{job_type}'"
                logger.error(err)
                await self._send_ack(job_id=job_id, success=False, error=err)
                return
        except Exception as e:
            err = f"Failed to format receipt for Order #{order_number}: {e}"
            logger.error(err)
            await self._send_ack(job_id=job_id, success=False, error=err)
            return

        # 3. Send Bytes to Thermal Printer
        logger.info(
            f"Printing {job_type} {order_number} to '{self.config.printer_name}'..."
        )
        success, err = print_raw(
            self.config.printer_name, raw_bytes, doc_name=f"{job_type}_{order_number}"
        )

        if success:
            logger.info(
                f"Print successful: {job_type} for Order #{order_number} (Job ID: {job_id})"
            )
            db.record_print(str(job_id), order_number=order_number, job_type=job_type)
            await self._send_ack(job_id=job_id, success=True)
        else:
            logger.error(f"Print failed for Order #{order_number}: {err}")
            await self._send_ack(
                job_id=job_id, success=False, error=err or "Printer unavailable"
            )

    async def _send_ack(
        self, job_id: Any, success: bool, error: Optional[str] = None
    ) -> None:
        """Sends print_ack JSON back to Django server."""
        if not self.ws or self.ws.closed:
            logger.warning(
                f"Cannot send ACK for job {job_id}: WebSocket not connected."
            )
            return

        ack = {
            "type": "print_ack",
            "job_id": job_id,
            "success": success,
        }
        if error:
            ack["error"] = error

        try:
            await self.ws.send(json.dumps(ack))
            logger.info(f"Sent ACK for job {job_id} (success={success})")
        except Exception as e:
            logger.error(f"Failed to send ACK for job {job_id}: {e}")
