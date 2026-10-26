// Run with node tools/test_contribution_ui.js; no browser/game/backend required.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const rootPath = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(rootPath, "content/gemtd_debug/panorama/scripts/custom_game/coop_contribution.js"), "utf8");

class Panel {
    constructor(type, parent, id) {
        this.type = type; this.parent = parent; this.id = id;
        this.style = {}; this.children = []; this.events = {}; this.text = "";
        if (parent) parent.children.push(this);
    }
    SetPanelEvent(event, action) { this.events[event] = action; }
    RemoveAndDeleteChildren() { this.children = []; }
    GetChild(index) { return this.children[index]; }
    MoveChildBefore(child, other) {
        assert.notEqual(child, other);
        this.children.splice(this.children.indexOf(child), 1);
        this.children.splice(this.children.indexOf(other), 0, child);
    }
    MoveChildAfter(child, other) {
        assert.notEqual(child, other);
        this.children.splice(this.children.indexOf(child), 1);
        this.children.splice(this.children.indexOf(other) + 1, 0, child);
    }
}

function setup(net) {
    const context = new Panel("Panel", null, "context");
    let callback;
    const timers = [];
    const sandbox = {
        $: {
            GetContextPanel: () => context,
            CreatePanel: (type, parent, id) => new Panel(type, parent, id),
            Localize: token => ({"#gemtd_baiyin": "白银塔", "#gemtd_baiyinqishi": "白银骑士"})[token] || token,
            Schedule: (time, fn) => timers.push(fn),
        },
        Players: {GetPlayerName: id => ["玩家 A", "玩家 B", "玩家 C", "玩家 D"][id]},
        CustomNetTables: {
            GetTableValue: (table, key) => { assert.equal(table, "coop_contribution"); return net[key]; },
            SubscribeNetTableListener: (table, fn) => { assert.equal(table, "coop_contribution"); callback = fn; },
        },
    };
    vm.runInNewContext(source, sandbox);
    function nodes(panel = context) { return [panel, ...panel.children.flatMap(nodes)]; }
    function click(text) {
        const label = nodes().find(p => p.text === text);
        assert(label, "missing button: " + text);
        assert.notEqual(label.parent.enabled, false, "disabled button: " + text);
        label.parent.events.onactivate();
    }
    return {context, nodes, click, timers,
        text: () => nodes().map(p => p.text).join("\n"),
        emit: () => callback("coop_contribution", "meta", net.meta),
        flush: () => { while (timers.length) timers.shift()(); },
    };
}

const net = {
    meta: {enabled: 1, latest: 1},
    round_1: {level: 1, damage: 90000, other_damage: 0, finished: 1, pages: 1,
        players: {"0": 30000, "1": 30000, "2": 30000}},
    round_1_page_1: {ids: {"1": 7}},
    round_1_tower_7: {id: 7, name: "gemtd_baiyin", owner: 0, damage: 90000, total_weight: 3,
        players: {"0": {player_id: 0, damage: 30000, share: 1 / 3, weight: 1},
            "1": {player_id: 1, damage: 30000, share: 1 / 3, weight: 1},
            "2": {player_id: 2, damage: 30000, share: 1 / 3, weight: 1}}},
};
const ui = setup(net);
assert.equal(ui.context.GetChild(0).style.visibility, "visible");
ui.click("合作贡献统计");
assert.match(ui.text(), /白银塔/);
assert.match(ui.text(), /本回合输出  90,000/);
for (const name of ["玩家 A", "玩家 B", "玩家 C"]) {
    assert(ui.text().includes(name + "   30,000   33.33%  ·  权重 1"));
}
console.log("PASS: initial/late-join snapshot renders 90000 silver tower with three 30000 / 33.33% rows");

net.meta.latest = 2;
net.round_2 = {level: 2, damage: 110000, other_damage: 25, finished: 0, pages: 1,
    players: {"0": 10000, "1": 30000, "2": 70000}};
net.round_2_page_1 = {ids: [9]};
net.round_2_tower_9 = {id: 9, name: "gemtd_baiyinqishi", owner: 1, damage: 110000, total_weight: 11,
    players: {"0": {player_id: 0, damage: 10000, share: 1 / 11, weight: 1},
        "1": {player_id: 1, damage: 30000, share: 3 / 11, weight: 3},
        "2": {player_id: 2, damage: 70000, share: 7 / 11, weight: 7}}};
for (let i = 0; i < 20; i++) ui.emit();
assert.equal(ui.timers.length, 1, "network burst must coalesce");
ui.flush();
assert.match(ui.text(), /第 2 回合 · 战斗中/);
assert.match(ui.text(), /其他来源伤害：25/);
assert(!ui.text().includes("白银塔"));
ui.click("上一回合");
assert.match(ui.text(), /第 1 回合 · 已结算/);
ui.emit(); ui.flush();
assert.match(ui.text(), /第 1 回合 · 已结算/);
ui.click("下一回合");
ui.click("最新");
assert.match(ui.text(), /白银骑士/);
const card = ui.nodes().find(p => p.text.includes("白银骑士")).parent;
ui.emit(); ui.flush();
assert.equal(ui.nodes().find(p => p.text.includes("白银骑士")).parent, card, "keep list cards and scroll container during updates");
console.log("PASS: burst debounce, history navigation, latest following, source names, other damage and stable cards");

net.meta.latest = 3;
net.round_3 = {level: 3, damage: 0, pages: 0, players: {}, finished: 0};
ui.emit(); ui.flush();
assert.match(ui.text(), /第 3 回合 · 战斗中/);
assert(!ui.text().includes("白银骑士"));
assert(!ui.text().includes("70,000"));
net.meta = {enabled: 0, latest: 0};
ui.emit(); ui.flush();
assert.equal(ui.context.GetChild(0).style.visibility, "collapse");
net.meta = {enabled: 1, latest: 0};
ui.emit(); ui.flush();
assert.match(ui.text(), /等待第一回合/);
console.log("PASS: empty rounds, race disabled, and new-match reset clear stale data");

const binary = fs.readFileSync(path.join(rootPath, "game/gemtd_debug/panorama/scripts/custom_game/gemtd.vjs_c"));
assert.equal(binary.readUInt32LE(0), binary.length);
assert.equal(binary.readUInt16LE(4), 12);
assert.equal(binary.readUInt16LE(6), 4);
assert.equal(binary.readUInt32LE(12), 2);
const dataEntry = 8 + binary.readUInt32LE(8) + 12;
assert.equal(binary.toString("ascii", dataEntry, dataEntry + 4), "DATA");
const start = dataEntry + 4 + binary.readUInt32LE(dataEntry + 4);
assert.equal(start + binary.readUInt32LE(dataEntry + 8), binary.length);
new vm.Script(binary.toString("utf8", start));
assert(binary.toString("utf8", start).endsWith(source));
console.log("PASS: shipped VJS container and complete legacy + contribution JavaScript syntax");
