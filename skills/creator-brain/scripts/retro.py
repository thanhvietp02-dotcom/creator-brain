"""读自己的发布记录，算自己平时一条多少赞、每条是平时的几倍、哪类选题和形式表现好。

每条内容可能记了好几次（发布当天、第 3 天、第 7 天），取最近一次记录。
"平时一条" = 所有内容最近一次点赞的中位数；有发布满 3 天的记录时，只用满 3 天的算，避免刚发的拉低基线。

用法：
  python retro.py --root "D:/我的自媒体"           # 写到 07.发布与复盘/复盘_日期.md
  python retro.py --root "D:/我的自媒体" --stdout
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (PUBLISH_CSV, fmt_num, md_cell, median, parse_date, parse_num, read_csv,  # noqa: E402
                     today_from, utf8_stdout)

MIN_POSTS = 5


def latest_snapshots(rows):
    latest = {}
    for i, r in enumerate(rows):
        key = r.get("链接") or (r.get("平台", ""), r.get("标题", ""))
        if not key or key == ("", ""):
            continue
        days = parse_num(r.get("发布后天数"))
        rec = parse_date(r.get("记录日期"))
        order = (days if days is not None else -1, rec.isoformat() if rec else "", i)
        if key not in latest or order >= latest[key][0]:
            latest[key] = (order, r)
    return [v[1] for v in latest.values()]


def analyze(root, today=None):
    today = today or today_from(None)
    header, rows = read_csv(Path(root) / PUBLISH_CSV)
    if header is None:
        return None
    posts = []
    for r in latest_snapshots(rows):
        likes = parse_num(r.get("点赞"))
        posts.append(dict(title=r.get("标题", ""), platform=r.get("平台", ""), topic=r.get("选题类型") or "未标注",
                          form=r.get("形式") or "未标注", date=parse_date(r.get("发布日期")),
                          days=parse_num(r.get("发布后天数")), views=parse_num(r.get("播放")), likes=likes,
                          collect=parse_num(r.get("收藏")), fans=parse_num(r.get("涨粉")), url=r.get("链接", "")))
    with_likes = [p for p in posts if p["likes"] is not None]
    mature = [p for p in with_likes if (p["days"] or 0) >= 3]
    base_set = mature if mature else with_likes
    base = median([p["likes"] for p in base_set])
    for p in posts:
        p["mult"] = (p["likes"] / max(base, 1)) if (base and p["likes"] is not None) else None

    def group(field):
        g = defaultdict(list)
        for p in posts:
            if p["mult"] is not None:
                g[p[field]].append(p["mult"])
        return sorted(((k, len(v), median(v)) for k, v in g.items()), key=lambda x: -x[2])

    return dict(today=today, posts=posts, base=base, base_n=len(base_set), mature=bool(mature),
                by_topic=group("topic"), by_form=group("form"))


def render(res):
    L = [f"# 发布复盘（{res['today'].isoformat()}）", ""]
    n = len(res["posts"])
    if res["base"] is None:
        L.append(f"记录了 {n} 条内容，但还没有点赞数据。发布 3 天后告诉 AI 数据（链接、截图或直接说），再来复盘。")
        return "\n".join(L) + "\n"
    note = "（只用发布满 3 天的记录）" if res["mature"] else "（还没有发布满 3 天的记录，基线可能偏低）"
    L.append(f"共 {n} 条内容。你平时一条大约 **{fmt_num(res['base'])} 赞**，按 {res['base_n']} 条算{note}。")
    if n < MIN_POSTS:
        L.append(f"> 发布还不到 {MIN_POSTS} 条，倍数只能参考，多发几条再看规律。")
    L += ["", "## 每条是平时的几倍", "", "| 发布日期 | 标题 | 选题类型 | 形式 | 记录时发布第几天 | 点赞 | 平时的几倍 | 收藏 | 涨粉 |",
          "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for p in sorted(res["posts"], key=lambda p: -(p["mult"] or -1)):
        title = md_cell(p["title"], 30)
        link = f"[{title}]({p['url']})" if p["url"] else title
        mult = f"{p['mult']:.1f} 倍" if p["mult"] is not None else "—"
        d = p["date"].isoformat() if p["date"] else "—"
        L.append(f"| {d} | {link} | {p['topic']} | {p['form']} | {fmt_num(p['days'])} | {fmt_num(p['likes'])} | {mult} | "
                 f"{fmt_num(p['collect'])} | {fmt_num(p['fans'])} |")
    for title, rows in (("按选题类型", res["by_topic"]), ("按形式", res["by_form"])):
        L += ["", f"## {title}", "", "| 类别 | 条数 | 倍数中位数 |", "|---|---:|---:|"]
        for k, cnt, m in rows:
            L.append(f"| {k} | {cnt} | {m:.1f} 倍 |")
    L += ["", "下一步：对第 7 天的数据，和 AI 一起写一句「为什么」和「下次怎么做」；同一个原因出现两次以上，写进 09.我的方法论/我的爆款规则.md。", ""]
    return "\n".join(L)


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(description="自己账号的发布复盘")
    ap.add_argument("--root", required=True, help="知识库文件夹")
    ap.add_argument("--today", default=None, help="把哪天当作今天（测试用）")
    ap.add_argument("--stdout", action="store_true", help="只打印，不写文件")
    args = ap.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    res = analyze(root, today_from(args.today))
    if res is None:
        print(f"还没有发布记录：{PUBLISH_CSV.as_posix()} 不存在。发了内容后告诉 AI，它会登记。")
        return 1
    text = render(res)
    if args.stdout:
        print(text)
        return 0
    out = root / "07.发布与复盘" / f"复盘_{res['today'].strftime('%Y%m%d')}.md"
    out.write_text(text, encoding="utf-8")
    base = fmt_num(res["base"]) if res["base"] is not None else "暂无"
    print(f"已生成 {out.relative_to(root).as_posix()}：{len(res['posts'])} 条内容，平时一条约 {base} 赞。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
