# NM System V9 Unified

Clean rebuild from scratch with Discord OAuth dashboard login.

## Railway Variables
Required:
- TOKEN
- DASHBOARD_SECRET_KEY
- NM_DATA_DIR=/data
- DASHBOARD_BASE_URL=https://your-service.up.railway.app
- DISCORD_CLIENT_ID
- DISCORD_CLIENT_SECRET

Optional future:
- OPENAI_API_KEY

## Discord OAuth Redirect
Add this in Discord Developer Portal -> OAuth2 -> Redirects:

`https://your-service.up.railway.app/auth/discord/callback`

## Run
```bash
pip install -r requirements.txt
python main.py
```
