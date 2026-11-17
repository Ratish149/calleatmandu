# Delayed, Human-Cancellable AI Replies (Celery + Redis + DB Dispatcher)

This document describes the change that makes the AI inbox bot **wait for a
configurable delay before answering on its own**, and **cancel the pending answer
when a human operator replies or takes over**.

It covers what changed, how it works, configuration, deployment (Docker/Coolify),
local development, operations/troubleshooting, testing, and rollback.

---

## 1. What changed and why

### Before
When a customer message arrived, the Zernio webhook immediately spawned a
`threading.Thread` that generated an Ollama reply and sent it. The bot answered
instantly. A human replying at the same time could take over, but only cancelled
the bot if the bot had not already sent.

### After
Inbound messages persist a due time in the database
(`Conversation.ai_reply_due_at`) equal to now + the branch's reply delay
(`BranchAISettings.ai_reply_delay_seconds`, default 120 seconds). A
periodic Celery beat task (`message.dispatch_due_ai_replies`) claims due
conversations with an atomic lease and generates the reply. While the delay runs, a
human operator can reply or take over, and the pending reply is **ignored**. Each
new inbound message **resets** the due time, giving the operator a fresh window.

Because the due time lives in the database, a stopped worker, a lost broker message,
or a restart no longer silently drops the reply: the next dispatcher run picks up
anything overdue. A short database lease prevents two dispatcher runs from
processing the same conversation at once; if a worker crashes mid-reply, the lease
expires and a later run retries it.

Redis is still required for two things:

1. **Celery broker/result backend** — carries the dispatcher and legacy tasks.
2. **Channels layer (`channels_redis`)** — the worker sends the AI message and then
   broadcasts websocket events; an in-memory channel layer would not reach
   clients connected to the `daphne` (web) process.

> TL;DR: Celery beat wakes up the dispatcher, but the database owns the schedule, so
> delayed replies survive worker/beat downtime.

---

## 2. Behavior

1. Customer sends a message → `Message` (INBOUND) saved → websocket broadcast →
   `Conversation.ai_reply_due_at` set to now + the branch reply delay.
2. During the delay:
   - **Human replies** (send message) → bot deactivated, pending reply cleared. ✔ cancelled
   - **Human clicks "takeover"** → bot deactivated, pending reply cleared. ✔ cancelled
   - **Customer sends another message** → due time resets (debounced). ↻
3. Celery beat runs `dispatch_due_ai_replies` periodically. It finds conversations
   with `ai_reply_pending=True`, `ai_replies_active=True`, and a due time in the
   past (or no due time for legacy rows), atomically claims each with a lease, then
   generates and sends the reply.
4. Semantics preserved from before:
   - The first **human** reply permanently deactivates the bot for that conversation.
   - A new inbound message **auto-reactivates** the bot (inbound overrides takeover).

### Correctness guards
Each scheduled reply gets a unique `task_id` stored on the conversation
(`Conversation.ai_reply_task_id`). A task only acts if that id still matches:

- At task start (`_is_current_pending`).
- Immediately before sending (`_send_if_still_pending`).
- When clearing the pending flag in `finally` (`_clear_pending_if_current`).

The dispatcher claim is an atomic conditional update of `ai_reply_due_at` to a
short future lease. A second dispatcher run sees the future due time and skips the
row. If the first worker dies, the lease expires and the reply is retried. This
gives at-least-once delivery; a crash after Zernio accepted the message but before
the DB was cleared can still produce a duplicate, which is the same trade-off as
Celery `acks_late`.

---

## 3. Files added / changed

