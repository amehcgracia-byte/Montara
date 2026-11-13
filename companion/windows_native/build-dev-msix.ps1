# Windows CI only. Development MSIX, not an approved release.
param([string]$Output = "$PSScriptRoot\dist")
$ErrorActionPreference='Stop'
$publish=Join-Path $Output 'publish'
$stage=Join-Path $Output 'package-root'
New-Item -ItemType Directory -Path $Output -Force|Out-Null
dotnet publish (Join-Path $PSScriptRoot 'Montara.Companion.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=None -p:DebugSymbols=false -o $publish --nologo
if($LASTEXITCODE -ne 0){throw 'dotnet publish failed'}
if(Test-Path $stage){Remove-Item $stage -Force -Recurse}
New-Item -ItemType Directory -Path $stage -Force|Out-Null
Get-ChildItem $publish | ForEach-Object {Copy-Item $_.FullName $stage -Recurse -Force}
$bundledService=Join-Path $PSScriptRoot 'service-bundle/Montara.Companion.Service'
if(!(Test-Path (Join-Path $bundledService 'Montara.Companion.Service.exe'))){
  throw 'Companion runtime service is missing. Refusing to package a Python-picker-only tray.'
}
Copy-Item $bundledService (Join-Path $stage 'service') -Recurse -Force
Copy-Item (Join-Path $PSScriptRoot 'Package.appxmanifest') (Join-Path $stage 'AppxManifest.xml')
$assets=Join-Path $stage 'Assets'
New-Item -ItemType Directory -Path $assets -Force|Out-Null
Add-Type -AssemblyName System.Drawing
foreach($item in @(@('StoreLogo.png',50,50),@('Square44x44Logo.png',44,44),@('Square150x150Logo.png',150,150),@('Square310x310Logo.png',310,310),@('Wide310x150Logo.png',310,150))){
  $w=[int]$item[1];$h=[int]$item[2]
  $bmp=[System.Drawing.Bitmap]::new($w,$h)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  try{
    $g.Clear([System.Drawing.Color]::FromArgb(16,16,20))
    $g.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $scale=[math]::Min($w/120.,$h/100.)*0.76
    $x=@(4,27,51,75,98);$heights=@(92,62,40,62,92)
    for($i=0;$i -lt 5;$i++){
      $color=if($i -eq 2){[Drawing.Color]::FromArgb(255,79,46)}else{[Drawing.Color]::FromArgb(245,243,239)}
      $pen=[Drawing.Pen]::new($color,([single](18*$scale)))
      try{
        $pen.StartCap=[Drawing.Drawing2D.LineCap]::Round
        $pen.EndCap=[Drawing.Drawing2D.LineCap]::Round
        $xx=[single](($w-120*$scale)/2+($x[$i]+9)*$scale)
        $yy=[single](($h-100*$scale)/2+4*$scale)
        $bottom=[single](($h-100*$scale)/2+$heights[$i]*$scale)
        $g.DrawLine($pen,$xx,$yy,$xx,$bottom)
      }finally{$pen.Dispose()}
    }
    $bmp.Save((Join-Path $assets $item[0]),[Drawing.Imaging.ImageFormat]::Png)
  }finally{$g.Dispose();$bmp.Dispose()}
}
$kits=Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Windows Kits\10\bin'
$makeappx=Get-ChildItem $kits -Filter makeappx.exe -File -Recurse|Where-Object FullName -like '*\x64\*'|Sort-Object FullName -Descending|Select-Object -First 1 -ExpandProperty FullName
$signtool=Get-ChildItem $kits -Filter signtool.exe -File -Recurse|Where-Object FullName -like '*\x64\*'|Sort-Object FullName -Descending|Select-Object -First 1 -ExpandProperty FullName
if(!$makeappx -or !$signtool){throw 'Windows SDK tools unavailable'}
$package=Join-Path $Output 'Montara.Companion.Dev_0.6.12.0_x64.msix'
& $makeappx pack /d $stage /p $package /o
if($LASTEXITCODE -ne 0){throw 'MakeAppx failed'}
$cert=New-SelfSignedCertificate -Type Custom -Subject 'CN=Montara Development' -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 -KeyUsage DigitalSignature -KeyExportPolicy NonExportable -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3') -FriendlyName 'Montara ephemeral dev signing'
if(!$cert){throw 'Cannot create dev cert'}
try{
  Export-Certificate -Cert $cert -FilePath (Join-Path $Output 'Montara-Development.cer')|Out-Null
  & $signtool sign /fd SHA256 /s My /sha1 $cert.Thumbprint $package
  if($LASTEXITCODE -ne 0){throw 'SignTool failed'}
  $signature=Get-AuthenticodeSignature $package
  if(!$signature.SignerCertificate -or $signature.SignerCertificate.Thumbprint -ne $cert.Thumbprint){throw 'Unexpected signature'}
}finally{
  Remove-Item -LiteralPath ('Cert:\CurrentUser\My\'+$cert.Thumbprint) -ErrorAction SilentlyContinue
}
Get-FileHash $package -Algorithm SHA256|Format-List|Out-String|Set-Content (Join-Path $Output 'SHA256.txt')
Write-Output ('MSIX_DEV_BUILT '+$package)
