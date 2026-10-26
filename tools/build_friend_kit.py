"""Build the dependency-free friend kit from pinned VPK + current tested runtime."""
import base64
import difflib
import hashlib
import json
from pathlib import Path
import zipfile
from vpk_baseline import read_vpk

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'dist/GemTD-Debug-Friend-Kit'
KIT.mkdir(parents=True, exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
def save_json(name, value):
    b=(json.dumps(value,ensure_ascii=True,separators=(',',':'))+'\n').encode()
    (KIT/name).write_bytes(b)
    return sha(b)

baseline=json.loads((ROOT/'baseline/manifest.json').read_text())
raw, entries, _=read_vpk(ROOT/'baseline/474619917.vpk')
assert sha(raw)==baseline['source_sha256']
runtime=ROOT/'game/gemtd_debug'
ignored=['tools_asset_info.bin','tools_thumbnail_cache.sqlite3','tools_thumbnail_cache.sqlite3-shm','tools_thumbnail_cache.sqlite3-wal']
expected_paths={record['path'] for record, _ in entries}
extras={p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}-expected_paths
assert extras.issubset(set(ignored)), f'Unreviewed runtime extras: {extras}'
patches=[]; records=[]
for record, old in sorted(entries,key=lambda e:e[0]['path']):
    path=record['path']; current=(runtime/path).read_bytes()
    records.append(dict(path=path,sha256=sha(current)))
    if old==current: continue
    assert path in ('scripts/vscripts/addon_game_mode.lua','resource/custom_game_whitelist.txt'), f'Unreviewed change: {path}'
    if path.endswith('.lua'):
        a=old.splitlines(keepends=True); b=current.splitlines(keepends=True)
        offsets=[0]
        for line in a: offsets.append(offsets[-1]+len(line))
        edits=[dict(offset=offsets[i],length=offsets[j]-offsets[i],data=base64.b64encode(b''.join(b[k:l])).decode())
               for op,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes() if op!='equal']
        assert sha(current)=='4bdfc10b344731b0e3004a7e589e14ed05d7fa0055e25153d2e7fd574da7b042', 'Lua differs from reviewed direct-connect initialization patch'
    else:
        start=0
        while start<min(len(old),len(current)) and old[start]==current[start]: start+=1
        suffix=0
        while suffix<min(len(old),len(current))-start and old[-suffix-1]==current[-suffix-1]: suffix+=1
        edits=[dict(offset=start,length=len(old)-start-suffix,data=base64.b64encode(current[start:len(current)-suffix if suffix else len(current)]).decode())]
    rebuilt=bytearray(); cursor=0
    for edit in edits:
        rebuilt.extend(old[cursor:edit['offset']]); rebuilt.extend(base64.b64decode(edit['data'])); cursor=edit['offset']+edit['length']
    rebuilt.extend(old[cursor:]); assert bytes(rebuilt)==current
    patches.append(dict(path=path,before_sha256=sha(old),after_sha256=sha(current),edits=edits))

template=ROOT/'tools/friend-kit-template'
extractor=(template/'Vpk.cs').read_bytes(); (KIT/'Vpk.cs').write_bytes(extractor)
fingerprint=sha(''.join(r['path']+'\0'+r['sha256']+'\n' for r in records).encode())
manifest=dict(source_sha256=baseline['source_sha256'],fingerprint=fingerprint,files=records,ignored=ignored,
              patches_sha256=save_json('patches.json',patches),extractor_sha256=sha(extractor))
manifest_hash=save_json('build.json',manifest)
script=(template/'GemTD-Debug.ps1').read_text().replace('@MANIFEST_HASH@',manifest_hash)
(KIT/'GemTD-Debug.ps1').write_bytes(script.replace('\n','\r\n').encode('utf-8-sig'))
for mode in ('Install','Verify','Uninstall'):
    cmd=f'''@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0GemTD-Debug.ps1" -Mode {mode} %*
set "result=%errorlevel%"
echo.
if not defined GEMTD_NO_PAUSE pause
exit /b %result%
'''
    (KIT/f'{mode}-GemTD-Debug.cmd').write_bytes(cmd.replace('\n','\r\n').encode('ascii'))
instructions=f'''GemTD Debug 好友安装包 / Friend Kit

1. Steam 订阅宝石TD（474619917），等待下载完成，关闭 Dota 2。
   https://steamcommunity.com/sharedfiles/filedetails/?id=474619917
2. 解压整个安装包，双击 Install-GemTD-Debug.cmd。
3. 成功时应显示 GemTD Debug Build: {fingerprint[:16].upper()}
4. 普通 Dota 2 控制台：sv_cheats 0
   然后：dota_launch_custom_game gemtd_debug gemtd_coop

校验：Verify-GemTD-Debug.cmd
卸载：Uninstall-GemTD-Debug.cmd（输入 YES；移到备份目录，不删除原版）
版本不匹配时停止，请联系房主更新安装包。
找不到目录时：Steam > Dota 2 > 属性 > 已安装文件 > 浏览，复制目录路径。

No Python, Git, Codex, Workshop Tools, or admin install is required.
Windows PowerShell 5.1 and .NET (included in Windows) are used.
Keep every kit file together. No source VPK or full addon is included.
The installer reads your subscribed VPK; it never changes it.
If a different debug install exists, type REBUILD to preserve it in a backup and replace it.
Backups/staging are outside dota_addons and are not active addons. No automatic deletion occurs.
If Windows folder permissions prevent writing, select a writable Steam library or resolve its permissions.
Junction/symlink installation targets are refused to protect other projects.

Advanced commands (PowerShell):
.\\Install-GemTD-Debug.cmd -DotaPath "F:\\Steam\\steamapps\\common\\dota 2 beta"
.\\Verify-GemTD-Debug.cmd -Target "F:\\CodexProjects\\GemTD-Debug\\game\\gemtd_debug"
.\\Install-GemTD-Debug.cmd -DotaPath "..." -VpkPath "...\\474619917.vpk" -Rebuild

Fingerprint: SHA256 of sorted UTF-8 path + NUL + lowercase file SHA256 + LF, for all 2508 runtime files.
Full SHA256: {fingerprint}
Only four root Tools cache files are ignored: {', '.join(ignored)}.
All other extra/missing/changed files fail verification. The tested runtime whitelist is included.
Lua patch is derived from the reviewed runtime: developer activation and direct-connect player initialization.
Wait for the host console to report player-info READY with every connected SteamID before Start Game.
'''
(KIT/'README.txt').write_bytes(instructions.replace('\n','\r\n').encode('utf-8-sig'))
archive=ROOT/'dist/GemTD-Debug-Friend-Kit.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(KIT.iterdir()):
        if p.is_file(): z.write(p,'GemTD-Debug-Friend-Kit/'+p.name)
print(json.dumps(dict(fingerprint=fingerprint,zip_bytes=archive.stat().st_size,unpacked_bytes=sum(p.stat().st_size for p in KIT.iterdir()),files=[p.name for p in sorted(KIT.iterdir())],patches=[(p['path'],len(p['edits'])) for p in patches]),indent=2))
