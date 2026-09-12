# AGENTS.md

## Architecture at a glance

- **Entry point:** `bot_pa.py` — WSGI app (`application = app_flask`) for PythonAnywhere/Gunicorn AND runnable locally (`python bot_pa.py`, Flask dev server on `0.0.0.0:5000` with reloader). It builds the Flask app, registers 7 blueprints under `/api`, and runs the Telegram `Application` in a **dedicated background event loop** (singleton) so webhook requests can dispatch updates without creating a new loop per request. The bootstrap is guarded by a `bootstrap_lock` / `bootstrap_done` flag; the Werkzeug reloader skip is keyed off `WERKZEUG_RUN_MAIN`.
- **Bot logic:** `bot_core.py` defines `create_and_initialize_app(token, mode, initialize_app)` which wires `CommandHandler` and two `ConversationHandler`s (products, email) from handlers re-exported by `shared/handlers/commands.py` (a façade over `auth.py`, `cart.py`, `products.py`, `payments.py`).
- **Conversation states** live in `utils/constants.py:EstadoConversacion`.
- **Database:** `database/db_manager.py:db_manager` is a **process-wide singleton** (`DatabaseManager` with `__new__`). `database/db_factory.py:DatabaseFactory` is a **per-config cache** keyed by `f"{type}_{hash(frozenset(kwargs))}"` — calling `init_db` twice with different kwargs creates a second instance; with the same kwargs you get the cached one. Three backends: SQLite (`db_pgsql.py`-style adapter, `db_path=`), PostgreSQL (`db_url=` or `DATABASE_URL`), MySQL. The runtime schema is applied automatically by `database/schema_manager.py:initialize_database()` at startup; do not add seed data to the schema files.
- **Schema source of truth:** `database/schema/<db_type>/` contains the incremental schema files (e.g. `001_base_schema.sql`). At startup `database/schema_manager.py:initialize_database()` applies any pending migration and records it in the `schema_migrations` table. The runtime schema is idempotent (`CREATE ... IF NOT EXISTS`) and contains no seed data. Legacy files `pedidos_bot.sql` and `pedidos_bot_postgresql.sql` are kept as reference but are no longer loaded automatically.
- **Two extra databases in the repo** (not SQLite, not used at runtime): `flask-sqlalchemy-postgres-moderno/` and `telegram-webhook-flask-ptb/` are vendored reference projects — do not edit them as if they were part of the app.

## Key conventions / gotchas

