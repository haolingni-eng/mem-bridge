#!/usr/bin/env python3
"""mem.py — 跨工具共享记忆的统一读写收口（Finch / Qoder / OpenCode / Trae / Antigravity / Command Code / PI-Desktop 共用）。

写权限铁律：外部工具只能通过 `append` 追加 daily log；MEMORY.md / notes/ 的整理提升只由 Finch 收尾时做。

用法：
  mem.py search  <关键词...>          加权检索（MEMORY.md 索引优先，其次 notes/、daily log）
  mem.py read    <目标>               读记忆。目标：MEMORY | AGENTS | <note名> | <日期 YYYY-MM-DD>
  mem.py notes                        列出 memory/notes/ 明细笔记
  mem.py append  --tool <名> [选项]   追加一条 daily log（模板固定，见 --help）
  mem.py inject  <主题关键词...>       生成可直接拼进 prompt 的"记忆注入块"
  mem.py protocol                     打印共享记忆使用协议

红线（写入时强制检查）：密钥/Token/密码/PII 一律拒写；需要时用 --force 会直接失败，不要绕。
"""

import argparse
import datetime
import fcntl
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

FINCHNEST = os.path.expanduser(os.environ.get("MEMORY_HOME", "~/finchnest"))
MEMORY_DIR = os.path.join(FINCHNEST, "memory")
NOTES_DIR = os.path.join(MEMORY_DIR, "notes")
MEMORY_MD = os.path.join(FINCHNEST, "MEMORY.md")
AGENTS_MD = os.path.join(FINCHNEST, "AGENTS.md")
LOCK_PATH = os.path.join(MEMORY_DIR, ".mem.lock")

# ---- 密钥/PII 拦截（红线：secrets never enter memory）----
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|password|passwd|credential)\s*[=:：]\s*\S+",
    r"\bsk-[A-Za-z0-9_-]{16,}\b",
    r"\bghp_[A-Za-z0-9]{20,}\b",
    r"\bBearer\s+[A-Za-z0-9._-]{16,}\b",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
]


def die(msg, code=2):
    print(f"[mem] 错误：{msg}", file=sys.stderr)
    sys.exit(code)


def _secret_hit(text):
    for pat in SECRET_PATTERNS:
        m = re.search(pat, text)
        if m:
            return m
    return None


def check_secrets(text):
    m = _secret_hit(text)
    if m:
        die(f"内容疑似含密钥/凭证（匹配 {m.group(0)[:20]}…），已拒写。红线：secrets never enter memory。")


def daily_log_path(date_str=None):
    d = date_str or datetime.date.today().isoformat()
    return os.path.join(MEMORY_DIR, f"{d}.md")


def iter_memory_files():
    """按加权优先级产出 (文件路径, 层级标签)。"""
    yield MEMORY_MD, "L1"
    if os.path.isdir(NOTES_DIR):
        for name in sorted(os.listdir(NOTES_DIR)):
            if name.endswith(".md"):
                yield os.path.join(NOTES_DIR, name), "L1-note"
    if os.path.isdir(MEMORY_DIR):
        for name in sorted(os.listdir(MEMORY_DIR), reverse=True):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", name):
                yield os.path.join(MEMORY_DIR, name), "L2-log"
        for name in sorted(os.listdir(MEMORY_DIR)):
            if name.startswith("spaces") and name.endswith(".md"):
                yield os.path.join(MEMORY_DIR, name), "L2-space"
        # 月度归档索引（摘要层，仍可检索；全文在 archive/ 内不进语料）
        arch = os.path.join(MEMORY_DIR, "archive")
        if os.path.isdir(arch):
            for name in sorted(os.listdir(arch)):
                if name.endswith("-index.md"):
                    yield os.path.join(arch, name), "L2-log"


