"""Exercise the shipped kit with Windows PowerShell 5.1 in workspace test folders."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TEST=ROOT/'tools/friend-kit-validation'
TEST.mkdir(exist_ok=True)
with zipfile.ZipFile(ROOT/'dist/GemTD-Debug-Friend-Kit.zip') as z:
    z.extractall(TEST/'unpacked')
KIT=TEST/'unpacked/GemTD-Debug-Friend-Kit'
TARGET=TEST/'install/game/dota_addons/gemtd_debug'
SOURCE=ROOT/'baseline/474619917.vpk'
PS=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
results=[]
def run(name, mode='Install', target=TARGET, extra=(), expected=0, message=None):
    args=[str(PS),'-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',str(KIT/'GemTD-Debug.ps1'),'-Mode',mode,'-Target',str(target)]
    if mode=='Install' and '-VpkPath' not in extra: args+=['-VpkPath',str(SOURCE)]
    args+=list(map(str,extra))
    p=subprocess.run(args,capture_output=True,timeout=120)
    output=p.stdout.decode(errors='replace')+p.stderr.decode(errors='replace')
    assert p.returncode==expected,(name,p.returncode,output)
    if message: assert message in output,(name,output)
    results.append({'test':name,'exit_code':p.returncode,'output':output.strip()})
    print('PASS:',name,flush=True)
    return output

assert not TARGET.exists(), 'Use a fresh validation directory for a new full run'
source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
(TEST/'upstream').mkdir(exist_ok=True)
bad=TEST/'upstream/wrong.vpk'; bad.write_bytes(b'Wrong workshop version')
run('Reject wrong VPK before target creation',extra=('-VpkPath',bad),expected=1,message='Workshop version differs')
assert not TARGET.exists()
run('Fresh install from shipped ZIP',message='SUCCESS:')
manifest=json.loads((KIT/'build.json').read_text())
for record in manifest['files']:
    assert (TARGET/record['path']).read_bytes()==(ROOT/'game/gemtd_debug'/record['path']).read_bytes(),record['path']
results.append({'test':'All 2508 installed files byte-identical to tested host runtime','passed':True})
run('Repeat install is no-op',message='no reinstall necessary')
run('Verify fresh install','Verify',message='Verified.')
run('Verify current host runtime with four ignored caches','Verify',ROOT/'game/gemtd_debug',message='Verified.')
(TARGET/'tools_asset_info.bin').write_bytes(b'generated cache')
run('Generated cache ignored','Verify',message='Verified.')
extra=TARGET/'unexpected.lua'; extra.write_bytes(b'-- unknown')
run('Unexpected runtime file rejected','Verify',expected=1,message='Unexpected runtime file')
run('Rebuild divergent addon and preserve backup',extra=('-Rebuild',),message='Previous installation preserved:')
backups=list((TEST/'install/game').glob('gemtd_debug.backup.*'))
assert len(backups)==1 and (backups[0]/'unexpected.lua').read_bytes()==b'-- unknown'
lua=TARGET/'scripts/vscripts/addon_game_mode.lua'
lua.write_bytes(lua.read_bytes()+b'\n-- altered\n')
run('Changed Lua rejected','Verify',expected=1,message='Different runtime file')
run('Rebuild altered Lua',extra=('-Rebuild',),message='SUCCESS:')
run('Rebuilt addon verifies','Verify',message='Verified.')
run('Uninstall disables addon and preserves backup','Uninstall',extra=('-Yes',),message='Uninstalled.')
assert not TARGET.exists()
backups=list((TEST/'install/game').glob('gemtd_debug.uninstalled.*'))
assert len(backups)==1 and (backups[0]/'addoninfo.txt').exists()
run('Uninstall is idempotent','Uninstall',extra=('-Yes',),message='Already uninstalled.')
run('Refuse developer junction target','Verify',Path(r'F:\Steam\steamapps\common\dota 2 beta\game\dota_addons\gemtd_debug'),expected=1,message='Refusing junction/symlink')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash

# Execute the actual discovery function independently, without touching game files.
discovery=TEST/'check-discovery.ps1'
discovery.write_text('''$ErrorActionPreference='Stop'
$scriptPath=$args[0]
$ast=[Management.Automation.Language.Parser]::ParseFile($scriptPath,[ref]$null,[ref]$null)
foreach($name in @('Full','Discover')) {
 $fn=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
 . ([scriptblock]::Create($fn.Extent.Text))
}
Discover | ConvertTo-Json -Compress
''')
p=subprocess.run([str(PS),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(discovery),str(KIT/'GemTD-Debug.ps1')],capture_output=True,timeout=30)
assert p.returncode==0,p.stderr
discovered=json.loads(p.stdout.decode())
assert r'F:\Steam\steamapps\common\dota 2 beta' in discovered['Dota'],discovered
assert r'F:\Steam\steamapps\workshop\content\570\474619917\474619917.vpk' in discovered['Vpk'],discovered
results.append({'test':'Actual Steam discovery under Windows PowerShell 5.1','result':discovered})

# Exercise the double-click wrapper, including argument forwarding and exit status.
env=dict(os.environ,GEMTD_NO_PAUSE='1')
p=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(KIT/'Verify-GemTD-Debug.cmd'),'-Target',str(ROOT/'game/gemtd_debug')],capture_output=True,env=env,timeout=120)
assert p.returncode==0,(p.stdout,p.stderr)
results.append({'test':'CMD wrapper succeeds with explicit host target','output':p.stdout.decode(errors='replace').strip()})
report=ROOT/'tools/friend-kit-validation.json'
report.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('All checks passed. Report:',report,flush=True)
