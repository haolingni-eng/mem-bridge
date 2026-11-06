# 共享记忆协议（AGENTS.memory.md）

你（本工具/本 agent）是跨工具共享记忆体系里的一个工作节点。记忆本体是 `~/finchnest` 下的纯文本文件，由 Finch 统一整理；你通过 `mem.py` 读写。**协议优先级低于用户当场指令。**

## 一、记忆在哪

| 层 | 文件 | 说明 |
|---|---|---|
| L0 规则 | `~/finchnest/AGENTS.md` | 长期硬规则、红线（本目录内工作时自动生效） |
| L1 索引 | `~/finchnest/MEMORY.md` | 一行式索引，只够判断相关性 |
| L1 明细 | `~/finchnest/memory/notes/<slug>.md` | 「触发 → 结论 → 复用条件」式笔记 |
| L2 日志 | `~/finchnest/memory/<日期>.md` | 工作日志、任务状态、踩坑记录 |
| L2 空间 | `~/finchnest/memory/spaces/<id>.md` | 项目状态与设计决策 |

## 二、开工必做

```bash
python3 ~/finchnest/tools/mem.py search <项目名/站点名/试剂引物名/报错关键词>
python3 ~/finchnest/tools/mem.py read <MEMORY|AGENTS|日期|笔记名>   # 命中后看明细
```

查到就照做，**禁止从零试探、禁止重复试错**。记录与实际不符时以实际为准。

## 三、收尾必做（你的写权限只有这一个口）

```bash
python3 ~/finchnest/tools/mem.py append --tool <你的名字> --task <任务名> --text "<内容>"
```

内容按固定五字段（缺省自动补全，缺的字段写"无"）：

- 完成：
- 停在哪：
- 下一步：
- 复用结论：[候选] <下次能少走一步的结论；没有就写"无">
- 踩坑：<症状 → 原因 → 下次怎么做；没有就写"无">

`[候选]` 不立即提升——等第二次用到才由 Finch 升进 MEMORY.md / notes。

**收尾不丢（双保险）**：会话收尾若未落五字段，视为本会话经验未登记——每日 20:00 的收割器
会从会话存档自动补摘要（带 `[harvest]` 标记），但自己写收尾信息质量更高，优先自己写。

## 四、禁止事项（红线）

1. **不许直接编辑** `MEMORY.md`、`memory/notes/`、`AGENTS.md`、`USER.md`——那些由 Finch 统一整理，你只写 daily log。
2. 密钥/Token/密码/PII 一律不写入记忆（CLI 会拦截，不要绕）。
3. 命名照原文：引物、载体、构建体、样本名、登录号一律照用户文档，不改写。
4. 不编造文献与数据；查不到就说查不到。
5. 原始数据只读，分析产物另存新文件。

## 五、速查

```bash
mem.py search <关键词...>    # 加权检索（L1 索引优先）
mem.py read <目标>           # 读明细
mem.py notes                 # 列笔记
mem.py append --tool X --task Y --text "..."   # 追加 daily log
mem.py inject <主题...>      # 生成可拼进 prompt 的记忆注入块
mem.py dispatch --task X <主题...>  # 三段式派发 prompt（注入块+任务+收尾指令）
mem.py harvest               # 收割六家会话存档（每晚定时自动跑）
mem.py sessions <关键词...>   # 下钻六家 transcript 原文
mem.py recall <关键词...>     # ContextBerg 活动下钻（当时屏幕上是什么；禁查键盘/剪贴板）
mem.py protocol              # 打印本协议
```
