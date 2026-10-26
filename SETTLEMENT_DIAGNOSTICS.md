# 单人 coop 结算诊断（2026-09-26）

只用于主机工作区。Friend Kit 没有重建，仍是稳定多人版本 `946DE6E9DDE8C806`。当前主机 Lua 故意与该包不同，因此旧包 Verify 对主机报告该 Lua 不一致是预期现象。

运行时只改 `game/gemtd_debug/scripts/vscripts/addon_game_mode.lua`：增加只读日志辅助函数，观察 `send_ranking()` 和 `OnCatchCrab()`。没有新增指令、HTTP 请求、重试、任务完成条件或奖励逻辑。原来的 `GetSendKey()` 保持原样且每个请求仍只调用一次。原回包原封不动转发给 Panorama；遮蔽只作用于日志。所有观察代码仅在 `_G.myself == true` 时运行，并用 `pcall` 隔离观察错误。

## 第一次实际测试

1. 重启普通 Dota 2，确保重新加载修改后的 Lua。
2. 控制台执行 `sv_cheats 0`，然后 `dota_launch_custom_game gemtd_debug gemtd_coop`。
3. 单人，按正常方式选英雄、开始、建造。不使用 `-crab`、`-money`、`-choose`、`-spawn` 等开发玩法命令，也不需要 `-debug`。
4. 玩几波后让城堡自然被摧毁；不要直接退出或断开。保留游戏/控制台，等待原流程结算及 HTTP 回调（配置的请求超时是 20 秒）。
5. 保存从 `send_ranking ENTER` 到 `response FORWARDED` 的全部 `[GemTD Settlement]` 行。如果链路中断，保存已有的行及第一条 Lua 错误。Steam ID 会出现在诊断中，公开分享前可自行遮蔽。

这是运输/认证测试，不是通关领奖测试。不到 51 关时，`award=0` 或空 `finishd_quest` 本身不能证明认证被拒绝。当前 `_G.myself=true` 仍启用；本次不使用玩法命令，仅用于排除实际调用这些命令的干扰，不能代表完全原版服务器。

## 预期日志链

```text
[GemTD Settlement] send_ranking ENTER
[GemTD Settlement] map=gemtd_coop
[GemTD Settlement] level=<当前关卡>
[GemTD Settlement] game_time=<游戏时间>
[GemTD Settlement] player_count=1
[GemTD Settlement] is_cheat=false
[GemTD Settlement] is_posted_game=nil
[GemTD Settlement] steam_ids=<你的SteamID>
[GemTD Settlement] PUBLISHED game_state.send_ranking; awaiting Panorama catch_crab
[GemTD Settlement] time_cost=<耗时>
[GemTD Settlement] finishd_quest=
[GemTD Settlement] towers=<原始汇总，限4096字节>
...
[GemTD Settlement] catch_crab request received
[GemTD Settlement] key1=<状态>
...
[GemTD Settlement] key5=<状态>
[GemTD Settlement] endpoint=gemtd/202408/ranking/add/ (URL arguments and keys omitted)
[GemTD Settlement] callback=send_ranking_cb
[GemTD Settlement] request_user=<你的SteamID>
[GemTD Settlement] HTTP request started; timeout_ms=20000
[GemTD Settlement] HTTP completed status=<HTTP状态>
[GemTD Settlement] response body bytes=<原始字节数> (log cap 16384 bytes)
[GemTD Settlement] response body chunk 1=<经过敏感信息检查的原始回包>
[GemTD Settlement] JSON err=<值或nil>
[GemTD Settlement] JSON msg=<值或nil>
[GemTD Settlement] JSON award=<值或nil>
...
[GemTD Settlement] response FORWARDED to original Panorama callback
```

`HTTP request started` 表示进入原有 `req:Send` 调用点，不单独证明后台已收到请求。必须结合 completed 状态和业务回包判断。`FORWARDED` 只证明已写回原来的 NetTable，不证明 UI 成功解析或渲染。

## 密钥与回包保护

