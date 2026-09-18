# InsightRAG 发布到 GitHub 的辅助脚本
# 会做 secret 扫描、检查 .gitignore，然后 commit + push。
# 需要机器已通过 `gh auth login` 或已配置 git remote。

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==> 检查 .gitignore 与敏感文件" -ForegroundColor Cyan

$sensitive = @(".env", "data/", "node_modules", "__pycache__", ".venv", "venv")
foreach ($s in $sensitive) {
    if (git ls-files $s) {
        Write-Host "警告: $s 已被 git 追踪，请先检查 .gitignore 并从索引移除" -ForegroundColor Red
    }
}

Write-Host "==> 扫描潜在密钥" -ForegroundColor Cyan
$secretPatterns = @("JWT_SECRET", "OPENAI_COMPATIBLE_API_KEY", "password_hash")
foreach ($p in $secretPatterns) {
    $hits = git grep -l $p -- "*.py" "*.md" "*.json" 2>$null
    if ($hits) {
        Write-Host "提示: 发现含 $p 的文件，请确认不含真实密钥" -ForegroundColor Yellow
        Write-Host $hits -ForegroundColor Yellow
    }
}

Write-Host "==> 当前 git 状态" -ForegroundColor Cyan
git status --short

Write-Host "==> 提交并推送" -ForegroundColor Cyan
git add -A
git commit -m "docs: finalize demo data and scripts" --no-verify

$remote = git remote get-url origin 2>$null
if ($remote) {
    git push -u origin main
} else {
    Write-Host "未配置 remote，尝试用 gh 创建并推送..." -ForegroundColor Yellow
    gh repo create insight-rag --public --source . --remote origin --push
}

Write-Host "完成。" -ForegroundColor Green
