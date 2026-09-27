# Restaurant Thermal Print Agent

A minimal, production-ready, headless background print agent for Windows. Built for the **CallEatMandu** multi-restaurant delivery system.

The application runs entirely in the background as a native **Windows Service** (or invisible process). It maintains a persistent WebSocket connection to Django Channels, listens for print jobs on `printer_branch_{branch_id}`, formats **Kitchen Order Tickets (KOT)** and **Customer Bills**, prints directly and silently to the local thermal printer using raw ESC/POS commands, and dispatches an acknowledgment back to Django.

---

## 🚫 No GUI / Silent Background Architecture

* **Zero GUI**: No PySide6, no Tkinter, no browser popups, no system tray, no notification dialogs.
* **Zero Backend On Premise**: The restaurant computer runs **ONLY** `RestaurantPrintAgent.exe` and its printer driver. **No Django, PostgreSQL, Redis, Node.js, or Docker is installed on the restaurant PC.**
* **Direct Raw Spooling**: Uses `pywin32` (`win32print.StartDocPrinter(..., "RAW")`) to send raw ESC/POS command bytes straight to the Windows print spooler. Never opens Chrome or a browser print dialog.

```text
                Django VPS (Remote)
                         │
                         │ WSS (Encrypted WebSocket)
                         ▼
             RestaurantPrintAgent.exe
             (C:\RestaurantPrintAgent\)
                         │
                         │ USB / Direct Spooler (RAW ESC/POS)
                         ▼
                  Thermal Printer
                  (e.g., XP-80C)
                   │           │
                   ▼           ▼
             Kitchen Order   Customer
             Ticket (KOT)      Bill
```

---

## 📁 Project Structure

```text
restaurant-print-agent/
├── agent.py               # Main headless CLI entrypoint & async runner
├── config.py              # Loads and validates config.json
├── websocket_client.py    # Persistent WebSocket client, auth, print flow & ACK
├── printer.py             # Raw Windows spooler printing via pywin32
├── formatter.py           # Pure ESC/POS binary formatter for KOT and Bills
├── database.py            # SQLite database for duplicate protection & idempotency
├── service.py             # Windows Service wrapper using pywin32
├── build.bat              # PyInstaller automated Windows .exe compiler
├── install_service.bat    # Windows Service automated installer & auto-recovery
├── uninstall_service.bat  # Windows Service clean uninstaller
├── test_agent.py          # Unit test suite
├── config.json.example    # Configuration template
├── requirements.txt       # Minimal dependencies
└── README.md              # Operations & deployment manual
```

---

## ⚙️ Configuration (`config.json`)

Create `config.json` beside `RestaurantPrintAgent.exe`:

```json
{
  "server_url": "wss://api.example.com/ws/printer/15/",
  "branch_id": 15,
  "printer_name": "XP-80C",
  "paper_width_mm": 80,
  "reconnect_interval_max": 30
}
```

### Configuration Options

| Key | Type | Description |
| :--- | :--- | :--- |
| `server_url` | String | Django Channels WebSocket endpoint (`wss://...` or `ws://...`) |
| `branch_id` | Integer / String | Assigned restaurant branch identifier |
| `printer_name` | String | Exact Windows printer name as shown in Windows Settings |
| `paper_width_mm` | Integer | Thermal roll width (`80` for 80mm/48-col, `58` for 58mm/32-col) |
| `reconnect_interval_max` | Integer | Max backoff delay in seconds for reconnection (default: 30) |

---

## 🏪 Production Restaurant Installation (Step-by-Step)

Follow these exact steps when provisioning a restaurant computer:

### Step 1: Install Printer Driver
Plug the thermal printer into the Windows computer via USB. Run the manufacturer driver installer (e.g., Xprinter XP-80C driver, Epson TM driver).

### Step 2: Confirm Printer in Windows
Open:
```text
Windows Settings -> Bluetooth & devices -> Printers & scanners
```
Verify the printer appears and is marked **Ready**.

### Step 3: Note Exact Printer Name
Click on the printer to check its name (e.g., `XP-80C`, `POS-80`, or `EPSON TM-T20III`).

### Step 4: Copy Files to Restaurant PC
Create the folder:
```text
C:\RestaurantPrintAgent\
```
Copy into this folder:
* `RestaurantPrintAgent.exe`
* `config.json`
* `install_service.bat`
* `uninstall_service.bat`

### Step 5: Configure `config.json`
Open `C:\RestaurantPrintAgent\config.json` in Notepad and set:
* `server_url`: `wss://api.calleatmandu.com/ws/printer/<branch_id>/`
* `branch_id`: Assigned branch number
* `printer_name`: Exact printer name found in Step 3

### Step 6: Install and Start Background Service
Right-click `install_service.bat` and select **Run as administrator**.

The script will:
1. Register `RestaurantPrintAgent` as an automatic Windows Service (`start= auto`).
2. Configure automatic crash recovery (restarts automatically after 5s, 10s, 30s).
3. Start the service immediately.

