# Montara H4 Windows notification icon; all updates are manual.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$updaterDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$c=Get-Content -Raw (Join-Path $updaterDir 'config.json') | ConvertFrom-Json
$env:MONTARA_COMPANION_HOME=Split-Path -Parent $c.video_path
$owned=$null
function Health {
  try { Invoke-RestMethod -Uri 'http://127.0.0.1:47820/health' -TimeoutSec 2 } catch { $null }
}
function StartCompanion {
  if(Health){return}
  if(!(Test-Path $c.companion_path) -or !(Test-Path $c.python_path)){
    [System.Windows.Forms.MessageBox]::Show('Companion o Python no encontrados. Ejecuta de nuevo el instalador.','Montara')|Out-Null
    return
  }
  $script:owned=Start-Process -FilePath $c.python_path -ArgumentList ('"'+$c.companion_path+'"') -PassThru -WindowStyle Hidden
}
$icon=New-Object System.Windows.Forms.NotifyIcon
$icon.Icon=[System.Drawing.SystemIcons]::Application
$icon.Text='Montara Companion'
$menu=New-Object System.Windows.Forms.ContextMenuStrip
$status=$menu.Items.Add('Estado de Companion')
$status.Add_Click({
  $s=Health
  $patch=Get-Content (Join-Path $updaterDir 'installed-version.txt') -ErrorAction SilentlyContinue | Select-Object -First 1
  $msg=if($s){"Conectado · beta "+$patch+" (núcleo "+$s.version+") · "+$(if($s.busy){'Ocupado'}else{'Libre'})}else{'Sin conexión'}
  [System.Windows.Forms.MessageBox]::Show($msg,'Montara Companion')|Out-Null
})
$update=$menu.Items.Add('Buscar e instalar actualización...')
$update.Add_Click({
  # A simple check must not interrupt a running Companion if already current.
  try {
    $next=Invoke-RestMethod -Uri $c.update_url -TimeoutSec 12
    $version=Get-Content (Join-Path $updaterDir 'installed-version.txt') -ErrorAction SilentlyContinue | Select-Object -First 1
    if($next.channel -ne 'montara-h4-windows'){
      throw 'La fuente de actualizaciones no es válida.'
    }
    if($next.version -eq $version){
      [System.Windows.Forms.MessageBox]::Show('Companion ya está actualizado: '+$version,'Montara')|Out-Null
      return
    }
  } catch {
    [System.Windows.Forms.MessageBox]::Show('No se pudo comprobar H4: '+$_.Exception.Message,'Montara')|Out-Null
    return
  }
  $s=Health
  if($s -and $s.busy){
    [System.Windows.Forms.MessageBox]::Show('Hay un render activo. Vuelve a intentarlo al terminar.','Montara')|Out-Null
    return
  }
  if($s -and (!$script:owned -or $script:owned.HasExited)){
    [System.Windows.Forms.MessageBox]::Show('Companion está abierto desde otra aplicación. Ciérralo antes de actualizar.','Montara')|Out-Null
    return
  }
  if($script:owned -and !$script:owned.HasExited){
    Stop-Process -Id $script:owned.Id -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
    if(Health){[System.Windows.Forms.MessageBox]::Show('No se pudo cerrar el proceso propio.','Montara')|Out-Null;return}
  }
  $script=Join-Path $updaterDir 'Montara-Actualizar.ps1'
  Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',('"'+$script+'"'),'-RestartAfter')
  $icon.Visible=$false
  [System.Windows.Forms.Application]::Exit()
})
$menu.Items.Add('-')|Out-Null
$exit=$menu.Items.Add('Salir de Companion')
$exit.Add_Click({
  $s=Health
  if($s -and $s.busy){[System.Windows.Forms.MessageBox]::Show('Hay un render activo.','Montara')|Out-Null;return}
  if($script:owned -and !$script:owned.HasExited){Stop-Process -Id $script:owned.Id -ErrorAction SilentlyContinue}
  $icon.Visible=$false
  [System.Windows.Forms.Application]::Exit()
})
$icon.ContextMenuStrip=$menu
$icon.Visible=$true
StartCompanion
$icon.ShowBalloonTip(2500,'Montara Companion','Clic derecho para buscar actualizaciones.',[System.Windows.Forms.ToolTipIcon]::Info)
try {[System.Windows.Forms.Application]::Run()} finally {$icon.Dispose()}
