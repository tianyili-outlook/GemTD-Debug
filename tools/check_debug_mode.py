"""Focused Lua 5.1 checks; run with the local tools/.test-deps lupa package."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/.test-deps'))
from lupa.lua51 import LuaRuntime
from vpk_baseline import read_vpk

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--behavior-only', action='store_true', help='Run Lua behavior tests without historical VPK/file-scope assertions or patch output')
args = parser.parse_args()

runtime = ROOT / 'game/gemtd_debug'
relative = 'scripts/vscripts/addon_game_mode.lua'
source = (runtime / relative).read_text(encoding='utf-8')

def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]

if not args.behavior_only:
    _, entries, _ = read_vpk(ROOT / 'baseline/474619917.vpk')
    original = next(data.decode('utf-8').replace('\r\n', '\n') for record, data in entries if record['path'] == relative)
    diff = ''.join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                     fromfile='baseline/' + relative, tofile='game/gemtd_debug/' + relative))
    (ROOT / 'tools/debug-mode.patch').write_text(diff, encoding='utf-8')
    print(diff)

    before = json.loads((ROOT / 'tools/pre_debug_file_hashes.json').read_text())
    after = {p.relative_to(runtime).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in runtime.rglob('*') if p.is_file()}
    assert before.keys() == after.keys(), 'Runtime file set changed'
    assert [p for p in before if before[p] != after[p]] == [relative], 'Unrelated runtime files changed'

    for start, end in [('function gemtd_build_stone(keys)', 'function choose_stone(keys)'),
                       ('function GemTD:OnNPCSpawned( keys )', 'function play_particle('),
                       ('function DetectCheatsThinker ()', 'function GemTD:InitGameMode()')]:
        assert section(source, start, end) == section(original, start, end)

lua = LuaRuntime()
lua.execute('function check_syntax(code) local f, err = loadstring(code); assert(f, err) end')
lua.globals().check_syntax(source)
lua.execute('''
GemTD = {}
function GemTD:InitGameMode() assert(_G.myself == true); initialized = true end
setmetatable(GemTD, {__call = function() return GemTD end})
GameRules = {
 GetGameModeEntity = function() return {SetThink = function() end} end,
 SendCustomMessage = function(_, text) message = text end,
 GetGameTime = function() return 123 end
}
CustomGameEventManager = {
 RegisterListener = function() end,
 Send_ServerToPlayer = function() end
}
CustomNetTables = {SetTableValue = function(_, table_name, key, value) last_net = value end}
function Dynamic_Wrap() end
function prt() end
function EmitGlobalSound() end
function RandomInt() return 1 end
function GetMapName() return 'gemtd_coop' end
function spawn_one_wave() spawned_level = _G.level end
PlayerResource = {
 GetPlayer = function(_, id) if id == 0 or id == 1 then return {} end end,
 GetSteamID = function(_, id) return '7656119800000000' .. id end,
 SetGold = function(_, id, gold) last_gold_player = id; last_gold = gold end,
 GetGold = function() return last_gold end
}
function string.trim(s) return s:match('^%s*(.-)%s*$') end
function string.split(s) local t = {}; for word in s:gmatch('%S+') do t[#t+1] = word end; return t end
_G.playerInfoReceived = {}
_G.playerid2hero = {}
_G.team_gold_race = {}
for id = 0, 1 do
 local player_id = id
 _G.playerid2hero[id] = {
  IsNull = function() return false end,
  GetEntityIndex = function() return 100 + player_id end,
  entindex = function() return 100 + player_id end,
  GetPlayerID = function() return player_id end
 }
end
''')
lua.execute('function Activate()' + section(source, 'function Activate()', 'function InitVaribles()'))
lua.execute('Activate(); assert(initialized)')
lua.execute('function GemTD:OnPlayerSay( keys )' + section(source, 'function GemTD:OnPlayerSay( keys )', 'function GemTD:OnPreviewEffect(keys)'))
lua.execute('''
function say(id, text) GemTD:OnPlayerSay({playerid=id, text=text}) end
for id = 0, 1 do
 say(id, '-debug'); assert(_G.is_debug == true)
 say(id, '-undebug'); assert(_G.is_debug == false)
 say(id, '-money'); assert(last_gold_player == id and last_gold == 9999)
end
say(0, '-crab heiyaoshi'); assert(_G.crab == 'heiyaoshi')
say(1, '-crab jingangshikulinan'); assert(_G.crab == 'jingangshikulinan')
say(0, '-choose 20'); assert(_G.level == 20)
say(1, '-spawn'); assert(spawned_level == 20 and _G.stop_watch == 123)
say(1, 'abcde-fghij-klmno'); assert(last_net.steam_id == '76561198000000001')
assert(next(_G.playerInfoReceived) == nil, 'Fallback must stay local to chat')
local record = {steam_id='existing-backend-id', onduty_hero='preserved'}
_G.playerInfoReceived[100] = record
say(0, 'abcde-fghij-klmno'); assert(last_net.steam_id == record.steam_id)
assert(_G.playerInfoReceived[100] == record and record.onduty_hero == 'preserved')
_G.myself = false; _G.is_debug = false; last_net = nil
say(1, '-debug'); assert(_G.is_debug == false and last_net == nil)
_G.myself = true
say(2, '-debug'); assert(_G.is_debug == false)
_G.playerid2hero[1] = nil
say(1, '-debug'); assert(_G.is_debug == false)
''')
print('PASS: full Lua 5.1 syntax; activation; two-player offline chat; shared crab assignment;')
print('money/debug/choose/spawn; local Steam ID; existing-record preservation; early guards;')
if not args.behavior_only:
    print('unchanged normal build and anti-cheat code; only intended runtime file changed.')
print('Dota engine execution and actual tower creation still require the manual runtime test.')
