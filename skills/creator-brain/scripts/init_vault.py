"""建自媒体知识库骨架。默认只预览；加 --apply 才写入。已存在的文件一律不覆盖。

用法：
  python init_vault.py --root "D:/我的自媒体" --name "我的账号"           # 预览
  python init_vault.py --root "D:/我的自媒体" --name "我的账号" --apply   # 写入
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import utf8_stdout  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vault-template"
TEXT_SUFFIXES = {".md", ".json", ".txt"}


def unsafe_root(root):
    """不能把知识库建在用户主目录、磁盘根目录、下载目录。"""
    home = Path.home().resolve()
    if root == home or root.parent == root or root == home / "Downloads" or root.name.lower() in {"downloads", "下载"}:
        return True
    return False


def plan(root, name, today):
    """返回 [(相对路径, 动作, 内容或 None)]，动作是 新建目录 / 新建文件 / 保留。"""
    items = []
    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        dst = root / rel
        if src.is_dir():
            if not dst.exists():
                items.append((rel, "新建目录", None))
            continue
        if dst.exists():
            items.append((rel, "保留", None))
            continue
        data = src.read_bytes()
        if src.suffix in TEXT_SUFFIXES:
            text = data.decode("utf-8").replace("{{名字}}", name).replace("{{日期}}", today)
            data = text.encode("utf-8")
        items.append((rel, "新建文件", data))
    return items


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(description="建自媒体知识库骨架（默认只预览）")
    ap.add_argument("--root", required=True, help="知识库文件夹")
    ap.add_argument("--name", default="我的账号", help="账号名，会写进入口文件")
    ap.add_argument("--apply", action="store_true", help="真正写入（不加只预览）")
    ap.add_argument("--date", default=None, help="写进文件的日期，默认今天（测试用）")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if unsafe_root(root):
        print(f"不建议把知识库建在 {root}（主目录、磁盘根目录或下载目录）。请换一个专门的文件夹。")
        return 2
    if root.exists() and not root.is_dir():
        print(f"{root} 是一个文件，不是文件夹。")
        return 2
    if not TEMPLATE.exists():
        print(f"找不到模板目录 {TEMPLATE}，Skill 可能没装完整。")
        return 2

    existing = sum(1 for _ in root.rglob("*") if _.is_file()) if root.exists() else 0
    items = plan(root, args.name, args.date or date.today().isoformat())
    new_dirs = [i for i in items if i[1] == "新建目录"]
    new_files = [i for i in items if i[1] == "新建文件"]
    kept = [i for i in items if i[1] == "保留"]

    print(f"知识库：{root}")
    print(f"文件夹里已有 {existing} 个文件，全部保持不动。")
    print(f"将新建 {len(new_dirs)} 个文件夹、{len(new_files)} 个文件；模板里有 {len(kept)} 个文件已存在，保留原样。")
    for rel, action, _ in items:
        if action != "保留":
            print(f"  [{action}] {rel.as_posix()}")
    for rel, _, _ in kept:
        print(f"  [保留，不覆盖] {rel.as_posix()}")

    if not args.apply:
        print("\n这是预览，没有写入任何东西。确认后加 --apply 再运行一次。")
        return 0

    root.mkdir(parents=True, exist_ok=True)
    for rel, action, data in items:
        dst = root / rel
        if action == "新建目录":
            dst.mkdir(parents=True, exist_ok=True)
        elif action == "新建文件" and not dst.exists():  # 再确认一次，防止预览后有人建了同名文件
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
    print(f"\n已写入：新建 {len(new_dirs)} 个文件夹、{len(new_files)} 个文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
