# InsightRAG 开发环境一键启动脚本
# 依次启动：PostgreSQL(Docker) -> 后端(FastAPI) -> 前端(Vite)
# 前提：Docker Desktop 已运行；Ollama 已运行（可选，用于 Embedding / LLM）

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==> 1/3 启动 PostgreSQL + pgvector (Docker)" -ForegroundColor Cyan
docker-compose up -d
Start-Sleep -Seconds 5

Write-Host "==> 2/3 启动后端 FastAPI (http://127.0.0.1:8000)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "==> 3/3 启动前端 Vite (http://localhost:5173)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host ""
Write-Host "启动完成：" -ForegroundColor Green
Write-Host "  前端: http://localhost:5173" -ForegroundColor Green
Write-Host "  后端: http://127.0.0.1:8000 (Swagger: /docs)" -ForegroundColor Green
Write-Host "  数据库: localhost:5433" -ForegroundColor Green
Write-Host ""
Write-Host "首次使用请先 seed 演示数据：" -ForegroundColor Yellow
Write-Host "  python scripts/seed_demo_data.py" -ForegroundColor Yellow
