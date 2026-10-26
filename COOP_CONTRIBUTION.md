# 合作贡献统计

2026-10-26：基于仓库 `03c1aa8` 实现，当前为本地开发版本。Lua 5.1 集成测试、Panorama 脚本模拟测试和原功能行为回归通过；尚未在 Dota 内完成新面板显示及真实多人验收，也未发布新的 Friend Kit。

## 项目进展梳理

| 已有工作 | 仓库记录的状态 |
| --- | --- |
| 原版基线 | 从 Workshop 474619917 提取运行资源，逐文件校验；版本来源和清单保存在 `baseline/manifest.json`。大型原 VPK 没有提交到 Git。 |
| 普通游戏运行 | README 记录已确认 `gemtd_coop` 的选英雄、建造、波次、击杀、回合推进和开发者命令可用；这是此前主机的实测记录，并非本次机器的新实测。 |
| 多人初始化 | 已修补晚加入、资料未返回时的英雄选择、异步初始化和重连；Lua 行为测试通过，记录中真实双人 Internet 验收仍待完成。详见 `MULTIPLAYER_INIT.md`。 |
| 好友安装包 | 记录中的稳定版本为 `946DE6E9DDE8C806`。安装/校验/备份逻辑已有验证记录；本次没有重建或覆盖它。 |
| 结算 | 主 Lua 已包含只读结算诊断。此前实测结算请求收到 HTTP 404，现有证据不足以确定是身份、路由还是其他服务条件。详见 `SETTLEMENT_DIAGNOSTICS.md`、`RANKING_404_INVESTIGATION.md`。 |
| 资源形态 | 主要是提取的编译资源，不是完整 Workshop Tools 创作工程。原 `custom_ui_manifest.xml` 与实际 `.vxml_c` 不等价，不能直接用该 XML 重建界面。 |

贡献统计独立于后台排名和奖励系统；现有结算请求、签名、反作弊、英雄初始化、塔攻击及 MVP 逻辑均保持原样。

## 使用效果

在新开局的 `gemtd_coop` / `gemtd_1p` 中，右上角增加「合作贡献统计」按钮。打开后可查看当前回合的玩家贡献总计、每一座有输出的塔的伤害和材料贡献明细；「上一回合 / 下一回合 / 最新」用于查看本局历史。已消耗的塔仍保留当回合的记录；同名塔按独立编号区分。

例如 A 建造 B1、B 建造 Y1、C 建造 D1，合成白银塔后输出 90,000：

| 玩家 | 材料权重 | 比例 | 分摊输出 |
| --- | ---: | ---: | ---: |
| A | 1 | 33.33% | 30,000 |
| B | 1 | 33.33% | 30,000 |
| C | 1 | 33.33% | 30,000 |

塔主和点击合成的人不改变材料贡献的归属。

## 计分规则

`玩家贡献比例 = 该玩家提供的材料权重合计 / 该塔全部材料权重合计`

`玩家分摊输出 = 该塔本回合统计伤害 × 玩家贡献比例`

| 宝石等级 | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 权重 | 1 | 2 | 6 | 12 | 24 | 1050 |

- 建造时保存建造者；保留、升级或降级宝石时保持建造者，按最后形成的基础宝石等级计权重。MVP 等战斗等级不改变材料权重。
- 普通合成只汇总真正被消耗的材料。相同种类的备用塔、未选中的候选宝石和留下的普通路障不增加贡献。
- 多级合成累加基础材料账本，不把中间塔重置成一份等权材料。例如上述白银塔继续与 B 的 Q2、C 的 R3 合成白银骑士，权重为 A=1、B=3、C=7，总权重 11。
- 一回合合成和隐藏配方只纳入对应配方所需材料；其余被选石流程丢弃的候选不计入。
- 石板按其配方材料记账，三块同种石板自动升级时继承全部来源。
- 五级宝石用四颗同类候选进行双升级得到「真假之石」时，保留实际四颗材料，总权重 96。它不是第七级基础宝石。
- 开发命令直接造出的特殊塔没有实际配方材料，标记为「含直建材料」，单份权重 1、归实际建造者；不会虚构它的配方。这只约定非正常材料生成路径，不影响正常合成的六级权重。
- 输出沿用原 `DamageStat` 的过滤器数值和向上取整规则，不声称是扣除护甲/过量伤害后的实际生命损失。
- 隐藏施法单位沿 `father` / owner 链归并至来源塔。创建时保存来源快照，即使父塔已合成销毁也保留原归属；旧伤害榜仍按原始攻击单位索引记账。
- 分摊以整座塔的累计回合伤害计算，再按最大余数法分配整数尾差；相同余数按玩家 ID 排序。不会逐次攻击取整。每座塔及玩家汇总严格守恒，显示的百分比保留两位小数，可能合计 99.99%。
- 没有材料来源的原统计事件单独显示为「其他来源伤害」，不会猜测贡献者。

## 实现位置与生命周期

