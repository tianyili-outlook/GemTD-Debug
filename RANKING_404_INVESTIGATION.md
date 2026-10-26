# GemTD 结算 HTTP 404 调查（2026-09-26）

## 结论与边界

本次只读检查运行时、原 VPK、保留备份和公开源代码/更新记录。未修改 runtime，未重建 Friend Kit，未请求 GemTD 后台接口（包括 HEAD/OPTIONS），未重放结算。新增的文件只有本报告和 tools/ranking-history 下的公开源码快照、接口匹配清单。

高置信度结论：202408 路径来自当前已安装的原版 Workshop 包，不是 debug 分支意外保留的旧地址。实测请求进入了原版设计的结算链，收到 HTTP 404 和纯文本 Not Found，尚未得到正常结算业务响应。不能据此证明“只允许官方服务器”，也不能证明“路由已经删除”。

仍需区分：原版服务/代理路由异常；按服务器身份或其他条件隐藏为 404；特定请求参数、网络入口或中间层的差异。现有静态证据不足以可靠地在前两者间排序。key2..5 的无效标记使服务器身份差异成为优先验证项，但它不是 404 原因的证明。key1 非空也不等于认证成功。

## 已安装原包核验

- 当前上游：F:\Steam\steamapps\workshop\content\570\474619917\474619917.vpk
- 保留基线：F:\CodexProjects\GemTD-Debug\baseline\474619917.vpk
- 两者 SHA-256 完全一致：47714373031d769c8cb12efd6e3f69633cfc3f1418578e5c1b804c4180e1bb2c。
- publish_data.txt 标示发布时间 2026-09-17 21:42:42；这是本机安装版本的证据，不是后台服务部署版本的证据。
- 通过 tools/vpk_baseline.py 的 read_vpk 在内存读取并校验全部 2508 个归档条目。扫描包括编译 Panorama 的可读字符串、Lua、KV、配置、文本和资源；另检索了七个内嵌 VPK 的目标字符串。未找到额外 ranking 写入路径。字符串扫描不等于能审计后台或任意压缩/动态生成代码。
- 原 VPK 的 send_ranking、OnCatchCrab、GetSendKey 与 tools/pre-settlement-addon_game_mode.lua 中对应函数逐字相同。当前诊断版在前两个函数上增加观察日志；GetSendKey 未改。Panorama 主脚本与原 VPK 字节完全相同。
- 原包 Lua 第 7991 行已包含 coop 重写，第 4366 行已包含 race 的 202408 路径；当前诊断版对应第 8138、4370 行。

## 排名相关接口清单

除单独写出地址者外，下表均以 http://gemtd.ppbizon.com 为前缀。路径中的参数用省略号表示。编译文件位置以函数名/字面量为可靠定位；可读文本行号并非原作者源码行号。

| 路径 | 用途和引用位置 | 是否附加 GetSendKey |
| --- | --- | --- |
| /gemtd/ranking/add/@… | 主 panorama/scripts/custom_game/gemtd.vjs_c 的结算组包；gemtd2 同名资源也有；Lua 尾部另有整段注释的 SendCoopRanking 示例 | 客户端组包时无；转 catch_crab 后追加 |
| /gemtd/202408/ranking/add/@… | scripts/vscripts/addon_game_mode.lua:8138，OnCatchCrab 将上行路径重写后实际请求 | 是，五个字段 |
| /gemtd/202408/race/ranking/save/@… | 同一 Lua:4370，race 死亡结算直接构造；附 duration、wave 等 | 是，直接调用同一 GetSendKey |
| /gemtd/20181201/ranking/getall | gemtd2/panorama/scripts/custom_game/gemtd.vjs_c，旧排行榜读取，经 RequestProxy | OnRequestProxy 不追加密钥 |
| /gemtd/leaderboard/@… | 主 Panorama 的 update_leaderboard，RequestProxy 读取排行榜 | OnRequestProxy 不追加密钥 |
| /gemtd/leaderboard/collect/@… | 主 Panorama 的领取排行榜奖励按钮，RequestProxy | OnRequestProxy 不追加密钥；它是领取操作，不是结算上传替代接口 |
| http://101.200.189.65:2009/gemtd/ranking/get | panorama/layout/custom_game/game_info.vxml_c 内嵌脚本，AsyncWebRequest 旧实时排行展示 | 客户端直接请求，无 GetSendKey；未确认此旧面板当前会加载 |
| /gemtd/201807/mmr/get/@… | 主 Panorama 和 gemtd2 副本的账户/MMR读取，经 RequestProxy | OnRequestProxy 不追加密钥；不是 ranking/add 替代路径 |

