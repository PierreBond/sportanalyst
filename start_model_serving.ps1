$root = "C:\Users\DELL\OneDrive\Desktop\sportanalyst"
$env:PYTHONPATH = "$root\libs;$root\services\model_serving\src"
$env:DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/sportspred"
$env:DATABASE_URL_SYNC = "postgresql://user:pass@localhost:5432/sportspred"
$env:API_KEY = "dev-key-123"
Set-Location $root\services\model_serving
Write-Host "Model-serving service starting on http://localhost:8004" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
& "$root\.venv\Scripts\uvicorn.exe" src.main:app --host 0.0.0.0 --port 8004 --reload
