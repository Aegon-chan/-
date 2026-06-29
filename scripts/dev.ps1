# =============================================================================
# Research Agent — 开发服务器启动脚本
# =============================================================================

Write-Host "=== Research Agent 开发服务器 ===" -ForegroundColor Cyan

# 检查虚拟环境
$venvPath = ".venv"
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $activate) {
    Write-Host "激活虚拟环境..." -ForegroundColor Yellow
    & $activate
} else {
    Write-Host "警告: 未找到虚拟环境，使用系统 Python" -ForegroundColor Red
}

Write-Host ""
Write-Host "启动服务:" -ForegroundColor Cyan
Write-Host "  后端 API:  http://localhost:8000"
Write-Host "  API 文档:   http://localhost:8000/docs"
Write-Host "  前端界面:  http://localhost:8080"
Write-Host ""

# 并行启动后端和前端（使用后台作业）
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
}

$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m frontend.app
}

Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor Yellow

try {
    # 等待任意一个任务结束
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
