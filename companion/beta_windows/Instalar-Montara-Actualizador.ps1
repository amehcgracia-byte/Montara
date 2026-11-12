# One-time installer for H4 Windows. Does not reinstall Engine or move originals.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
$root=Join-Path $env:LOCALAPPDATA 'MontaraSMARTBeta'
$video=Join-Path $root 'video'
$home=Join-Path $root 'Updater'
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
function Notice($text,$level='Information'){
  [System.Windows.Forms.MessageBox]::Show($text,'Montara Companion','OK',$level)|Out-Null
}
try {
  if(!(Test-Path (Join-Path $video 'engine/core/stages/export.py'))){
    throw ('No encontramos el Engine existente en '+$video+'. No se ha modificado nada.')
  }
  $health=$null
  try {$health=Invoke-RestMethod 'http://127.0.0.1:47820/health' -TimeoutSec 2}catch{}
  if($health){throw 'Primero cierra Companion. Este instalador no detiene procesos activos.'}
  $known=@((Join-Path $root 'companion.py'),(Join-Path $root 'companion/companion.py'),
           (Join-Path $env:USERPROFILE '.montara-companion/companion.py'))
  $source=@($known|Where-Object {Test-Path $_}|Select-Object -First 1)[0]
  if(!$source){
    $picker=New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title='Selecciona el companion.py que utilizabas (solo se pide una vez)'
    $picker.Filter='Companion Python (companion.py)|companion.py'
    $picker.InitialDirectory=[Environment]::GetFolderPath('UserProfile')
    if($picker.ShowDialog() -ne 'OK'){throw 'No se ha elegido companion.py.'}
    $source=$picker.FileName
  }
  $python=$null
  try {$python=(& py -3.11 -c 'import sys;print(sys.executable)' 2>$null|Select-Object -Last 1).Trim()}catch{}
  if(!$python -or !(Test-Path $python)){
    $picker=New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title='Selecciona Python 3.11 (python.exe) utilizado por Companion'
    $picker.Filter='Python (python.exe)|python.exe'
    if($picker.ShowDialog() -ne 'OK'){throw 'Python 3.11 no localizado.'}
    $python=$picker.FileName
  }
  $version=& $python -c 'import sys;print("%d.%d"%sys.version_info[:2])'
  if($version.Trim() -ne '3.11'){throw 'Debe seleccionarse Python 3.11.'}
  New-Item -ItemType Directory -Path $home -Force|Out-Null
  $target=Join-Path $video 'local_video.py'
  if(!(Test-Path $target)){throw ('No se encuentra '+$target)}
  Copy-Item $target (Join-Path $home 'local_video.anterior.py') -Force
  $fresh=Join-Path $here 'local_video.py'
  if(!(Test-Path $fresh)){throw 'El paquete no incluye local_video.py.'}
  Copy-Item $fresh ($target+'.new') -Force
  Move-Item ($target+'.new') $target -Force
  foreach($item in @('Montara-Bandeja.ps1','Montara-Actualizar.ps1')){
    Copy-Item (Join-Path $here $item) (Join-Path $home $item) -Force
  }
  @{
    companion_path=[string]$source
    python_path=[string]$python
    video_path=[string]$video
    update_url='https://montara-owner-h4.memoriainvalida001.workers.dev/urano/v1/companion-updates/manifest.json'
  }|ConvertTo-Json|Set-Content (Join-Path $home 'config.json') -Encoding UTF8
  Set-Content (Join-Path $home 'installed-version.txt') '0.6.11-h4.1' -Encoding ASCII
  $shell=New-Object -ComObject WScript.Shell
  $link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Montara Companion.lnk'))
  $link.TargetPath=(Join-Path $PSHOME 'powershell.exe')
  $link.Arguments='-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $home 'Montara-Bandeja.ps1')+'"'
  $link.WorkingDirectory=$home
  $link.Save()
  Notice ('Montara actualizado. Solo se ha cambiado local_video.py.'+[Environment]::NewLine+
          'Motor, proyectos, originales y ajustes conservados.'+[Environment]::NewLine+
          'A partir de ahora, clic derecho en el icono junto al reloj para buscar actualizaciones.')
  Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-STA','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',('"'+(Join-Path $home 'Montara-Bandeja.ps1')+'"'))
} catch {
  Notice $_.Exception.Message 'Error'
  exit 1
}