### Added
| File | Purpose |
|---|---|
| `calleatmandu/celery.py` | Celery app, reads `CELERY_*` Django settings, autodiscovers tasks. |
| `message/tasks.py` | `send_ai_reply` (legacy), `dispatch_due_ai_replies`, `revoke_task()` helper. |
| `message/migrations/0004_conversation_ai_reply_task_id.py` | Adds `Conversation.ai_reply_task_id`. |
| `message/migrations/0007_branchaisettings_ai_reply_delay_seconds.py` | Adds `BranchAISettings.ai_reply_delay_seconds`. |
| `message/migrations/0008_conversation_ai_reply_due_at.py` | Adds the durable `Conversation.ai_reply_due_at` schedule. |
| `message/management/commands/clear_ai_reply_queue.py` | Clears pending DB state and optionally purges queued Celery messages. |
| `DELAYED_AI_REPLIES.md` | This document. |

### Changed
| File | Change |
|---|---|
| `requirements.txt` | Added `celery==5.6.3`, `channels-redis==4.3.0`, `redis==6.4.0`. |
| `calleatmandu/__init__.py` | Imports the Celery app so `celery -A calleatmandu` works. |
| `calleatmandu/settings.py` | `AI_REPLY_DISPATCH_LEASE_SECONDS`, `CELERY_BEAT_SCHEDULE`, `REDIS_URL`, `CELERY_*`; `CHANNEL_LAYERS` now `channels_redis` when `REDIS_URL` is set, else in-memory. |
| `message/models.py` | `Conversation.ai_reply_task_id` / `ai_reply_due_at`; per-branch `BranchAISettings.ai_reply_delay_seconds` (non-null, default 120s). |
| `message/services/ai_reply_service.py` | `maybe_schedule_reply` persists `ai_reply_due_at`; `dispatch_due_replies` claims and sends due replies; `deactivate`/`activate` clear pending state; `_generate_and_send` keeps task-id guards. |
| `message/management/commands/resume_ai_replies.py` | Also clears `ai_reply_task_id` / `ai_reply_due_at`. |
| `common/apps.py` | Enables SQLite **WAL** + busy timeout via `connection_created` signal. |
| `docker-compose.yaml` | Added `redis`, `worker`, and `beat` services; `REDIS_URL` wiring; worker/beat restart policy. |
| `message/tests.py` | Celery eager mode; due-at scheduling, dispatcher lease, queue-clear, guard/debounce/revoke tests. |
| `.env` | Commented guidance for the new variables (no behavior change). |

Key entry points:
- Scheduling: `message/services/ai_reply_service.py` → `maybe_schedule_reply`
- Dispatcher: `message/services/ai_reply_service.py` → `dispatch_due_replies`; `message/tasks.py` → `dispatch_due_ai_replies`
- Task body/guards: `message/services/ai_reply_service.py` → `_generate_and_send`, `_is_current_pending`, `_send_if_still_pending`, `_clear_pending_if_current`
- Trigger: `message/services/messaging_service.py` → `handle_incoming_webhook` (calls `maybe_schedule_reply`)
- Human reply/Takeover: `send_message` → `AIReplyService.deactivate`; `ConversationTakeoverAIAPIView`

---

## 4. Configuration

Infrastructure flags via environment variables (`.env` or the orchestrator's
env). Defaults in `calleatmandu/settings.py`. The AI reply delay is stored in
the database instead: `BranchAISettings.ai_reply_delay_seconds` (non-null,
default `120`) is set per branch, and branches without a settings row use the
same `120`-second default.

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | *(empty)* | Redis connection string used for **both** the Celery broker/result backend and the Channels layer. **Required in production.** |
| `CELERY_BROKER_URL` | `REDIS_URL` or `memory://` | Override broker only if you want it separate from `REDIS_URL`. |
| `CELERY_RESULT_BACKEND` | `REDIS_URL` or `cache+memory://` | Override result backend only if needed. |
| `AI_REPLY_DISPATCH_INTERVAL_SECONDS` | `15` | How often Celery beat runs the due-reply dispatcher. |
| `AI_REPLY_DISPATCH_LEASE_SECONDS` | `300` | How long a dispatcher claim is reserved while generating. If the worker dies, the reply is retried after this lease expires. |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | When `true`, tasks run inline in the web process (no worker/beat, delay ignored). For tests/local only. |