本包 gemtd2 是遗留/重复资源，不能仅凭文件存在断言当前主界面使用它。公开镜像中的 gemtd2/scripts/vscripts/addon_game_mode.lua 也检查过：不含目标结算路径；该 Lua 不在本地原 VPK 的同名位置。

没有找到 2019、2020 或比 202408 更新的另一条 ranking/add 或 ranking/save 写入版本。具体匹配保存在 tools/ranking-history/installed-endpoint-inventory.json，来源是原 VPK 而不是改过的 Lua。

## 其他写操作与密钥范围

“活跃”在这里指仍有调用代码，未经实际操作确认服务可用。

| 路径家族 | 调用方式 | 密钥处理 |
| --- | --- | --- |
| /gemtd/201803/boxwinter/buy、hero/buy、ability/buy、effect/buy | 主 Panorama 的购买处理 → catch_crab | 同一五字段 GetSendKey |
| /gemtd/201811/toy/buy | 主 Panorama → catch_crab | 同上 |
| /gemtd/hero/recycle/progress、/gemtd/ability/delete | 主 Panorama 的 confirm_recycle / confirm_delete → catch_crab | 同上 |
| /gemtd/hero/save | Lua OnSaveHero:14254 | 直接 GetSendKey |
| /gemtd/maze/save、/gemtd/quest/begin | Lua 独立请求（maze:3248，quest:11775/13383） | 调用点没有追加 GetSendKey |
| /gemtd/extend/use、/gemtd/cdkey/use、/gemtd/leaderboard/collect | 主 Panorama → RequestProxy | OnRequestProxy 不追加 GetSendKey |
| /gemtd/202203/heros/get | Lua 获取玩家资料，含 award 参数的调用也存在 | 该 Lua 调用直接 GetSendKey；不能简单视为纯查询探针 |

OnCatchCrab 对所有进入它的 URL 追加同一组 key、key2、key3、key4、key5。只对精确匹配 gemtd/ranking/add/ 的子串实施 202408 重写，不判断地图。race 绕过此函数，但显式调用同一个 GetSendKey。OnRequestProxy:14226 按传入 URL 创建 GET，不追加这些字段。

因此不能把“账户能读”“兑换/领取能成功”直接当成 ranking 写入已获授权；路由和认证要求可能不同。也不能推断所有写操作都必须同一套认证。不同年代路由并存，版本年份本身不构成失效证据。

## 历史与迁移原因

公开仓库是自动处理的 source dump，不是完整的原作者开发历史：

