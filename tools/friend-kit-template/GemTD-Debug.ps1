[CmdletBinding()]
param([ValidateSet('Install','Verify','Uninstall')][string]$Mode='Install',
      [string]$DotaPath, [string]$VpkPath, [string]$Target, [switch]$Rebuild, [switch]$Yes)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Management\Microsoft.PowerShell.Management.psd1')
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Full([string]$Path) { [IO.Path]::GetFullPath($Path.Trim().Trim('"')).TrimEnd('\') }
function NoLinks([string]$Path) {
 $p=Full $Path
 while($p) {
  if((Test-Path -LiteralPath $p) -and ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Refusing junction/symlink: $p" }
  $p=[IO.Path]::GetDirectoryName($p)
 }
}
function Files([string]$Root) {
 foreach($p in Get-ChildItem -LiteralPath $Root -Force) {
  if($p.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked entry: $($p.FullName)" }
  if($p.PSIsContainer) { Files $p.FullName } else { $p }
 }
}
function CheckBuild([string]$Root) {
 if(!(Test-Path -LiteralPath $Root -PathType Container)) { throw "Addon not found: $Root" }
 NoLinks $Root
 $expected=@{}; foreach($f in $manifest.files) { $expected[$f.path]=$f.sha256 }
 $found=@{}; $canonical=New-Object Text.StringBuilder
 foreach($f in Files $Root) {
  $rel=$f.FullName.Substring($Root.Length+1).Replace('\','/')
  if($manifest.ignored -contains $rel) { continue }
  if(!$expected.ContainsKey($rel)) { throw "Unexpected runtime file: $rel" }
  $h=Hash $f.FullName
  if($h -ne $expected[$rel]) { throw "Different runtime file: $rel" }
  $found[$rel]=$h
 }
 foreach($f in $manifest.files) {
  if(!$found.ContainsKey($f.path)) { throw "Missing runtime file: $($f.path)" }
  [void]$canonical.Append($f.path).Append([char]0).Append($found[$f.path]).Append("`n")
 }
 $sha=[Security.Cryptography.SHA256]::Create()
 try { $fingerprint=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical.ToString())))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
 if($fingerprint -ne $manifest.fingerprint) { throw 'Build fingerprint mismatch' }
}
function Discover {
 $roots=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
 foreach($process in Get-Process steam -ErrorAction SilentlyContinue) {
  if($process.Path) { [void]$roots.Add([IO.Path]::GetDirectoryName($process.Path)) }
 }
 foreach($entry in @(@('HKCU:\Software\Valve\Steam','SteamPath'),@('HKLM:\SOFTWARE\WOW6432Node\Valve\Steam','InstallPath'),@('HKLM:\SOFTWARE\Valve\Steam','InstallPath'))) {
  $v=Get-ItemProperty -LiteralPath $entry[0] -Name $entry[1] -ErrorAction SilentlyContinue
  if($v) { [void]$roots.Add((Full $v.($entry[1]))) }
 }
 foreach($p in @("${env:ProgramFiles(x86)}\Steam", "$env:ProgramFiles\Steam")) { if(Test-Path -LiteralPath $p) { [void]$roots.Add((Full $p)) } }
 foreach($root in @($roots)) {
  $vdf=Join-Path $root 'steamapps\libraryfolders.vdf'
  if(Test-Path -LiteralPath $vdf) {
   $text=[IO.File]::ReadAllText($vdf)
   foreach($m in [regex]::Matches($text,'"(?:path|[0-9]+)"\s*"([^"\r\n]+)"')) {
    $p=$m.Groups[1].Value.Replace('\\','\')
    if([IO.Path]::IsPathRooted($p)) { [void]$roots.Add((Full $p)) }
   }
  }
 }
 $dota=New-Object 'Collections.Generic.List[string]'; $vpks=New-Object 'Collections.Generic.List[string]'
 foreach($root in $roots) {
  $p=Join-Path $root 'steamapps\common\dota 2 beta'
  if(Test-Path -LiteralPath (Join-Path $p 'game\bin\win64\dota2.exe')) { $dota.Add($p) }
  $p=Join-Path $root 'steamapps\workshop\content\570\474619917\474619917.vpk'
  if(Test-Path -LiteralPath $p) { $vpks.Add($p) }
 }
 return @{Dota=@($dota.ToArray()); Vpk=@($vpks.ToArray())}
}
try {
 if((Hash (Join-Path $PSScriptRoot 'build.json')) -ne '@MANIFEST_HASH@') { throw 'Kit manifest is damaged. Extract the kit ZIP again.' }
 $manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'build.json') -Raw | ConvertFrom-Json
 if((Hash (Join-Path $PSScriptRoot 'Vpk.cs')) -ne $manifest.extractor_sha256) { throw 'Kit extractor is damaged.' }
 if((Hash (Join-Path $PSScriptRoot 'patches.json')) -ne $manifest.patches_sha256) { throw 'Kit patches are damaged.' }
 $paths=Discover
 if(!$Target) {
  if(!$DotaPath -and $paths.Dota.Count -eq 1) { $DotaPath=$paths.Dota[0] }
  if(!$DotaPath) {
   Write-Host 'Steam > Dota 2 > Properties > Installed Files > Browse. Copy the folder path.'
   if($paths.Dota.Count) { Write-Host ($paths.Dota -join "`n") }
   $DotaPath=Read-Host 'Dota 2 folder (containing game\bin\win64\dota2.exe)'
  }
  $DotaPath=Full $DotaPath
  if(!(Test-Path -LiteralPath (Join-Path $DotaPath 'game\bin\win64\dota2.exe'))) { throw 'Dota folder is invalid.' }
  $Target=Join-Path $DotaPath 'game\dota_addons\gemtd_debug'
 }
 $Target=Full $Target
 if([IO.Path]::GetFileName($Target) -ne 'gemtd_debug') { throw 'Target folder must be named gemtd_debug.' }
 NoLinks $Target
 if($Mode -eq 'Verify') { CheckBuild $Target; Write-Host "Verified. GemTD Debug Build: $($manifest.fingerprint.Substring(0,16).ToUpperInvariant())"; exit 0 }
 if(!$PSBoundParameters.ContainsKey('Target') -and (Get-Process dota2,dota2cfg,resourcecompiler -ErrorAction SilentlyContinue)) { throw 'Close Dota 2 and Workshop Tools, then run again.' }
 if($Mode -eq 'Uninstall') {
  if(!(Test-Path -LiteralPath $Target)) { Write-Host 'Already uninstalled.'; exit 0 }
  $null=@(Files $Target)
  if(!$Yes -and (Read-Host "Uninstall $Target by moving it to a backup? Type YES") -cne 'YES') { throw 'Cancelled; nothing changed.' }
  $backup=Join-Path ([IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($Target))) ('gemtd_debug.uninstalled.'+[guid]::NewGuid().ToString('N'))
  Move-Item -LiteralPath $Target -Destination $backup
  Write-Host "Uninstalled. Files preserved at: $backup"; exit 0
 }
 if(!$VpkPath -and $DotaPath) {
  $library=[IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName((Full $DotaPath)))
  $candidate=Join-Path $library 'workshop\content\570\474619917\474619917.vpk'
  if(Test-Path -LiteralPath $candidate) { $VpkPath=$candidate }
 }
 if(!$VpkPath -and $paths.Vpk.Count -eq 1) { $VpkPath=$paths.Vpk[0] }
 if(!$VpkPath) {
  Write-Host 'Subscribe to Workshop item 474619917 and wait for Steam downloads to finish.'
  Write-Host 'Look in a Steam library under steamapps\workshop\content\570\474619917\474619917.vpk.'
  if($paths.Vpk.Count) { Write-Host ($paths.Vpk -join "`n") }
  $VpkPath=Read-Host 'Full path to 474619917.vpk'
 }
 $VpkPath=Full $VpkPath
 $upstream=[IO.Path]::GetDirectoryName($VpkPath)+'\'
 if(($Target+'\').StartsWith($upstream,[StringComparison]::OrdinalIgnoreCase)) { throw 'Target must not be inside the upstream Workshop directory.' }
 if((Hash $VpkPath) -ne $manifest.source_sha256) { throw 'Workshop version differs from the tested GemTD Debug baseline. Nothing installed. Ask the host for a kit supporting your version; do not patch this unknown version.' }
 if(Test-Path -LiteralPath $Target) {
  try { CheckBuild $Target; Write-Host "Already installed; no reinstall necessary. GemTD Debug Build: $($manifest.fingerprint.Substring(0,16).ToUpperInvariant())"; exit 0 }
  catch { Write-Host $_.Exception.Message }
  $null=@(Files $Target)
  if(!$Rebuild -and (Read-Host 'Rebuild and preserve existing addon in a backup? Type REBUILD') -cne 'REBUILD') { throw 'Cancelled; nothing changed.' }
 }
 $parent=[IO.Path]::GetDirectoryName($Target)
 [void][IO.Directory]::CreateDirectory($parent)
 $stage=Join-Path ([IO.Path]::GetDirectoryName($parent)) ('gemtd_debug.staging.'+[guid]::NewGuid().ToString('N'))
 [void][IO.Directory]::CreateDirectory($stage)
 Add-Type -Path (Join-Path $PSScriptRoot 'Vpk.cs')
 Write-Host 'Extracting and checking the tested Workshop build...'
 [GemVpk]::Extract($VpkPath,$stage)
 if((Hash $VpkPath) -ne $manifest.source_sha256) { throw 'Source changed during extraction; installation stopped.' }
 $patches=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'patches.json') -Raw | ConvertFrom-Json
 foreach($patch in $patches) {
  $path=Join-Path $stage $patch.path
  if((Hash $path) -ne $patch.before_sha256) { throw "Patch input mismatch: $($patch.path)" }
  [GemVpk]::Patch($path,[long[]]@($patch.edits | ForEach-Object {$_.offset}),[int[]]@($patch.edits | ForEach-Object {$_.length}),[string[]]@($patch.edits | ForEach-Object {$_.data}))
  if((Hash $path) -ne $patch.after_sha256) { throw "Patch output mismatch: $($patch.path)" }
 }
 CheckBuild $stage
 $backup=$null
 if(Test-Path -LiteralPath $Target) {
  NoLinks $Target
  $backup=Join-Path ([IO.Path]::GetDirectoryName($parent)) ('gemtd_debug.backup.'+[guid]::NewGuid().ToString('N'))
  Move-Item -LiteralPath $Target -Destination $backup
 }
 try { Move-Item -LiteralPath $stage -Destination $Target }
 catch { if($backup -and !(Test-Path -LiteralPath $Target)) { Move-Item -LiteralPath $backup -Destination $Target }; throw }
 Write-Host "SUCCESS: $Target"
 Write-Host "GemTD Debug Build: $($manifest.fingerprint.Substring(0,16).ToUpperInvariant())"
 if($backup) { Write-Host "Previous installation preserved: $backup" }
 Write-Host 'Normal Dota console: sv_cheats 0'
 Write-Host 'Then: dota_launch_custom_game gemtd_debug gemtd_coop'
 exit 0
} catch {
 Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
 if(Get-Variable stage -ErrorAction SilentlyContinue) { Write-Host "Incomplete staging folder (not installed): $stage" }
 exit 1
}
