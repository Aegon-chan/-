# =============================================================================
# Research Agent 鈥?鐜鍒濆鍖栬剼鏈?# =============================================================================

Write-Host "=== Research Agent 鐜鍒濆鍖?===" -ForegroundColor Cyan

# 1. 鍒涘缓铏氭嫙鐜
$venvPath = ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "[1/5] 鍒涘缓 Python 铏氭嫙鐜..." -ForegroundColor Yellow
    python -m venv $venvPath
    Write-Host "  鉁?铏氭嫙鐜宸插垱寤? $venvPath" -ForegroundColor Green
} else {
    Write-Host "[1/5] 铏氭嫙鐜宸插瓨鍦紝璺宠繃" -ForegroundColor Green
}

# 2. 婵€娲昏櫄鎷熺幆澧冨苟瀹夎渚濊禆
Write-Host "[2/5] 瀹夎 Python 渚濊禆..." -ForegroundColor Yellow
$pip = Join-Path $venvPath "Scripts\pip.exe"
if (-not (Test-Path $pip)) {
    $pip = "pip"
}

# 鍒嗘瀹夎锛屼究浜庢帓鏌?& $pip install --upgrade pip
& $pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "  鉁?渚濊禆瀹夎瀹屾垚" -ForegroundColor Green
} else {
    Write-Host "  鉁?渚濊禆瀹夎澶辫触锛岃妫€鏌?requirements.txt" -ForegroundColor Red
    exit 1
}

# 3. 鍒濆鍖?.env
Write-Host "[3/5] 鍒濆鍖栫幆澧冮厤缃?.." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  鉁?.env 宸插垱寤猴紙璇风紪杈戝～鍏?API Key锛? -ForegroundColor Green
} else {
    Write-Host "  鉁?.env 宸插瓨鍦紝璺宠繃" -ForegroundColor Green
}

# 4. 鍒涘缓鏁版嵁鐩綍
Write-Host "[5/5] 鍒涘缓鏁版嵁鐩綍..." -ForegroundColor Yellow
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
Write-Host "  鉁?鏁版嵁鐩綍宸插垱寤? -ForegroundColor Green

Write-Host ""
Write-Host "=== 鐜鍒濆鍖栧畬鎴?===" -ForegroundColor Cyan
Write-Host ""
Write-Host "涓嬩竴姝?" -ForegroundColor Yellow
Write-Host "  1. 缂栬緫 .env 鏂囦欢濉叆 API Key"
Write-Host "  2. 杩愯 .venv\Scripts\Activate.ps1 婵€娲荤幆澧?
Write-Host "  3. 杩愯 scripts\dev.ps1 鍚姩寮€鍙戞湇鍔″櫒"

