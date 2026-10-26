// Appended to the shipped gemtd script by tools/build_contribution_ui.py.
// ES5-compatible Panorama; isolated from the original damage board and callbacks.
(function () {
    "use strict";
    var table = "coop_contribution";
    var context = $.GetContextPanel();
    var root = $.CreatePanel("Panel", context, "CoopContributionRoot");
    var open = false, selected = 0, shown = -1, scheduled = false;
    var cards = {};

    function style(panel, values) {
        Object.keys(values).forEach(function (key) { panel.style[key] = values[key]; });
        return panel;
    }
    function panel(parent, type, values) {
        return style($.CreatePanel(type, parent, ""), values || {});
    }
    function label(parent, text, values) {
        var result = panel(parent, "Label", values);
        result.text = text;
        result.hittest = false;
        return result;
    }
    function button(parent, text, action, values) {
        var result = panel(parent, "Button", values);
        label(result, text, {color: "#e3edf2", "font-size": "17px", "horizontal-align": "center"});
        result.SetPanelEvent("onactivate", action);
        return result;
    }
    function number(value) {
        return Math.round(Number(value) || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }
    function playerName(id) {
        return Players.GetPlayerName(Number(id)) || ("玩家 " + (Number(id) + 1));
    }
    function entries(value) {
        return Object.keys(value || {}).map(function (key) { return value[key]; });
    }
    function get(key) { return CustomNetTables.GetTableValue(table, key); }

    style(root, {width: "100%", height: "100%", visibility: "collapse"});
    root.hittest = false;
    button(root, "合作贡献统计", function () {
        open = !open;
        body.style.visibility = open ? "visible" : "collapse";
        if (open) render();
    }, {"horizontal-align": "right", "margin-right": "24px", "margin-top": "126px",
        padding: "8px 16px", "background-color": "#192d3af5", border: "1px solid #607e8d"});

    var body = panel(root, "Panel", {"horizontal-align": "right", "margin-right": "24px",
        "margin-top": "172px", width: "420px", height: "620px", padding: "16px",
        "flow-children": "down", "background-color": "#111d28f5", border: "1px solid #47606e",
        visibility: "collapse"});
    label(body, "合作贡献统计", {color: "#f3d695", "font-size": "24px", "font-weight": "bold"});
    label(body, "按建造材料来源分摊塔的输出", {color: "#a2b5c1", "font-size": "16px", "margin-top": "3px"});
    var nav = panel(body, "Panel", {"flow-children": "right", "margin-top": "12px", width: "100%"});
    var navStyle = {padding: "5px 10px", "background-color": "#29404d", "margin-right": "6px"};
    var prev = button(nav, "上一回合", function () {
        var meta = get("meta") || {};
        selected = Math.max(1, (selected || Number(meta.latest)) - 1);
        render();
    }, navStyle);
    var next = button(nav, "下一回合", function () {
        var latest = Number((get("meta") || {}).latest) || 0;
        selected = Math.min(latest, (selected || latest) + 1);
        render();
    }, navStyle);
    button(nav, "最新", function () { selected = 0; render(); }, navStyle);
    var title = label(body, "等待第一回合", {color: "#ffffff", "font-size": "19px", "margin-top": "12px"});
    var total = label(body, "", {color: "#f3d695", "font-size": "22px", "margin-top": "5px"});
    var summary = panel(body, "Panel", {"flow-children": "down", width: "100%", "margin-top": "6px"});
    var note = label(body, "", {color: "#8fa4b4", "font-size": "14px", "margin-top": "5px", width: "100%"});
    var list = panel(body, "Panel", {"flow-children": "down", width: "100%", height: "fill-parent-flow(1)",
        overflow: "squish scroll", "margin-top": "10px"});
    label(body, "宝石 1–6 级权重：1 / 2 / 6 / 12 / 24 / 1050", {
        color: "#8297a5", "font-size": "13px", "margin-top": "8px"});

    function makeCard() {
        var card = panel(list, "Panel", {width: "100%", "flow-children": "down", padding: "10px",
            "margin-bottom": "8px", "background-color": "#21313e"});
        var name = label(card, "", {color: "#d7e9f2", "font-size": "18px", "font-weight": "bold", width: "100%"});
        var damage = label(card, "", {color: "#f3d695", "font-size": "21px", "margin-top": "4px"});
        var owner = label(card, "", {color: "#90a4b3", "font-size": "13px", width: "100%"});
        var rows = panel(card, "Panel", {"flow-children": "down", width: "100%", "margin-top": "7px"});
        return {panel: card, name: name, damage: damage, owner: owner, rows: rows};
    }

    function render() {
        var meta = get("meta");
        root.style.visibility = meta && Number(meta.enabled) === 1 ? "visible" : "collapse";
        if (!open || !meta) return;
        var latest = Number(meta.latest) || 0;
        if (selected > latest) selected = 0;
        var id = selected || latest;
        prev.enabled = id > 1;
        next.enabled = id > 0 && id < latest;
        var round = id ? get("round_" + id) : null;
        if (shown !== id) {
            list.RemoveAndDeleteChildren();
            summary.RemoveAndDeleteChildren();
            cards = {};
            shown = id;
        }
        if (!round) {
            title.text = "等待第一回合";
            total.text = "";
            note.text = "开始战斗后，贡献会随伤害实时更新。";
            return;
        }
        title.text = "第 " + round.level + " 回合 · " + (Number(round.finished) ? "已结算" : "战斗中");
        total.text = "塔总输出  " + number(round.damage);
        summary.RemoveAndDeleteChildren();
        Object.keys(round.players || {}).sort(function (a, b) {
            return round.players[b] - round.players[a] || Number(a) - Number(b);
        }).forEach(function (pid) {
            var share = round.damage > 0 ? round.players[pid] / round.damage * 100 : 0;
            label(summary, playerName(pid) + "   " + number(round.players[pid]) + "   " + share.toFixed(2) + "%", {
                color: "#bed2df", "font-size": "16px", width: "100%"});
        });
        note.text = "沿用原伤害统计口径；材料占比决定贡献。" +
            (round.other_damage > 0 ? " 其他来源伤害：" + number(round.other_damage) : "");
        var towers = [];
        for (var page = 1; page <= Number(round.pages); page++) {
            var index = get("round_" + id + "_page_" + page);
            entries(index && index.ids).forEach(function (towerId) {
                var tower = get("round_" + id + "_tower_" + towerId);
                if (tower) towers.push(tower);
            });
        }
        towers.sort(function (a, b) { return b.damage - a.damage || a.id - b.id; });
        var previous = null;
        towers.forEach(function (tower) {
            var card = cards[tower.id] || (cards[tower.id] = makeCard());
            var name = $.Localize("#" + tower.name);
            card.name.text = (name === "#" + tower.name ? tower.name : name) + "  ·  #" + tower.id;
            card.damage.text = "本回合输出  " + number(tower.damage);
            card.owner.text = "塔主：" + playerName(tower.owner) + " · 材料总权重 " + number(tower.total_weight) +
                (Number(tower.direct) ? " · 含直建材料" : "");
            card.rows.RemoveAndDeleteChildren();
            entries(tower.players).sort(function (a, b) { return a.player_id - b.player_id; }).forEach(function (row) {
                label(card.rows, playerName(row.player_id) + "   " + number(row.damage) + "   " +
                    (Number(row.share) * 100).toFixed(2) + "%  ·  权重 " + number(row.weight), {
                    color: "#e1e9ed", "font-size": "16px", width: "100%", "margin-top": "3px"});
            });
            if (previous) list.MoveChildAfter(card.panel, previous);
            else if (list.GetChild(0) !== card.panel) list.MoveChildBefore(card.panel, list.GetChild(0));
            previous = card.panel;
        });
    }

    CustomNetTables.SubscribeNetTableListener(table, function () {
        if (scheduled) return;
        scheduled = true;
        $.Schedule(0.05, function () { scheduled = false; render(); });
    });
    // Initial snapshot also covers late joins/reconnects without waiting for another hit.
    render();
}());
