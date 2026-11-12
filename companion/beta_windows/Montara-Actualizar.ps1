# Manual-only H4 updater: immutable channel, SHA-256 and rollback.
param([switch]$RestartAfter)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
$updaterDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$c=Get-Content -Raw (Join-Path $updaterDir 'config.json') | ConvertFrom-Json
function Info($text,$level='Information'){
  [System.Windows.Forms.MessageBox]::Show($text,'Montara Companion','OK',$level)|Out-Null
}
function RestartTray {
  if($RestartAfter){
    $tray=Join-Path $updaterDir 'Montara-Bandeja.ps1'
    Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-STA','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',('"'+$tray+'"'))
  }
}
try {
  $manifest=Invoke-RestMethod -Uri $c.update_url -TimeoutSec 20
  $prefix='https://montara-owner-h4.memoriainvalida001.workers.dev/urano/v1/companion-updates/'
  if($manifest.channel -ne 'montara-h4-windows' -or
     $manifest.version -notmatch '^0\.6\.[0-9]+-h4\.[0-9]+$' -or
     $manifest.sha256 -notmatch '^[a-f0-9]{64}$' -or
     !$manifest.url.StartsWith($prefix) -or
     $manifest.bytes -lt 100 -or $manifest.bytes -gt 1000000) {
    throw 'El manifiesto H4 no es válido.'
  }
  $installed=Get-Content (Join-Path $updaterDir 'installed-version.txt') -ErrorAction SilentlyContinue | Select-Object -First 1
  if($installed -eq $manifest.version){
    Info ("Ya tienes la versión "+$installed+".")
    RestartTray
    exit 0
  }
  $answer=[System.Windows.Forms.MessageBox]::Show(
    ("Instalada: "+$installed+[Environment]::NewLine+"Disponible: "+$manifest.version+
    [Environment]::NewLine+"Solo se actualiza Companion, no el Engine, vídeos ni proyectos."+
    [Environment]::NewLine+"¿Instalar?"),'Montara','YesNo','Question')
  if($answer -ne 'Yes'){RestartTray;exit 0}
  $health=$null
  try {$health=Invoke-RestMethod 'http://127.0.0.1:47820/health' -TimeoutSec 2}catch{}
  if($health){throw 'Cierra Companion antes de actualizar; puede haber un render en curso.'}
  $stage=Join-Path $env:TEMP ('Montara-H4-'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $stage|Out-Null
  try {
    $zip=Join-Path $stage 'package.zip'
    Invoke-WebRequest -Uri $manifest.url -OutFile $zip -UseBasicParsing -TimeoutSec 45
    if((Get-Item $zip).Length -ne [int]$manifest.bytes){throw 'Tamaño inesperado.'}
    if((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sha256){throw 'SHA-256 incorrecto.'}
    $expanded=Join-Path $stage 'content'
    Expand-Archive -LiteralPath $zip -DestinationPath $expanded
    # Fixed destination map. Future releases can update Companion modules,
    # never engine/venv, external paths, arbitrary ZIP entries or user data.
    $program=Split-Path -Parent $c.companion_path
    $targets=@{
      'local_video.py'=(Join-Path $c.video_path 'local_video.py')
      'companion.py'=$c.companion_path
      'video_jobs.py'=(Join-Path $program 'video_jobs.py')
      'video_recipe.py'=(Join-Path $program 'video_recipe.py')
      'windows_support.py'=(Join-Path $program 'windows_support.py')
      'spherical_proxy.py'=(Join-Path $program 'spherical_proxy.py')
      'Montara-Bandeja.ps1'=(Join-Path $updaterDir 'Montara-Bandeja.ps1')
      'Montara-Actualizar.ps1'=(Join-Path $updaterDir 'Montara-Actualizar.ps1')
    }
    $files=@(Get-ChildItem $expanded -Force)
    $allowed=@($files|ForEach-Object {$_.Name})
    if($files.Count -lt 1 -or $files.Count -gt 8 -or
       @($files|Where-Object {$_.PSIsContainer -or !$targets.ContainsKey($_.Name)}).Count){
      throw 'El paquete contiene archivos inesperados.'
    }
    foreach($file in $allowed){
      if(!(Test-Path -LiteralPath $targets[$file])){throw ("Falta el archivo local "+$file+"; actualiza mediante instalador revisado.") }
      Copy-Item -LiteralPath $targets[$file] -Destination ($targets[$file]+'.rollback') -Force
    }
    try {
      foreach($file in $allowed){
        Copy-Item -LiteralPath (Join-Path $expanded $file) -Destination $targets[$file] -Force
      }
      Set-Content (Join-Path $updaterDir 'installed-version.txt') $manifest.version -Encoding ASCII
    } catch {
      foreach($file in $allowed){
        if(Test-Path ($targets[$file]+'.rollback')){
          Copy-Item -LiteralPath ($targets[$file]+'.rollback') -Destination $targets[$file] -Force
        }
      }
      throw
    }
  } finally {Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue}
  Info ("Actualizado a "+$manifest.version+". Companion se abrirá ahora.")
  RestartTray
} catch {
  Info $_.Exception.Message 'Error'
  RestartTray
  exit 1
}