- **Bot mode is webhook-only.** `bot_core.py:create_and_initialize_app` raises `ValueError` if `bot_mode != "WEBHOOK"`. `bot_pa.py` coerces `BOT_MODE` to `WEBHOOK` and logs a warning.
- **Webhook URL must include a path token AND a secret header.** `bot_pa.py:webhook()` requires both `TELEGRAM_WEBHOOK_PATH_TOKEN` (URL segment) and `TELEGRAM_WEBHOOK_SECRET_TOKEN` (header `X-Telegram-Bot-Api-Secret-Token`) to be set; otherwise it returns 503. The configured webhook URL is `f"{WEBHOOK_URL}/webhook/{TELEGRAM_WEBHOOK_PATH_TOKEN}"` and must start with `https://`.
- **Default DB type is PostgreSQL** (`utils/config.py:Config.DB_TYPE = DatabaseType.POSTGRESQL` — the SQLITE line is commented out). Tests force `DB_TYPE=sqlite` + `DATABASE_PATH=:memory:` in `tests/conftest.py` before importing the app.
- **Invoice IDs are UUID v7 in both PostgreSQL and SQLite.** `invoices.id` and all `invoice_id` foreign keys are stored as `UUID` in PostgreSQL (via `pg_uuidv7`) and as `TEXT` in SQLite. New invoices receive a UUID v7 generated in pure Python by `utils/uuid_utils.py:uuidv7()`; no native SQLite UUID extension is required. Legacy SQLite databases with integer invoice IDs are migrated by `database/schema/sqlite/005_migrate_invoices_to_uuid.sql` (UUID v4 is generated for existing rows; new rows use v7).
- **SQL placeholders.** SQL written for SQLite uses `?`; `db_pgsql.py:_adapt_query` rewrites `?` to `%s` and strips `INSERT OR IGNORE`. Don't use psycopg2 `%`-formatting style by hand in new code — the adapter handles it.
- **Response formatting for bot output.** Use `utils/formatters.py:TelegramTable(rows, headers=None)` for tabular results (categories, products, etc.). Build via `RowAdapterFactory.create(row, headers)` for sqlite3.Row / psycopg2 RealDictRow / plain tuples. Empty rows render as `<pre>Sin resultados</pre>`.
- **Auth on `/api/*` routes** uses `@api_token_required` (JWT, `shared/decorators.py`) and optionally `@admin_required` (must come **after** `@api_token_required`). The login route is `/api/auth/login` (`routes/auth_routes.py`).
- **MercadoPago** webhook is `/mercadopago-webhook/` (trailing slash — keep it). Return URLs are `/okpago`, `/failpago`, `/pendpago`. Signature validation lives in `utils/mpago.py:verificar_firma`.
- **First admin:** `python create_first_admin.py` — interactive, requires DB reachable and no existing admin (`is_admin=1`) in `customers`. The script is blocked if any admin row already exists; the docs/AGENTS files mention a "first superadmin" but the only programmatic alternative is POST `/api/register` with an existing admin's JWT.
- **Logging is split into two streams.** `utils/logging_config.py:configure_logging()` creates two dedicated `RotatingFileHandler`s: `logs/bot.log` for Telegram activity and `logs/api.log` for Flask API activity. Both propagate to the console via the root logger. Use `utils/logger_factory.py:get_bot_logger(__name__)` in bot handlers and `get_api_logger(__name__)` in API routes; never use `logging.getLogger(__name__)` directly in new bot/API modules. Use `log_bot_event(logger, update, action)` for high-level bot events so `telegram_user_id` is captured.
- **Log levels are independent.** `BOT_LOG_LEVEL` (default `DEBUG`) and `API_LOG_LEVEL` (default `INFO`) control each file. `LOG_LEVEL` still acts as a fallback for both. Rotation is size-based: `LOG_MAX_BYTES` (default 10 MB) and `LOG_BACKUP_COUNT` (default 5). Set `LOG_DIR` to change the output directory (default `./logs`).
- **Never log sensitive data.** Do not log passwords, verification codes, JWT tokens, Telegram secret tokens, or raw payment payloads (headers, bodies). MercadoPago webhook logs only topic/resource_id/result.
- **API request traceability.** Every Flask request is logged with a `request_id` generated in `bot_pa.py:before_request` and included in the `api.log` format. Bot logs include `telegram_user_id` via `log_bot_event` / `logger` extra fields.
- **Tests avoid writing logs.** `tests/conftest.py` sets `LOG_DIR` to a temp directory so file handlers (if ever initialized by bot imports) do not write to the repo.

## Commands

Run from project root (Windows PowerShell 5.1):

```powershell
# Install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Local dev (Flask + PTB webhook bootstrap in one process)
python bot_pa.py
# Expose to Telegram:
ngrok http 5000
# Point Telegram at it (one-shot):
curl -F "url=https://<ngrok>/webhook/<TELEGRAM_WEBHOOK_PATH_TOKEN>" `
     https://api.telegram.org/bot<BOT_TOKEN>/setWebhook
# Reconfigure from a script (see getupdates.py for the same flow):
python getupdates.py
# Production WSGI:
gunicorn --workers 4 --bind 0.0.0.0:8000 "bot_pa:application"

# Tests (the only configured test runner — no pytest.ini/pyproject.toml)
pytest -v
pytest tests/test_admin_api.py -v            # single file
pytest tests/test_admin_api.py -k login      # single test pattern
pytest --cov=. --cov-report=term-missing

# Schema / migrations
python database/apply_schema.py --database sqlite --db-path ./pedidos_bot.db
python database/apply_schema.py --database postgresql --connection-string "$env:DATABASE_URL"
python database/apply_schema.py --database postgresql --db-host localhost --db-name db --db-user admin --db-password pass

# Mark existing schema as applied (legacy databases)
python database/apply_schema.py --database postgresql --connection-string "$env:DATABASE_URL" --mark-applied

