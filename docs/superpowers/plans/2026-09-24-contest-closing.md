# 成军台预赛收尾（归档 · 事实校正 · 台账）实施方案

**Goal:** 把 2026-08 预赛交付物从「只存在于本地的一次性产物」变成可校验、可追溯、不丢失的归档，并把散落在 docs/ 里的过期事实统一校正为实测值，建立赛事结果与云资源到期台账。

**Architecture:** 一条「实测 → 生成 → 归档 → 台账」链路。先用脚本从真实文件（ffprobe / pptx zip / sha256）产出单一事实来源 `docs/DELIVERABLES.md`，再据此手工校正 docs 里的过期表述，最后把两个 mp4 推上 GitHub Release 作为异地归档，并把需要人工确认的赛事结论与云资源到期日记入 `docs/OUTCOME.md`。

**Tech Stack:** Python 3.13 标准库（zipfile / hashlib / subprocess / pathlib）+ ffprobe + GitHub CLI（`gh` 2.89，已登录 `yigenfeng0707-netizen`，scope 含 `repo`）+ Git Bash on Windows。

**Spec:** 本方案源自 2026-09-24 的工作区进度核查（对话内实测结论），无独立 spec 文件。

## Global Constraints

- Git 仓库根是 `D:/APPs/天翼息壤杯/chengjuntai`（工作区根 `D:/APPs/天翼息壤杯` 不在版本控制内），远端名 `chengjuntai`，分支 `main`，当前与远端 0/0 同步、工作树干净。所有路径相对该仓库根。
- **绝不提交**：`content_factory/config.yaml`（含 api_token / web_password，已被 .gitignore 第 2 行忽略）、`content_factory/users.json`、任何 `*.mp4`（`.gitignore:36 demo-output/`、`:38 demo-video/out/*.mp4`）、`docs/ADMIN_ACCESS.local.md`。
- 仓库在 GitHub 上是 **PUBLIC**（diskUsage 24.9MB）。任何 `git push` / `gh release create` 都是对外可见动作，**执行前必须逐次获得用户确认**；本方案不使用 `--force`、不重写历史。
- 不新建 `demo-output/` 目录：该路径从未存在，是文档臆造。真实成片在 `demo-video/out/`。
- 文档校正一律写「实测值 + 实测日期（2026-09-24）」，不把自评快照（如 8/6 的五维 89 分）当作可改数据偷偷更新。
- `docs/archive/` 下的文件视为历史快照，**只读不改**。
- 提交信息沿用仓库既有风格：`fix:` / `docs:` / `chore:` + 中文描述。

## 实测基线（本方案所有数字的唯一来源，2026-09-24 本机实测）

| 事实 | 实测值 | 出处 |
|---|---|---|
| 提交版视频 | `demo-video/out/demo-video-60s.mp4` · 58.97s · 6,019,286 B（5.74 MiB） · 1920×1080 · h264 | ffprobe |
| 母版视频 | `demo-video/out/demo-video.mp4` · 71.02s · 8,915,419 B（8.50 MiB） · 1920×1080 | ffprobe |
| 分镜数 | 13 镜 · 2129 帧 @30fps（= 71.0s，即母版时长） | `demo-video/public/shots.json` |
| 答辩 PPT | `docs/成军台_息壤杯预赛答辩.pptx` · **15 页** · 1,718,207 B | zipfile 计 `ppt/slides/slideN.xml` |
| 公网 Demo | `https://opcopcos.cn:8088/` → HTTP 200；`/api/v1/health` → 401（鉴权，符合预期） | curl |
| TLS 证书 | `notAfter = 2026-11-08 06:27:26 GMT`（剩 ~45 天），Let's Encrypt | openssl s_client |
| 代码规模 | 106 个 `.py` / 19,105 行（不含 `.git`、`__pycache__`） | find |
| 赛事硬时点 | 官网截止 **2026-08-20**；入口 `https://ai.js.189.cn/OPCCompetition/OPCOutFiles`；赛道 惠民产品创新 / AI+自选开放场景 | `docs/delivery-notes.md:5-7` |
| 最后一次提交 | `5915737` 2026-08-11 08:40:38 +0800 | git log |

**已确认的文档缺陷（Task 1/2/5 的处理对象）：**

