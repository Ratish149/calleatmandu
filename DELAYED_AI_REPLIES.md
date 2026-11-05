# Delayed, Human-Cancellable AI Replies (Celery + Redis)

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
Inbound messages schedule the reply through **Celery** with a `countdown` equal to
`AI_REPLY_DELAY_SECONDS`. While that countdown runs, a human operator can reply or
take over, and the scheduled reply is **revoked/ignored**. Each new inbound
message **resets** the countdown, giving the operator a fresh window.

Because the reply is now produced **in a separate Celery worker process**, Redis is
required for two things:

1. **Celery broker/result backend** — carries the delayed task.
2. **Channels layer (`channels_redis`)** — the worker sends the AI message and then
   broadcasts websocket events; an in-memory channel layer would not reach
   clients connected to the `daphne` (web) process.

> TL;DR: delaying was possible with a thread + sleep, but the chosen durable design
> (survive restarts, revocable, decoupled worker) needs Redis.

---

## 2. Behavior

1. Customer sends a message → `Message` (INBOUND) saved → websocket broadcast →
   `AI_REPLY_DELAY_SECONDS` countdown scheduled.
2. During the countdown:
   - **Human replies** (send message) → bot deactivated, task revoked. ✔ cancelled
   - **Human clicks "takeover"** → bot deactivated, task revoked. ✔ cancelled
   - **Customer sends another message** → countdown resets (debounced). ↻
3. If the countdown elapses with no human action, the worker generates the reply
   and sends it (still re-checking that the task is the current one).
4. Semantics preserved from before:
   - The first **human** reply permanently deactivates the bot for that conversation.
   - A new inbound message **auto-reactivates** the bot (inbound overrides takeover).

### Correctness guards
Each scheduled task gets a unique `task_id` stored on the conversation
(`Conversation.ai_reply_task_id`). A task only acts if that id still matches:

- At task start (`_is_current_pending`).
- Immediately before sending (`_send_if_still_pending`).
- When clearing the pending flag in `finally` (`_clear_pending_if_current`).

So even if Celery `revoke()` arrives too late (the task already started), a
superseded/cancelled task can never send a stale reply, and an old task can never
clear a newer task's pending flag.

---

## 3. Files added / changed

### Added
| File | Purpose |
|---|---|
| `calleatmandu/celery.py` | Celery app, reads `CELERY_*` Django settings, autodiscovers tasks. |
| `message/tasks.py` | `send_ai_reply` task + `revoke_task()` helper. |
| `message/migrations/0004_conversation_ai_reply_task_id.py` | Adds `Conversation.ai_reply_task_id`. |
| `DELAYED_AI_REPLIES.md` | This document. |

### Changed
| File | Change |
|---|---|
| `requirements.txt` | Added `celery==5.6.3`, `channels-redis==4.3.0`, `redis==6.4.0`. |
| `calleatmandu/__init__.py` | Imports the Celery app so `celery -A calleatmandu` works. |
| `calleatmandu/settings.py` | `AI_REPLY_DELAY_SECONDS`, `REDIS_URL`, `CELERY_*`; `CHANNEL_LAYERS` now `channels_redis` when `REDIS_URL` is set, else in-memory. |
| `message/models.py` | `Conversation.ai_reply_task_id` field. |
| `message/services/ai_reply_service.py` | `maybe_schedule_reply` schedules/reschedules a Celery task; `deactivate`/`activate` revoke; `_generate_and_send` is now the task body with task-id guards; removed `threading`. |
| `message/management/commands/resume_ai_replies.py` | Also clears `ai_reply_task_id`. |
| `common/apps.py` | Enables SQLite **WAL** + busy timeout via `connection_created` signal. |
| `docker-compose.yaml` | Added `redis` and `worker` services; `REDIS_URL` wiring. |
| `message/tests.py` | Celery eager mode; updated thread tests; new guard/debounce/revoke tests. |
| `.env` | Commented guidance for the new variables (no behavior change). |

