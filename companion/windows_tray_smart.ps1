# Montara SMART Beta -- isolated Windows tray, adapted from Fernando's W3L prototype.
# Uses only the local Python Companion; never stops another application.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$root = $PSScriptRoot
$launcher = Join-Path $root "smart_beta_launcher.py"
$origin = "https://montara-owner.memoriainvalida001.workers.dev"
$state = Join-Path $env:LOCALAPPDATA "MontaraSMARTBeta"
$port = 47820

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    [System.Windows.Forms.MessageBox]::Show("Falta smart_beta_launcher.py.", "Montara SMART Beta") | Out-Null
    exit 2
}
$python = (Get-Command python -ErrorAction Stop).Source
$null = New-Item -ItemType Directory -Path $state -Force
$busy = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    [System.Windows.Forms.MessageBox]::Show(
        "El puerto 47820 esta ocupado. No cerraremos ni sustituiremos otro Companion.",
        "Montara SMART Beta"
    ) | Out-Null
    exit 3
}

$env:MONTARA_COMPANION_HOME = $state
$env:MONTARA_COMPANION_PORT = "$port"
$child = $null
$tray = $null
$timer = $null
$menu = $null
$context = $null
$quitAllowed = $false

function Get-LocalHealth {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:47820/health" -Headers @{ Origin = $origin } -TimeoutSec 2
    } catch {
        return $null
    }
}

try {
    $child = Start-Process -FilePath $python -ArgumentList @("smart_beta_launcher.py") -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $state "stdout.log") -RedirectStandardError (Join-Path $state "stderr.log") -PassThru

    $context = New-Object System.Windows.Forms.ApplicationContext
    $menu = New-Object System.Windows.Forms.ContextMenuStrip

    $status = New-Object System.Windows.Forms.ToolStripMenuItem
    $status.Enabled = $false
    $status.Text = "Estado: iniciando"
    [void]$menu.Items.Add($status)

    $openBeta = New-Object System.Windows.Forms.ToolStripMenuItem
    $openBeta.Text = "Abrir Montara SMART Beta"
    $openBeta.Add_Click({ Start-Process $origin })
    [void]$menu.Items.Add($openBeta)

    $check = New-Object System.Windows.Forms.ToolStripMenuItem
    $check.Text = "Comprobar Companion local"
    $check.Add_Click({ Start-Process "http://127.0.0.1:47820/health" })
    [void]$menu.Items.Add($check)

    [void]$menu.Items.Add("-")
    $exit = New-Object System.Windows.Forms.ToolStripMenuItem
    $exit.Text = "Salir (solo sin trabajos)"
    $exit.Add_Click({
        $stateNow = Get-LocalHealth
        if ($stateNow -and $stateNow.busy) {
            [System.Windows.Forms.MessageBox]::Show(
                "Hay un render, proxy o mezcla en curso. Termina el trabajo antes de salir.",
                "Montara SMART Beta"
            ) | Out-Null
            return
        }
        if (-not $stateNow -and $child -and -not $child.HasExited) {
            [System.Windows.Forms.MessageBox]::Show(
                "No se puede confirmar si hay un trabajo en curso. Companion continuara ejecutandose.",
                "Montara SMART Beta"
            ) | Out-Null
            return
        }
        $script:quitAllowed = $true
        $context.ExitThread()
    })
    [void]$menu.Items.Add($exit)

    $tray = New-Object System.Windows.Forms.NotifyIcon
    $tray.Icon = [System.Drawing.SystemIcons]::Application
    $tray.Text = "Montara SMART Beta"
    $tray.ContextMenuStrip = $menu
    $tray.Visible = $true

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2500
    $timer.Add_Tick({
        $child.Refresh()
        if ($child.HasExited) {
            $status.Text = "Estado: detenido"
            return
        }
        $health = Get-LocalHealth
        if ($null -eq $health) {
            $status.Text = "Estado: iniciando o sin respuesta"
        } elseif ($health.app -ne "montara-companion") {
            $status.Text = "Estado: servicio desconocido"
        } elseif ($health.busy) {
            $status.Text = "Estado: trabajo en curso"
        } else {
            $status.Text = "Estado: listo"
        }
    })
    $timer.Start()
    [System.Windows.Forms.Application]::Run($context)
} finally {
    if ($timer) { $timer.Stop(); $timer.Dispose() }
    if ($tray) { $tray.Visible = $false; $tray.Dispose() }
    if ($menu) { $menu.Dispose() }
    if ($child) {
        $child.Refresh()
        if (-not $child.HasExited -and $quitAllowed) {
            $health = Get-LocalHealth
            if ($health -and $health.app -eq "montara-companion" -and -not $health.busy) {
                # Terminate only our process and its descendants.
                & taskkill.exe /PID $child.Id /T /F *> $null
            }
        }
        $child.Dispose()
    }
}