- [仓库说明](https://github.com/QFunnn/dota2-customs)
- [2026-08-28 快照 2cc0d498ead5b1363c2250e0e8c9f6a8674b9167](https://github.com/QFunnn/dota2-customs/commit/2cc0d498ead5b1363c2250e0e8c9f6a8674b9167)
- [2026-09-18 快照 b73b329ddc17547feaa1e486eaf29a4b5aa3cc59](https://github.com/QFunnn/dota2-customs/commit/b73b329ddc17547feaa1e486eaf29a4b5aa3cc59)

gem-td 分支可达历史只有这两个提交，提交说明均为 action: update custom。两份主 Lua 的 OnCatchCrab 第 8593 行均有同样重写，race 均为 202408；GetSendKey 相同。两份主 Panorama 除生成器 build 注释外相同。主 Lua 差异是生成器标记、作者注释及被注释的 IsPlayerHost 示例，没有结算路由变化。保留的本地基线和前几次备份也始终包含同一重写。

所以“能证明最早存在”的日期是 2026-08-28；不能将此当成首次引入日期。202408 是路径标签，不是可验证的提交时间。

[官方 Workshop 更新记录第 2 页](https://steamcommunity.com/sharedfiles/filedetails/changelog/474619917?p=2) 有两条相关事件：2024-07-31 因 Dota 更新后不稳定而暂时关闭排行榜；2024-08-01 说明 Dota 7.37 引起严重问题，已从 8 月 1 日清空排行榜记录。这个时间与 202408 命名一致，支持“排行榜重置后启用新命名空间”的推测。公告没有提及具体 API、密钥认证或故意返回 404，因而不能证明迁移的代码日期或今天的故障原因。

## 实测请求是否符合原版逻辑

符合已核对的代码结构：send_ranking → NetTable → Panorama 构建无版本 URL → catch_crab → 202408 重写 → GetSendKey → GET。原版客户端参数包括 time_cost、level、kills、player_ids、finishd_quest、local_id，以及 towers、ac=20180827、gold、extra_kill、maze_length、player_count。

这不意味着本地服务器与官方请求字节完全相同：服务器密钥、实际玩家/对局数据、运行环境当然不同；现有日志也没有暴露完整带密钥 URL，不宜宣称每个实际参数都已与官方实测请求对齐。is_cheat=false 和本局未用开发玩法命令排除了本次明显的本地结算跳过分支，不能代替后台接受证明。

JSON.parse 失败是上游返回非 JSON 后的后续异常，不是请求产生 404 的原因。404 只能说明某个 HTTP 响应方返回了 Not Found；仅凭状态和正文不能识别它是应用、鉴权层、反向代理还是其他中间层。也不能从 404 保证后台完全没有副作用，故不应手工重试原结算。

## 假设 A–D

本次请求没有列出 A–D 的具体定义，以下是本报告用于比较的工作定义；与上次诊断文档 A/B/C 三个“问题类别”不同。

| 假设 | 支持/反证 | 当前判断 |
| --- | --- | --- |
| A：debug 使用了原版已经不用的旧结算地址 | 当前上游 VPK 与基线哈希相同；原版 Lua/客户端同一路由；两次公开快照一致 | 对当前已安装版本，高置信度排除 |
| B：原版 202408 路由已停用、配置异常或服务故障 | 404 + Not Found 与此相容；客户端源码不能证明服务在线 | 保留，缺少同时间官方环境对照 |
| C：本地服务器身份/密钥被拒绝，后台用 404 隐藏 | key2..5 明确不是 dedicated-server 有效值；原版写入携带密钥 | 优先验证，但无后台日志/官方对照，不可定论 |
| D：具体请求参数、URL 处理、网络入口或中间层差异 | HTTP 404 不提供生成层；未逐字核对官方实测请求 | 保留；标准组包和原版同源使意外改坏 URL 的解释较弱 |

最可靠的解释是“原版要求的 202408 结算请求在本地主机上下文下没有得到正常业务响应”，置信度高。把原因进一步归为身份拒绝或路由故障，置信度均不足。不到 51 波的奖励资格属于后续问题，目前没有业务回包证明资格检查已经执行。

## 下一步（只建议，未实施）

最直接、无新增写入的证据：请地图维护者按既有测试的准确时间、路径、地图和 HTTP 状态查询服务日志，确认请求是否命中 ranking/add、是否被鉴权层隐藏为 404、路由是否仍部署。不要发送任何服务器密钥。此举需要用户自行联系；本次没有联系任何人。

若维护者无法协助，下一次游戏实验应为原版 Workshop 在正常 Arcade 服务器上的短局自然失败对照，而不是再打一场相同本地环境：

1. 从 Dota 游廊启动订阅原版 GemTD，coop 地图；使用正常平台分配的服务器，不用 dota_launch_custom_game gemtd_debug，不用 direct-connect 本地主机。
2. 不用玩法作弊命令，几波后自然失败，保留结算界面、可见控制台错误、时间和比赛/大厅信息；尽量与本地失败测试时间接近。
3. 若原版能完成正常结算业务显示，本地仍为 404，则“接口对所有环境已失效”的解释明显减弱，身份/参数/网络差异成为重点。单纯没奖励不算结算失败，因为低关卡本来可能无奖励。
4. 若原版也出现同类 Not Found/JSON.parse 错误，则应优先查共同后台/路由问题。只有空奖励面板而没有可确认错误，结果是不确定，不能强行归因。

普通官方对局客户端未必能取得服务器 HTTP 状态；本地诊断 Lua 也不会被自动部署到官方服务器。若界面证据不足，应由维护者提供只含状态/业务结果的服务端记录，而不是要求玩家提取密钥。

没有实施 HEAD/OPTIONS：方法支持、通配路由、鉴权隐藏都可能让结果无法区分 B/C；而这些业务接口用 GET 写入，不能未经验证就保证 HEAD 处理完全无副作用。对路径根部发探针也不等价于携完整路径参数的真实请求。

当前没有必要打到 50 波以上。level 9 已走到真实 HTTP 完成回调，足够研究当前传输/认证问题。先确认可以得到正常 JSON，再单独研究 >50 波、每周任务和 -crab 使用是否影响奖励资格；目前不能承诺 -crab 与官方奖励能够并存。
