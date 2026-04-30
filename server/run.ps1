# 성가 선곡 어시스턴트 서버 기동
# 사용: powershell -File server\run.ps1

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Set-Location $projectRoot

if (Test-Path "$scriptDir\.env") {
    Get-Content "$scriptDir\.env" | ForEach-Object {
        if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') {
            $name = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

if (-not $env:ANTHROPIC_API_KEY) {
    Write-Warning "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다. server/.env 를 만드세요."
}

python -m uvicorn server.app:app --host 0.0.0.0 --port 10007
