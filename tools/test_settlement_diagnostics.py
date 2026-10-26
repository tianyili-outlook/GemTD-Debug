"""Compare original/new settlement execution with fake HTTP; no live submissions."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/.test-deps'))
from lupa.lua51 import LuaRuntime
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--behavior-only',action='store_true',help='Run Lua behavior tests without historical release file-scope assertions or patch output')
args=parser.parse_args()
runtime=ROOT/'game/gemtd_debug'
path='scripts/vscripts/addon_game_mode.lua'
old=(ROOT/'tools/pre-settlement-addon_game_mode.lua').read_text(encoding='utf-8')
new=(runtime/path).read_text(encoding='utf-8')
def section(s,a,b): return a+s.split(a,1)[1].split(b,1)[0]
helpers=section(new,'function GemTDSettlementObserve(callback)','function send_ranking ()')
dkjson=(runtime/'scripts/vscripts/dkjson.lua').read_text(encoding='utf-8')
def setup(source,debug=True):
    lua=LuaRuntime()
    lua.execute('function syntax(s) local f,e=loadstring(s); assert(f,e) end')
    lua.globals().syntax(source)
    lua.globals().json=lua.execute(dkjson)
    lua.execute('''
GemTD={}; logs={}; published={}; timers={}; requests={}; key_calls=0
function print(s) logs[#logs+1]=tostring(s) end
function GetMapName() return 'gemtd_coop' end
GameRules={GetGameTime=function() return 300 end,SendCustomMessage=function() end}
PlayerResource={GetPlayerCount=function() return 1 end}
function show_quest() end
function SetQuest(q,v) _G.quest_status[q]=v end
function EmitGlobalSound() end
function RandomInt() return 3 end
function RandomFloat() return 0.25 end
CustomNetTables={SetTableValue=function(_,t,k,v) published[t..'/'..k]=v end}
Timers={CreateTimer=function(_,delay,callback) timers[#timers+1]={delay=delay,callback=callback} end}
function CreateHTTPRequestScriptVM(method,url)
 local req={method=method,url=url}
 function req:SetHTTPRequestAbsoluteTimeoutMS(ms) self.timeout=ms end
 function req:Send(cb) self.callback=cb; requests[#requests+1]=self end
 return req
end
function GetSendKey()
 key_calls=key_calls+1
 return '&key=SECRET_ALPHA_0123456789&key2=Invalid_NotOnDedicatedServer&key3=&key4=SECRET_BETA_9876543210&key5=Invalid_Other'
end
_G.level=4; _G.game_time=0; _G.is_cheat=false; _G.is_posted_game=nil
_G.quest={q105=false}; _G.quest_status={}; _G.gem_castle_hp=0; _G.gemtd_pool={}
_G.gem_maze_length=13.4; _G.team_gold=10; _G.extra_kill=0; _G.kills=20
_G.steam_ids_only='TEST_PLAYER'; _G.navi=1234; _G.playerInfoReceived={}
function capture()
 local reqs={}
 for i,r in ipairs(requests) do reqs[i]={method=r.method,url=r.url,timeout=r.timeout} end
 return json.encode({published=published,posted=_G.is_posted_game,quest=_G.quest_status,
  requests=reqs,key_calls=key_calls,level=_G.level,gold=_G.team_gold,maze=_G.gem_maze_length})
end
function logs_text() return table.concat(logs,'\\n') end
function request()
 GemTD:OnCatchCrab({url='http://gemtd.ppbizon.com/gemtd/ranking/add/@300@4@20@TEST_PLAYER@,@TEST_PLAYER?gold=10',cb='send_ranking_cb',user='TEST_PLAYER'})
 for _,t in ipairs(timers) do t.callback() end
end
''')
    lua.globals().myself=debug
    if source==new: lua.execute(helpers)
    lua.execute(section(source,'function send_ranking ()','function start_build()'))
    lua.execute(section(source,'function GemTD:OnCatchCrab(keys)','function rasterize_vector(pp)'))
    return lua

for level,cheat,posted in [(4,False,None),(51,False,None),(4,2,None),(4,False,True)]:
    snapshots=[]
    for source in (old,new):
        l=setup(source); l.globals().level=level; l.globals().is_cheat=cheat; l.globals().is_posted_game=posted
        l.execute('send_ranking(); send_ranking()')
        snapshots.append(json.loads(l.globals().capture()))
    assert snapshots[0]==snapshots[1],(level,cheat,posted)

bodies=[(200,'{"err":0,"award":0,"level":4,"rank":2}'),
        (200,'{"err":1200,"msg":"invalid server key"}'),
        (503,'<html>Unavailable</html>'),(0,None),(200,''),
        (200,'{"msg":"SECRET_ALPHA_0123456789","token":"UNKNOWN_TOKEN"}'),
        (200,'{"\\u006b\\u0065\\u0079":"UNKNOWN_TOKEN"}'),
        (200,'{"msg":"\\u0053ECRET_ALPHA_0123456789"}'),
        (200,'password=UNKNOWN_PASSWORD'),(200,'x'*20000)]
for status,body in bodies:
    snapshots=[]
    for source in (old,new):
        l=setup(source); l.execute('request()')
        l.globals().status=status; l.globals().body=body
        l.execute('requests[1].callback({StatusCode=status,Body=body})')
        snapshots.append(json.loads(l.globals().capture()))
        logs=l.globals().logs_text()
        if source==new:
            assert len(l.globals().requests)==1 and l.globals().key_calls==1
            assert 'HTTP completed status='+str(status) in logs
            assert 'response FORWARDED' in logs
            for secret in ['SECRET_ALPHA_0123456789','SECRET_BETA_9876543210','UNKNOWN_TOKEN','UNKNOWN_PASSWORD']:
                assert secret not in logs,(secret,logs)
            assert len(logs)<23000,'Unbounded logging'
    assert snapshots[0]==snapshots[1],(status,body)

# Diagnostics cannot break requests if the observer encounters an error.
l=setup(new); l.execute('GemTDSettlementKeys=function() error("SECRET_ALPHA_0123456789") end; request(); requests[1].callback({StatusCode=200,Body="SECRET_ALPHA_0123456789"})')
assert len(l.globals().requests)==1 and 'SECRET_ALPHA_0123456789' not in l.globals().logs_text()
# No diagnostic output for non-debug or unrelated catch_crab requests.
l=setup(new,False); l.execute('send_ranking(); request()'); assert '[GemTD Settlement]' not in l.globals().logs_text()
l=setup(new); l.execute('GemTD:OnCatchCrab({url="http://example.invalid/unrelated",cb="other",user="TEST_PLAYER"}); timers[1].callback(); requests[1].callback({StatusCode=200,Body="{}"})')
assert '[GemTD Settlement]' not in l.globals().logs_text()

if args.behavior_only:
    print('PASS: Lua 5.1 settlement behavior; original state/HTTP/callback equality; error handling; sensitive-data redaction; observer isolation.')
    raise SystemExit(0)

# Every preexisting function outside the two instrumented handlers is byte-identical.
def rest(s):
    if 'function GemTDSettlementObserve' in s:
        a=s.index('-- Read-only observers:');b=s.index('function send_ranking ()',a);s=s[:a]+s[b:]
    for a,b in [('function send_ranking ()','function start_build()'),('function GemTD:OnCatchCrab(keys)','function rasterize_vector(pp)')]:
        i=s.index(a);j=s.index(b,i);s=s[:i]+s[j:]
    return s
assert rest(old)==rest(new)
manifest=json.loads((ROOT/'dist/GemTD-Debug-Friend-Kit/build.json').read_text())
changed=[f['path'] for f in manifest['files'] if hashlib.sha256((runtime/f['path']).read_bytes()).hexdigest()!=f['sha256']]
assert changed==[path],changed
diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='stable-946DE6E9DDE8C806/addon_game_mode.lua',tofile='settlement-diagnostics/addon_game_mode.lua'))
(ROOT/'tools/settlement-diagnostics.patch').write_text(diff,encoding='utf-8')
print('PASS: full Lua 5.1 syntax; exact old/new settlement state, HTTP URL/count/timeout and callback payload equality;')
print('success/error/non-JSON/empty/transport-failure responses; key and credential redaction (including escaped JSON);')
print('bounded logs; observer failure isolation; non-debug/unrelated requests silent; all other existing functions unchanged.')