1. `docs/delivery-notes.md:13,58`、`docs/demo-video.md:9`、`docs/CHECKLIST.md:41`、`docs/STORE_REGISTRATION.md:19`、`docs/FINAL_DELIVERY_REPORT.html:258` 共 5 处指向不存在的 `demo-output/Chengjuntai_demo_cinematic_60s.mp4`（及从未存在的 `_submit` 变体）。
2. `docs/delivery-notes.md:14` 称 PPT 13 页，实测 15 页。
3. `docs/delivery-notes.md:13` 称视频 ~8MB / 59.5s，实测提交版 5.74 MiB / 58.97s（8.5 MiB 是 71s 母版）。
4. `docs/FINAL_DELIVERY_REPORT.html:258` 仍标「演示视频成片 未生成」，实际两份成片均在位。
5. `docs/SCORE_REPORT_2026.html:213` 称「56个Python文件 / 13563行代码」——这是 2026-08-06 自评快照，**不改数字**，改为补一行口径说明（Task 1 Step 5）。
6. `README.md:26,100-103` 引用的 `docs/P0_WEEK_PLAN.md`、`docs/USER_ONLY_TODO.md`、`docs/CTYUN_TRIAL.md`、`docs/NEXT_SPRINT.md` 已被移入 `docs/archive/`，链接全部失效（Task 5）。

## File Structure

- 新建 `scripts/record_deliverables.py` — 唯一的事实采集器：探测视频/ PPT、算 sha256，渲染 `docs/DELIVERABLES.md`。
- 新建 `docs/DELIVERABLES.md` — 生成物，交付物指纹清单（单一事实来源，供 Release 与台账引用）。
- 修改 `docs/delivery-notes.md`、`docs/demo-video.md`、`docs/CHECKLIST.md`、`docs/STORE_REGISTRATION.md`、`docs/FINAL_DELIVERY_REPORT.html` — 事实校正。
- 新建 `docs/OUTCOME.md` — 赛事结果 + 云资源到期台账（人工确认字段留空，非占位符，见该任务正文）。
- 修改 `README.md` — 4 处链接重定位。
- GitHub Release `v1.0.0-submit-2026-08`（远端）— 承接 `chengjuntai-xirang-preliminary-2026-08.zip` 归档包。
- 记忆：新建 `C:/Users/52637/.qoder-cn/projects/D--APPs------/memory/project-xirang-chengjuntai.md`，修改同目录 `MEMORY.md`（Task 6）。

---

## Task 1: 文档事实校正（交付物路径 · 页数 · 体积 · 过期状态）

**Files:**
- Modify: `docs/delivery-notes.md:13,14,57-58`
- Modify: `docs/demo-video.md:9`
- Modify: `docs/CHECKLIST.md:41`
- Modify: `docs/STORE_REGISTRATION.md:19`
- Modify: `docs/FINAL_DELIVERY_REPORT.html:258`
- Modify: `docs/SCORE_REPORT_2026.html:213` 附近（补口径说明行）
- Test: 无 pytest；用 grep 断言零残留 + 路径存在性检查

**Interfaces:**
- Consumes: 实测基线表（本文件顶部）
- Produces: docs 中所有交付物表述与磁盘一致；`demo-output` 仅出现在 `docs/archive/REPO_COMPARISON.md:15`（历史快照，保留）

- [ ] **Step 1: 确认当前有 5 处 phantom 引用（改前基线）**

```bash
cd /d/APPs/天翼息壤杯/chengjuntai
grep -rn 'demo-output' --include='*.md' --include='*.html' docs | grep -v 'docs/archive/' | wc -l
```
Expected: `5`

- [ ] **Step 2: 改 `docs/delivery-notes.md` 必交两项表（第 13-14 行）**

把第 13-14 行整两行替换为：

```markdown
| 演示视频（提交版） | `demo-video/out/demo-video-60s.mp4` | **58.97s** · 5.74 MiB · 1920×1080 h264+aac · 硬烧字幕 |
| 演示视频（母版，仅本地） | `demo-video/out/demo-video.mp4` | 71.02s · 8.50 MiB · 13 分镜（`demo-video/public/shots.json`） |
```

- [ ] **Step 3: 改 `docs/delivery-notes.md` 验收段（第 57-58 行）的 ffprobe 路径**

```powershell
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate `
  -of default=noprint_wrappers=1 demo-video\out\demo-video-60s.mp4
