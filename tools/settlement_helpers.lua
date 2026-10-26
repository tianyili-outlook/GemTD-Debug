-- Read-only observers: failures must never interrupt the original settlement flow.
function GemTDSettlementObserve(callback)
	if _G.myself ~= true then return end
	local ok = pcall(callback)
	if not ok then print('[GemTD Settlement] diagnostic unavailable (observer error; details withheld)') end
end

function GemTDSettlementSafe(value, secrets)
	local text = tostring(value)
	for _, secret in ipairs(secrets or {}) do
		if secret ~= '' then
			local pattern = secret:gsub('(%W)', '%%%1')
			text = text:gsub(pattern, '<redacted>')
			-- Also cover a server echo using JSON escapes or URL encoding.
			local encoded = json.encode(secret)
			if type(encoded) == 'string' then
				encoded = encoded:sub(2, -2):gsub('(%W)', '%%%1')
				text = text:gsub(encoded, '<redacted>')
			end
			local escaped = secret:gsub('([^%w%-%._~])', function(c) return string.format('%%%02X', string.byte(c)) end)
			text = text:gsub(escaped:gsub('(%W)', '%%%1'), '<redacted>')
		end
	end
	-- Never emit credential-bearing fields, even if not one of our own keys.
	local lower = text:lower()
	for offset in lower:gmatch('()[:=]') do
		local name = lower:sub(math.max(1, offset-256), offset-1):match('([%w_%-]+)["\']?%s*$') or ''
		if name:find('key', 1, true) or name:find('token', 1, true) or name:find('secret', 1, true)
			or name:find('password', 1, true) or name:find('auth', 1, true) or name:find('credential', 1, true)
			or name:find('cookie', 1, true) or name:find('signature', 1, true) then
			return '<withheld: sensitive field>'
		end
	end
	return text:gsub('[%z\1-\8\11\12\14-\31\127]', '?'):gsub('\r', '\\r'):gsub('\n', '\\n')
end

function GemTDSettlementLog(label, value, secrets, limit)
	local text = GemTDSettlementSafe(value, secrets)
	local cap = limit or 2048
	if #text > cap then text = text:sub(1, cap)..' <truncated>' end
	print('[GemTD Settlement] '..label..'='..text)
end

function GemTDSettlementKeys(query)
	local secrets = {}
	for index = 1, 5 do
		local name = index == 1 and 'key' or ('key'..index)
		local value = query:match('[?&]'..name..'=([^&]*)')
		local status
		if value == nil then status = 'MISSING'
		elseif value == '' then status = 'EMPTY'
		elseif value == 'Invalid_NotOnDedicatedServer' then status = value
		elseif value:match('^Invalid_') then status = 'INVALID_SENTINEL (value withheld)'; table.insert(secrets, value)
		else
			status = 'PRESENT_OPAQUE (not proof of backend acceptance)'
			table.insert(secrets, value)
		end
		print('[GemTD Settlement] key'..index..'='..status)
	end
	return secrets
end

function GemTDSettlementResponse(result, secrets)
	GemTDSettlementLog('HTTP completed status', result.StatusCode)
	if result.StatusCode == nil or result.StatusCode == 0 then
		print('[GemTD Settlement] transport failure/timeout (HTTP callback supplies no precise cause)')
	end
	local body = result.Body
	if body == nil or body == '' then
		print('[GemTD Settlement] response body EMPTY/MISSING')
		return
	end
	print('[GemTD Settlement] response body bytes='..#body..' (log cap 16384 bytes)')
	local ok, decoded = pcall(json.decode, body)
	-- Inspect decoded strings too: a key may be Unicode-escaped in the raw JSON.
	local function contains_secret(value, depth)
		if depth > 16 then return true end
		if type(value) == 'string' then
			for _, secret in ipairs(secrets) do if value:find(secret, 1, true) then return true end end
		elseif type(value) == 'table' then
			for k, v in pairs(value) do
				if type(k) == 'string' and GemTDSettlementSafe('"'..k..'":', {}) == '<withheld: sensitive field>' then return true end
				if contains_secret(k, depth+1) or contains_secret(v, depth+1) then return true end
			end
		end
		return false
	end
	if ok and contains_secret(decoded, 0) then
		print('[GemTD Settlement] response body=<withheld: sensitive content>')
	else
		local safe = GemTDSettlementSafe(body, secrets)
		local length = math.min(#safe, 16384)
		for offset = 1, length, 1024 do
			print('[GemTD Settlement] response body chunk '..math.floor((offset-1)/1024+1)..'='..safe:sub(offset, math.min(offset+1023, length)))
		end
		if #safe > length then print('[GemTD Settlement] response body TRUNCATED at 16384 bytes') end
	end
	if not ok or type(decoded) ~= 'table' then
		print('[GemTD Settlement] JSON summary unavailable: invalid JSON or non-object response')
		return
	end
	for _, field in ipairs({'err', 'msg', 'error', 'status', 'success', 'award', 'award_item', 'award_extend',
		'level', 'rank', 'total', 'shell', 'player_count', 'quest', 'quest_expire', 'quest_finish_count', 'finishd_quest'}) do
		local value = decoded[field]
		if type(value) == 'table' then value = '<object; see sanitized response body>' end
		GemTDSettlementLog('JSON '..field, value, secrets, 512)
	end
end
