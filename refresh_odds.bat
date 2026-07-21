@echo off
cd /d "C:\Users\DELL\OneDrive\Desktop\sportanalyst"
set DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/sportspred
python scripts\refresh_odds.py
pause
