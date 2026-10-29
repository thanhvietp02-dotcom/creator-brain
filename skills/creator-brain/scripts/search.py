"""知识库本地全文检索。中文按两个字一组匹配，英文按单词匹配；返回 文件:行号 和那一行内容。

用法：
  python search.py --root "D:/我的自媒体" "知识库 引流"
  python search.py --root "D:/我的自媒体" "Codex" --limit 10
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import utf8_stdout  # noqa: E402

SUFFIXES = {".md", ".txt", ".csv"}
SKIP_DIRS = {".git", ".obsidian", "node_modules", ".trash", "__pycache__"}
CJK = re.compile(r"[\u4e00-\u9fff]")


def grams(term):
    """中文词拆成两字一组（'知识库' → 知识、识库），英文和数字整体保留。"""
    term = term.lower()
    out = set()
    for chunk in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_.\-]+", term):
        if CJK.match(chunk) and len(chunk) > 2:
            out.update(chunk[i:i + 2] for i in range(len(chunk) - 1))
        else:
            out.add(chunk)
    return out


def score_line(line, terms, term_grams):
    low = line.lower()
    s = 0.0
    for t, gs in zip(terms, term_grams):
        if t in low:
            s += 10 + len(t)          # 整个词出现，分最高
        elif gs:
            hit = sum(1 for g in gs if g in low)
            s += 6 * hit / len(gs)     # 只出现一部分，按比例给分
    return s


def search(root, query, limit=20):
    terms = [t.lower() for t in query.split() if t.strip()]
    term_grams = [grams(t) for t in terms]
    results = []
    for p in root.rglob("*"):
        rel_parts = p.relative_to(root).parts
        if not p.is_file() or p.suffix.lower() not in SUFFIXES or any(x in SKIP_DIRS for x in rel_parts):
            continue
        name_bonus = score_line(p.stem, terms, term_grams) * 0.5
        try:
            lines = p.read_text("utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            s = score_line(line, terms, term_grams)
            if s >= 6:
                results.append((s + name_bonus, p.relative_to(root).as_posix(), i, line.strip()))
    results.sort(key=lambda x: (-x[0], x[1], x[2]))
    return results[:limit]


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(description="知识库全文检索")
    ap.add_argument("query", help="要找的词，多个词用空格隔开")
    ap.add_argument("--root", required=True, help="知识库文件夹")
    ap.add_argument("--limit", type=int, default=20, help="最多返回几条（默认 20）")
    args = ap.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"找不到知识库文件夹：{root}")
        return 2
    hits = search(root, args.query, args.limit)
    if not hits:
        print(f"没有找到「{args.query}」相关的内容。")
        return 0
    for _, path, line_no, text in hits:
        print(f"{path}:{line_no}: {text[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