### Per-branch delay

The delay is configured per branch with the existing AI settings popover/API:

```http
POST /api/conversations/<conversation_id>/ai/order-settings/
{"ai_reply_delay_seconds": 30}
```

- New rows default to `120` seconds; set `0` for near-instant replies.
- `null` resets the branch delay to `120`.
- Conversation responses include the effective value as `ai_reply_delay_seconds`.
- The value is read when an inbound message schedules a reply, so it applies to
  subsequent messages; already-pending replies keep their original due time.
- Branches with no settings row (and conversations without a branch) use `120`.

Channels decision:
- `REDIS_URL` set → `channels_redis.core.RedisChannelLayer` (multi-process safe).
- `REDIS_URL` empty → `channels.layers.InMemoryChannelLayer` (single process only).

---

## 5. Deployment

### 5.1 Docker Compose (bundled Redis)

`docker-compose.yaml` now defines:

- `redis` (persistent via `calleatmandu_redis_data` volume),
- `web` (`daphne`, runs migrations on start),
- `worker` (`celery -A calleatmandu worker -l info --concurrency=1 --pool=solo`),
- `beat` (`celery -A calleatmandu beat -l info`), which enqueues the dispatcher.

`worker` and `beat` use `restart: unless-stopped`. Both are required: beat schedules
the dispatcher, and the worker executes it.

`REDIS_URL` defaults to `redis://redis:6379/0` inside Compose, and is overridable
with `COMPOSE_REDIS_URL` (`REDIS_URL=${COMPOSE_REDIS_URL:-redis://redis:6379/0}`).
The local `.env` `REDIS_URL=localhost` is intentionally ignored inside containers.

`.dockerignore` excludes `.env`, `db.sqlite3`, `.venv`, and media so secrets and
local data are not baked into the image.

Steps:
1. Apply the new migration (the `web` service does this automatically on start, or run it manually):
   ```sh
   python manage.py migrate
   ```
2. Rebuild and start:
   ```sh
   docker compose build
   docker compose up -d
   ```
3. Confirm the worker and beat are running:
   ```sh
   docker compose logs -f worker beat
   ```

Worker flags note:
- `--pool=solo --concurrency=1` is used because the project runs on **SQLite**
  (avoids writer contention). See §7.
- On Linux/Postgres you can drop `--pool=solo` and raise concurrency:
  `celery -A calleatmandu worker -l info --concurrency=4`.

### 5.2 Coolify / managed Redis

Preferred for production: point at a managed Redis instead of the bundled container.

1. Create a Redis instance (Coolify addon or external provider).
2. Set `COMPOSE_REDIS_URL` on the Compose resource so **all** services receive it
   (e.g. `redis://default:PASSWORD@host:6379/0`, or `rediss://...` for TLS). Do not
   use the local `REDIS_URL` name for Compose.
3. Deploy the `worker` as a separate process/container with the same env and code as
   `web`, command:
   ```
   celery -A calleatmandu worker -l info --concurrency=1 --pool=solo
   ```
   (raise concurrency if not on SQLite).
4. Deploy a **single** `beat` process/container:
   ```
   celery -A calleatmandu beat -l info --schedule=/tmp/celerybeat-schedule
   ```
   Do not run multiple beat processes for the same schedule unless you use a
   distributed lock; duplicates are usually harmless because of the DB lease, but
   they waste work.
5. Run migrations once (`python manage.py migrate`) — the `web` command already does
   this.
6. Ensure only **one** worker consumes the queue per environment unless you have
   scaled the DB (see §7).

Because `load_dotenv(..., override=False)` is used, real environment variables win
over anything in `.env`, so Coolify-provided values take precedence.

### 5.3 Migrations summary

Relevant migrations:
- `message/migrations/0004_conversation_ai_reply_task_id.py` (nullable, indexed
  `ai_reply_task_id` column).
