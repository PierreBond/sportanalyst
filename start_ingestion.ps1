$root = "C:\Users\DELL\OneDrive\Desktop\sportanalyst"
$env:PYTHONPATH = "$root\services\ingestion;$root\libs"
Set-Location $root
Write-Host "Ingestion service starting on http://localhost:8001" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
& "$root\.venv\Scripts\uvicorn.exe" src.main:app --host 0.0.0.0 --port 8001 --reload
