"""Lua 5.1 integration tests using actual gameplay handlers and disposable engine stubs.

Install test dependency: python -m pip install --target tools/.test-deps lupa==2.8
Run: python tools/test_coop_contribution.py
No Dota, HTTP, or external account mutations are performed.
"""
from pathlib import Path
import json
import hashlib
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/.test-deps'))
from lupa.lua51 import LuaRuntime

GAME = ROOT / 'game/gemtd_debug'
source = (GAME / 'scripts/vscripts/addon_game_mode.lua').read_text(encoding='utf-8')
module = (GAME / 'scripts/vscripts/coop_contribution.lua').read_text(encoding='utf-8')


def function(name, text=source):
    start = re.search(r'^function ' + re.escape(name) + r'\s*\(', text, re.M).start()
    end = re.search(r'^function ', text[start + 1:], re.M)
    return text[start:start + 1 + end.start()] if end else text[start:]


lua = LuaRuntime()
lua.execute('function syntax(s) local f,e=loadstring(s); assert(f,e) end')
lua.globals().syntax(source)
lua.globals().syntax(module)
lua.execute(r'''
GemTD={}; DOTA_TEAM_GOODGUYS=2; DOTA_GAMERULES_STATE_POST_GAME=9
function clone(t)
 if type(t)~='table' then return t end
 local c={}; for k,v in pairs(t) do c[k]=clone(v) end; return c
end
CustomNetTables={SetTableValue=function(_,t,k,v)
 net[t..'/'..k]=clone(v); writes=writes+1
 write_counts[t..'/'..k]=(write_counts[t..'/'..k] or 0)+1
end}
GameRules={GetGameTime=function() return now end, State_Get=function() return phase end,
 GetGameModeEntity=function() return game_mode end}
function GetMapName() return map end
function RandomInt(a,b) return a end
function RandomFloat() return 0 end
function Vector(x,y,z) return {x=x,y=y,z=z} end
function noop() end
EmitGlobalSound=noop; EmitSoundOn=noop; ShowCombat=noop; PlayCombineSound=noop; play_merge_particle=noop
play_particle=noop; stone_quest=noop; send_merge_board=noop; finish_build=noop
SetAbilityActiveStatus=noop; ChangeStoneStyle=noop; sync_player_gold=noop; level_up=noop
SetQuest=noop; start_shiban_timer=noop; FindEnemyPath=noop
find_all_path=noop
ParticleManager={CreateParticle=function() return 1 end,DestroyParticle=noop}
CustomGameEventManager={Send_ServerToAllClients=noop,Send_ServerToPlayer=noop}
function FindUnitsInRadius() return {} end
Entities={FindByName=function() return {GetAbsOrigin=function() return Vector(-2000,-2000,0) end} end}
Timers={CreateTimer=function(_,delay,fn) callbacks[#callbacks+1]=fn end}
PlayerResource={IncrementAssists=noop}
function IsUnitExist(u) return u and not u:IsNull() end
IsValidEntity=IsUnitExist
function IsTower() return false end -- end-of-round MVP has its own preserved implementation
function EntIndexToHScript(id) return entities[id] end
function unit(name,id)
 next_entity=next_entity+1
 local u={name=name,id=next_entity,pid=id,dead=false,pos=Vector(0,0,0),abilities={}}
 function u:IsNull() return self.dead end
 function u:IsAlive() return not self.dead end
 function u:IsHero() return false end
 function u:HasModifier() return false end
 function u:GetUnitName() assert(not self.dead,'Read name after destruction'); return self.name end
 function u:GetOwner() return self.owner end
 function u:GetPlayerID() return self.pid end
 function u:GetPlayerOwner() return self.owner end
 function u:GetLevel() return 1 end
 function u:GetAbsOrigin() assert(not self.dead); return clone(self.pos) end
 function u:GetEntityIndex() return self.id end
 u.entindex=u.GetEntityIndex
 function u:SetOwner(owner) self.owner=owner end
 function u:Destroy() self.dead=true end
 u.ForceKill=u.Destroy
 function u:AddAbility(a) self.abilities[a]={SetLevel=noop} end
 function u:FindAbilityByName(a) return self.abilities[a] or {SetLevel=noop} end
 function u:HasAbility(a) return self.abilities[a]~=nil end
 u.RemoveAbility=noop; u.SetHullRadius=noop; u.RemoveModifierByName=noop
 u.SetForwardVector=noop; u.SetControllableByPlayer=noop
 u.SetMana=noop
 entities[u.id]=u
 return u
end
function CreateUnitByName(name,p)
 local u=unit(name,-1); u.pos=clone(p); created[#created+1]=u; return u
end
function reset()
 map='gemtd_coop'; phase=7; now=10; net={}; writes=0; write_counts={}; created={}; callbacks={}; entities={}; next_entity=0; game_mode={}
 _G.game_status=2; _G.level=1; _G.damage={}; _G.damage_race={[0]={},[1]={},[2]={},[3]={}}
 _G.game_time=0; _G.stop_watch=0; _G.last_g_time=nil
 _G.gemtd_pool={}; _G.gemtd_pool_race={[0]={},[1]={},[2]={},[3]={}}
 _G.gemtd_pool_can_merge={}; _G.gemtd_pool_can_merge_all={}; _G.build_curr={}; _G.is_build_ready={}
 _G.shiban_index={}; _G.shiban_ability_list={}; _G.gem_is_shuaguaiing=false
 heroes={}; for i=0,3 do heroes[i]=unit('hero',i) end
 GemTDContribution.Reset()
end
function gem(name,id)
 local u=unit(name,id); u.owner=heroes[id]; GemTDContribution.RegisterBase(u,id); return u
end
function merge(name,units,caster)
 _G.gemtd_pool={}; for _,u in ipairs(units) do _G.gemtd_pool[#_G.gemtd_pool+1]=u end
 _G.gemtd_pool_can_merge[name]=units; merge_tower(name,caster)
 return _G.gemtd_pool[#_G.gemtd_pool]
end
function summary(id) return net['coop_contribution/round_'..id] end
function tower(id,u) return net['coop_contribution/round_'..id..'_tower_'..u.gemtd_contribution.id] end
function hit(u,d) DamageStat(u,nil,d) end
function candidates(id,names)
 local result={}; for i,name in ipairs(names) do result[i-1]=gem(name,id) end
 _G.build_curr[id]=result; return result[0]
end
function total(t) local n=0; for _,v in pairs(t) do n=n+v end; return n end
''')
lua.globals().GemTDContribution = lua.execute(module)
for name in ['gemtd_merge', 'gemtd_merge_secret', 'gemtd_merge_shiban', 'gemtd_merge_shiban_update']:
    start = source.index('\t_G.' + name + ' = {')
    end = source.index('\n\t}', start) + len('\n\t}')
    lua.execute(source[start:end])
