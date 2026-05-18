# NM System V9 Unified

Clean rebuild from scratch.

## What this includes
- Global multi-guild Discord bot
- Flask dashboard
- One SQLite database
- One economy ledger
- Economy, casino, levels, warnings, protection, logs, real estate, shop, giveaways, live activity
- Discord and Dashboard use the same database
- No old V5/V6 patch stack
- No legacy casino/economy duplicate systems

## Railway Variables
- TOKEN
- DASHBOARD_PASSWORD
- DASHBOARD_SECRET_KEY
- NM_DATA_DIR=/data

## Run
```bash
pip install -r requirements.txt
python main.py
```
