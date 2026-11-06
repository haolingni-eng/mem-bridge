#!/usr/bin/env python3
"""End-to-end self check for mem.py against a throwaway store.

Covers: protocol output, basic retrieval, the five-field write path, secret rejection,
and concurrent appends. Run with `python3 scripts/selfcheck.py`; exits non-zero on the
first failure.
"""

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(ROOT, "mem.py")


def run(store, *args, stdin=None):
    env = dict(os.environ, MEMORY_HOME=store)
    return subprocess.run(
        [sys.executable, MEM, *args],
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
    )


def fail(msg):
    print(f"FAIL  {msg}")
    sys.exit(1)


def main():
    with tempfile.TemporaryDirectory() as store:
        os.makedirs(os.path.join(store, "memory", "notes"))
        with open(os.path.join(store, "MEMORY.md"), "w", encoding="utf-8") as fh:
            fh.write("## Notes\n- acceptance rule: a click that returns ok is not a submit\n")

        # 1. protocol
        r = run(store, "protocol")
        if r.returncode != 0 or "共享记忆" not in (r.stdout + r.stderr):
            fail(f"protocol exited {r.returncode}: {r.stderr[:200]}")

        # 2. retrieval
        r = run(store, "search", "acceptance")
        if r.returncode != 0 or "acceptance rule" not in r.stdout:
            fail(f"search missed the indexed line: {r.stdout[:200]}")
        print("ok    protocol + search")

        # 3. write path, five fields filled
        r = run(store, "append", "--tool", "selfcheck", "--task", "smoke", "--text", "完成：写一条")
        if r.returncode != 0:
            fail(f"append exited {r.returncode}: {r.stderr[:200]}")
        day = time.strftime("%Y-%m-%d")
        log = os.path.join(store, "memory", f"{day}.md")
        body = open(log, encoding="utf-8").read()
        for field in ("完成", "停在哪", "下一步", "复用结论", "踩坑"):
            if field not in body:
                fail(f"append dropped field {field}")
        print("ok    append writes the five fields")

        # 4. secret rejection
        before = len(body.splitlines())
        secret = "- 完成：api_key = sk-abcdefghijklmnopqrstuvwx"
        r = run(store, "append", "--tool", "selfcheck", "--task", "leak", "--text", secret)
        if r.returncode == 0:
            fail("append accepted secret-shaped text")
        after_body = open(log, encoding="utf-8").read()
        if len(after_body.splitlines()) != before or "sk-abcdefghijklmnopqrst" in after_body:
            fail("rejected write still modified the log")
        print("ok    secrets rejected before disk")

        # 5. concurrent appends
        before = len(open(log, encoding="utf-8").read().splitlines())
        env = dict(os.environ, MEMORY_HOME=store)
        procs = [
            subprocess.Popen(
                [sys.executable, MEM, "append", "--tool", f"p{i}", "--task", "race", "--text", f"- 完成：并发 {i}"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            for i in range(5)
        ]
        codes = [p.wait() for p in procs]
        if any(c != 0 for c in codes):
            fail(f"concurrent append failed: {codes}")
        lines = open(log, encoding="utf-8").read().splitlines()
        added = [ln for ln in lines if "并发" in ln]
        if len(added) != 5:
            fail(f"expected 5 concurrent entries, found {len(added)}")
        print("ok    5 concurrent appends all landed")

    print("\nall checks passed")


if __name__ == "__main__":
    main()