```

并把紧随其后的「期望」行改为：`期望：时长 ≤60s，1920×1080，h264+aac，文件 ≤100MB。`（原值若已如此则不动）

- [ ] **Step 4: 改其余 3 处 phantom 路径**

`docs/demo-video.md:9` 替换为：

```markdown
| `demo-video/out/demo-video-60s.mp4` | 提交用成片（1080p30 · CRF17 · 硬烧字幕 · 58.97s） |
```

`docs/CHECKLIST.md:41` 替换为（同时勾选，因为磁盘已验证在位）：

```markdown
- [x] 本地交付物就绪：`demo-video/out/demo-video-60s.mp4` + `docs/成军台_息壤杯预赛答辩.pptx`（15 页）+ `docs/DELIVERABLES.md` 指纹清单（见 `delivery-notes.md`）
```

`docs/STORE_REGISTRATION.md:19` 替换为：

```markdown
- 演示视频：本地成片 `demo-video/out/demo-video-60s.mp4`（58.97s，≤60s 合规；母版 `demo-video/out/demo-video.mp4` 71.02s 不外发）
```

- [ ] **Step 5: 改 `docs/FINAL_DELIVERY_REPORT.html:258` 的过期状态；给 `SCORE_REPORT_2026.html:213` 补口径**

`FINAL_DELIVERY_REPORT.html` 第 258 行整行替换（把 red 徽标改为 green，路径改为真实路径）：

```html
    <tr><td>演示视频成片</td><td>demo-video/out/demo-video-60s.mp4</td><td>58.97s / 1080p30 / 5.74 MiB（实测 2026-09-24）</td><td><span class="badge badge-green">已生成</span></td></tr>
```

`SCORE_REPORT_2026.html` 第 213 行**保持原文不动**，在其 `</tr>` 之后插入一行说明：

```html
    <tr><td colspan="3" style="color:#64748b;font-size:.9em">口径说明：本页数字为 2026-08-06 自评快照（56 个 Python 文件 / 13563 行）。截至 2026-09-24 实测为 106 个 .py / 19105 行。</td></tr>
```

若该文件无 `badge-green` 类，先用 `grep -n 'badge-green' docs/FINAL_DELIVERY_REPORT.html | head -3` 确认；不存在则改用文件中已有的通过态类名（`grep -o 'badge-[a-z]*' docs/FINAL_DELIVERY_REPORT.html | sort -u` 取值）。

- [ ] **Step 6: 验证零残留 + 路径真实存在**

```bash
grep -rn 'demo-output' --include='*.md' --include='*.html' docs | grep -v 'docs/archive/'
# 期望：无输出（0 处）
grep -rn '13 页' docs/delivery-notes.md; echo "exit=$?"
# 期望：无输出
for f in demo-video/out/demo-video-60s.mp4 demo-video/out/demo-video.mp4 docs/成军台_息壤杯预赛答辩.pptx; do
  [ -f "$f" ] && echo "OK $f" || echo "MISSING $f"; done
