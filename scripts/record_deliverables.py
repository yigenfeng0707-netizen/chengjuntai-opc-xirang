# scripts/record_deliverables.py
"""从真实文件生成 docs/DELIVERABLES.md —— 交付物指纹清单（单一事实来源）。"""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DOC = ROOT / "docs" / "DELIVERABLES.md"
SHOTS = ROOT / "demo-video" / "public" / "shots.json"

# 交付物指纹清单 —— 只含三件对外交付物，勿加 README（README 每次改 docs 都会变，会让 --check 长期报不一致）
TARGETS = [
    ("提交版演示视频", "demo-video/out/demo-video-60s.mp4"),
    ("母版演示视频", "demo-video/out/demo-video.mp4"),
    ("预赛答辩 PPT", "docs/成军台_息壤杯预赛答辩.pptx"),
]


def sha256_12(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def probe_video(path: Path) -> str:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-select_streams", "v:0", "-of", "json", str(path),
    ]
    info = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    st = info["streams"][0]
    return "%ss · %s×%s · %s" % (
        round(float(info["format"]["duration"]), 2), st["width"], st["height"], st["codec_name"]
    )


def pptx_slides(path: Path) -> int:
    with zipfile.ZipFile(path) as z:
        return sum(1 for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))


def shot_count() -> str:
    if not SHOTS.exists():
        return "n/a"
    d = json.loads(SHOTS.read_text(encoding="utf-8"))
    return "%d 镜 · %s 帧 @%sfps" % (len(d["shots"]), d["totalFrames"], d["fps"])


def head_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip() or "n/a"


def build() -> str:
    rows = []
    for label, rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            rows.append((label, rel, "缺失", "", ""))
            continue
        size = "%.2f MiB" % (p.stat().st_size / 1048576)
        if rel.endswith(".mp4"):
            spec = probe_video(p) + (
                " · 剪辑自母版" if "60s" in rel else " · " + shot_count()
            )
        elif rel.endswith(".pptx"):
            spec = "%d 页 · pptx" % pptx_slides(p)
        else:
            spec = "主分支 README"
        rows.append((label, rel, size, spec, sha256_12(p)))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 交付物指纹清单", "", "> 由 `python scripts/record_deliverables.py` 生成，勿手工编辑。",
        "> 生成时间：%s · HEAD `%s`" % (now, head_sha()), "",
        "| 交付物 | 路径 | 体积 | 实测规格 | sha256(12) |",
        "|---|---|---|---|---|",
    ]
    lines += ["| %s | `%s` | %s | %s | `%s` |" % r for r in rows]
    lines += [
        "", "## 说明", "",
        "- `demo-video/out/*.mp4` 被 `.gitignore` 排除，**仅存本地 + GitHub Release 归档**（见 `docs/OUTCOME.md`）。",
        "- 提交版 = 59s 合规剪辑；母版 = 完整 13 分镜，含更多讲解，不用于官方提交。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写文件；不一致时退出码 1")
    ap.add_argument("--stdout", action="store_true", help="打印到标准输出")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    content = build()
    if args.stdout:
        print(content)
        return 0
    if args.check:
        current = OUT_DOC.read_text(encoding="utf-8") if OUT_DOC.exists() else ""

        def body(text):
            return [l for l in text.splitlines() if not l.startswith("> 生成时间")]

        ok = body(content) == body(current)
        print("DELIVERABLES.md 与实际文件一致" if ok else "不一致，请重跑 python scripts/record_deliverables.py")
        return 0 if ok else 1
    OUT_DOC.write_text(content, encoding="utf-8", newline="\n")
    print("已写入 %s" % OUT_DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