for name in ['AddDamageStat', 'RemoveDamageStat', 'GetDamageStat', 'DamageStat', 'gemtd_build_stone',
             'merge_tower', 'merge_tower1', 'choose_stone', 'choose_update_stone',
             'choose_update_update_stone', 'gemtd_downgrade_stone',
             'gemtd_downgrade_stone_fengbaozhichui', 'merge_shiban', 'shiban_update_one',
             'ChainFrost', 'InvisibleUnitCast', 'EndRoundIfNoEnemyAlive',
              'build_1_stone', 'GemTD:DamageFilter']:
    lua.execute(function(name))

tests = {
    'normal construction records builder before selection or damage': r'''
reset(); local builder=heroes[2]; builder.owner=unit('player',2)
_G.build_curr[2]={}; _G.build_index={[2]=0}; _G.gem_gailv={[1]={}}; _G.gem_tower_basic={'gemtd_b'}
_G.gem_map=nil; _G.gem_path={{1},{1},{1},{1},{1},{1}}
gemtd_build_stone({caster=builder,ability={},target_points={Vector(0,0,0)}})
local built=_G.build_curr[2][0]
assert(built.gemtd_contribution.weights[2]==1 and built.gemtd_contribution.materials['2:gemtd_b1'].count==1)
assert(built:GetOwner()==builder and _G.build_index[2]==1)
''',
    'three builders, duplicate candidates, original stats and exact 90000 split': r'''
reset(); GemTDContribution.StartRound(1)
a=gem('gemtd_b1',0); b=gem('gemtd_y1',1); c=gem('gemtd_d1',2); spare=gem('gemtd_b1',3)
hit(a,99); silver=merge('gemtd_baiyin',{spare,b,a,c},a)
assert(spare:IsAlive() and silver:GetUnitName()=='gemtd_baiyin')
assert(silver:GetOwner()==heroes[0] and silver.gemtd_contribution.total_weight==3)
assert(not silver.gemtd_contribution.weights[3])
for _,u in ipairs(created) do if u.name=='gemtd_stone' then assert(not u.gemtd_contribution) end end
hit(silver,90000); GemTDContribution.Publish()
local t=tower(1,silver)
for i=0,2 do assert(t.players[tostring(i)].damage==30000 and t.players[tostring(i)].share==1/3) end
assert(_G.damage[a.id]==nil and _G.damage[silver.id]==90000)
assert(summary(1).damage==90099 and summary(1).players['0']==30099)
assert(total(summary(1).players)==summary(1).damage)
''',
    'all tier weights, tier 6 is 1050, and regraded gems keep their builder': r'''
reset()
for tier,w in ipairs({1,2,6,12,24,1050}) do
 local u=gem('gemtd_d'..string.rep('1',tier),2); assert(u.gemtd_contribution.total_weight==w)
end
assert(GemTDContribution.GemWeight('gemtd_baiyin')==nil)
local u=gem('gemtd_b1',2); u.owner=heroes[0]
local materials=GemTDContribution.Selection(u,'gemtd_b111111')
local v=unit('gemtd_b111111',0); v.owner=heroes[0]; GemTDContribution.Attach(v,0,materials)
assert(v.gemtd_contribution.weights[2]==1050 and not v.gemtd_contribution.weights[0])
GemTDContribution.StartRound(6)
local d=gem('gemtd_d1',0); local y=gem('gemtd_y11',1)
local merged=unit('example',0); merged.owner=heroes[0]
GemTDContribution.Attach(merged,0,GemTDContribution.Collect({v,d,y}))
hit(merged,105300); GemTDContribution.Publish()
local p=tower(1,merged).players
assert(p['2'].damage==105000 and p['0'].damage==100 and p['1'].damage==200)
''',
    'chained merge retains raw weights and immutable past rounds': r'''
reset(); GemTDContribution.StartRound(1)
local a=gem('gemtd_b1',0); local b=gem('gemtd_y1',1); local c=gem('gemtd_d1',2)
local silver=merge('gemtd_baiyin',{a,b,c},a); hit(silver,90000)
GemTDContribution.FinishRound(); local old=clone(tower(1,silver))
GemTDContribution.StartRound(2)
local q=gem('gemtd_q11',1); local r=gem('gemtd_r111',2)
local knight=merge('gemtd_baiyinqishi',{silver,q,r},q)
assert(knight.gemtd_contribution.total_weight==11)
assert(knight.gemtd_contribution.weights[0]==1 and knight.gemtd_contribution.weights[1]==3 and knight.gemtd_contribution.weights[2]==7)
hit(knight,110000); GemTDContribution.Publish()
assert(summary(2).players['0']==10000 and summary(2).players['1']==30000 and summary(2).players['2']==70000)
assert(tower(1,silver).damage==old.damage and summary(1).finished==1)
assert(tower(1,silver).players['0'].damage==30000)
''',
    'actual selection handlers: keep, upgrade, double upgrade and downgrade': r'''
for _,case in ipairs({
 {'choose_stone','gemtd_b1',1}, {'choose_update_stone','gemtd_b1',2},
 {'choose_update_update_stone','gemtd_b1111',1050},
 {'choose_update_update_stone','gemtd_b11111',96},
 {'gemtd_downgrade_stone','gemtd_b111',2}, {'gemtd_downgrade_stone_fengbaozhichui','gemtd_b111111',24}
}) do
 reset(); local caster=candidates(1,{case[2],case[2],case[2],case[2],'gemtd_y1'})
 _G[case[1]]({caster=caster})
 local result=_G.gemtd_pool[1]
 assert(result.gemtd_contribution.total_weight==case[3],case[1])
 assert(result.gemtd_contribution.weights[1]==case[3])
 for _,u in ipairs(created) do if u.name=='gemtd_stone' then assert(not u.gemtd_contribution) end end
end
''',
    'one-wave recipes exclude unused gems and preserve hidden recipe weights': r'''
reset(); local caster=candidates(0,{'gemtd_b1','gemtd_y1','gemtd_d1','gemtd_b111111','gemtd_q111111'})
merge_tower1('gemtd_baiyin',caster)
local silver=_G.gemtd_pool[1]; assert(silver.gemtd_contribution.total_weight==3)
reset(); caster=candidates(1,{'gemtd_b11111','gemtd_y11111','gemtd_d11111','gemtd_b1','gemtd_y1'})
merge_tower1('gemtd_heiyaoshi',caster)
assert(_G.gemtd_pool[1].gemtd_contribution.total_weight==72)
reset(); caster=candidates(2,{'gemtd_p1','gemtd_p11','gemtd_p111','gemtd_p1111','gemtd_p11111'})
merge_tower1('gemtd_keyinuoerguangmingzhishan',caster)
assert(_G.gemtd_pool[1].gemtd_contribution.total_weight==45)
''',
    'slab construction and cross-player automatic slab upgrade': r'''
reset(); local caster=candidates(0,{'gemtd_b111','gemtd_q11','gemtd_b111111','gemtd_y1','gemtd_d1'})
merge_shiban('gemtd_hongliushiban','test_ability',10,caster)
local slab=_G.gemtd_pool[1]; assert(slab.gemtd_contribution.total_weight==8)
local left=unit('gemtd_hongliushiban',1); left.owner=heroes[1]
GemTDContribution.Attach(left,1,GemTDContribution.Collect({gem('gemtd_b111',1),gem('gemtd_q11',1)}))
local right=unit('gemtd_hongliushiban',2); right.owner=heroes[2]
GemTDContribution.Attach(right,2,GemTDContribution.Collect({gem('gemtd_b111',2),gem('gemtd_q11',2)}))
_G.gemtd_pool={slab,left,right}; _G.shiban_index['20_19']=left; _G.shiban_index['18_19']=right
shiban_update_one(slab,19,19)
local upgraded=_G.shiban_index['19_19']; assert(upgraded.name=='gemtd_hongliushiban_yin')
assert(upgraded.gemtd_contribution.total_weight==24)
for i=0,2 do assert(upgraded.gemtd_contribution.weights[i]==8) end
''',
    'original DamageFilter: live father counts once for source tower': r'''
reset(); GemTDContribution.StartRound(1)
local a=gem('gemtd_b1',0); local b=gem('gemtd_y1',1); local c=gem('gemtd_d1',2)
local silver=merge('gemtd_baiyin',{a,b,c},a)
InvisibleUnitCast({caster=silver,ability='test',level=1}); local proxy=created[#created]
local victim=unit('test_creep',-1)
assert(GemTD:DamageFilter({entindex_attacker_const=proxy.id, entindex_victim_const=victim.id,
    damage=90000, damagetype_const=0})==true)
GemTDContribution.Publish()
assert(_G.damage[silver.id]==90000 and _G.damage[proxy.id]==nil)
local stat=tower(1,silver)
for id=0,2 do assert(stat.players[tostring(id)].damage==30000) end
assert(summary(1).damage==90000)
''',
    'original DamageFilter: destroyed father damage is ignored': r'''
reset(); GemTDContribution.StartRound(1)
local a=gem('gemtd_b1',0); local b=gem('gemtd_y1',1); local c=gem('gemtd_d1',2)
local silver=merge('gemtd_baiyin',{a,b,c},a)
InvisibleUnitCast({caster=silver,ability='test',level=1}); local proxy=created[#created]
local victim=unit('test_creep',-1)
local before=writes
silver:Destroy()
assert(GemTD:DamageFilter({entindex_attacker_const=proxy.id, entindex_victim_const=victim.id,
    damage=60000, damagetype_const=0})==nil)
assert(next(_G.damage)==nil and summary(1).damage==0 and writes==before)
''',
    'original DamageFilter: delayed hit after parent merged is ignored': r'''
reset(); GemTDContribution.StartRound(1)
local a=gem('gemtd_b1',0); local b=gem('gemtd_y1',1); local c=gem('gemtd_d1',2)
local silver=merge('gemtd_baiyin',{a,b,c},a)
InvisibleUnitCast({caster=silver,ability='test',level=1}); local proxy=created[#created]
local q=gem('gemtd_q11',1); local r=gem('gemtd_r111',2)
local knight=merge('gemtd_baiyinqishi',{silver,q,r},q)
local victim=unit('test_creep',-1)
assert(silver:IsNull() and knight:IsAlive())
assert(GemTD:DamageFilter({entindex_attacker_const=proxy.id, entindex_victim_const=victim.id,
    damage=60000, damagetype_const=0})==nil)
assert(GemTD:DamageFilter({entindex_attacker_const=knight.id, entindex_victim_const=victim.id,
    damage=110000, damagetype_const=0})==true)
GemTDContribution.Publish()
assert(_G.damage[silver.id]==nil and _G.damage[proxy.id]==nil)
assert(summary(1).damage==110000 and tower(1,knight).damage==110000)
assert(not net['coop_contribution/round_1_tower_'..silver.gemtd_contribution.id])
''',
    'giant-stone build_1_stone tracks actual gem, not path-blocking stone': r'''
reset(); local builder=heroes[2]; builder.owner=unit('player',2)
_G.gem_map=nil; _G.gem_path={{1},{1},{1},{1},{1},{1}}
local ok,block=build_1_stone({p=Vector(0,0,0),caster=builder,can_remove_stone=false})
assert(ok and block:GetUnitName()=='gemtd_stone' and not block.gemtd_contribution)
local ok2,built=build_1_stone({p=Vector(128,0,0),caster=builder,stone_name='gemtd_b1111'})
assert(ok2 and built:GetOwner()==builder)
assert(built.gemtd_contribution.weights[2]==12 and built.gemtd_contribution.total_weight==12)
assert(not built.gemtd_contribution.weights[0])
''',
    'live contribution publishes at original damage_stat cadence': r'''
reset(); GemTDContribution.StartRound(1)
local u=gem('gemtd_b1',0)
local meta_before=write_counts['coop_contribution/meta']
assert(meta_before==2) -- reset and round start
hit(u,10)
assert(write_counts['game_state/damage_stat']==1)
assert(write_counts['coop_contribution/round_1']==2)
local n=writes
now=10.5; hit(u,20); GemTDContribution.Tick()
assert(writes==n and write_counts['game_state/damage_stat']==1)
now=11.0; hit(u,30)
assert(writes==n) -- original gate uses >1, not >=1
now=11.1; hit(u,40)
assert(write_counts['game_state/damage_stat']==2)
assert(write_counts['coop_contribution/round_1']==3)
assert(write_counts['coop_contribution/meta']==meta_before)
assert(summary(1).damage==100)
GemTDContribution.FinishRound()
assert(summary(1).finished==1 and summary(1).damage==100)
''',
    'integer conservation independent of hit frequency, same player and sparse IDs': r'''
reset(); local a=gem('gemtd_b1',0); local b=gem('gemtd_y1',3); local c=gem('gemtd_d1',3)
local u=merge('gemtd_baiyin',{a,b,c},a); GemTDContribution.StartRound(1)
for i=1,101 do hit(u,1) end
GemTDContribution.Publish(); local p=tower(1,u).players
assert(p['0'].damage==34 and p['3'].damage==67 and total(summary(1).players)==101)
GemTDContribution.FinishRound(); GemTDContribution.StartRound(2); hit(u,101); GemTDContribution.Publish()
assert(tower(2,u).players['0'].damage==34 and tower(2,u).players['3'].damage==67)
for damage=1,1000 do
 local split=GemTDContribution.Split(damage,{[0]=1,[2]=24,[3]=1050}); local sum=0
 for _,row in pairs(split) do sum=sum+row.damage end; assert(sum==damage)
end
''',
    'original ceil, other damage, final flush, no duplicate finishing and next round reset': r'''
reset(); GemTDContribution.StartRound(1)
local u=gem('gemtd_b1',0); hit(u,0.1); hit(u,0); hit(u,-5)
local hero=unit('hero_attacker',1); hero.owner=heroes[1]; hit(hero,2.5)
_G.level=1; function StatEnemyCountAndShow() return 0 end
EndRoundIfNoEnemyAlive(); callbacks[1]()
assert(summary(1).finished==1 and summary(1).damage==1 and summary(1).other_damage==3)
assert(next(_G.damage)==nil)
local n=writes; GemTDContribution.FinishRound(); GemTDContribution.Tick(); assert(writes==n)
GemTDContribution.StartRound(2); assert(summary(2).damage==0 and summary(2).pages==0)
hit(u,17); _G.game_status=3; GemTDContribution.Tick()
assert(summary(2).damage==17 and summary(2).finished==1)
''',
    'race isolation and new-game state reset': r'''
reset(); map='gemtd_race'; GemTDContribution.Reset(); local n=writes
local u=gem('gemtd_b1',0); GemTDContribution.StartRound(1); hit(u,123); GemTDContribution.Tick()
assert(not u.gemtd_contribution and _G.damage_race[0][u.id]==123)
assert(not summary(1) and net['coop_contribution/meta'].enabled==0)
map='gemtd_1p'; GemTDContribution.Reset(); assert(net['coop_contribution/meta'].latest==0)
GemTDContribution.StartRound(1); assert(summary(1).damage==0 and summary(1).tower_count==0)
''',
    'direct debug towers are explicit, not assigned fabricated recipe ingredients': r'''
reset(); local u=gem('gemtd_jingangshikulinan',2)
assert(u.gemtd_contribution.direct and u.gemtd_contribution.total_weight==1)
GemTDContribution.StartRound(1); hit(u,50); GemTDContribution.Publish()
assert(tower(1,u).direct==1 and tower(1,u).players['2'].damage==50)
''',
    'large round uses bounded packets and publishes only dirty towers': r'''
reset(); GemTDContribution.StartRound(1)
for i=1,300 do local u=gem('gemtd_b1',i%4); hit(u,100+i) end
GemTDContribution.Publish(); assert(summary(1).pages==5 and summary(1).tower_count==300)
assert(total(summary(1).players)==summary(1).damage)
local n=writes; GemTDContribution.Tick(); assert(writes==n)
''',
}
for name, code in tests.items():
    lua.execute(code)
    print('PASS:', name)

def plain(value):
    if hasattr(value, 'items'):
        return {str(k): plain(v) for k, v in value.items()}
    return value

payloads = plain(lua.globals().net)
largest = max(len(json.dumps(value, ensure_ascii=False).encode('utf-8')) for value in payloads.values())
assert largest < 12000, largest
print('PASS: 300-tower serialized packet upper bound:', largest, 'bytes (below 16 KiB)')

# All preexisting code is preserved by removing only the new additive integration lines.
without_hooks = ''.join(line for line in source.splitlines(keepends=True)
                        if 'GemTDContribution' not in line and 'local contribution_materials' not in line)
BASE_GAMEPLAY_SHA256 = 'e19785e283b2b2e6ed70efd457751335e27df4559c4e4d67cbc16134b187c8d9'
assert hashlib.sha256(without_hooks.encode('utf-8')).hexdigest() == BASE_GAMEPLAY_SHA256, 'Unexpected changes to original gameplay/settlement code'
print('PASS: original gameplay, damage tables, MVP, backend and anti-cheat code preserved')
