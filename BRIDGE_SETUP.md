# MT5 Windows Bridge Setup (Free Option)

## A) Linux server (already running trader)
1. Generate bridge token:
```bash
openssl rand -hex 32
```
2. Put it in `/opt/linkat-mj-trader/.env`:
```env
BRIDGE_TOKEN=PUT_RANDOM_TOKEN_HERE
```
3. Start bridge API:
```bash
cd /opt/linkat-mj-trader
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/run_bridge_api.sh
```

## B) Windows machine
1. Copy folder `bridge/windows` to Windows.
2. Copy `.env.example` to `.env` and fill:
   - `BRIDGE_API_BASE=http://<linux-ip>:8787`
   - `BRIDGE_TOKEN=<same token>`
   - MT5 credentials
3. Run `run_bridge.bat`
4. Keep MT5 terminal running and logged in.

## C) Verify
- Linux:
```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8787/bridge/state
```
You should see `snapshot` populated.
