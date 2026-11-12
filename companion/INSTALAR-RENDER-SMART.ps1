# Montara SMART Beta native Windows renderer - explicit opt-in.
# Operates ONLY inside %LOCALAPPDATA%\MontaraSMARTBeta, never older Companion.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$state = Join-Path $env:LOCALAPPDATA "MontaraSMARTBeta"
$video = Join-Path $state "video"
$source = Join-Path $root "renderer"
$expected = "b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b"
$required = @("engine", "local_video.py", "video_recipe.py", "brand", "ENGINE_COMMIT")

Write-Host "=== MONTARA SMART | RENDER WINDOWS ==="
Write-Host "Instalacion aislada:" $video
if (-not (Test-Path $source -PathType Container)) {
    throw "Este ZIP no contiene el Engine local. No instalar una version de solo proxies."
}
foreach ($item in $required) {
    if (-not (Test-Path (Join-Path $source $item))) { throw "Falta en el paquete: $item" }
}
$actual = (Get-Content (Join-Path $source "ENGINE_COMMIT") -Raw).Trim()
if ($actual -ne $expected) { throw "Engine no coincide con el Stage de la beta" }

# Never replace a running Companion or interrupt a render.
$busy = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 47820 -State Listen -ErrorAction SilentlyContinue
if ($busy) { throw "Un Companion esta abierto en el puerto 47820. Termina sus trabajos y cierralo antes de instalar." }

try {
    $version = (& py -3.11 -c "import sys;print(sys.version_info[:2])" 2>$null | Select-Object -Last 1).Trim()
} catch {
    throw "Se necesita Python 3.11 en Windows. Ejecuta py -3.11 --version y comprueba que existe."
}
if ($version -ne "(3, 11)") { throw "El motor local requiere Python 3.11." }
foreach ($exe in @("ffmpeg","ffprobe")) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "Falta $exe en PATH. No se han modificado otras instalaciones."
    }
}
$null = New-Item -ItemType Directory -Path $video -Force
$venv = Join-Path $video "venv"
$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    & py -3.11 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear entorno Python 3.11." }
}
Write-Host "Preparando dependencias locales de render ..."
& $python -m pip install --disable-pip-version-check -q "numpy>=1.26,<2" "scipy>=1.11,<1.15" "opencv-python-headless>=4.9,<4.12" "pillow>=10" "flask>=3"
if ($LASTEXITCODE -ne 0) { throw "No se pudieron preparar dependencias; ninguna instalacion antigua se ha tocado." }

$staging = Join-Path $video (".update-" + [guid]::NewGuid().ToString("N"))
$previous = Join-Path $video (".previous-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory $staging
$null = New-Item -ItemType Directory $previous
$applied = @()
$moved = @()
try {
    foreach ($item in $required) {
        Copy-Item -LiteralPath (Join-Path $source $item) -Destination (Join-Path $staging $item) -Recurse -Force
    }
    $env:ZUCKER_DATA_ROOT = Join-Path $staging "smoke"
    $env:ZUCKER_GLOBAL_CACHE = Join-Path $staging "smoke\Cache"
    $smoke = Join-Path $staging "engine"
    Push-Location $smoke
    try {
        & $python -c "from core.stages.export import ExportStage; print('ENGINE_IMPORT_PASS')"
        if ($LASTEXITCODE -ne 0) { throw "El motor de exportacion no supera la prueba." }
    } finally { Pop-Location }

    New-Item -ItemType File -Path (Join-Path $video "INSTALLING") -Force | Out-Null
    foreach ($item in $required) {
        $current = Join-Path $video $item
        if (Test-Path $current) {
            Move-Item -LiteralPath $current -Destination (Join-Path $previous $item)
            $moved += $item
        }
    }
    foreach ($item in $required) {
        Move-Item -LiteralPath (Join-Path $staging $item) -Destination (Join-Path $video $item)
        $applied += $item
    }
    Remove-Item -LiteralPath (Join-Path $video "INSTALLING") -Force
    Write-Host "RESULTADO: RENDER LOCAL LISTO, ENGINE $expected"
    Write-Host "Los tres Companion anteriores permanecen intactos."
    Write-Host "Ya puedes abrir INICIAR-SMART-BETA.cmd para iniciar el icono de bandeja."
} catch {
    foreach ($item in $applied) {
        $target = Join-Path $video $item
        if (Test-Path $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    }
    foreach ($item in $moved) {
        Move-Item -LiteralPath (Join-Path $previous $item) -Destination (Join-Path $video $item)
    }
    throw
} finally {
    Remove-Item -LiteralPath (Join-Path $video "INSTALLING") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}