- `message/migrations/0006_branchaisettings_ai_chat_enabled.py` (per-branch chat
  toggle).
- `message/migrations/0007_branchaisettings_ai_reply_delay_seconds.py`
  (per-branch reply delay override).
- `message/migrations/0008_conversation_ai_reply_due_at.py` (durable delayed-reply
  due time).

All are additive and non-destructive. Existing pending conversations with
`ai_reply_due_at=NULL` are treated as due immediately by the dispatcher, so they
self-heal after deployment unless you clear them first.

---

## 6. Local development

You have two options.

**Option A — run Redis + a worker (mirrors production):**
```sh
# start a local Redis, e.g.:
docker run --rm -p 6379:6379 redis:7-alpine
```
Set in `.env`:
```
REDIS_URL=redis://localhost:6379/0
```
Then in two terminals:
```sh
python manage.py runserver          # web (or daphne)
# Windows: -B embeds beat in the worker (fine for local single-worker use)
celery -A calleatmandu worker -l info --pool=solo -B
# Linux/macOS:
celery -A calleatmandu worker -l info -B
```
Alternatively run `celery -A calleatmandu beat -l info` in a third terminal. The
dispatcher interval is controlled by `AI_REPLY_DISPATCH_INTERVAL_SECONDS`
(default 15 seconds).

**Option B — no Redis (inline, for quick checks):**
```
CELERY_TASK_ALWAYS_EAGER=true
```
Tasks run inline in the web process; the branch delay is ignored and the
webhook blocks while the reply is generated. Do **not** use this in production.

> Reminder: with no `REDIS_URL` and no eager mode, the broker is `memory://` and
> **no worker/beat exists**, so the due time is persisted but no dispatcher runs.
> Reply once the worker/beat is running; the DB due time is not lost.

Windows workers require `--pool=solo` for local runs (billiard prefork is
problematic on Windows).

---

## 7. SQLite caveats (current database)

The project currently uses SQLite (`calleatmandu/settings.py`), and `.env` DB_* keys
are not wired up (the Postgres block is commented out). A Celery worker is a second
process writing to the same SQLite file, which can cause `database is locked`.

> **Do not run the Compose `worker` in production while the project uses SQLite.**
> `web` and `worker` are separate containers, so each has its own `db.sqlite3`.
> The worker would read different data (or no tables) than the web process. Switch
> to Postgres, or share a single SQLite volume, before enabling the worker.

Mitigations included:
- `common/apps.py` sets `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, and
  `busy_timeout=5000` on every new SQLite connection.
- The Compose worker is pinned to `--concurrency=1 --pool=solo`.

Recommendations:
- Keep worker concurrency at **1** while on SQLite.
- For anything beyond light traffic, switch to Postgres (everything is already
  prepared: `psycopg2-binary` is installed and a Postgres settings block exists,
  commented out). Then raise worker concurrency.

---

## 8. Operations & troubleshooting

### A reply never got sent
1. Is `REDIS_URL` set and are **both** the worker and beat running? Check
   `docker compose logs worker beat`.
2. Did a human reply/takeover within the window? That is expected cancellation.
3. Is the delay unusually long? Check the branch's `ai_reply_delay_seconds`
   (default `120`) and the conversation's `ai_reply_due_at`.
4. Is the dispatcher running? Look for `dispatch_due_ai_replies` in the worker log.
5. Is the conversation stuck with `ai_reply_pending=True`? First clear the stale
   queue:
   ```sh
   python manage.py clear_ai_reply_queue --purge-broker
   ```
   This clears pending DB state and deletes queued Celery messages. To clear a
   single conversation only:
   ```sh
   python manage.py clear_ai_reply_queue --conversation-id 123
   ```
   To re-enable AI and leave the conversation ready for the next inbound:
   ```sh
   python manage.py resume_ai_replies --include-active
   ```

### Bot replied even after a human took over
Not expected: the task-id guards prevent this. If it happens, confirm all processes
share the **same** Redis and the **same** database, and check that the takeover
actually persisted (`ai_replies_active=False`). If needed, inspect Celery:
```sh
celery -A calleatmandu inspect active
celery -A calleatmandu inspect scheduled
```

### WebSocket updates stopped after deploying the worker
This means the worker's broadcasts are going to a different channel layer than the
web process. Ensure `REDIS_URL` is set for **both** `web` and `worker` so both use
`channels_redis`. With in-memory channels, broadcasts cannot cross processes.

### Revoke warning in logs
`revoke_task` is best-effort and swallows errors (logged). A missed revoke is not a
correctness problem because the task re-checks the DB before acting. Celery
`revoke()` is also not a reliable queue purge for tasks already sitting in Redis;
use `clear_ai_reply_queue --purge-broker` if you need the queue emptied now.

### Task seems to vanish / another project's worker is running
Celery uses the **default queue name `celery`** and, by default, Redis **DB 0**.
If two Django projects share `redis://host:6379/0`, their workers consume from the
same queue: a worker from the other project may receive this project's dispatcher
task, log "Received unregistered task", and discard it. The DB due time remains, so
the next beat tick will enqueue it again once the right worker is running, but the
constant churn is still undesirable. `revoke`/pidbox broadcasts also leak to the
wrong worker.