Key entry points:
- Scheduling: `message/services/ai_reply_service.py` → `maybe_schedule_reply`
- Task: `message/tasks.py` → `send_ai_reply`
- Task body/guards: `message/services/ai_reply_service.py` → `_generate_and_send`, `_is_current_pending`, `_send_if_still_pending`, `_clear_pending_if_current`
- Trigger: `message/services/messaging_service.py` → `handle_incoming_webhook` (calls `maybe_schedule_reply`)
- Human reply/Takeover: `send_message` → `AIReplyService.deactivate`; `ConversationTakeoverAIAPIView`

---

## 4. Configuration

All via environment variables (`.env` or the orchestrator's env). Defaults in
`calleatmandu/settings.py`.

| Variable | Default | Description |
|---|---|---|
| `AI_REPLY_DELAY_SECONDS` | `120` | Seconds the bot waits before answering on its own. Set `0` to answer almost immediately. |
| `REDIS_URL` | *(empty)* | Redis connection string used for **both** the Celery broker/result backend and the Channels layer. **Required in production.** |
| `CELERY_BROKER_URL` | `REDIS_URL` or `memory://` | Override broker only if you want it separate from `REDIS_URL`. |
| `CELERY_RESULT_BACKEND` | `REDIS_URL` or `cache+memory://` | Override result backend only if needed. |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | When `true`, tasks run inline in the web process (no worker, delay ignored). For tests/local only. |

Channels decision:
- `REDIS_URL` set → `channels_redis.core.RedisChannelLayer` (multi-process safe).
- `REDIS_URL` empty → `channels.layers.InMemoryChannelLayer` (single process only).

---

## 5. Deployment

### 5.1 Docker Compose (bundled Redis)

`docker-compose.yaml` now defines:

- `redis` (persistent via `calleatmandu_redis_data` volume),
- `web` (`daphne`, runs migrations on start),
- `worker` (`celery -A calleatmandu worker -l info --concurrency=1 --pool=solo`).

`REDIS_URL` defaults to `redis://redis:6379/0` inside Compose, and is overridable
(`REDIS_URL=${REDIS_URL:-redis://redis:6379/0}`).

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
3. Confirm the worker is consuming:
   ```sh
   docker compose logs -f worker
   ```

Worker flags note:
- `--pool=solo --concurrency=1` is used because the project runs on **SQLite**
  (avoids writer contention). See §7.
- On Linux/Postgres you can drop `--pool=solo` and raise concurrency:
  `celery -A calleatmandu worker -l info --concurrency=4`.

### 5.2 Coolify / managed Redis

Preferred for production: point at a managed Redis instead of the bundled container.

1. Create a Redis instance (Coolify addon or external provider).
2. Set the `REDIS_URL` environment variable for **both** the `web` and `worker`
   services (e.g. `redis://default:PASSWORD@host:6379/0`, or `rediss://...` for TLS).
3. Deploy the `worker` as a separate process/container with the same env and code as
   `web`, command:
   ```
   celery -A calleatmandu worker -l info --concurrency=1 --pool=solo
   ```
   (raise concurrency if not on SQLite).
4. Run migrations once (`python manage.py migrate`) — the `web` command already does
   this.
5. Ensure only **one** worker consumes the queue per environment unless you have
   scaled the DB (see §7).

Because `load_dotenv(..., override=False)` is used, real environment variables win
over anything in `.env`, so Coolify-provided values take precedence.

### 5.3 Migrations summary

Only one new migration:
`message/migrations/0004_conversation_ai_reply_task_id.py` (adds a nullable,
indexed `ai_reply_task_id` column). It is additive and non-destructive.

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
Then in three terminals:
```sh
python manage.py runserver          # web (or daphne)
# Windows:
celery -A calleatmandu worker -l info --pool=solo
# Linux/macOS:
celery -A calleatmandu worker -l info
```

**Option B — no Redis (inline, for quick checks):**
```
CELERY_TASK_ALWAYS_EAGER=true
```
Tasks run inline in the web process; `AI_REPLY_DELAY_SECONDS` is ignored and the
webhook blocks while the reply is generated. Do **not** use this in production.

> Reminder: with no `REDIS_URL` and no eager mode, the broker is `memory://` and
> **no worker exists**, so AI replies are silently queued in memory and never sent.

Windows workers require `--pool=solo` for local runs (billiard prefork is
problematic on Windows).

---

## 7. SQLite caveats (current database)

The project currently uses SQLite (`calleatmandu/settings.py`), and `.env` DB_* keys
are not wired up (the Postgres block is commented out). A Celery worker is a second
process writing to the same SQLite file, which can cause `database is locked`.

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
1. Is `REDIS_URL` set and is the worker running? Check `docker compose logs worker`.
2. Did a human reply/takeover within the window? That is expected cancellation.
3. Is the delay unusually long? Check `AI_REPLY_DELAY_SECONDS`.
4. Is the conversation stuck with `ai_reply_pending=True`? Run:
   ```sh
   python manage.py resume_ai_replies --include-active
   ```
   This re-enables AI and clears `ai_reply_pending` / `ai_reply_task_id` (including
   conversations stuck mid-generation).

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
correctness problem because the task re-checks the DB before acting.

### Task seems to vanish / another project's worker is running
Celery uses the **default queue name `celery`** and, by default, Redis **DB 0**.
If two Django projects share `redis://host:6379/0`, their workers consume from the
same queue: a worker from the other project will receive this project's task, log
"Received unregistered task", and discard it — leaving the conversation stuck with
`ai_reply_pending=True`. `revoke`/pidbox broadcasts also leak to the wrong worker.

Fix: give each project its own Redis database (or its own queue name). For example,
in this project's `.env`:
```
REDIS_URL=redis://localhost:6379/1
```
This isolates both the Celery broker/result backend and the Channels layer. Restart
the web process **and** the worker after changing it. Recover any conversations left
stuck with:
```sh
python manage.py resume_ai_replies --include-active
```

### Tuning the delay
- Lower `AI_REPLY_DELAY_SECONDS` (e.g. `30`) for faster automation.
- Set `0` for near-instant replies while keeping the new architecture.
- The value is read at scheduling time, so a restart/redeploy picks up changes.

---

## 9. Testing

The suite runs Celery in **eager** mode (set in `message/tests.py`), so no broker or
worker is needed:
```sh
python manage.py test
```
Covered behaviors:
- Inbound schedules a task; pending reply is rescheduled on a new inbound (debounce).
- Inbound reactivates an inactive conversation.
- A stale task id cannot send a reply and does not clear a newer task's pending flag.
- `deactivate`/`activate` revoke the pending task and clear `ai_reply_task_id`.
- Existing generation, human-takeover, signature, language, and tool tests.

---

## 10. Rollback

Quick, no code revert required:
- To restore near-instant replies: set `AI_REPLY_DELAY_SECONDS=0`.
- To make replies inline again without a worker: set `CELERY_TASK_ALWAYS_EAGER=true`
  (note: blocks the web request during generation and ignores the delay).
- To fully revert the feature, restore the previous `threading.Thread` based
  `maybe_schedule_reply` / `deactivate` / `activate` and remove the Redis/worker
  services. The additive migration can stay (harmless nullable column) or be rolled
  back with `python manage.py migrate message 0003`.

---

## 11. Possible future improvements

- **Periodic safety-net** (`celery beat`) to clear conversations stuck with
  `ai_reply_pending=True` (e.g. after a crash).
- **Retries on Ollama failure** with backoff (currently a failed generation simply
  drops the reply; the next inbound reschedules).
- **Migrate to Postgres** and raise worker concurrency.
- **Surface the countdown** in the operator UI (the serializer already exposes
  `ai_reply_pending`/`ai_replies_active`; `ai_reply_task_id` is available on the
  model if a countdown/status widget is desired).
