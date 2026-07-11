# =============================================================================
# Research Agent 开发服务器启动脚本
# =============================================================================

Write-Host "=== Research Agent 开发服务器 ===" -ForegroundColor Cyan

# 配置
$BACKEND_PORT = 8000
$FRONTEND_PORT = 8080
$VENV_PATH = ".venv"
$ACTIVATE = Join-Path $VENV_PATH "Scripts\Activate.ps1"

# 激活虚拟环境
if (Test-Path $ACTIVATE) {
    Write-Host "激活虚拟环境..." -ForegroundColor Yellow
    & $ACTIVATE
} else {
    Write-Host "警告: 未找到虚拟环境，使用系统 Python" -ForegroundColor Red
}

# 端口清理函数
function Free-Port($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        $pid = $conn.OwningProcess
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  端口 $port 被 $($proc.ProcessName) (PID $pid) 占用，正在释放..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep 1
        }
    }
}

Write-Host "检查端口..." -ForegroundColor Yellow
Free-Port $BACKEND_PORT
Free-Port $FRONTEND_PORT

Write-Host ""
Write-Host "启动服务:" -ForegroundColor Cyan
Write-Host "  后端 API:  http://localhost:$BACKEND_PORT"
Write-Host "  API 文档:   http://localhost:$BACKEND_PORT/docs"
Write-Host "  前端界面:  http://localhost:$FRONTEND_PORT"
Write-Host ""

# 并行启动后端和前端
$backendJob = Start-Job -ScriptBlock {
    param($dir, $port)
    Set-Location $dir
    python -m uvicorn backend.main:app --host 0.0.0.0 --port $port --reload
} -ArgumentList $PWD, $BACKEND_PORT

Start-Sleep 2

$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    python -m frontend.app
} -ArgumentList $PWD

Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor Yellow

try {
    while ($true) {
        $backendStatus = $backendJob | Receive-Job
        $frontendStatus = $frontendJob | Receive-Job
        if ($backendJob.State -eq "Failed") {
            Write-Host "后端异常: $($backendJob.ChildJobs[0].JobStateInfo.Reason)" -ForegroundColor Red
            break
        }
        if ($frontendJob.State -eq "Failed") {
            Write-Host "前端异常: $($frontendJob.ChildJobs[0].JobStateInfo.Reason)" -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "正在停止服务..." -ForegroundColor Yellow
    $backendJob | Stop-Job -PassThru | Remove-Job
    $frontendJob | Stop-Job -PassThru | Remove-Job
    Write-Host "服务已停止" -ForegroundColor Green
}
