from pathlib import Path
p=Path('game/gemtd_debug/scripts/vscripts/addon_game_mode.lua')
s=p.read_bytes().decode().replace('\r\n','\n')
assert 'function GemTDSettlementObserve' not in s
start=s.index('function send_ranking ()')
end=s.index('function start_build()',start)
part=s[start:end]
part=part.replace('function send_ranking ()\n','''function send_ranking ()
	GemTDSettlementObserve(function()
		print('[GemTD Settlement] send_ranking ENTER')
		GemTDSettlementLog('map', GetMapName())
		GemTDSettlementLog('level', _G.level)
		GemTDSettlementLog('game_time', GameRules:GetGameTime())
		GemTDSettlementLog('player_count', PlayerResource:GetPlayerCount())
		GemTDSettlementLog('is_cheat', _G.is_cheat)
		GemTDSettlementLog('is_posted_game', _G.is_posted_game)
		GemTDSettlementLog('steam_ids', _G.steam_ids_only)
	end)
''')
part=part.replace('\tif _G.is_cheat == 2 then\n',"\tif _G.is_cheat == 2 then\n\t\tGemTDSettlementObserve(function() print('[GemTD Settlement] SKIP is_cheat == 2') end)\n")
part=part.replace('\t\tif _G.is_posted_game == true then\n',"\t\tif _G.is_posted_game == true then\n\t\t\tGemTDSettlementObserve(function() print('[GemTD Settlement] SKIP already posted') end)\n")
part=part.replace('\t\t-- SendCoopRanking({','''		GemTDSettlementObserve(function()
			print('[GemTD Settlement] PUBLISHED game_state.send_ranking; awaiting Panorama catch_crab')
			GemTDSettlementLog('time_cost', g_time)
			GemTDSettlementLog('finishd_quest', finishd_quest)
			GemTDSettlementLog('towers', towers_str, nil, 4096)
			GemTDSettlementLog('kills', _G.kills)
			GemTDSettlementLog('gold', _G.team_gold)
			GemTDSettlementLog('extra_kill', _G.extra_kill)
			GemTDSettlementLog('maze_length', _G.gem_maze_length)
		end)

		-- SendCoopRanking({''')
s=s[:start]+Path('tools/settlement_helpers.lua').read_text(encoding='utf-8')+'\n'+part+s[end:]
start=s.index('function GemTD:OnCatchCrab(keys)')
end=s.index('function rasterize_vector(pp)',start)
part=s[start:end]
part=part.replace('\tlocal user = keys.user\n','''	local user = keys.user
	local settlement_diag = _G.myself == true and (cb == 'send_ranking_cb' or (type(url) == 'string' and url:find('/ranking/add/', 1, true) ~= nil))
	local diag_secrets = nil
	if settlement_diag then
		GemTDSettlementObserve(function() print('[GemTD Settlement] catch_crab request received') end)
	end
''')
part=part.replace('\turl = url..GetSendKey()','''	local send_key = GetSendKey()
	url = url..send_key
	if settlement_diag then
		GemTDSettlementObserve(function()
			diag_secrets = GemTDSettlementKeys(send_key)
			print('[GemTD Settlement] endpoint=gemtd/202408/ranking/add/ (URL arguments and keys omitted)')
			GemTDSettlementLog('callback', cb, diag_secrets)
			GemTDSettlementLog('request_user', user, diag_secrets)
		end)
	end''')
part=part.replace('\t\treq:Send(function (result)','''		if settlement_diag then
			GemTDSettlementObserve(function() print('[GemTD Settlement] HTTP request started; timeout_ms=20000') end)
		end
		req:Send(function (result)''')
part=part.replace('\t\t\t-- local t = json.decode(result["Body"])','''			if settlement_diag then
				GemTDSettlementObserve(function()
					if diag_secrets == nil then
						print('[GemTD Settlement] response withheld: key sanitization context unavailable')
					else
						GemTDSettlementResponse(result, diag_secrets)
					end
				end)
			end
			-- local t = json.decode(result["Body"])''')
part=part.replace('\t\tend)\n    end)', '''			if settlement_diag then
				GemTDSettlementObserve(function() print('[GemTD Settlement] response FORWARDED to original Panorama callback') end)
			end
		end)
    end)''')
s=s[:start]+part+s[end:]
p.write_bytes(s.replace('\n','\r\n').encode())
