# Botify Observability Demo Platform - PowerShell Launcher
Write-Host "========================================================" -ForegroundColor Gold
Write-Host " Launching Botify Observability Demo Platform..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Gold

# Check Python Installation
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Error: Python 3 is required to run the backend engine." -ForegroundColor Red
    Exit 1
}

# Install dependencies if needed
Write-Host "Checking & installing Python package requirements..." -ForegroundColor Yellow
python -m pip install -r requirements.txt --quiet

# Launch Backend Server
Write-Host "Starting Botify Demo Server on http://localhost:8000 ..." -ForegroundColor Green
python run.py
