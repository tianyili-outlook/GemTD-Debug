-- Material provenance is independent of tower ownership and the original damage/MVP tables.
local M = {}
M.GEM_WEIGHTS = {1, 2, 6, 12, 24, 1050}
local state

local function enabled()
    return GetMapName() == "gemtd_coop" or GetMapName() == "gemtd_1p"
end

local function valid(unit)
    return unit ~= nil and not unit:IsNull()
end

local function copy(materials)
    local result = {}
    for key, material in pairs(materials or {}) do
        result[key] = {player_id = material.player_id, gem = material.gem,
            weight = material.weight, count = material.count, direct = material.direct}
    end
    return result
end

function M.GemWeight(name)
    local tier = string.match(name or "", "^gemtd_[bdyegqrp](1+)$")
    return tier and M.GEM_WEIGHTS[#tier] or nil
end

function M.Reset()
    state = {next_tower = 0, round_count = 0}
    CustomNetTables:SetTableValue("coop_contribution", "meta", {
        enabled = enabled() and 1 or 0, latest = 0, version = 1})
end

function M.Capture(unit)
    if not valid(unit) or not unit.gemtd_contribution then return {} end
    return copy(unit.gemtd_contribution.materials)
end

function M.Join(target, materials)
    for key, material in pairs(materials or {}) do
        local entry = target[key]
        if entry then
            entry.weight = entry.weight + material.weight
            entry.count = entry.count + material.count
        else
            target[key] = copy({[key] = material})[key]
        end
    end
    return target
end

function M.Collect(units)
    local materials, seen = {}, {}
    for _, unit in pairs(units or {}) do
        if not seen[unit] then
            seen[unit] = true
            M.Join(materials, M.Capture(unit))
        end
    end
    return materials
end

function M.Attach(unit, player_id, materials)
    if not enabled() or not valid(unit) then return end
    local weights, total, direct = {}, 0, false
    materials = copy(materials)
    for _, material in pairs(materials) do
        local id = material.player_id
        weights[id] = (weights[id] or 0) + material.weight
        total = total + material.weight
        direct = direct or material.direct == true
    end
    if total <= 0 then return end
    state.next_tower = state.next_tower + 1
    unit.gemtd_contribution = {id = state.next_tower, name = unit:GetUnitName(),
        owner = player_id, materials = materials, weights = weights,
        total_weight = total, direct = direct}
end

function M.RegisterBase(unit, player_id)
    if not enabled() or not valid(unit) or player_id == nil or player_id < 0 then return end
    local name = unit:GetUnitName()
    local weight = M.GemWeight(name)
    -- Direct debug-created special towers have no fabricated recipe/history.
    local materials = {[player_id .. ":" .. name] = {player_id = player_id, gem = name,
        weight = weight or 1, count = 1, direct = weight == nil}}
    M.Attach(unit, player_id, materials)
end

-- A kept/upgraded/downgraded basic gem uses its final tier's weight; its builder stays fixed.
function M.Selection(caster, name, candidates)
    local old = M.Capture(caster)
    local weight = M.GemWeight(name)
    if weight then
        local weights, total, result = {}, 0, {}
        for _, material in pairs(old) do
            weights[material.player_id] = (weights[material.player_id] or 0) + material.weight
            total = total + material.weight
        end
        for id, value in pairs(weights) do
            result[id .. ":" .. name] = {player_id = id, gem = name,
                weight = weight * value / total, count = 1, direct = false}
        end
        return result
    end
    if name == "gemtd_zhenjiazhishi" and M.GemWeight(caster:GetUnitName()) then
        local selected = {caster}
        for _, unit in pairs(candidates or {}) do
            if #selected < 4 and valid(unit) and unit ~= caster and unit:GetUnitName() == caster:GetUnitName() then
                selected[#selected + 1] = unit
            end
        end
        return M.Collect(selected)
    end
    return old
end

-- One-wave synthesis discards unused candidates too; only recipe ingredients count.
function M.RecipeMaterials(name, candidates, caster, recipes)
    for _, book in ipairs(recipes) do
        local recipe = book[name]
        if recipe then
            local needed, chosen, used = {}, {}, {}
            for _, gem in ipairs(recipe) do needed[gem] = (needed[gem] or 0) + 1 end
            local function select(unit)
                if valid(unit) and not used[unit] then
                    local gem = unit:GetUnitName()
                    if (needed[gem] or 0) > 0 then
                        needed[gem] = needed[gem] - 1
                        used[unit] = true
                        chosen[#chosen + 1] = unit
                    end
                end
            end
            select(caster)
            for _, unit in pairs(candidates or {}) do select(unit) end
            if #chosen == #recipe then return M.Collect(chosen) end
        end
    end
    return {}
end

local function source_for(unit, seen)
    if not valid(unit) or seen[unit] then return nil end
    seen[unit] = true
    if unit.gemtd_damage_source then return unit.gemtd_damage_source end
    if unit.gemtd_contribution then return unit.gemtd_contribution end
    return source_for(unit.father, seen) or source_for(unit:GetOwner(), seen)
end

function M.BindProxy(unit, parent)
    if enabled() then unit.gemtd_damage_source = source_for(parent, {}) end
end

local function write(key, value)
    CustomNetTables:SetTableValue("coop_contribution", key, value)
end

-- Round totals are apportioned once, rather than rounding every hit toward one player.
function M.Split(damage, weights)
    local total, rows, allocated = 0, {}, 0
    for _, weight in pairs(weights) do total = total + weight end
    for id, weight in pairs(weights) do
        local exact = damage * weight / total
        local amount = math.floor(exact)
        rows[#rows + 1] = {player_id = id, weight = weight, share = weight / total,
            damage = amount, remainder = exact - amount}
        allocated = allocated + amount
    end
    table.sort(rows, function(a, b)
        if a.remainder == b.remainder then return a.player_id < b.player_id end
        return a.remainder > b.remainder
    end)
    for i = 1, damage - allocated do rows[i].damage = rows[i].damage + 1 end
    local result = {}
    for _, row in ipairs(rows) do
        row.remainder = nil
        result[tostring(row.player_id)] = row
    end
    return result
end

function M.Publish()
    local round = state and state.round
    if not round or not round.dirty then return end
    local prefix = "round_" .. round.id
    local players, ids = {}, {}
    for id, tower in pairs(round.towers) do
        local source = tower.source
        local shares = M.Split(tower.damage, source.weights)
        for player_id, row in pairs(shares) do
            players[player_id] = (players[player_id] or 0) + row.damage
        end
        if tower.dirty then
            write(prefix .. "_tower_" .. id, {id = id, name = source.name, owner = source.owner,
                damage = tower.damage, total_weight = source.total_weight, players = shares,
                direct = source.direct and 1 or 0})
            tower.dirty = false
        end
        ids[#ids + 1] = id
    end
    table.sort(ids)
    -- Each payload is bounded; a whole match never goes into a single NetTable value.
    local pages = math.ceil(#ids / 64)
    if round.index_dirty then
        for page = 1, pages do
            local entries = {}
            for i = (page - 1) * 64 + 1, math.min(page * 64, #ids) do
                entries[#entries + 1] = ids[i]
            end
            write(prefix .. "_page_" .. page, {ids = entries})
        end
        round.index_dirty = false
    end
    write(prefix, {id = round.id, level = round.level, finished = round.finished and 1 or 0,
        damage = round.damage, other_damage = round.other_damage, players = players,
        pages = pages, tower_count = #ids})
    if round.meta_dirty then
        write("meta", {enabled = 1, latest = round.id, version = 1})
        round.meta_dirty = false
    end
    round.dirty = false
end

function M.FinishRound()
    local round = state and state.round
    if round and not round.finished then
        round.finished, round.dirty = true, true
        M.Publish()
    end
end

function M.StartRound(level)
    if not enabled() then return end
    M.FinishRound()
    state.round_count = state.round_count + 1
    state.round = {id = state.round_count, level = level, towers = {}, damage = 0,
        other_damage = 0, finished = false, dirty = true, index_dirty = true, meta_dirty = true}
    M.Publish()
end

function M.RecordDamage(attacker, damage)
    local round = state and state.round
    if not enabled() or not round or round.finished or not damage or damage <= 0 then return end
    damage = math.ceil(damage) -- same measurement as DamageStat; not post-mitigation HP loss
    local source = source_for(attacker, {})
    if source then
        local tower = round.towers[source.id]
        if not tower then
            tower = {source = source, damage = 0}
            round.towers[source.id] = tower
            round.index_dirty = true
        end
        tower.damage, tower.dirty = tower.damage + damage, true
        round.damage = round.damage + damage
    else
        round.other_damage = round.other_damage + damage
    end
    round.dirty = true
end

function M.Tick()
    if not enabled() then return end
    -- Regular updates are triggered by the existing DamageStat throttle.
    -- Retain this Think hook only as the original end-of-game fallback.
    if _G.game_status == 3 or GameRules:State_Get() >= DOTA_GAMERULES_STATE_POST_GAME then
        M.FinishRound()
    end
end

return M
