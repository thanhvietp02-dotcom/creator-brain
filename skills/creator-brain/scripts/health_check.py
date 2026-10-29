"""知识库健康检查（只读）：入口文件、断链、孤立笔记、收件箱积压、重复终稿、疑似敏感文件、数据文件格式。

用法：
  python health_check.py --root "D:/我的自媒体"
  python health_check.py --root "D:/我的自媒体" --save-state    # 结果另存到 system/健康状态.json
  python health_check.py --root "D:/我的自媒体" --json
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PUBLISH_CSV, PUBLISH_HEADER, WORKS_CSV, WORKS_HEADER, parse_num, read_csv, utf8_stdout  # noqa: E402

ENTRY_FILES = ["AGENTS.md", "INDEX.md", "本周.md", "system/日志.md"]
SKIP_DIRS = {".git", ".obsidian", "node_modules", ".trash", "__pycache__"}
NOT_ORPHAN = {"README.md", "_索引.md", "AGENTS.md", "CLAUDE.md", "INDEX.md", "本周.md"}
REPORT = re.compile(r"^(选题验证|复盘)_\d{8}$")  # 脚本生成的报告按日期找，不算孤立
WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MDLINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FINAL = re.compile(r"最终|终版|定稿版|final", re.I)
SENSITIVE = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|\.p12$|^id_rsa|cookie|token|password|passwd|secret|密码|凭证)", re.I)
NUMERIC = {WORKS_CSV: ["粉丝", "点赞", "收藏", "评论", "分享"], PUBLISH_CSV: ["播放", "点赞", "收藏", "评论", "分享", "涨粉"]}
HEADERS = {WORKS_CSV: WORKS_HEADER, PUBLISH_CSV: PUBLISH_HEADER}


def walk(root):
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        yield p


def check(root, now=None):
    now = now or time.time()
    files = [p for p in walk(root) if p.is_file()]
    notes = [p for p in files if p.suffix == ".md"]
    rel = lambda p: p.relative_to(root).as_posix()
    by_stem = defaultdict(list)
    for p in files:
        by_stem[p.stem].append(p)
        by_stem[p.name].append(p)
    issues = []

    for f in ENTRY_FILES:
        if not (root / f).exists():
            issues.append(dict(kind="入口文件缺失", path=f, detail="AI 进入知识库时找不到这个入口", fix="运行 init_vault.py --apply 补齐（不会覆盖已有文件）"))

    referenced, index_text = set(), []
    for n in notes:
        text = n.read_text("utf-8", errors="ignore")
        if n.name in ("_索引.md", "INDEX.md"):
            index_text.append(text)
        for m in WIKI.finditer(text):
            target = m.group(1).strip()
            hits = by_stem.get(target) or by_stem.get(Path(target).name) or by_stem.get(Path(target).stem)
            if hits or (root / target).exists() or (root / f"{target}.md").exists():
                for h in hits or []:
                    referenced.add(h)
                continue
            issues.append(dict(kind="断链", path=rel(n), detail=f"[[{target}]] 找不到", fix="改成正确的笔记名，或补建这篇笔记"))
        for m in MDLINK.finditer(text):
            target = unquote(m.group(1)).split("#")[0]
            if not target or re.match(r"^[a-z]+:", target, re.I):
                continue
            dest = (n.parent / target).resolve()
            if dest.exists():
                referenced.add(dest)
            else:
                issues.append(dict(kind="断链", path=rel(n), detail=f"({m.group(1)}) 指向的文件不存在", fix="修正路径，或把文件放回原处"))

    joined_index = "\n".join(index_text)
    referenced = {x.resolve() for x in referenced}
    for n in notes:
        r = rel(n)
        if n.name in NOT_ORPHAN or REPORT.match(n.stem) or r.startswith("system/") or "_旧版" in r or r.startswith("00.收件箱/"):
            continue
        if n.resolve() in referenced or n.stem in joined_index:
            continue
        issues.append(dict(kind="孤立笔记", path=r, detail="没有任何笔记或索引提到它，以后很难被找到", fix="在所在目录的 _索引.md 里加一行，或从相关笔记链接过来"))

    inbox = root / "00.收件箱"
    if inbox.exists():
        for p in inbox.rglob("*"):
            if p.is_file() and p.name != "README.md" and now - p.stat().st_mtime > 7 * 86400:
                days = int((now - p.stat().st_mtime) // 86400)
                issues.append(dict(kind="收件箱积压", path=rel(p), detail=f"放了 {days} 天还没整理", fix="说一句「整理收件箱」"))

    finals = defaultdict(list)
    for p in files:
        if FINAL.search(p.stem) and "_旧版" not in rel(p):
            finals[p.parent].append(p)
    for d, ps in finals.items():
        if len(ps) >= 2:
            issues.append(dict(kind="重复终稿", path=rel(d) if d != root else ".", detail="、".join(p.name for p in ps),
                               fix="确认哪个是当前版本，其余移到 _旧版/"))

    for p in files:
        if SENSITIVE.search(p.name):
            issues.append(dict(kind="疑似敏感文件", path=rel(p), detail="文件名像密钥、密码或 Cookie（未读取内容）", fix="确认是否该放在知识库里；不需要就移走"))

    for csv_rel, numeric in NUMERIC.items():
        path = root / csv_rel
        if not path.exists():
            continue
        header, rows = read_csv(path)
        want = HEADERS[csv_rel]
        if header != want:
            missing = [h for h in want if h not in (header or [])]
            issues.append(dict(kind="数据文件表头不对", path=csv_rel.as_posix(),
                               detail=("缺少列：" + "、".join(missing)) if missing else "列的顺序或名字和标准不同",
                               fix="让 AI 按 benchmark.md / publish-retro.md 里的标准表头修正"))
        bad = sum(1 for r in rows for c in numeric if (r.get(c) or "").strip() and parse_num(r.get(c)) is None)
        if bad:
            issues.append(dict(kind="数据读不出数字", path=csv_rel.as_posix(), detail=f"{bad} 个格子不是数字", fix="改成纯数字，例如 1.2万 写成 12000"))

    return dict(root=str(root), checked_at=time.strftime("%Y-%m-%d %H:%M", time.localtime(now)),
                notes=len(notes), files=len(files), issues=issues)


def render(res):
    L = [f"知识库：{res['root']}", f"检查时间：{res['checked_at']}，共 {res['files']} 个文件，其中 {res['notes']} 篇笔记。"]
    if not res["issues"]:
        L.append("整体健康，没有发现问题。")
        return "\n".join(L)
    count = defaultdict(int)
    for i in res["issues"]:
        count[i["kind"]] += 1
    L.append(f"发现 {len(res['issues'])} 个问题：" + "，".join(f"{k} {v} 个" for k, v in count.items()) + "。")
    for i in res["issues"]:
        L.append(f"- [{i['kind']}] {i['path']}：{i['detail']}。建议：{i['fix']}")
    return "\n".join(L)


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(description="知识库健康检查（只读）")
    ap.add_argument("--root", required=True, help="知识库文件夹")
    ap.add_argument("--save-state", action="store_true", help="结果另存到 system/健康状态.json")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"找不到知识库文件夹：{root}")
        return 2
    res = check(root)
    print(json.dumps(res, ensure_ascii=False, indent=1) if args.json else render(res))
    if args.save_state:
        (root / "system").mkdir(exist_ok=True)
        (root / "system" / "健康状态.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