def search(query, max_hits=8):
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    if not tokens:
        die("检索需要关键词")
    hits = []
    for path, layer in iter_memory_files():
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            score = sum(1 for t in tokens if t.lower() in line.lower())
            if score:
                # 层级加权：L1 索引 > 明细笔记 > daily log
                weight = score + {"L1": 3, "L1-note": 2, "L2-log": 1, "L2-space": 1}.get(layer, 0)
                hits.append((weight, path, i + 1, line.rstrip()))
    hits.sort(key=lambda h: -h[0])
    if not hits:
        print(f"[mem] 未找到与「{query}」相关的记忆。")
        return
    for weight, path, lineno, line in hits[:max_hits]:
        rel = os.path.relpath(path, FINCHNEST)
        snippet = line if len(line) <= 200 else line[:200] + "…"
        print(f"[{rel}:{lineno}] {snippet}")
    if len(hits) > max_hits:
        print(f"[mem] 另有 {len(hits) - max_hits} 条命中未显示，可用更精确关键词缩小范围。")


# ==== 混合检索（BM25 + Cloudflare bge-m3 向量 + 关键词，RRF 融合）====
EMBED_CFG = os.path.expanduser("~/.config/mem-embed.json")
INDEX_DIR = os.path.join(MEMORY_DIR, ".search-index")