### Step 7: Verification
The agent connects to Django, authenticates silently, and sits idle waiting for orders. You can verify live operation by checking:
```cmd
type C:\RestaurantPrintAgent\logs\agent.log
```

---

## 🛠️ Operational & Testing Commands

### 1. Local Development
```bash
# Activate virtual environment
source ../env/bin/activate    # macOS/Linux
# or .\venv\Scripts\activate  # Windows

cd restaurant-print-agent
pip install -r requirements.txt
```

### 2. Verify Configuration & Detect Printers
```bash
python agent.py --config config.json.example --test-config
```
Output displays validated parameters and lists all installed printers.

### 3. Test Physical Printer (Diagnostic Test Print)
```bash
python agent.py --config config.json.example --test-printer
```
Sends a diagnostic test receipt with branch ID and printer information.

### 4. Run Unit Tests
```bash
python -m unittest test_agent.py
```
Runs 6 automated tests validating config parsing, token masking, duplicate prevention, and KOT/Bill ESC/POS formatting.

### 5. Run Agent in Foreground (For Debugging)
```bash
python agent.py --foreground
```
Runs the agent in interactive console mode showing live WebSocket events and raw printer logs.

### 6. Test WebSocket Connection & Auth Handshake
Using Python:
```python
import asyncio, websockets, json

async def test():
    async with websockets.connect("ws://127.0.0.1:8000/ws/printer/15/") as ws:
        await ws.send(json.dumps({
            "type": "authenticate",
            "printer_id": 7,
            "branch_id": 15,
            "token": "YOUR_SECRET_TOKEN"
        }))
        print("Server Response:", await ws.recv())

asyncio.run(test())
```

### 7. Send Test KOT Print Job (from Django Shell)
```bash
python manage.py shell
```
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    "printer_branch_15",
    {
        "type": "print_order",
        "data": {
            "job_id": 1001,
            "job_type": "KOT",
            "order": {
                "order_number": "ORD-1025",
                "restaurant_name": "ABC Restaurant",
                "order_type": "DELIVERY",
                "created_at": "2026-09-27T14:20:00",
                "notes": "Extra spicy",
                "items": [
                    {"name": "Chicken Momo", "quantity": 2},
                    {"name": "Chowmein", "quantity": 1}
                ]
            }
        }
    }
)
```

### 8. Send Test BILL Print Job (from Django Shell)
```python
async_to_sync(channel_layer.group_send)(
    "printer_branch_15",
    {
        "type": "print_order",
        "data": {
            "job_id": 1002,
            "job_type": "BILL",
            "order": {
                "order_number": "ORD-1025",
                "restaurant_name": "ABC Restaurant",
                "order_type": "DELIVERY",
                "created_at": "2026-09-27T14:20:00",
                "customer": {"name": "John", "phone": "9800000000"},
                "items": [
                    {"name": "Chicken Momo", "quantity": 2, "price": "150.00", "total": "300.00"},
                    {"name": "Chowmein", "quantity": 1, "price": "200.00", "total": "200.00"}
                ],
                "subtotal": "500.00",
                "delivery_fee": "50.00",
                "discount": "0.00",
                "total": "550.00"
            }
        }
    }
)
```

### 9. Build Standalone `.exe`
Run `build.bat` on a Windows machine:
```cmd
build.bat
```
Generates `dist\RestaurantPrintAgent.exe`.

### 10. Service Management Commands (Windows CMD as Administrator)
* **Check Service Status**:
  ```cmd
  sc query RestaurantPrintAgent
  ```
* **Start Service**:
  ```cmd
  net start RestaurantPrintAgent
  ```
* **Stop Service**:
  ```cmd
  net stop RestaurantPrintAgent
  ```
* **Uninstall Service**:
  ```cmd
  uninstall_service.bat
  ```
* **View Live Logs**:
  ```cmd
  type C:\RestaurantPrintAgent\logs\agent.log
  ```

---

## 🔒 Security & Idempotency Guarantees

1. **Authentication Gate**: The agent authenticates immediately upon connecting. If credentials are rejected by Django, the socket is disconnected and will retry after backoff delay. Print jobs sent to unauthenticated connections are discarded.
2. **Token Masking**: The printer secret token is never written to disk logs or printed on receipts.
3. **Duplicate Protection**: Every print job contains a unique `job_id`. Once successfully printed, the `job_id` is recorded in local SQLite database (`data/printer_jobs.db`). If the server resends the same job after a reconnection, the agent acknowledges the job without reprinting.
4. **Resilient Reconnection**: If the internet or Django server drops, the agent backs off exponentially (1s, 2s, 4s, 8s, 16s, 30s) and automatically re-authenticates when connectivity returns.
5. **Printer Offline Safety**: If the thermal printer is powered off or unplugged from USB, the agent logs `Printer unavailable` and returns a failed ACK without crashing.
