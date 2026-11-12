# Installing Hearth

Hearth is a Python application. It has one package manager (`pip`, driven by
`requirements.txt`) and one database file it creates itself.

## Prerequisites

Check these first — the installer intentionally does not touch system packages:

- **Python 3.11 or newer** (`python3 --version`)
- **pip** for that interpreter (`python3 -m pip --version`)
- **SQLite 3.35 or newer** — the `sqlite3` module ships with CPython; Hearth only
  needs it, nothing else to install
- About 40 MB of disk for dependencies plus whatever `hearth.db` grows into

Nothing else: no Node, no Redis, no Postgres, no reverse proxy required to run
locally.

## 1. Install the project dependencies (this also creates and seeds the database)

```bash
sh install.sh
```

`install.sh` runs `pip install -r requirements.txt`, copies `.env.example` to
`.env` if you do not have one, creates `data/hearth.db`, seeds the demo household
and exits. It never starts the server, and it is safe to re-run.

Prefer to do it by hand?

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
python3 -m app.seed          # create the schema and the demo data
```

## 2. Seed the demo data as its own step (already done by install.sh)

```bash
python3 -m app.seed
```

Idempotent: run it as often as you like. It prints what it inserted and the demo
login. It exits without binding a port. The server also seeds on boot, so a bare
`python3 -m app.server` on a fresh clone works even if you skip this step.

## 3. Run it in development

```bash
python3 -m app.server
# or any of these, they are the same process:
#   python3 server.py
#   python3 main.py
#   python3 app/server.py
#   sh start.sh
```

Open <http://127.0.0.1:8000> and sign in with the demo account shown on the login
card: **cenius@cenius.ai / cenius**.

The server binds `0.0.0.0` and reads `PORT` (or `APP_PORT`), so you can move it
without editing code:

```bash
PORT=9000 python3 -m app.server
```

## 4. Verify the install

```bash
python3 -m pytest -q        # 37 tests against a throwaway database
python3 tests/smoke.py      # live checks against the server you just started
```

## 5. Run it for real

- Put Hearth behind your reverse proxy and terminate TLS there.
- Set `DATA_DIR` to a backed-up directory; that one folder is the whole state.
- Change or remove the demo accounts before exposing the app to anyone else.
- Optionally point `HEARTH_BOOT_PROBE=0` if you do not want the self-probe tile
  checked at boot.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: sanic` | run `python3 -m pip install -r requirements.txt` with the same interpreter you start the app with |
| `Address already in use` | something else owns the port: `PORT=8001 python3 -m app.server` |
| Login says the credentials are wrong | re-run `python3 -m app.seed` and use the printed demo login |
| Tiles show grey "Never checked" | that service has no recorded check yet — press **Recheck** on the tile |
| A tile shows red | the probe could not reach that URL; the tooltip names the reason (`timeout`, `connection refused`, `HTTP 502`, …) |