def _embed_cfg():
    try:
        with open(EMBED_CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _embed_texts(texts):
    """批量向量化（Cloudflare Workers AI）。返回与 texts 对齐的向量列表；失败返回 None。"""
    cfg = _embed_cfg()
    if not cfg or not texts:
        return None
    out = []
    url = f"{cfg['api_base']}/accounts/{cfg['account_id']}/ai/run/{cfg['model']}"
    for i in range(0, len(texts), 40):
        batch = texts[i:i + 40]
        body = json.dumps({"text": batch}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {cfg['api_token']}", "Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.load(r)
                out.extend(e for e in data["result"]["data"])
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[mem] 向量服务失败，降级词面检索：{type(e).__name__}", file=sys.stderr)
                    return None
                time.sleep(1.5 * (attempt + 1))
    return out


def _corpus_blocks():
    """把记忆文件切成段块（段落/条目），返回 [(key, file, line, text)]。"""
    blocks = []
    for path, _layer in iter_memory_files():
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        rel = os.path.relpath(path, FINCHNEST)
        buf, start = [], 0
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if not s or s.startswith("## ") or s.startswith("---"):
                if buf:
                    text = " ".join(buf)
                    if not _secret_hit(text):
                        blocks.append((f"{rel}:{start}", rel, start, text))
                    buf = []
                start = i
                continue
            if not buf:
                start = i
            buf.append(s)
            if sum(len(x) for x in buf) > 500:
                text = " ".join(buf)
                if not _secret_hit(text):
                    blocks.append((f"{rel}:{start}", rel, start, text))
                buf = []
        if buf:
            text = " ".join(buf)
            if not _secret_hit(text):
                blocks.append((f"{rel}:{start}", rel, start, text))
    return blocks


def _index_state():
    try:
        with open(os.path.join(INDEX_DIR, "state.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"files": {}}


def _index_update():
    """增量建/更新向量索引（文件 mtime 签名驱动）。返回 (blocks, vecs) 或 (blocks, None)。"""
    os.makedirs(INDEX_DIR, exist_ok=True)
    state = _index_state()
    changed = []
    for path, _layer in iter_memory_files():
        try:
            st = os.stat(path)
        except OSError:
            continue
        sig = f"{st.st_mtime_ns}:{st.st_size}"
        if state["files"].get(path) != sig:
            changed.append((path, sig))
    entries_path = os.path.join(INDEX_DIR, "entries.jsonl")
    entries = {}
    if os.path.isfile(entries_path):
        with open(entries_path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    entries[e["key"]] = e
                except Exception:
                    continue
    if changed:
        blocks = _corpus_blocks()
        need = [b for b in blocks if any(b[1] == os.path.relpath(p, FINCHNEST) for p, _ in changed)]
        # 重建全部条目中属于变更文件的部分
        for key in list(entries):
            if any(entries[key]["file"] == os.path.relpath(p, FINCHNEST) for p, _ in changed):
                del entries[key]
        vecs = _embed_texts([b[3] for b in need]) if need else []
        if vecs is None and need:
            vecs = [None] * len(need)
        for b, v in zip(need, vecs):
            entries[b[0]] = {"key": b[0], "file": b[1], "line": b[2], "text": b[3], "vec": v}
        with open(entries_path, "w", encoding="utf-8") as f:
            for e in entries.values():
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        for p, sig in changed:
            state["files"][p] = sig
        with open(os.path.join(INDEX_DIR, "state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        print(f"[mem] 索引更新：{len(changed)} 个文件 / {len(need)} 段", file=sys.stderr)
    return list(entries.values())


def _tokenize(text):
    """中文友好分词：英文词 + 中文字符二元组。"""
    toks = re.findall(r"[a-z0-9_]+", text.lower())
    cn = re.findall(r"[\u4e00-\u9fff]", text)
    toks += ["".join(p) for p in zip(cn, cn[1:])] if len(cn) > 1 else cn
    return toks


def _rrf(rank_lists, k=60):
    scores = {}
    for ranks in rank_lists:
        for r, key in enumerate(ranks, 1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + r)
    return sorted(scores, key=scores.get, reverse=True)


def search_hybrid(query, max_hits=8):
    """融合检索：关键词现算法 + BM25 + 向量余弦（RRF）。索引/向量不可用时自动降级。"""
    try:
        entries = _index_update()
    except Exception as e:
        print(f"[mem] 索引不可用（{type(e).__name__}），降级词面检索", file=sys.stderr)
        return search(query, max_hits)
    if not entries:
        return search(query, max_hits)
    # 1) 关键词现算法排名
    kw_hits = []
    buf = io.StringIO()
    stdout, sys.stdout = sys.stdout, buf
    try:
        search(query, max_hits=len(entries))
    finally:
        sys.stdout = stdout
    for line in buf.getvalue().splitlines():
        m = re.match(r"\[([^:]+):(\d+)\]", line)
        if m:
            kw_hits.append(f"{m.group(1)}:{m.group(2)}")
    # 2) BM25
    toks = _tokenize(query)
    df = {}
    for e in entries:
        ts = set(_tokenize(e["text"]))
        for t in toks:
            if t in ts:
                df[t] = df.get(t, 0) + 1
    n = len(entries)
    bm25 = []
    for e in entries:
        ts = _tokenize(e["text"])
        score = 0.0
        for t in toks:
            f = ts.count(t)
            if f:
                d = df.get(t, 1)
                score += (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * len(ts) / 40)) * (2.2 and (n - d + 0.5) / (d + 0.5))
        if score:
            bm25.append((score, e["key"]))
    bm25_keys = [k for _, k in sorted(bm25, reverse=True)]
    # 3) 向量
    vec_keys = []
    qv = _embed_texts([query])
    if qv and qv[0]:
        q = qv[0]
        scored = []
        for e in entries:
            v = e.get("vec")
            if not v:
                continue
            dot = sum(a * b for a, b in zip(q, v))
            na = sum(a * a for a in q) ** 0.5
            nb = sum(b * b for b in v) ** 0.5
            if na and nb:
                scored.append((dot / (na * nb), e["key"]))
        vec_keys = [k for _, k in sorted(scored, reverse=True)]
    order = _rrf([kw_hits, bm25_keys, vec_keys])
    emap = {e["key"]: e for e in entries}
    shown = 0
    for key in order:
        e = emap.get(key)
        if not e:
            continue
        snippet = e["text"] if len(e["text"]) <= 200 else e["text"][:200] + "…"
        print(f"[{e['file']}:{e['line']}] {snippet}")
        shown += 1
        if shown >= max_hits:
            break
    if not shown:
        print(f"[mem] 未找到与「{query}」相关的记忆。")


def read(target):
    if target.upper() == "MEMORY":
        path = MEMORY_MD
    elif target.upper() == "AGENTS":
        path = AGENTS_MD
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", target):
        path = daily_log_path(target)
        if not os.path.isfile(path):
            # 月度归档回退
            arch = os.path.join(MEMORY_DIR, "archive", target[:7], f"{target}.md")
            if os.path.isfile(arch):
                path = arch
    else:
        slug = target.removesuffix(".md")
        path = os.path.join(NOTES_DIR, slug + ".md")
    if not os.path.isfile(path):
        die(f"文件不存在：{os.path.relpath(path, FINCHNEST)}（read 支持 MEMORY/AGENTS/日期/笔记名）")
    with open(path, encoding="utf-8", errors="replace") as f:
        sys.stdout.write(f.read())


def list_notes():
    if not os.path.isdir(NOTES_DIR):
        print("[mem] notes 目录不存在")
        return
    for name in sorted(os.listdir(NOTES_DIR)):
        if name.endswith(".md"):
            print(name.removesuffix(".md"))


def cmd_append(args):
    if not args.tool:
        die("append 需要 --tool 标明来源工具（如 --tool qoder）")
    text = args.text
    if text is None:
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        die("内容为空")
    if args.task and not re.search(r"^- 完成：", text, re.M):
        # 用固定模板（AGENTS.md 第五节）补全
        fields = ["完成", "停在哪", "下一步", "复用结论", "踩坑"]
        parts = {}
        for line in text.splitlines():
            m = re.match(r"^-\s*(完成|停在哪|下一步|复用结论|踩坑)\s*[:：]\s*(.*)$", line.strip())
            if m:
                parts[m.group(1)] = m.group(2)
        body = "\n".join(f"- {k}：{parts.get(k, '无')}" for k in fields)
        text = body
    check_secrets(text)
    now = datetime.datetime.now()
    header = f"\n## {now:%H:%M} · {args.task or '未命名任务'} [tool:{args.tool}]"
    entry = header + "\n" + text + "\n"
    path = daily_log_path()
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(LOCK_PATH, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)  # 跨工具并发写串行化
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        fcntl.flock(lk, fcntl.LOCK_UN)
    print(f"[mem] 已追加到 {os.path.relpath(path, FINCHNEST)}")


def cmd_inject(args):
    """生成记忆注入块：派发/开工前拼进 prompt，替代自动注入缺失。"""
    query = " ".join(args.query)
    import io
    buf = io.StringIO()
    stdout, sys.stdout = sys.stdout, buf
    try:
        search(query, max_hits=6)
    finally:
        sys.stdout = stdout
    hits = buf.getvalue().strip()
    if hits.startswith("[mem] 未找到"):
        print(f"<memory topic=\"{query}\">\n(无相关既往记忆，按常规执行，注意遵守 AGENTS.md 红线)\n</memory>")
        return
    print(f"<memory topic=\"{query}\">")
    print("以下为既往记忆摘录，有记录就照做，禁止从零试探；与实际不符时以实际为准：")
    print(hits)
    print("另：任务收尾必须按 AGENTS.md 第五节模板追加 daily log。")
    print("</memory>")


PROTOCOL = """共享记忆使用协议（所有接入工具必须遵守）
================================================
记忆位置：~/finchnest/MEMORY.md（L1 索引）、~/finchnest/memory/notes/（L1 明细）、
          ~/finchnest/memory/<日期>.md（L2 工作日志）、~/finchnest/AGENTS.md（L0 规则）。
统一入口：python3 ~/finchnest/tools/mem.py <search|read|notes|append|inject|protocol>

读：开工先 `mem.py search <项目名/关键词>`；命中后 `mem.py read <目标>` 看明细。查到照做，禁止从零试探。
写（本工具权限：仅 daily log）：收尾用 `mem.py append --tool <你的名字> --task <任务名>`，
  内容按固定模板五字段（完成/停在哪/下一步/复用结论/踩坑），复用结论标 [候选]。
  不许直接编辑 MEMORY.md / notes/ / AGENTS.md——那些由 Finch 统一整理。
红线：密钥/Token/密码/PII 一律不写入记忆（CLI 会拦截）；命名照原文不改写；不编造文献与数据；
  原始数据只读，分析产物另存。
"""


def cmd_dispatch(args):
    """生成完整派发 prompt：记忆注入块 + 任务 + 收尾登记指令（派发即注入、回收即登记）。"""
    import io
    buf = io.StringIO()
    stdout, sys.stdout = sys.stdout, buf
    try:
        search(" ".join(args.query), max_hits=6)
    finally:
        sys.stdout = stdout
    hits = buf.getvalue().strip()
    print(f'<memory topic="{" ".join(args.query)}">')
    if hits.startswith("[mem] 未找到"):
        print("(无相关既往记忆，按常规执行，注意遵守 AGENTS.md 红线)")
    else:
        print("以下为既往记忆摘录，有记录就照做，禁止从零试探；与实际不符时以实际为准：")
        print(hits)
    print("</memory>")
    print("<task>")
    print(args.task)
    print("</task>")
    print("<handoff>")
    print("完成后请在最终回复末尾按五字段给出收尾：完成/停在哪/下一步/复用结论[候选]/踩坑。")
    print("该收尾由 Finch 统一登记进共享记忆，你不写也不会丢；")
    print("若已接入共享记忆协议，也可自行 python3 ~/finchnest/tools/mem.py append --tool <你的名字> --task <任务名> --text '<五字段>'。")
    print("</handoff>")


# ==== harvest / sessions：会话收割与原文下钻 ====
import glob as _glob
import sqlite3 as _sqlite3

STATE_PATH = os.path.join(MEMORY_DIR, ".harvest-state.json")
MAX_HARVEST_PER_RUN = 12

# (工具名, glob, 适配器)  —— transcript 路径图谱（2026-11-05 勘察）
SOURCES = [
    ("PI-Desktop", "~/.pi-desktop/sessions/*.jsonl", "jsonl_msg"),
    ("Command Code", "~/.commandcode/projects/*/*.jsonl", "jsonl_msg"),
    ("Qoder", "~/.qoder/projects/*/memory/*.md", "md_note"),
    ("Trae", "~/.trae-cn/memory/projects/*/*/session_memory_*.jsonl", "trae_mem"),
    ("OpenCode", "~/finchnest/runs/opencode/*.log", "run_log"),
]
AGY_DB = "~/.gemini/antigravity/conversation_summaries.db"
EXCLUDE_NAMES = {"user-shared-memory.md", "MEMORY.md"}  # 协议/索引文件不收割


def _clip(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def _jsonl_msg(path):
    """PI / Command Code / 通用消息 jsonl：首问 + 末答。"""
    first_user = last_asst = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            role = (msg.get("role") or obj.get("role") or "").lower()
            if role not in ("user", "assistant"):
                continue
            text = msg.get("text") or msg.get("content")
            if isinstance(text, list):
                text = " ".join(b.get("text", "") for b in text if isinstance(b, dict))
            if not isinstance(text, str) or not text.strip():
                blocks = msg.get("blocks")
                if isinstance(blocks, list):
                    text = " ".join(b.get("text", "") for b in blocks if isinstance(b, dict))
            if not isinstance(text, str) or not text.strip():
                continue
            if role == "user" and first_user is None:
                first_user = text
            elif role == "assistant":
                last_asst = text
    if not first_user and not last_asst:
        return None
    return {"title": _clip(first_user or last_asst, 24),
            "gist": f"问：{_clip(first_user, 90)}｜答：{_clip(last_asst, 110)}"}


def _md_note(path):
    """Qoder 项目记忆 md（本身已是蒸馏摘要）。"""
    name = os.path.basename(path)
    if name in EXCLUDE_NAMES:
        return None
    lines_out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        in_fm = False
        for ln in f:
            s = ln.strip()
            if s.startswith("---") and not lines_out:
                in_fm = not in_fm
                continue
            if in_fm or not s or s.startswith("#"):
                continue
            lines_out.append(s)
            if len(lines_out) >= 2:
                break
    if not lines_out:
        return None
    return {"title": _clip(os.path.splitext(name)[0], 24), "gist": _clip(" / ".join(lines_out), 200)}


def _trae_mem(path):
    """Trae session_memory jsonl：intent/actions/outcome/learned 结构。"""
    intents, outcomes = [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                if isinstance(obj.get("intent"), str):
                    intents.append(obj["intent"])
                if isinstance(obj.get("outcome"), str):
                    outcomes.append(obj["outcome"])
    if not intents and not outcomes:
        return None
    return {"title": _clip(intents[0] if intents else outcomes[0], 24),
            "gist": f"意图：{_clip(intents[0] if intents else '-', 80)}｜结果：{_clip(outcomes[-1] if outcomes else '-', 100)}"}


def _run_log(path):
    """OpenCode 无头执行日志：文件名即任务，尾部即结论。"""
    name = os.path.basename(path)
    tail = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for ln in f:
            s = ln.strip()
            if s and not s.startswith("$") and not s.startswith("→"):
                tail = (tail + [s])[-2:]
    return {"title": _clip(name.removesuffix(".log"), 24),
            "gist": _clip(" / ".join(tail) if tail else "(空日志)", 180)}


def _agy_summaries(state):
    """Antigravity conversation_summaries.db（WAL，先拷贝再查）。"""
    src = os.path.expanduser(AGY_DB)
    if not os.path.isfile(src):
        return []
    tmp = "/tmp/agy_sum_harvest.db"
    out = []
    try:
        import shutil
        shutil.copyfile(src, tmp)
        con = _sqlite3.connect(tmp)
        cur = con.execute("select * from conversation_summaries")
        cols = [d[0] for d in cur.description]
        id_i = cols.index("id") if "id" in cols else 0
        for row in cur.fetchall():
            rid = str(row[id_i])
            if state.get("agy_ids", {}).get(rid):
                continue
            texts = []
            for c in row:
                if not isinstance(c, str):
                    continue
                s = c.strip()
                if len(s) < 8 or len(s) > 4000 or s == rid:
                    continue
                if re.match(r"^[\d\-: T.+Z]+$", s) or re.match(r"^[0-9a-f\-]{36}$", s):
                    continue  # 时间戳 / uuid
                if s.startswith("file:") or s.startswith("[") or re.match(r"^[A-Z0-9_]+$", s):
                    continue  # 文件列表 / 枚举
                texts.append(s)
            if not texts:
                continue
            gist_src = max(texts, key=len)
            out.append({"id": rid, "title": _clip(texts[0], 24), "gist": _clip(gist_src, 180)})
        con.close()
    except Exception:
        return out
    return out


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"files": {}, "agy_ids": {}}


def _save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def _append_locked(path, entry):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(LOCK_PATH, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        fcntl.flock(lk, fcntl.LOCK_UN)


def cmd_harvest(args):
    """增量收割六家会话存档 → 五字段摘要落 daily log（[harvest] 标记）。"""
    import shutil
    state = _load_state()
    emitted = 0
    for tool, pattern, adapter in SOURCES:
        if emitted >= args.limit:
            break
        for path in sorted(_glob.glob(os.path.expanduser(pattern))):
            if emitted >= args.limit:
                break
            st = os.stat(path)
            sig = f"{st.st_mtime_ns}:{st.st_size}"
            if state["files"].get(path) == sig:
                continue
            state["files"][path] = sig  # 先标记：坏文件不反复重试
            try:
                item = {"jsonl_msg": _jsonl_msg, "md_note": _md_note,
                        "trae_mem": _trae_mem, "run_log": _run_log}[adapter](path)
            except Exception as e:
                item = {"title": "解析失败", "gist": f"{type(e).__name__}: {e}"}
            if not item:
                continue
            text = (f"- 完成：[收割] {item['gist']}\n"
                    f"- 停在哪：无（自动收割；过程原文：{os.path.relpath(path, os.path.expanduser('~'))}）\n"
                    f"- 下一步：需要细节时执行 mem.py sessions <关键词> 下钻\n"
                    f"- 复用结论：[候选] {_clip(item['gist'], 80)}\n"
                    f"- 踩坑：无")
            check_secrets(text)
            now = datetime.datetime.now()
            entry = f"\n## {now:%H:%M} · 收割·{tool}·{item['title']} [tool:{tool}|harvest]\n{text}\n"
            _append_locked(daily_log_path(), entry)
            print(f"[harvest] {tool} ← {os.path.basename(path)}")
            emitted += 1
    # Antigravity 摘要库（按 id 去重）
    if emitted < args.limit:
        for item in _agy_summaries(state):
            if emitted >= args.limit:
                break
            state.setdefault("agy_ids", {})[item["id"]] = True
            text = (f"- 完成：[收割] {item['gist']}\n"
                    f"- 停在哪：无（自动收割；原文 ~/.gemini/antigravity/conversations/{item['id']}.db）\n"
                    f"- 下一步：需要细节时打开对应会话库\n"
                    f"- 复用结论：[候选] {_clip(item['gist'], 80)}\n"
                    f"- 踩坑：无")
            check_secrets(text)
            now = datetime.datetime.now()
            entry = f"\n## {now:%H:%M} · 收割·Antigravity·{item['title']} [tool:Antigravity|harvest]\n{text}\n"
            _append_locked(daily_log_path(), entry)
            print(f"[harvest] Antigravity ← {item['id'][:8]}")
            emitted += 1
    _save_state(state)
    print(f"[harvest] 完成：本轮登记 {emitted} 条（上限 {args.limit}）。")
    # 每晚顺手做月度归档检查（幂等）
    try:
        cmd_archive(argparse.Namespace(days=45))
    except Exception:
        pass


def cmd_sessions(args):
    """下钻六家 transcript 原文：关键词全文检索（共享层没命中时用）。"""
    kw = " ".join(args.query).lower()
    hits = 0
    for tool, pattern, _adapter in SOURCES:
        for path in _glob.glob(os.path.expanduser(pattern)):
            if hits >= args.limit:
                return
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for ln, line in enumerate(f, 1):
                        if kw in line.lower():
                            rel = os.path.relpath(path, os.path.expanduser("~"))
                            print(f"[{tool} {rel}:{ln}] {_clip(line.strip(), 150)}")
                            hits += 1
                            if hits >= args.limit:
                                return
            except OSError:
                continue
    if not hits:
        print(f"[sessions] 六家 transcript 原文中未找到「{args.query}」。")


def cmd_recall(args):
    """ContextBerg 活动下钻：OCR 文本 / 窗口标题 / 浏览器历史按关键词+时间窗检索。
    隐私规则：KeystrokeLogs / ClipboardLogs 永不查询；命中含密钥特征的行只报位置不报内容。"""
    src = os.path.expanduser("~/Library/Application Support/dev.trackq.contextberg/contextberg.db")
    if not os.path.isfile(src):
        die("ContextBerg 数据库不存在（应用未安装？）")
    import shutil
    shutil.copyfile(src, "/tmp/cb_recall.db")
    con = _sqlite3.connect("/tmp/cb_recall.db")
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=args.hours)).strftime("%Y-%m-%d %H:%M:%S")
    kws = [f"%{' '.join(args.query)}%"]
    hits = []
    q1 = ("select s.capturedAt, a.applicationName, t.text from ScreenshotTexts t "
          "join Screenshots s on s.id=t.screenshotId "
          "left join ApplicationUsages a on a.id=s.usageId "
          "where s.capturedAt > ? and t.text like ? order by s.capturedAt desc limit 20")
    for at, app, text in con.execute(q1, (cutoff, kws[0])):
        hits.append((at, app or "?", text))
    q2 = ("select startAt, applicationName, windowTitle from ApplicationUsages "
          "where startAt > ? and windowTitle like ? order by startAt desc limit 10")
    for at, app, title in con.execute(q2, (cutoff, kws[0])):
        hits.append((at, app or "?", f"[窗口] {title}"))
    q3 = ("select visitedAt, browser, title, domain from BrowserVisits "
          "where visitedAt > ? and (title like ? or domain like ?) order by visitedAt desc limit 10")
    for at, br, title, dom in con.execute(q3, (cutoff, kws[0], kws[0])):
        hits.append((at, br or "?", f"[网页] {title} ({dom})"))
    con.close()
    if not hits:
        print(f"[recall] 近 {args.hours}h 内未找到「{' '.join(args.query)}」。可加大 --hours 或换关键词。")
        return
    for at, app, text in sorted(hits, reverse=True)[:args.limit]:
        snippet = " ".join(text.split())
        if _secret_hit(snippet):
            snippet = f"[已过滤：疑似含密钥，原始内容见 ContextBerg 库 {at}]"
        elif len(snippet) > 140:
            snippet = snippet[:140] + "…"
        print(f"[{at} | {app}] {snippet}")


def cmd_archive(args):
    """月度归档：把超过 N 天的 daily log 移入 memory/archive/<YYYY-MM>/，
    并生成当月摘要索引 <YYYY-MM>-index.md（保 search 可检索、read 按日期回退）。"""
    cutoff = (datetime.date.today() - datetime.timedelta(days=args.days)).isoformat()
    moved = {}
    if not os.path.isdir(MEMORY_DIR):
        return moved
    for name in sorted(os.listdir(MEMORY_DIR)):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.md", name)
        if not m or m.group(1) >= cutoff:
            continue
        date = m.group(1)
        src = os.path.join(MEMORY_DIR, name)
        month_dir = os.path.join(MEMORY_DIR, "archive", date[:7])
        os.makedirs(month_dir, exist_ok=True)
        dst = os.path.join(month_dir, name)
        os.replace(src, dst)
        moved.setdefault(date[:7], []).append(dst)
    for month, files in moved.items():
        idx_path = os.path.join(MEMORY_DIR, "archive", f"{month}-index.md")
        existing = ""
        if os.path.isfile(idx_path):
            with open(idx_path, encoding="utf-8") as f:
                existing = f.read()
        parts = [existing] if existing.strip() else [f"# {month} 月度归档索引\n"]
        for fpath in sorted(files):
            date = os.path.basename(fpath).removesuffix(".md")
            entries = []
            with open(fpath, encoding="utf-8", errors="replace") as f:
                for ln in f:
                    if ln.startswith("## "):
                        entries.append(ln.strip())
            parts.append(f"\n## {date}（{len(entries)} 条）")
            for e in entries:
                parts.append(f"- {e[3:]}")
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts) + "\n")
        print(f"[archive] {month}：归档 {len(files)} 个日志，索引 {os.path.relpath(idx_path, FINCHNEST)}")
    if not moved:
        print(f"[archive] 无超过 {args.days} 天的日志，无需归档。")
    return moved


def main():
    p = argparse.ArgumentParser(prog="mem", description="跨工具共享记忆 CLI")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("search"); sp.add_argument("query", nargs="+")
    rp = sub.add_parser("read"); rp.add_argument("target")
    sub.add_parser("notes")
    ap = sub.add_parser("append")
    ap.add_argument("--tool", required=True)
    ap.add_argument("--task", default=None)
    ap.add_argument("--text", default=None, help="缺省从 stdin 读")
    ip = sub.add_parser("inject"); ip.add_argument("query", nargs="+")
    dp = sub.add_parser("dispatch"); dp.add_argument("query", nargs="+")
    dp.add_argument("--task", required=True, help="任务描述")
    hp = sub.add_parser("harvest"); hp.add_argument("--limit", type=int, default=MAX_HARVEST_PER_RUN)
    ss = sub.add_parser("sessions"); ss.add_argument("query", nargs="+")
    ss.add_argument("--limit", type=int, default=20)
    rc = sub.add_parser("recall"); rc.add_argument("query", nargs="+")
    rc.add_argument("--hours", type=int, default=24)
    rc.add_argument("--limit", type=int, default=15)
    ac = sub.add_parser("archive"); ac.add_argument("--days", type=int, default=45)
    sub.add_parser("protocol")

    args = p.parse_args()
    if args.cmd == "search":
        search_hybrid(" ".join(args.query))
    elif args.cmd == "read":
        read(args.target)
    elif args.cmd == "notes":
        list_notes()
    elif args.cmd == "append":
        cmd_append(args)
    elif args.cmd == "inject":
        cmd_inject(args)
    elif args.cmd == "dispatch":
        cmd_dispatch(args)
    elif args.cmd == "harvest":
        cmd_harvest(args)
    elif args.cmd == "sessions":
        cmd_sessions(args)
    elif args.cmd == "recall":
        cmd_recall(args)
    elif args.cmd == "archive":
        cmd_archive(args)
    elif args.cmd == "protocol":
        print(PROTOCOL)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