# The app verifies (not applies) the schema at startup. Set DB_AUTO_MIGRATE=true
# only for local convenience; prefer apply_schema.py for any environment.
# Add new incremental migrations under database/schema/<db_type>/NNN_description.sql.

# First admin
python create_first_admin.py

# Backups (SQLite)
python scripts/backup_database.py

# Schedule it (examples):
# PythonAnywhere Scheduled Task (daily at 03:00 UTC):
#   /home/<username>/.virtualenvs/<venv>/bin/python /home/<username>/<project>/scripts/backup_database.py
#
# Cron (Linux/VPS) — daily at 03:00:
#   0 3 * * * /home/user/<project>/.venv/bin/python /home/user/<project>/scripts/backup_database.py >> /home/user/<project>/logs/backup_cron.log 2>&1
```

## Schema management

The runtime schema lives under `database/schema/<db_type>/` as numbered SQL
files. There are two roles involved:

- **Administrator (DDL user):** runs `database/apply_schema.py` to create/alter
tables, indexes and extensions. This is the only process that executes DDL.
- **Application (runtime user):** verifies at startup, via
`database/schema_manager.py`, that every known migration is recorded in
`schema_migrations`. If a migration is missing, the app fails with a clear
message pointing to `apply_schema.py`.

`DB_AUTO_MIGRATE=true` can make the app apply migrations itself, but this is
only intended for local convenience. Production and shared environments should
always use `apply_schema.py` with an administrator user.

PostgreSQL notes:
- The extension `pg_uuidv7` must be installed by the administrator before the
app starts (the schema executes `CREATE EXTENSION IF NOT EXISTS pg_uuidv7`).
- If tables were created by a different user, the runtime user will not be able
to create indexes on them; use `apply_schema.py` with the table owner.

SQLite in production (low-cost deployments):
- SQLite is a valid low-cost production option. Set `DB_TYPE=sqlite` and
`DATABASE_PATH=/absolute/path/to/db.sqlite` (or `SQLITE_PATH`).
- Use an absolute path. On PythonAnywhere this is required; on other hosts a
relative path can be lost across deploys or worker restarts.
- Enable WAL for concurrency: it is already set in `database/db_sqlite.py`
(`PRAGMA journal_mode = WAL`). Do not disable it.
- Use `scripts/backup_database.py` for automated backups. It uses SQLite's
online `backup()` API, so it produces a consistent snapshot without requiring
the `-wal`/`-shm` siblings to be copied manually, and it works while the app
is running. Configure `SQLITE_PATH`, `BACKUP_DIR`, and `BACKUP_RETENTION_DAYS`
as needed. See the "Commands" section for scheduling examples on
PythonAnywhere and cron.
- For moderate write concurrency, keep transactions short. The bot uses one
connection per request; long-running operations can block writers.
- Schema changes must still be applied with `python database/apply_schema.py --database sqlite --db-path <path>`.

Legacy databases that already contain the correct schema can be synchronized
with the migration tracker by running `apply_schema.py --mark-applied`. This
only inserts records into `schema_migrations` without executing any SQL.

There is **no** Black/Flake8/mypy/isort configuration in the repo (`requirements.txt` doesn't list them and there is no `pyproject.toml`/`setup.cfg`/`.flake8`). Don't add a `lint` step or assume `black .` is wired anywhere.

## Required `.env` variables

Used at import time in `utils/config.py` and `bot_pa.py`:

- `BOT_TOKEN` — required for bot startup
- `WEBHOOK_URL` — must be `https://`; if missing, `setup_webhook()` only logs a warning and the bot still starts
- `TELEGRAM_WEBHOOK_PATH_TOKEN`, `TELEGRAM_WEBHOOK_SECRET_TOKEN` — **both required** for `/webhook/<token>` to accept updates (503 otherwise)
- `SECRET_KEY` — Flask session/uploads
- `DB_TYPE` — `sqlite`, `postgresql` or `mysql` (default `postgresql`); controls which backend and schema are loaded at startup
- `DATABASE_URL` — required for PostgreSQL backend
- `DATABASE_PATH` or `SQLITE_PATH` — SQLite database file path (default `./data.db`)
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` — used for MySQL backend
- `DB_AUTO_MIGRATE` — `true/1/yes/on` to apply migrations at startup (default `false`); production and local development should use `database/apply_schema.py` instead
- `JWT_SECRET_KEY` (fallback `your-secret-key-change-in-production` — change in prod), `JWT_ACCESS_TOKEN_EXPIRES` (default 3600), `JWT_REFRESH_TOKEN_EXPIRES` (default 2592000)
- `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT` (default 465), `EMAIL_FROM_NAME`, `BUSINESS_NAME`, `BUSINESS_EMAIL`, `SEND_PDF_MODE` (default `EMAIL`)
- `MP_ACCESS_TOKEN` — MercadoPago SDK init
- `DEBUG_MODE` (truthy values: `1/true/yes/on`) and `LOG_LEVEL` (e.g. `INFO`, `DEBUG`)
- `LOG_DIR` (default `./logs`), `BOT_LOG_LEVEL` (default `DEBUG`), `API_LOG_LEVEL` (default `INFO`), `LOG_MAX_BYTES` (default `10485760`), `LOG_BACKUP_COUNT` (default `5`)
- For PythonAnywhere: `PYTHONANYWHERE_DOMAIN` triggers `bootstrap_webhook_runtime()` on WSGI import (so PTB initializes once per worker, not per request)

## Test layout

- `conftest.py` (root) only adds the project root to `sys.path`.
- `tests/conftest.py` sets test env vars **before** any app import and provides fixtures: `app` (function-scope Flask app built from a long-lived in-memory SQLite connection wrapping `pedidos_bot.sql` via a duck-typed shim — see `_build_persistent_db`), `client`, `auth_headers` / `access_token`, `admin_auth_headers` / `admin_access_token`, `setup_test_user`, `setup_test_admin`. The shim exists because `SQLiteDatabase` opens a fresh connection per call, which would lose the schema for `:memory:`.
- Async handler tests use `@pytest.mark.asyncio` (pytest-asyncio 1.3) and build fake `Update`/`Context` objects with `SimpleNamespace` + `AsyncMock` — see `tests/test_checkout_handlers.py` for the pattern.
- API tests use `app.test_client()` and JSON bodies. Login as the seeded admin with `username: TEST_ADMIN_USER` / `password: TEST_ADMIN_PASSWORD` from `tests/conftest.py`.
- `EmailService.clear_sent_emails()` is called between tests to reset the in-memory mailbox.

## Endpoint map (for verification)

- `GET /` — landing HTML (links to `/api/*` resources)
- `GET /health`, `GET /health_db` — health probes
- `POST /webhook/<TELEGRAM_WEBHOOK_PATH_TOKEN>` — Telegram updates
- `POST /mercadopago-webhook/` — MP notifications (note trailing slash)
- `GET|POST /<estado>` — payment return URLs (`okpago`, `failpago`, `pendpago`)
- `/api/...` — blueprints: `auth`, `admin`, `csv`, `products`, `categories`, `customers`, `invoices` (all require JWT except `auth/login`, `auth/refresh`, and registration/password-reset flows)
  - `GET /api/products/<id>/stock` — current inventory (JWT)
  - `POST /api/products/<id>/stock` — add stock, admin only (JWT + admin)

## Things agents commonly get wrong here

- Importing `from shared.handlers.commands import ...` for handlers is fine — that module is a façade. The real handler implementations live in `shared/handlers/{auth,cart,products,payments}.py`. `shared/handlers/commands_new.py` exists but is **not** the one wired up.
- The schema has a `customers` table (API users live there) that is distinct from the bot's "cliente" concept handled by the `customers` service.
- `utils/init_database.py` is a **standalone** SQLite bootstrap script with its own minimal schema (`productos`, `clientes`, `pedidos`) — it is **not** what the app uses at runtime. The runtime schema is loaded from `database/schema/<db_type>/` by `database/schema_manager.py`.
- Do not run `python ejemplo_corto1.py` or `python getupdates.py` against a real webhook unless you intend to reset the live `setWebhook` (the script does `deleteWebhook?drop_pending_updates=true`).
- The `database/db_manager.py:db_manager` singleton stores the chosen DB on `_db`. Tests reset it via `db_manager._db = None` between cases — if you add code that reads the manager without `get_db()`, you may bypass test cleanup.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->
