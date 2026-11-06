#!/usr/bin/env python3
"""Render the demo run into a silent MP4 (terminal-screencast style).

The output is the real stdout of demo/demo.sh, split into screens and re-rendered at
1920x1080. Nothing is invented: every line comes from an actual run against a temp store.

    python3 demo/render_cast.py                 # writes demo/membridge-demo.mp4
    python3 demo/render_cast.py --out /tmp/x.mp4
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
W, H = 1920, 1080
PAD = 96
BG = (18, 18, 22)
FG = (222, 226, 232)
DIM = (150, 158, 170)
ACCENT = (94, 214, 214)
WARN = (240, 190, 110)
OK = (140, 220, 150)

LATIN = "/System/Library/Fonts/Menlo.ttc"
CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def font_set(size):
    return (ImageFont.truetype(LATIN, size), ImageFont.truetype(CJK, size))


def is_cjk(ch):
    return ord(ch) > 0x2E7F


def draw_runs(draw, x, y, runs, fonts, color=FG):
    """Draw [(text, color)] left to right, advancing per glyph so CJK aligns."""
    latin, cjk = fonts
    for text, col in runs:
        col = col or color
        for ch in text:
            f = cjk if is_cjk(ch) else latin
            draw.text((x, y), ch, font=f, fill=col)
            x += draw.textlength(ch, font=f)
    return x


def wrap(text, fonts, draw, max_px):
    """Wrap by glyph, but prefer a space boundary when one is available."""
    lines, cur, width = [], "", 0
    latin, cjk = fonts
    for ch in text:
        f = cjk if is_cjk(ch) else latin
        adv = draw.textlength(ch, font=f)
        if ch == "\n":
            lines.append(cur)
            cur, width = "", 0
            continue
        if width + adv > max_px and cur:
            cut = cur.rfind(" ")
            if cut > 12 and len(cur) - cut < 30:
                lines.append(cur[:cut])
                cur = cur[cut + 1:] + ch
                width = draw.textlength(cur, font=latin)
            else:
                lines.append(cur)
                cur, width = "", 0
            continue
        cur += ch
        width += adv
    if cur:
        lines.append(cur)
    return lines


def frame(title, body, footer, fonts):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    head, small = fonts
    d.text((PAD, PAD - 22), "MemBridge", font=head, fill=ACCENT)
    d.text((PAD + d.textlength("MemBridge", font=head) + 24, PAD - 16), "shared memory for multi-agent AI coding",
           font=small, fill=DIM)
    d.line([(PAD, PAD + 48), (W - PAD, PAD + 48)], fill=(52, 56, 64), width=2)

    y = PAD + 84
    if title:
        d.text((PAD, y), title, font=head, fill=ACCENT)
        y += 58
    for line, colour in body:
        if y > H - PAD - 40:
            break
        d.text((PAD, y), line, font=small, fill=colour)
        y += 30
    if footer:
        d.text((PAD, H - PAD - 10), footer, font=small, fill=DIM)
    return img


def capture():
    env = dict(os.environ, PAUSE="0", TERM="dumb")
    r = subprocess.run(["bash", os.path.join(HERE, "demo.sh")], env=env, capture_output=True, text=True)
    return ANSI.sub("", r.stdout + r.stderr)


def split_screens(raw):
    """Group output into screens: one per `== n/6 ... ==` banner. Returns [(label, lines)]."""
    screens, cur, label = [], [], ""

    def flush():
        lines = [ln for ln in cur if ln.strip()]
        if lines:
            screens.append((label, lines))

    for line in raw.splitlines():
        text = line.rstrip()
        if re.match(r"^=+\s*\d+/\d+", text.strip()):
            flush()
            label = text.strip().strip("=").strip()
            cur = []
            continue
        cur.append(text)
    flush()
    return screens


def colour_for(line):
    if line.startswith("$ "):
        return (200, 210, 225)
    if re.search(r"错误|refused|拒写", line):
        return WARN
    if line.startswith("ok ") or "all checks passed" in line:
        return OK
    if line.startswith("# "):
        return WARN
    if line.startswith("[mem]"):
        return DIM
    return FG


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "membridge-demo.mp4"))
    ap.add_argument("--seconds-per-screen", type=float, default=6.0)
    args = ap.parse_args()

    raw = capture()
    screens = split_screens(raw)
    if not screens:
        sys.exit("no output captured from demo.sh")

    title_fonts = font_set(46)
    body_fonts = font_set(24)
    small_fonts = font_set(20)

    tmp = tempfile.mkdtemp(prefix="memcast.")
    paths, durations = [], []

    probe = ImageDraw.Draw(Image.new("RGB", (W, H)))
    max_px = W - 2 * PAD

    intro = frame(
        "One memory. Six agents.",
        [("", DIM)],
        "recorded from a real run against a throwaway store",
        (title_fonts[0], small_fonts[1]),
    )
    p = os.path.join(tmp, "000.png")
    intro.save(p)
    paths.append(p)
    durations.append(5.0)

    history = []
    newest = 0
    visible = (H - PAD - 84 - 58 - 60) // 30

    for idx, (label, block) in enumerate(screens, start=1):
        added = []
        for line in block:
            for wrapped in wrap(line, body_fonts, probe, max_px) or [""]:
                added.append((wrapped, colour_for(line)))
        history.extend(added)
        newest = len(added)
        body = history[-visible:]
        p = os.path.join(tmp, f"{idx:03d}.png")
        frame(label or f"step {idx}", body, "", body_fonts).save(p)
        paths.append(p)
        durations.append(args.seconds_per_screen)

    # Real repo content, shown as text cards: how Kiro is wired into the project.
    kiro = [
        (".kiro/steering/tech.md", 16),
        (".kiro/specs/shared-memory-layer/requirements.md", 14),
        (".kiro/hooks/verify-after-edit.kiro.hook", 18),
    ]
    for idx, (rel, nlines) in enumerate(kiro, start=1):
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        head = open(path, encoding="utf-8").read().splitlines()[:nlines]
        body = [("$ cat " + rel, DIM)]
        for line in head:
            for wrapped in wrap(line, body_fonts, probe, max_px) or [""]:
                body.append((wrapped, FG))
        p = os.path.join(tmp, f"kiro{idx}.png")
        frame("Kiro in the repo", body, "committed, not ignored — specs, steering, hooks", body_fonts).save(p)
        paths.append(p)
        durations.append(6.0)

    outro = frame(
        "github.com/haolingni-eng/mem-bridge",
        [("standard library only  ·  MIT  ·  .kiro specs, steering and hooks checked in", DIM)],
        "demo: ./demo/demo.sh   contract: python3 scripts/selfcheck.py",
        (title_fonts[0], small_fonts[1]),
    )
    p = os.path.join(tmp, "999.png")
    outro.save(p)
    paths.append(p)
    durations.append(5.0)

    listing = os.path.join(tmp, "list.txt")
    with open(listing, "w") as fh:
        for path, dur in zip(paths, durations):
            fh.write(f"file '{path}'\nduration {dur}\n")
        fh.write(f"file '{paths[-1]}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", listing,
        "-vf", "format=yuv420p,fps=12", "-c:v", "libx264", "-crf", "20",
        args.out,
    ], check=True)

    shutil.rmtree(tmp, ignore_errors=True)
    size = os.path.getsize(args.out) / 1e6
    total = sum(durations)
    print(f"{args.out}  {total:.0f}s  {size:.1f} MB  ({len(screens)} steps)")


if __name__ == "__main__":
    main()
