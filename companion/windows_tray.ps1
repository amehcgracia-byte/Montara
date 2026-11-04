# Montara Companion Windows tray prototype (PowerShell 5.1+).
# Run hidden through a Windows shortcut with powershell.exe -STA -WindowStyle Hidden.
# Requires packaged MontaraCompanion.exe beside this file or override env.
# Experimental only: not a signed installer or Windows service.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$root = $PSScriptRoot
$exe = if ($env:MONTARA_COMPANION_EXE) { $env:MONTARA_COMPANION_EXE } else { Join-Path $root "MontaraCompanion.exe" }
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    [System.Windows.Forms.MessageBox]::Show("No se encuentra MontaraCompanion.exe junto al lanzador.", "Montara Companion") | Out-Null
    exit 1
}

$port = 47820
$home = Join-Path $env:LOCALAPPDATA "Montara-Companion"
$null = New-Item -ItemType Directory -Path $home -Force

# Never stop another process using the port.
$occupied = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($occupied) {
    [System.Windows.Forms.MessageBox]::Show("El puerto local 47820 esta ocupado. No se iniciara otro Companion.", "Montara Companion") | Out-Null
    exit 1
}

$child = $null
$icon = $null
$timer = $null
$menu = $null
try {
    $env:MONTARA_COMPANION_HOME = $home
    $env:MONTARA_COMPANION_PORT = "$port"
    $launch = @{
        FilePath = $exe
        WorkingDirectory = (Split-Path -Parent $exe)
        WindowStyle = "Hidden"
        PassThru = $true
        RedirectStandardOutput = (Join-Path $home "stdout.log")
        RedirectStandardError = (Join-Path $home "stderr.log")
    }
    $child = Start-Process @launch

    $ctx = New-Object System.Windows.Forms.ApplicationContext
    $menu = New-Object System.Windows.Forms.ContextMenuStrip
    $status = New-Object System.Windows.Forms.ToolStripMenuItem
    $status.Enabled = $false
    $status.Text = "Estado: iniciando"
    [void] $menu.Items.Add($status)

    $health = New-Object System.Windows.Forms.ToolStripMenuItem
    $health.Text = "Comprobar conexion"
    $health.Add_Click({ Start-Process "http://127.0.0.1:47820/health" })
    [void] $menu.Items.Add($health)

    [void] $menu.Items.Add("-")
    $exit = New-Object System.Windows.Forms.ToolStripMenuItem
    $exit.Text = "Salir de Montara"
    $exit.Add_Click({ $ctx.ExitThread() })
    [void] $menu.Items.Add($exit)

    $icon = New-Object System.Windows.Forms.NotifyIcon
    $icon.Icon = [System.Drawing.SystemIcons]::Application
    $icon.ContextMenuStrip = $menu
    $icon.Text = "Montara Companion - laboratorio"
    $icon.Visible = $true

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2500
    $timer.Add_Tick({
        $child.Refresh()
        if ($child.HasExited) {
            $status.Text = "Estado: detenido"
            return
        }
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:47820/health" -TimeoutSec 2
            $status.Text = if ($response.app -eq "montara-companion") { "Estado: funcionando" } else { "Estado: comprobando" }
        } catch {
            $status.Text = "Estado: iniciando"
        }
    })
    $timer.Start()
    [System.Windows.Forms.Application]::Run($ctx)
} finally {
    if ($timer) { $timer.Stop(); $timer.Dispose() }
    if ($icon) { $icon.Visible = $false; $icon.Dispose() }
    if ($menu) { $menu.Dispose() }
    if ($child) {
        $child.Refresh()
        if (-not $child.HasExited) {
            # /T includes FFmpeg descendants; /PID limits to this owned EXE.
            # Never kill by image name or by port.
            & taskkill.exe /PID $child.Id /T /F *> $null
        }
        $child.Dispose()
    }
}