- `MISSING`：GetSendKey 返回的参数串里没有对应字段。
- `EMPTY`：字段为空。
- `Invalid_NotOnDedicatedServer`：允许明文打印的已知公开无效标记。
- `INVALID_SENTINEL (value withheld)`：其他以 `Invalid_` 开头的值，具体值不打印。
- `PRESENT_OPAQUE (not proof of backend acceptance)`：存在非空不透明值，但这不证明后台接受。实际值不打印。

不打印携带密钥的完整 URL、请求头或 GetSendKey 返回串。回包中已知密钥及其常见 JSON/URL 编码形式会遮蔽；凭据字段（key/token/auth/secret/password/credential/cookie/signature）会触发内容隐藏。有效 JSON 还检查解码后的字段名和值，防止 Unicode 转义绕过日志遮蔽。解析错误不输出可能包含原文的异常信息。

正常回包保留原始文本（控制字符转义），每块最多 1024 字节，每次响应最多记录 16384 字节；超出明确显示 TRUNCATED。敏感正文显示 withheld。JSON 摘要字段最多 512 字节，嵌套对象只提示查看安全正文。没有每帧日志、轮询或新增定时器；只在原有结算事件/回调中记录。

## 如何判断故障层

| 观察结果 | 能说明什么 |
| --- | --- |
| 没有 ENTER | 原结算入口没有被观察到；先排查是否真正自然结束、是否加载诊断 Lua |
| ENTER 后 SKIP | 原来的作弊状态或已提交防重复分支阻止了本次发布 |
| PUBLISHED 后没有 catch_crab | 问题位于 NetTable → Panorama 监听/组包 → 客户端事件送达之间；这组 Lua 日志不能进一步区分是哪一环 |
| received 后没有 HTTP started | 看 Lua 错误；原 GetSendKey、随机延迟定时器或请求创建可能没有完成 |
| HTTP status 0/缺失 | 运输失败或超时类别；API 未提供精确原因时不武断认定超时 |
| 非 2xx 或空/非 JSON 正文 | HTTP/代理/后台异常；不能直接等同于账号无奖励资格 |
| HTTP 200，但 err/msg 明确拒绝 | HTTP 到达不等于业务接受；以回包的错误说明判断认证或规则拒绝 |
| 回包表示成功且 award=0 | 可能仅为低关卡、冷却、任务或其他资格原因，不足以推断本地主机被拒绝 |
| 回包有奖励，但 UI 不显示 | 继续检查原 Panorama JSON 解析/奖励展示和随后账户读取；不单凭日志宣称到账 |

没有改编译 Panorama。已检查 `panorama/scripts/custom_game/gemtd.vjs_c` 中可读的运行时代码：监听 `send_ranking`，构建 URL，并发送 `catch_crab`（callback=`send_ranking_cb`）；回包通过 `JSON.parse(data.crab)` 处理。Lua 的 published/received 边界足以观察客户端链路是否走通，但没有 received 时不能证明客户端究竟没生成、没发送还是没送达。

静态发现：`send_ranking()` 在收到后台确认之前就设置 `_G.is_posted_game=true`；未发现这个结算请求的自动重试。任务完成列表只在 `_G.level>50` 时汇总。原 Panorama 将 err=1200 显示为后端消息，奖励由回包字段控制。本次均未更改。

## 验证与产物

- `tools/test_settlement_diagnostics.py`：真实 Lua 5.1 执行前后对照，无实际 HTTP；核对结算状态、已提交标志、任务状态、URL、请求次数、超时和回包转发完全一致。覆盖成功、业务错误、HTTP错误、空正文、非JSON、长正文、密钥回显、凭据字段、Unicode转义、观察失败隔离及非调试/无关请求静默。
- 原多人初始化及开发者命令回归测试通过。所有既有函数除两个加日志的结算处理函数外保持相同；塔逻辑、`-crab`、反作弊、服务器密钥函数和连接兼容性不变。
- `tools/settlement-diagnostics.patch`：相对于稳定多人版本的诊断差异。
- `tools/pre-settlement-addon_game_mode.lua`：改动前完整备份；以后结束诊断时可恢复。
- Friend Kit 和打包脚本的稳定源码校验值未更新，避免把未经真实结算验证的主机诊断版误当成新发行版本。
