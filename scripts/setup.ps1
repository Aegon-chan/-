# =============================================================================
# Research Agent — 环境初始化脚本
# =============================================================================

Write-Host "=== Research Agent 环境初始化 ===" -ForegroundColor Cyan

# 1. 创建虚拟环境
$venvPath = ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "[1/4] 创建 Python 虚拟环境..." -ForegroundColor Yellow
    python -m venv $venvPath
    Write-Host "  ✓ 虚拟环境已创建: $venvPath" -ForegroundColor Green
} else {
    Write-Host "[1/4] 虚拟环境已存在，跳过" -ForegroundColor Green
}

# 2. 激活虚拟环境并安装依赖
Write-Host "[2/4] 安装 Python 依赖..." -ForegroundColor Yellow
$pip = Join-Path $venvPath "Scripts\pip.exe"
if (-not (Test-Path $pip)) {
    $pip = "pip"
}

# 分步安装，便于排查
& $pip install --upgrade pip
& $pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  ✗ 依赖安装失败，请检查 requirements.txt" -ForegroundColor Red
    exit 1
}

# 3. 初始化 .env
Write-Host "[3/4] 初始化环境配置..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ .env 已创建（请编辑填入 API Key）" -ForegroundColor Green
} else {
    Write-Host "  ✓ .env 已存在，跳过" -ForegroundColor Green
}

# 4. 创建数据目录
Write-Host "[4/4] 创建数据目录..." -ForegroundColor Yellow
$dirs = @(
    "data\raw",
    "data\processed",
    "data\logs",
    "data\chroma_db",
    "data\memories",
    "data\lora_checkpoints",
    "reports\output"
)
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "  ✓ 数据目录已创建" -ForegroundColor Green

Write-Host ""
Write-Host "=== 环境初始化完成 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 编辑 .env 文件填入 API Key"
Write-Host "  2. 运行 .venv\Scripts\Activate.ps1 激活环境"
Write-Host "  3. 运行 scripts\dev.ps1 启动开发服务器"
