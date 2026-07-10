param(
    [int]$Port = 8501,
    [int]$WaitSeconds = 25,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppPath = Join-Path $ProjectRoot "app.py"
$StreamlitExe = Join-Path $ProjectRoot ".venv\Scripts\streamlit.exe"

if (-not (Test-Path -LiteralPath $StreamlitExe)) {
    throw "streamlit.exe not found: $StreamlitExe"
}

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like "*streamlit*" -and
        (
            $_.CommandLine.Contains($AppPath) -or
            ($_.CommandLine.Contains($ProjectRoot) -and $_.CommandLine.Contains("app.py"))
        )
    }

foreach ($proc in $processes) {
    Write-Host "Stopping old Streamlit process PID=$($proc.ProcessId)"
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

if ($NoStart) {
    Write-Host "Old process check complete. NoStart mode skips launch."
    exit 0
}

Write-Host "Starting ETF dashboard: http://127.0.0.1:$Port"
Start-Process -FilePath $StreamlitExe `
    -ArgumentList @("run", $AppPath, "--server.port=$Port", "--server.address=127.0.0.1", "--server.headless=true", "--server.runOnSave=true") `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden

$url = "http://127.0.0.1:$Port"
$ready = $false
for ($i = 0; $i -lt $WaitSeconds; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            $ready = $true
            break
        }
    } catch {
        # Streamlit can take several seconds before it starts listening.
    }
}

if ($ready) {
    Write-Host "Dashboard is ready: $url"
} else {
    Write-Host "Dashboard is still starting. Try opening it manually in a few seconds: $url"
}