# 期望：3 行 OK
```

- [ ] **Step 7: 提交（不推送）**

```bash
git add docs/delivery-notes.md docs/demo-video.md docs/CHECKLIST.md docs/STORE_REGISTRATION.md docs/FINAL_DELIVERY_REPORT.html docs/SCORE_REPORT_2026.html
git commit -m "docs: 校正交付物事实（真实视频路径/15页PPT/实测时长体积/成片状态）"
```

---

## Task 2: 交付物指纹清单生成器 `scripts/record_deliverables.py` → `docs/DELIVERABLES.md`

**Files:**
- Create: `scripts/record_deliverables.py`
- Create（由脚本生成）: `docs/DELIVERABLES.md`
- Test: 脚本自带 `--check` 模式，退出码即断言

**Interfaces:**
- Consumes: 磁盘上的 `demo-video/out/*.mp4`、`docs/成军台_息壤杯预赛答辩.pptx`、`git rev-parse HEAD`
- Produces: `docs/DELIVERABLES.md`（Markdown 表格，含 sha256 前 12 位）；供 Task 3 的 Release 说明与 Task 4 的台账引用

- [ ] **Step 1: 写入脚本**

```python
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
```

- [ ] **Step 2: 跑一次，人工核对输出**

```bash
python scripts/record_deliverables.py --stdout
```
Expected: 3 行数据；提交版显示 `58.97s · 1920×1080 · h264 · 剪辑自母版`，母版显示 `71.02s · 1920×1080 · h264 · 13 镜 · 2129 帧 @30fps`，PPT 显示 `15 页`，无任何一行出现「缺失」。

- [ ] **Step 3: 生成文件并验证幂等**

```bash
python scripts/record_deliverables.py
python scripts/record_deliverables.py --check; echo "exit=$?"
```
Expected: `不一致…` **不得**出现；`exit=0`（幂等，时间戳行已排除比对）。

- [ ] **Step 4: 验证未污染仓库（mp4 不入库）**

```bash
git status --porcelain
```
Expected: 仅出现 `?? scripts/record_deliverables.py`、`?? docs/DELIVERABLES.md`（以及尚未提交的 `?? docs/superpowers/`）。若出现 `.mp4`，立即停止并检查 `.gitignore`（不得提交大文件）。

- [ ] **Step 5: 提交**

```bash
git add scripts/record_deliverables.py docs/DELIVERABLES.md
git commit -m "feat: 交付物指纹清单生成器（ffprobe+pptx页数+sha256，产出 docs/DELIVERABLES.md）"
```

---

## Task 3: 异地归档 —— GitHub Release 附件（**外部可见，需逐次确认**）

**Files:**
- Create（远端）: GitHub Release `v1.0.0-submit-2026-08` on `yigenfeng0707-netizen/chengjuntai-opc-xirang`
- Create（临时，不入库）: `/tmp/chengjuntai-xirang-preliminary-2026-08/` 打包目录
- Verify: `docs/DELIVERABLES.md` 的 sha256 必须与下载回来的资产逐字节对上

**Interfaces:**
- Consumes: Task 2 的 `docs/DELIVERABLES.md`（作为 Release 说明正文的一部分 + 校验基准）
- Produces: 永久下载 URL `https://github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang/releases/tag/v1.0.0-submit-2026-08`，供 Task 4 台账记录

**为什么打成 zip 而不是直传两个 mp4：** 单包便于校验与二次分发，且把 15 页 PPT（已在库内，但 zip 里留一份带时间点的完整快照）与视频、指纹清单绑定在同一不可变 tag 上。仓库是 public —— Release 资产对外可下载，这一点必须先向用户点明确认。

- [ ] **Step 1: 向用户确认后再继续（不可跳过）**

明确告知：目标仓库为 **public**，Release 资产（演示视频 14.2 MiB + 答辩 PPT 1.64 MiB）将任何人可下载；不需要 GitHub 认证即可访问下载链接。得到「可以」才执行 Step 2。若用户拒绝公开，改走 Step 6 的私有替代方案。

- [ ] **Step 2: 组装打包目录（只放 4 个文件，禁止 config/users）**

```bash
STAGE=/tmp/chengjuntai-xirang-preliminary-2026-08
mkdir -p "$STAGE"
cp demo-video/out/demo-video-60s.mp4 "$STAGE/成军台_提交版_59s_1080p.mp4"
cp demo-video/out/demo-video.mp4     "$STAGE/成军台_母版_71s_1080p.mp4"
cp docs/成军台_息壤杯预赛答辩.pptx      "$STAGE/"
cp docs/DELIVERABLES.md              "$STAGE/"
python -c "
import hashlib,pathlib,sys
sys.stdout.reconfigure(encoding='utf-8')
p=pathlib.Path('$STAGE')
lines=[('%s  %s'%(f.name,hashlib.sha256(f.read_bytes()).hexdigest())) for f in sorted(p.iterdir()) if f.name!='SHA256SUMS.txt']
(p/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))"
ls -la "$STAGE"
```
Expected: 目录内 5 个文件（2 mp4 + 1 pptx + 1 md + SHA256SUMS.txt）；**出现任何 `config.yaml` / `users.json` / `.env` 立即删除并中止**。

- [ ] **Step 3: 压缩并核对体积**

```bash
cd /tmp && rm -f chengjuntai-xirang-preliminary-2026-08.zip
powershell.exe -NoProfile -Command "Compress-Archive -Path 'C:\tmp\chengjuntai-xirang-preliminary-2026-08\*' -DestinationPath 'C:\tmp\chengjuntai-xirang-preliminary-2026-08.zip' -Force" 2>/dev/null \
  || python -c "
import shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
shutil.make_archive('/tmp/chengjuntai-xirang-preliminary-2026-08','zip','/tmp/chengjuntai-xirang-preliminary-2026-08')
print('已用 python zipfile 打包')"
ls -la /tmp/chengjuntai-xirang-preliminary-2026-08.zip
```
Expected: 约 15–16 MiB（mp4 已高压缩，zip 不再显著变小）。若 >100 MiB 说明误打包了别的东西，中止并检查。

- [ ] **Step 4: 创建 Release（tag 不可变，命名固定）**

```bash
cd /d/APPs/天翼息壤杯/chengjuntai
gh release create v1.0.0-submit-2026-08 \
  /tmp/chengjuntai-xirang-preliminary-2026-08.zip \
  --title "成军台 · 2026 息壤杯预赛提交包（2026-08-11 冻结点）" \
  --notes "2026 息壤杯 OPC 创新大赛（惠民产品创新 / AI+自选开放场景）预赛交付物归档。提交版视频 58.97s/1080p，母版 71.02s/13 分镜，答辩 PPT 15 页。指纹见包内 SHA256SUMS.txt 与 docs/DELIVERABLES.md。冻结点 commit 5915737 (2026-08-11)。公网 Demo https://opcopcos.cn:8088 证书有效期至 2026-11-08。" \
  --latest
```
Expected: 输出 Release URL，退出码 0。

- [ ] **Step 5: 下载回来做闭环校验（归档没验证等于没归档）**

```bash
gh release download v1.0.0-submit-2026-08 -R yigenfeng0707-netizen/chengjuntai-opc-xirang -D /tmp/verify-release
python -c "
import zipfile,hashlib,pathlib,sys
sys.stdout.reconfigure(encoding='utf-8')
z=zipfile.ZipFile(next(pathlib.Path('/tmp/verify-release').glob('*.zip')))
for n in sorted(z.namelist()):
    if n=='SHA256SUMS.txt': continue
    print('%-46s %s'%(n,hashlib.sha256(z.read(n)).hexdigest()[:12]))
print('--- SHA256SUMS.txt ---'); print(z.read('SHA256SUMS.txt').decode('utf-8'))"
```
Expected: 4 个 sha256(12) 与 Step 2 打印值逐行相同。

- [ ] **Step 6: 私有替代方案（仅当 Step 1 被拒时执行）**

同内容改为推送到私有仓的 Release，或天翼云 OBS 私有桶（`docs/` 已有 OBS 相关说明则沿用）：
`git init` 一个 `chengjuntai-archive` 私有仓（`gh repo create yigenfeng0707-netizen/chengjuntai-archive --private --source . --push`），复用 Step 2–5，把 Step 4 的 `-R` 换成新私有仓、并加 `--draft=false`。台账中注明「私有，需授权访问」。

- [ ] **Step 7: 提交 Task 2 产物的引用（本任务无仓库文件变更则跳过）**

Release 不产生仓库改动。若 Step 4/6 变更了 `docs/OUTCOME.md`（在 Task 4 做），则在 Task 4 一并提交。清理临时文件：`rm -rf /tmp/chengjuntai-xirang-preliminary-2026-08 /tmp/verify-release`。

---

## Task 4: 赛事结果与云资源台账 `docs/OUTCOME.md`

**Files:**
- Create: `docs/OUTCOME.md`
- Modify: `README.md:98-111`「参赛材料」列表 —— 追加两行指向 `docs/OUTCOME.md`、`docs/DELIVERABLES.md`
- Test: `docs/OUTCOME.md` 内所有勾选项必须处于「已知」或「待核实」两态之一，禁止空单元格

**Interfaces:**
- Consumes: Task 3 的 Release URL；本方案实测基线表
- Produces: 后续任何会话判断「这个项目到底结没结束、还剩哪些资源要管」的入口文档

- [ ] **Step 1: 写入台账（已知事实全部填实，未知字段显式标 `待核实` 并写明核实途径 —— 这不是占位符，是给用户的提问清单）**

```markdown
# 成军台 · 赛事结果与资源台账

> 建立于 2026-09-24。用途：一处看清「交了没有 / 结果如何 / 还有什么在计费或会到期」。
> 交付物指纹见 `docs/DELIVERABLES.md`；部署操作见 `DEPLOY天翼云.md`。

## 1. 赛事状态

| 项 | 状态 | 依据 |
|---|---|---|
| 报名 | 已完成 | `README.md:26`「报名状态：已报名」 |
| 赛道 | 惠民产品创新 / AI+自选开放场景 | `docs/delivery-notes.md:5` |
| 官方截止 | 2026-08-20 | `docs/delivery-notes.md:5` |
| 材料就绪 | 已就绪（视频 58.97s + PPT 15 页 + 公网 Demo + 仓库） | 2026-09-24 实测 |
| **Store 实际上传** | **待核实** —— 登录 https://ai.js.189.cn/OPCCompetition/OPCOutFiles 查「我的作品」；`docs/SUBMISSION_CHECKLIST.html` 明确记录 Agent 无法代登，故仓库内无回执 | 用户本人 |
| **8/11 聚能湾答辩结果** | **待核实** —— 仓库内无任何晋级/淘汰记录 | 用户本人 / 赛事通知 |
| 复赛 / 决赛安排 | **待核实** | 赛事通知 |
| 归档包 | Release `v1.0.0-submit-2026-08`（见 §3） | Task 3 |

自评快照（不作为当前结论）：五维 89/A（2026-08-06），最低项为商业模式 7.75。

## 2. 在跑的资源与到期日

| 资源 | 现状（2026-09-24 实测） | 到期 / 需动作 |
|---|---|---|
| 天翼云 ECS | `https://opcopcos.cn:8088/` → 200；`/api/v1/health` → 401（鉴权，正常） | **试用到期日待核实**（天翼云控制台 → 云主机）。`docs/archive/APPLY_ECS_TOKEN.md` 建议授权覆盖至复赛/决赛 + 7~14 天 |
| Let's Encrypt 证书 | `notAfter = 2026-11-08 06:27:26 UTC`（剩约 45 天） | 若需继续对外演示，确认服务器上的 certbot 续期定时任务仍生效 |
| 3 个 systemd 服务 | `teleagent-backend` / `teleagent-mcp` / `teleagent-web` | 停服即断公网 Demo；不再需要时按 `DEPLOY天翼云.md` §9 下线并释放 |
| LLM 主链路 Token | 息壤/星辰为正式口径，级联含壁韧/SenseNova 兜底 | 试用 Token 到期日待核实 |
| 本地密钥 | `content_factory/config.yaml`（含 api_token / web 口令），已 gitignore，9/7 有改动 | 不外发；轮换见 `docs/SECURITY_KEY_ROTATION.md` |

## 3. 归档与恢复

- 归档包：`<Release URL>`（zip，含 2 个 mp4 + 15 页 PPT + `SHA256SUMS.txt` + 指纹清单）
- 冻结点：`5915737`（2026-08-11 08:40 +0800）
- 重跑视频 / PPT：`docs/delivery-notes.md`「视频重跑」「PPT 重生成」两节
- 官方提交规格复核：视频 ≤60s、1920×1080、h264+aac、≤100MB —— 提交版 4 项全合规

## 4. 休眠与重启

最后一次代码提交 2026-08-11，至 2026-09-24 无活动。重启本地演示：
`scripts/start_local_demo.bat` → http://127.0.0.1:8090（评委 60 秒体验路径见 `README.md`）。
先跑 `python scripts/health_check.py` 与 `python tests/test_campaign_core.py`。
```

- [ ] **Step 2: 追加 README 指针**

在 `README.md`「参赛材料」列表 `docs/CHECKLIST.md` 那行之后插入：

```markdown
- [docs/OUTCOME.md](./docs/OUTCOME.md) 赛事结果 + 云资源到期台账（**先查这份再动手**）
- [docs/DELIVERABLES.md](./docs/DELIVERABLES.md) 交付物指纹清单（`python scripts/record_deliverables.py` 重生成）
```

- [ ] **Step 3: 验证无空字段、README 新链接可解析**

```bash
grep -n '|' docs/OUTCOME.md | grep -E '\|\s*\|\s*\|' && echo "FAIL 有空单元格" || echo "OK 无空单元格"
python - <<'PY'
import re,pathlib
t=pathlib.Path('README.md').read_text(encoding='utf-8')
bad=[l for l in re.findall(r'\]\(\./([^)]+)\)',t) if not pathlib.Path(l).exists()]
print('README 失效链接:', bad)
PY
```
Expected: `OK 无空单元格`；失效链接列表**不含** `docs/OUTCOME.md` 与 `docs/DELIVERABLES.md`（其余 4 项由 Task 5 处理，此时可能仍在列，属预期）。

- [ ] **Step 4: 把 Release URL 填进台账**

```bash
URL=$(gh release view v1.0.0-submit-2026-08 -R yigenfeng0707-netizen/chengjuntai-opc-xirang --json url -q .url)
sed -i "s|<Release URL>|$URL|" docs/OUTCOME.md
grep -n 'github.com' docs/OUTCOME.md
```
Expected: 至少 1 行含真实 URL，且不再有 `<Release URL>` 字样。

- [ ] **Step 5: 提交**

```bash
git add docs/OUTCOME.md README.md
git commit -m "docs: 新增赛事结果与云资源到期台账（含证书 2026-11-08 与待核实项）"
```

---

## Task 5: 修复 README 4 处失效链接（文档移入 archive 后未更新）

**Files:**
- Modify: `README.md:26`、`README.md:93`、`README.md:100-103`
- Test: 仓库内相对链接全部可解析

**Interfaces:**
- Consumes: 实际位置 `docs/archive/{P0_WEEK_PLAN,USER_ONLY_TODO,CTYUN_TRIAL,NEXT_SPRINT}.md`（2026-08-10 清理时移入）
- Produces: `README.md` 相对链接 0 失效 —— Task 4 Step 3 的验证脚本变全绿

- [ ] **Step 1: 确认失效集合**

```bash
python - <<'PY'
import re,pathlib
t=pathlib.Path('README.md').read_text(encoding='utf-8')
bad=[l for l in re.findall(r'\]\(\./([^)]+)\)',t) if not pathlib.Path(l).exists()]
print('失效:', sorted(set(bad)))
PY
```
Expected: 恰好 `['docs/CTYUN_TRIAL.md', 'docs/NEXT_SPRINT.md', 'docs/P0_WEEK_PLAN.md', 'docs/USER_ONLY_TODO.md']`（Task 4 若已跑则这 4 项在内）。

- [ ] **Step 2: 逐处替换为 archive 路径**

第 26 行（同一行内 3 处）：
- `[docs/P0_WEEK_PLAN.md](./docs/P0_WEEK_PLAN.md)` → `[docs/archive/P0_WEEK_PLAN.md](./docs/archive/P0_WEEK_PLAN.md)`
- `[docs/USER_ONLY_TODO.md](./docs/USER_ONLY_TODO.md)` → `[docs/archive/USER_ONLY_TODO.md](./docs/archive/USER_ONLY_TODO.md)`
- `[docs/CTYUN_TRIAL.md](./docs/CTYUN_TRIAL.md)` → `[docs/archive/CTYUN_TRIAL.md](./docs/archive/CTYUN_TRIAL.md)`

第 93 行：`[docs/CTYUN_TRIAL.md](./docs/CTYUN_TRIAL.md)` → `[docs/archive/CTYUN_TRIAL.md](./docs/archive/CTYUN_TRIAL.md)`

第 100-103 行四条列表项：把每行的 `](./docs/X.md)` 改为 `](./docs/archive/X.md)`，显示文本同步带上 `docs/archive/` 前缀，并在这 4 行之后补一行说明：

```markdown
  （以上 4 份为 2026-08 预赛期计划文档，已归档，保留原貌）
```

- [ ] **Step 3: 验证全绿**

```bash
python - <<'PY'
import re,pathlib
t=pathlib.Path('README.md').read_text(encoding='utf-8')
bad=[l for l in re.findall(r'\]\(\./([^)]+)\)',t) if not pathlib.Path(l).exists()]
print('失效:', sorted(set(bad)) or '无')
PY
git diff --stat
```
Expected: `失效: 无`；diff 仅 `README.md`。

- [ ] **Step 4: 提交**

```bash
git add README.md
git commit -m "docs: 修复 README 4 处指向已归档计划文档的失效链接"
```

---

## Task 6: 记忆歧义处理（不删除，只标归属）

**Files:**
- Create: `C:/Users/52637/.qoder-cn/projects/D--APPs------/memory/project-xirang-chengjuntai.md`
- Modify: `C:/Users/52637/.qoder-cn/projects/D--APPs------/memory/MEMORY.md`
- 只读不改：同目录 `project-qiming-competition.md`

**Interfaces:**
- Consumes: 用户指令「启明杯是另外一个项目」
- Produces: 两个同名 5 汉字目录共用一个 key 时，index 每条自带归属路径

**为什么必须保留启明杯条目：** `D:\APPs\天翼息壤杯` 与 `D:\APPs\启明杯比赛` 各 5 个汉字，脱敏后同为 `D--APPs------`，`projects\D--APPs------\memory\` 是**同一个物理目录、同一份 MEMORY.md**（不存在另一份可迁移的目标）。删除会毁掉启明杯（截止 2026-10-30，仍在推进）的项目记忆。唯一安全做法：给每条 index 加归属路径。

- [ ] **Step 1: 写入本项目记忆**

```markdown
---
name: project-xirang-chengjuntai
description: D:\APPs\天翼息壤杯 是 2026 息壤杯 OPC 大赛参赛作品「成军台」；预赛材料已于 2026-08 交付、项目休眠中，仅剩赛事结果与云资源到期两个未知项
metadata:
  type: project
---

**仅适用于 `D:\APPs\天翼息壤杯`（成军台 / chengjuntai-xirang）。** 2026 息壤杯全国 AI OPC 创新大赛，赛道「惠民产品创新 / AI+自选开放场景」，官方截止 2026-08-20，8/11 聚能湾答辩。Git 根是子目录 `chengjuntai/`（工作区根不受版本控制），远端 public 仓 `yigenfeng0707-netizen/chengjuntai-opc-xirang`。

**Why:** 最后代码提交 2026-08-11，至 2026-09-24 无活动 —— 这是收尾期，不是开发期。真正的风险不是代码，而是（a）仓库里查不到 Store 是否真的提交成功、也查不到答辩结果，(b) 两个 mp4 被 gitignore、只存本地，(c) 公网 Demo 依赖会到期的天翼云试用 ECS + Let's Encrypt 证书（2026-11-08）。

**How to apply:** 动手前先读 `chengjuntai/docs/OUTCOME.md`（结果与到期台账）和 `docs/DELIVERABLES.md`（交付物指纹，`python scripts/record_deliverables.py` 重生成），不要重新推导交付物规格。文档里的 `demo-output/` 是历史笔误，真实路径 `demo-video/out/`。对外可见动作（push、Release）先确认。同 key 下另有 [[project-qiming-competition]]，属另一个工作区，勿混用。
```

- [ ] **Step 2: 重写 index（两条都标归属）**

`MEMORY.md` 内容替换为：

```markdown
# MEMORY.md

> 本目录被两个同名 5 汉字工作区共用（脱敏 key 冲突）：`D:\APPs\天翼息壤杯` 与 `D:\APPs\启明杯比赛`。读任何条目前先看归属路径。

- [启明杯 competition entry](project-qiming-competition.md) — 属 `D:\APPs\启明杯比赛`：电信启明杯 3-3，截止 2026-10-30；emp#25 已发布，郑奕调用审批 pending
- [成军台 (息壤杯) 收尾状态](project-xirang-chengjuntai.md) — 属 `D:\APPs\天翼息壤杯`：预赛材料已交付、休眠中；先看 docs/OUTCOME.md 与 DELIVERABLES.md
```

- [ ] **Step 3: 验证两份记忆都在、启明杯原文未被改动**

```bash
D="/c/Users/52637/.qoder-cn/projects/D--APPs------/memory"
ls "$D"
python - <<PY
import pathlib,sys;sys.stdout.reconfigure(encoding='utf-8')
d=pathlib.Path(r'$D'.replace('/c/','C:/'))
q=(d/'project-qiming-competition.md').read_text(encoding='utf-8')
print('qiming 行数:',len(q.splitlines()),'| 含 emp#25:', '已发布' in q)
print('index 条目:',(d/'MEMORY.md').read_text(encoding='utf-8').count(']('))
PY
```
Expected: 目录含 3 个文件；`qiming 行数` ≥10 且 `含 emp#25: True`；`index 条目: 2`。

- [ ] **Step 4: 本节无 git 提交（记忆目录不在项目仓内）**

---

## Self-Review

**1. Spec 覆盖**：① 归档 → Task 2（指纹清单）+ Task 3（异地归档 + 闭环校验）；② 事实校正 → Task 1（5 处 phantom + 页数 + 体积 + 状态 + 快照口径）+ Task 5（失效链接）；③ 结果台账 → Task 4（含资源到期，覆盖我上一轮点出的证书/ECS 隐患）；④ 记忆歧义 → Task 6。无遗漏。

**2. Placeholder 扫描**：Task 4 的 `待核实` 是给用户的、附核实途径的提问字段（Store 登录 / 天翼云控制台 / 赛事通知），非实施缺口；其余步骤均给出可执行命令或完整文件内容。Task 3 Step 6 是条件分支而非「稍后补充」。

**3. 类型一致性**：`docs/DELIVERABLES.md` 由 `scripts/record_deliverables.py` 的 `build()` 产出，Task 2 Step 4 与 Task 4 Step 1 引用的路径一致；Release tag `v1.0.0-submit-2026-08` 在 Task 3 Step 4、Task 4 Step 1/4 三处命名一致；`5915737` 冻结点、`2026-11-08` 证书日、`58.97s`/`71.02s`/`15 页` 与实测基线表一致。

**依赖顺序（执行期修订，见 ledger Ruling 1/2）**：Task 2 → Task 1 → Task 5 →（需确认）Task 3 → Task 4 → Task 6。
Task 2 提前：Task 1 的 `docs/CHECKLIST.md` 一行要引用 `docs/DELIVERABLES.md`，先有生成器才不出现悬空引用。
Task 5 提前于 Task 4：两者都改 `README.md`（Task 4 在 98-111 行区间插入 2 行，会把 Task 5 引用的 100-103 行号整体下移），先做链接修复再做 README 追加。
Task 6 由控制器直接执行（记忆目录不属于本仓，也不该由子代理写入）。