- `game/gemtd_debug/scripts/vscripts/coop_contribution.lua`：材料账本、独立塔编号、隐藏单位来源快照、累计伤害分摊和网络发布。
- `game/gemtd_debug/scripts/vscripts/addon_game_mode.lua`：只增加接入点；移除这些新增行后，与 `03c1aa8` 的原 Lua 内容完全一致。
- `game/gemtd_debug/scripts/custom_net_tables.txt`：注册独立的 `coop_contribution` 表；原 `game_state.damage_stat`、`damage_stat_race`、`_G.damage` 和 MVP 计算不变。
- `content/gemtd_debug/panorama/scripts/custom_game/coop_contribution.js`：可审查的新增面板源码。
- `tools/build_contribution_ui.py`：将独立脚本追加到现有 `gemtd.vjs_c` 的 DATA 区；生成文件已更新并纳入工作区改动。

建造与合成保留材料账本，回合开始清空新模块的当回合累计；原全局 Think 每秒发布脏数据，回合结束及游戏结束补发最终值。玩家按 ID 汇总，不依赖玩家在线状态或当前塔主。回合历史保存在 NetTables，重连客户端主动读取已有快照；新开局重置索引，不跨局持久化。

网络数据按回合、塔和每页最多 64 个塔索引拆分，避免整局塞进单个 NetTable 值。300 座塔的压力测试中，最大 JSON 测试载荷为 704 字节；无新伤害时不重复发布。客户端合并同一批更新，保留列表容器与塔卡片，避免每次刷新重建整个滚动列表。

竞速模式保留原行为，新面板隐藏。

## Panorama 资源处理

当前主机没有 `resourcecompiler.exe`，而仓库实际加载的是编译后的 UI。现有 `gemtd.vjs_c` 是资源头版本 12、脚本版本 4，DATA 中存放 UTF-8 JavaScript。格式依据见 [ValveResourceFormat 的 Panorama 实现](https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/ResourceTypes/Panorama.cs)。

重建工具仅接受清单中锁定的原始资源或由本工具生成的资源，校验文件长度、块边界和原始 SHA-256。保留 RED2 和全部原脚本字节，只增加独立 IIFE，更新文件长度与 DATA 长度。重复执行结果一致。原 XML、CSS、地图、模型及其他编译资源不变。

```powershell
python tools/build_contribution_ui.py
python tools/build_contribution_ui.py --check
```

这是对现有脚本容器的定向更新，并非完整 Workshop Tools 编译；仍需普通 Dota 客户端实测确认资源加载和 Panorama 布局。

## 自动验证

在 PowerShell 7 中，从仓库根目录执行：

```powershell
python -m pip install --target tools/.test-deps lupa==2.8
python tools/test_coop_contribution.py
node tools/test_contribution_ui.js
python tools/build_contribution_ui.py --check
python tools/test_multiplayer_init.py
python tools/check_debug_mode.py --behavior-only
python tools/test_settlement_diagnostics.py --behavior-only
git -c core.whitespace=cr-at-eol diff --check
```

已通过真实 Lua 5.1 的 13 组功能场景，涵盖正常建造、三人白银、多级合成、全部等级、实际升降级处理函数、隐藏配方、石板、已销毁父塔代理、实体索引复用、稀疏玩家 ID、尾差守恒、回合结算、竞速隔离及大量塔。Node 测试执行实际新增 UI 脚本，验证重连快照、三人分摊显示、历史浏览、空回合、更新合并，并解析完整运行时脚本。

既有调试与结算测试增加 `--behavior-only`，用于运行全部行为断言而跳过历史发行包文件范围断言、VPK 依赖及旧补丁输出。默认模式仍保留原来的历史校验。新增测试另行验证本次改动没有改变原游戏代码。

这些测试使用引擎桩和 Panorama API 模拟，不替代真实联网和界面渲染验证。

## 游戏内验收与交付边界

所有测试玩家需加载同一开发版本，重启 Dota 并新开局。已有对局无法恢复补丁加载前未记录的材料来源。

1. 将本工作区运行目录部署到独立 `gemtd_debug` addon 后，用普通 Dota 控制台执行 `sv_cheats 0`、`dota_launch_custom_game gemtd_debug gemtd_coop`。本次没有修改本机 Steam/Dota 安装目录。
2. 确认原伤害榜仍显示，右上角「合作贡献统计」可开关且不遮挡常用操作；检查不同分辨率和长玩家名。
3. A/B/C 分别保留 B1/Y1/D1，由其中一人合成白银，核对三人的材料权重均为 1、比例均为 33.33%。90,000 的固定值已在自动测试验证；真实战斗按实际输出分摊。
4. 再用其他玩家的 Q2、R3 合成白银骑士，核对继承后 1:3:7 的权重；查看上一回合确认历史没有变化。
5. 验证石板代理伤害、同名多塔区分、最后一击与过关后的最终数值、重连快照和正常失败结算后的记录保留。

旧 Friend Kit 的打包器锁定稳定版文件清单和 Lua 哈希，不支持本次新增文件；本次没有放宽其发布校验，也没有生成新安装包。源码、运行资源和自动测试随本次功能提交，且不改变已有 404 调查结论。
