"""Deterministic tests of actual Lua backend/controller/hero handlers; no live HTTP."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/.test-deps'))
from lupa.lua51 import LuaRuntime
source=(ROOT/'game/gemtd_debug/scripts/vscripts/addon_game_mode.lua').read_text(encoding='utf-8')
def fn(start,end): return start+source.split(start,1)[1].split(end,1)[0]
lua=LuaRuntime()
lua.execute('function syntax(s) local f,e=loadstring(s); assert(f,e) end')
lua.globals().syntax(source)
lua.execute('''
DOTA_CONNECTION_STATE_CONNECTED=2
DOTA_GAMERULES_STATE_PRE_GAME=7
DOTA_GAMERULES_STATE_POST_GAME=9
DOTA_TEAM_BADGUYS=3
GemTD={}
logs={}; function print(s) logs[#logs+1]=s end
function Time() return now end
function RandomInt() return 1 end
function GetMapName() return 'gemtd_coop' end
function GetSendKey() return '&test=1' end
function JoinTableString(t) return table.concat(t, ',') end
function prt() end
function SetHeroLevelShow() effects=effects+1 end
ParticleManager={CreateParticle=function() effects=effects+1; return 1 end}
function EntIndexToHScript(i) return entities[i] end
function StartGame() starts=starts+1 end
GameRules={State_Get=function() return phase end,
 SendCustomMessage=function() end, SetGameWinner=function(_,team) winner=team end}
PlayerResource={GetPlayer=function(_,id) return players[id] end,
 GetSteamID=function(_,id) return players[id] and players[id].steam or '0' end,
 GetConnectionState=function(_,id) return players[id] and players[id].state or 0 end,
 GetPlayerCount=function() local n=0; for _,p in pairs(players) do if p.steam~='0' then n=n+1 end end; return n end,
 GetSelectedHeroEntity=function(_,id) return players[id] and players[id].hero end,
 GetSelectedHeroName=function() return nil end}
CustomNetTables={GetTableValue=function(_,t,k) return net[t..'/'..k] end,
 SetTableValue=function(_,t,k,v) net[t..'/'..k]=v end}
CustomGameEventManager={Send_ServerToAllClients=function() end}
Timers={CreateTimer=function(_,a,b) timers[#timers+1]=type(a)=='table' and a.callback or b end}
json={decode=function(body) if body=='bad' then error('invalid JSON') end; return body end}
function CreateHTTPRequestScriptVM(method,url)
 local r={url=url, SetHTTPRequestAbsoluteTimeoutMS=function() end}
 function r:Send(cb) self.callback=cb; requests[#requests+1]=self end
 return r
end
function record() return {hero_sea={hero1={}},quest={},onduty_hero={hero_id='hero1'}} end
function info(id) return net['player_info_table/player_info_'..players[id].steam] end
function add(id,steam)
 local hero={IsNull=function() return false end,GetPlayerID=function() return id end,
 GetUnitName=function() return 'npc_dota_hero_riki' end,
 GetItemInSlot=function() return nil end,GetAbilityByIndex=function() return nil end}
 players[id]={steam=steam,state=2,hero=hero}; entities[100+id]=hero
end
function pick(id) GemTD:OnPlayerPickHero({player=id,heroindex=100+id}) end
function reply(index,data,status)
 requests[index].callback({StatusCode=status or 200,Body=data=='bad' and 'bad' or {err=0,data=data}})
end
function tick()
 now=now+1; local current=timers; timers={}
 for _,cb in ipairs(current) do if cb() then timers[#timers+1]=cb end end
end
function reset()
 now=0; phase=2; players={}; entities={}; net={}; requests={}; timers={}; logs={}; winner=nil; effects=0; starts=0; received={}
 _G.myself=true; _G.debug_player_info={pending={},initialized={},seen={},retry_at=0,failures=0}
 _G.is_heros_get_sended=nil; _G.online_player_count=1; _G.quest={}; _G.quest_status={}; _G.zaotui_table={}
 _G.hero={}; _G.gem_hero={}; _G.choose_hero_info={}; _G.playerid2hero={}
end
function GemTD:OnReceiveHeroInfo(keys)
 received[#received+1]=keys
 -- Hero creation is intentionally completed by tests later, like async precache.
end
''')
lua.execute(fn('function GemTD:DebugPlayerInfoValid(info)','function StartGame()'))
lua.execute(fn('function GemTD:OnPlayerPickHero(keys)','function GemTD:OnLobster2(t)'))
lua.execute(fn('function GemTD:OnPlayerConnectFull (keys)','-- Private debug build:'))
lua.execute(fn('function GemTD:OnPlayerReconnected(keys)','function concat_table_str(table)'))
lua.execute('''
-- Host first, friend joins while the host HTTP request is outstanding.
reset(); add(0,'host'); GemTD:OnPlayerConnectFull({}); tick()
assert(#requests==1 and requests[1].url:find('@host?ver=',1,true))
for i=1,3 do GemTD:OnPlayerStartTeamSelect({}) end
add(3,'friend'); GemTD:OnPlayerConnectFull({}); tick()
assert(#requests==1, 'Overlapping HTTP requests')
reply(1,{host=record()}); local host_record=info(0); tick()
assert(#requests==2 and requests[2].url:find('@host,friend?ver=',1,true))
assert(requests[2].url:find('pcount=2p',1,true))
-- Hero choice before data cannot dereference nil or end the match.
GemTD:OnPlayerRequestChooseHero({PlayerID=3,hero='hero1'}); assert(winner==nil)
pick(0); pick(3); pick(3)
assert(#received==1 and _G.debug_player_info.pending[103] and _G.hero[103]==nil)
phase=8; tick(); assert(#requests==2 and winner==nil and starts==0)
reply(2,{host=record(),friend=record()}); tick()
assert(info(0)==host_record, 'Refresh overwrote an existing player record')
assert(#received==2 and received[2].steam_id=='friend' and winner==nil)
pick(3); assert(#received==2, 'Duplicate hero initialization')
tick(); assert(starts==0, 'Started before asynchronous hero replacement')
_G.playerid2hero[0]=players[0].hero; _G.playerid2hero[3]=players[3].hero
tick(); tick(); assert(starts==1)

-- A late join after a completed request also refreshes despite the old one-shot flag.
reset(); add(0,'host'); GemTD:OnPlayerStartTeamSelect({}); reply(1,{host=record()}); tick()
_G.is_heros_get_sended=true
add(1,'late'); GemTD:OnPlayerConnectFull({}); tick(); assert(#requests==2)
reply(2,{host=record(),late=record()}); tick()
assert(_G.debug_player_info.ready=='host,late')
players[1].state=3; tick(); players[1].state=2
GemTD:OnPlayerReconnected({PlayerID=1}); tick(); assert(#requests==2,'Reconnect refetched valid records')

-- HTTP failure, malformed JSON, incomplete response, backoff, then recovery.
reset(); add(0,'host'); GemTD:OnPlayerStartTeamSelect({}); pick(0)
reply(1,{},503); tick(); assert(#requests==1 and winner==nil)
now=5; tick(); assert(#requests==2)
reply(2,'bad'); tick(); assert(#requests==2 and winner==nil)
now=20; tick(); assert(#requests==3)
reply(3,{host={quest={}}}); assert(info(0)==nil)
now=40; tick(); assert(#requests==4)
reply(4,{host=record()}); tick(); assert(#received==1 and winner==nil)

-- Stale callbacks after initialization reset and stale hero handles are ignored.
reset(); add(0,'host'); GemTD:OnPlayerStartTeamSelect({}); local old=requests[1].callback
_G.debug_player_info={pending={},initialized={},seen={},retry_at=0,failures=0}
old({StatusCode=200,Body={err=0,data={host=record()}}}); assert(info(0)==nil)
pick(0); players[0].hero={}; tick(); assert(next(_G.debug_player_info.pending)==nil and #received==0)

-- No mid-match refresh for an unrelated new connection without pending initialization.
reset(); phase=8; add(0,'host'); GemTD:OnPlayerConnectFull({}); tick(); assert(#requests==0)
-- Bots/non-connected slots never enter the request roster.
reset(); add(0,'host'); add(1,'0'); add(2,'offline'); players[2].state=3
GemTD:OnPlayerStartTeamSelect({}); assert(requests[1].url:find('@host?ver=',1,true))

-- Original non-debug one-shot request and missing-record loss are preserved.
reset(); _G.myself=false; add(0,'host'); GemTD:OnPlayerStartTeamSelect({})
GemTD:OnPlayerStartTeamSelect({}); assert(#requests==1)
pick(0); assert(winner==DOTA_TEAM_BADGUYS)
reset(); _G.myself=false; add(0,'host'); GemTD:OnPlayerConnectFull({}); assert(#timers==0 and #requests==0)
-- The original backend blocked result still ends the game.
reset(); add(0,'host'); GemTD:OnPlayerStartTeamSelect({})
requests[1].callback({StatusCode=200,Body={err=1200,msg='blocked'}}); assert(winner==DOTA_TEAM_BADGUYS)
''')
print('PASS: Lua 5.1 compile; late joins before/after HTTP; single-flight; sparse IDs; reconnect;')
print('pending/deduplicated hero initialization; async hero creation start gate; retry/backoff;')
print('bad JSON/partial data; stale callbacks/entities; bot/disconnect filtering; non-debug behavior.')
