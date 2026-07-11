# =============================================================================
# Research Agent — PyInstaller 桌面打包脚本 (Windows)
#
# 将 NiceGUI 前端 + 所有后端模块打包为 Windows 可执行文件。
# 生成结果位于 dist/ResearchAgent/ 目录。
# =============================================================================

param(
    [switch]$Console,       # 保留控制台窗口（调试用）
    [switch]$OneFile,       # 打包为单个 .exe（较大，启动慢）
    [switch]$SkipTests      # 跳过打包前的测试
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot

Write-Host "=== Research Agent — 桌面打包 ===" -ForegroundColor Cyan
Write-Host "  项目目录: $ProjectRoot"
Write-Host ""

# ── Step 1: 运行测试 ──
if (-not $SkipTests) {
    Write-Host "[1/4] 运行单元测试..." -ForegroundColor Yellow
    $activate = Join-Path $ProjectRoot ".venv" "Scripts" "Activate.ps1"
    if (Test-Path $activate) {
        & $activate
    }
    $testResult = & python -m pytest tests/ -v --tb=short 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  测试失败，中止打包。请先修复测试。" -ForegroundColor Red
        Write-Host $testResult
        exit 1
    }
    Write-Host "  ✅ 全部测试通过" -ForegroundColor Green
} else {
    Write-Host "[1/4] 跳过测试" -ForegroundColor Yellow
}

# ── Step 2: 检查 PyInstaller ──
Write-Host "[2/4] 检查 PyInstaller..." -ForegroundColor Yellow
$pyinstaller = Get-Command "pyinstaller" -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "  安装 PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller
}
Write-Host "  ✅ PyInstaller 就绪" -ForegroundColor Green

# ── Step 3: 确保数据目录存在 ──
Write-Host "[3/4] 准备数据目录..." -ForegroundColor Yellow
$dirs = @(
    "data\raw", "data\processed", "data\logs",
    "data\chroma_db", "data\memories", "data\lora_checkpoints",
    "reports\output"
)
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  创建: $dir"
    }
}
Write-Host "  ✅ 数据目录就绪" -ForegroundColor Green

# ── Step 4: 执行打包 ──
Write-Host "[4/4] 执行 PyInstaller 打包..." -ForegroundColor Yellow

$pyinstallerArgs = @(
    "research-agent.spec",
    "--clean",
    "--noconfirm"
)

# 添加图标（如果存在）
$iconPath = Join-Path $ProjectRoot "frontend" "assets" "icon.ico"
if (Test-Path $iconPath) {
    $pyinstallerArgs += "--icon=$iconPath"
}

if ($Console) {
    Write-Host "  模式: 调试模式（显示控制台）" -ForegroundColor Cyan
} else {
    # 默认无控制台（GUI 模式）
    Write-Host "  模式: GUI 应用（无控制台）" -ForegroundColor Cyan
}

if ($OneFile) {
    Write-Host "  打包方式: 单文件 (--onefile)" -ForegroundColor Cyan
    pyinstaller @pyinstallerArgs --onefile
} else {
    Write-Host "  打包方式: 文件夹" -ForegroundColor Cyan
    pyinstaller @pyinstallerArgs
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========== 打包成功 ==========" -ForegroundColor Green
    Write-Host ""
    if ($OneFile) {
        $exePath = Join-Path $ProjectRoot "dist" "ResearchAgent.exe"
        if (Test-Path $exePath) {
            Write-Host "  可执行文件: $exePath" -ForegroundColor Cyan
        }
    } else {
        $distPath = Join-Path $ProjectRoot "dist" "ResearchAgent"
        if (Test-Path $distPath) {
            Write-Host "  输出目录: $distPath" -ForegroundColor Cyan
            Write-Host "  可执行文件: $(Join-Path $distPath 'ResearchAgent.exe')" -ForegroundColor Cyan
        }
    }
    Write-Host "  大小:" -ForegroundColor Cyan
    Get-ChildItem -Path $distPath -Recurse -File | Measure-Object -Property Length -Sum | ForEach-Object {
        $sizeMB = [math]::Round($_.Sum / 1MB, 1)
        Write-Host "    $sizeMB MB" -ForegroundColor Cyan
    }
    Write-Host ""
    Write-Host "使用说明:" -ForegroundColor Yellow
    Write-Host "  直接运行 ResearchAgent.exe 即可启动应用" -ForegroundColor White
    Write-Host "  应用将在 http://localhost:8080 打开" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "========== 打包失败 ==========" -ForegroundColor Red
    Write-Host "请检查上述错误信息" -ForegroundColor Red
    exit 1
}