Fix: give each project its own Redis database (or its own queue name). For example,
in this project's `.env`:
```
REDIS_URL=redis://localhost:6379/1
```
This isolates both the Celery broker/result backend and the Channels layer. Restart
the web process, worker, and beat after changing it. Recover any conversations left
stuck with:
```sh
python manage.py clear_ai_reply_queue --purge-broker
python manage.py resume_ai_replies --include-active
```

### Tuning the delay
- Use the AI settings popover/API to set a branch's delay (e.g. `30`) for faster
  automation, or `0` for near-instant replies.
- Branches without a settings row use the `120`-second default.
- The value is read at scheduling time, so changes apply to subsequent messages
  without a restart; already-pending replies keep their original due time.

---

## 9. Testing

The suite runs Celery in **eager** mode (set in `message/tests.py`), so no broker or
worker is needed:
```sh
python manage.py test
```
Covered behaviors:
- Inbound sets a database due time; pending reply is rescheduled on a new inbound
  (debounce).
- Inbound reactivates an inactive conversation.
- Dispatcher sends only due, active, pending conversations; legacy pending rows with
  no due time are picked up.
- A claimed reply is not dispatched twice; a failed generation is retried once its
  lease expires.
- A stale task id cannot send a reply and does not clear a newer task's pending flag.
- `deactivate`/`activate` clear pending state and due time.
- `clear_ai_reply_queue` clears DB state and can purge the broker.
- Existing generation, human-takeover, signature, language, and tool tests.

---

## 10. Rollback

Quick, no code revert required:
- To restore near-instant replies: set the branch delay to `0` via the AI settings
  popover/API (or Django admin).
- To make replies inline again without a worker: set `CELERY_TASK_ALWAYS_EAGER=true`
  (note: blocks the web request during generation and ignores the delay).
- To fully revert the feature, restore the previous `threading.Thread` based
  `maybe_schedule_reply` / `deactivate` / `activate` and remove the Redis/worker/beat
   services. Migrations can stay, or be rolled back with
   `python manage.py migrate message 0007` (removes `ai_reply_due_at` and restores
   the nullable delay column).

---

## 11. Possible future improvements

- **Retries on Ollama failure** with backoff (currently a failed generation simply
  drops the reply; the next inbound reschedules).
- **Idempotency key for Zernio sends** to eliminate the remaining at-least-once
  duplicate window if a worker dies after an external send but before clearing the DB.
- **Migrate to Postgres** and raise worker concurrency.
- **Surface the countdown** in the operator UI. The serializer already exposes
  `ai_reply_pending`/`ai_replies_active`; `ai_reply_due_at` is available on the model
  if a countdown/status widget is desired.
