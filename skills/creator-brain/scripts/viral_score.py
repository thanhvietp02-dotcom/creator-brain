"""读对标作品数据，算每个号平时一条多少赞、每条是平时的几倍，找出被多个号反复做爆的选题类型。

爆款倍数 = 这条点赞 ÷ 这个号平时一条的点赞（非置顶作品点赞的中位数）。作品少于 8 条的号算不准，不给倍数。

用法：
  python viral_score.py --root "D:/我的自媒体"                 # 近 45 天，写报告到 02.对标库/选题验证_日期.md
  python viral_score.py --root "D:/我的自媒体" --days 30 --stdout
"""
import argparse
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (OTHER, WORKS_CSV, WORKS_HEADER, classify, fmt_num, load_topics, md_cell, median,  # noqa: E402
                     parse_date, parse_num, read_csv, today_from, utf8_stdout)

MIN_WORKS = 8          # 少于这么多条作品的号不算倍数
SMALL_FANS = 50000     # 粉丝少于这个算"小号"
STRONG_ACCOUNTS = 4    # 推荐选题至少几个号做爆过
RECENT_DAYS = 30       # 推荐选题最近一次爆款要在几天内


def load_works(root):
    """读作品表；同一条作品记过多次只留最近一次记录。"""
    header, rows = read_csv(Path(root) / WORKS_CSV)
    if header is None:
        return None, []
    missing = [h for h in ("账号", "作品标题", "点赞") if h not in header]
    if missing:
        raise ValueError(f"作品表缺少列：{'、'.join(missing)}（标准表头见 benchmark.md）")
    latest = {}
    for i, r in enumerate(rows):
        key = (r.get("账号", ""), r.get("作品链接") or r.get("作品标题", ""))
        rec = parse_date(r.get("记录日期")) or parse_date("1970-01-01")
        if key not in latest or (rec, i) >= latest[key][0]:
            latest[key] = ((rec, i), r)
    return header, [v[1] for v in latest.values()]


def analyze(root, days=45, mult_min=5.0, likes_min=3000, today=None):
    today = today or today_from(None)
    _, rows = load_works(root)
    topics = load_topics(root)
    by_acc = defaultdict(list)
    for r in rows:
        if r.get("账号"):
            by_acc[r["账号"]].append(r)

    accounts, works = [], []
    for acc, items in by_acc.items():
        fans = None
        for r in sorted(items, key=lambda x: parse_date(x.get("记录日期")) or today):
            fans = parse_num(r.get("粉丝")) or fans
        likes_all = [parse_num(r.get("点赞")) for r in items]
        normal = [parse_num(r.get("点赞")) for r in items if r.get("是否置顶", "") not in ("是", "1", "true", "True")]
        normal = [x for x in normal if x is not None]
        med = median(normal) if len(normal) >= MIN_WORKS else None
        acc_works = []
        for r in items:
            likes = parse_num(r.get("点赞"))
            if likes is None:
                continue
            collect = parse_num(r.get("收藏"))
            w = dict(acc=acc, platform=r.get("平台", ""), fans=fans, title=r.get("作品标题", ""),
                     date=parse_date(r.get("发布日期")), likes=likes, collect=collect,
                     save=(collect / likes) if (collect is not None and likes) else None,
                     mult=(likes / max(med, 50)) if med is not None else None,
                     url=r.get("作品链接", ""), topic=classify(r.get("作品标题", ""), topics))
            acc_works.append(w)
        works.extend(acc_works)
        mults = [w["mult"] for w in acc_works if w["mult"] is not None]
        accounts.append(dict(acc=acc, platform=items[0].get("平台", ""), fans=fans, n=len([x for x in likes_all if x is not None]),
                             med=med, top=max(mults) if mults else None))

    start = today - timedelta(days=days)
    in_window = [w for w in works if w["date"] and start <= w["date"] <= today]
    hits = [w for w in in_window if w["mult"] is not None and w["mult"] >= mult_min and w["likes"] >= likes_min]

    groups = defaultdict(list)
    for w in hits:
        groups[w["topic"]].append(w)
    topic_rows = []
    for name, ws in groups.items():
        accs = {w["acc"] for w in ws}
        last = max(w["date"] for w in ws)
        saves = [w["save"] for w in ws if w["save"] is not None]
        topic_rows.append(dict(topic=name, hits=len(ws), accounts=len(accs),
                               small=sum(1 for w in ws if w["fans"] is not None and w["fans"] < SMALL_FANS),
                               last=last, save=median(saves),
                               strong=name != OTHER and len(accs) >= STRONG_ACCOUNTS and (today - last).days <= RECENT_DAYS,
                               works=sorted(ws, key=lambda w: (w["date"], w["mult"]), reverse=True)))
    topic_rows.sort(key=lambda t: (t["strong"], t["accounts"], t["last"]), reverse=True)
    return dict(today=today, days=days, mult_min=mult_min, likes_min=likes_min, accounts=accounts,
                works=works, in_window=in_window, hits=hits, topics=topic_rows)


def render(res):
    t, L = res["today"], []
    L.append(f"# 选题验证报告（近 {res['days']} 天，{t.isoformat()}）")
    L.append("")
    counted = [a for a in res["accounts"] if a["med"] is not None]
    L.append(f"对标号 {len(res['accounts'])} 个，其中 {len(counted)} 个作品够 {MIN_WORKS} 条、能算倍数；"
             f"近 {res['days']} 天有发布日期的作品 {len(res['in_window'])} 条。")
    L.append(f"爆款标准：点赞是这个号平时一条的 **{res['mult_min']:g} 倍以上**，且点赞 ≥ {res['likes_min']}。共 **{len(res['hits'])} 条**。")
    L.append("")
    if len(counted) < 5:
        L.append(f"> 样本还少：能算倍数的号只有 {len(counted)} 个。至少 5 个号、每个 8 条以上作品，结论才比较可靠。")
        L.append("")

    L += ["## 选题验证", "",
          f"「推荐」= 至少 {STRONG_ACCOUNTS} 个号做爆过，且最近一次在 {RECENT_DAYS} 天内。", "",
          "| 推荐 | 选题类型 | 爆款条数 | 做爆的号数 | 小号也爆 | 最近一次 | 收藏/点赞 |",
          "|---|---|---:|---:|---:|---|---:|"]
    for tr in res["topics"]:
        save = f"{tr['save']:.2f}" if tr["save"] is not None else "—"
        L.append(f"| {'✅' if tr['strong'] else ''} | {tr['topic']} | {tr['hits']} | {tr['accounts']} | {tr['small']} | "
                 f"{tr['last'].isoformat()} | {save} |")
    if not res["topics"]:
        L.append("| | 暂无达到标准的爆款 | | | | | |")
    L.append("")

    L += ["## 每类选题的爆款（按日期从新到旧）", ""]
    for tr in res["topics"]:
        L += [f"### {tr['topic']}（{tr['hits']} 条，{tr['accounts']} 个号）", "",
              "| 日期 | 账号 | 粉丝 | 作品 | 点赞 | 平时的几倍 | 收藏/点赞 |", "|---|---|---:|---|---:|---:|---:|"]
        for w in tr["works"]:
            title = md_cell(w["title"].split("#")[0] or w["title"], 30)
            link = f"[{title}]({w['url']})" if w["url"] else title
            save = f"{w['save']:.2f}" if w["save"] is not None else "—"
            L.append(f"| {w['date'].isoformat()} | {md_cell(w['acc'], 16)} | {fmt_num(w['fans'])} | {link} | "
                     f"{fmt_num(w['likes'])} | {w['mult']:.0f} 倍 | {save} |")
        L.append("")

    L += ["## 对标号一览", "", "| 账号 | 平台 | 粉丝 | 记录作品数 | 平时一条（中位数） | 最高倍数 |", "|---|---|---:|---:|---:|---:|"]
    for a in sorted(res["accounts"], key=lambda a: -(a["top"] or 0)):
        med = fmt_num(a["med"]) if a["med"] is not None else f"作品不足 {MIN_WORKS} 条"
        top = f"{a['top']:.0f} 倍" if a["top"] is not None else "—"
        L.append(f"| {md_cell(a['acc'], 16)} | {a['platform']} | {fmt_num(a['fans'])} | {a['n']} | {med} | {top} |")
    L += ["", "说明：选题类型按标题关键词自动分类（规则在 system/选题分类.json），会有少量误差；"
          "平时只有几十赞的号偶尔一条爆了，倍数会非常大，看「做爆的号数」和「收藏/点赞」比只看倍数更可靠。", ""]
    return "\n".join(L)


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(description="对标作品爆款倍数和选题验证")
    ap.add_argument("--root", required=True, help="知识库文件夹")
    ap.add_argument("--days", type=int, default=45, help="只看最近多少天发布的作品（默认 45）")
    ap.add_argument("--mult", type=float, default=5.0, help="爆款倍数门槛（默认 5）")
    ap.add_argument("--min-likes", type=int, default=3000, help="爆款点赞下限（默认 3000）")
    ap.add_argument("--today", default=None, help="把哪天当作今天，默认真实今天（测试用）")
    ap.add_argument("--stdout", action="store_true", help="只打印，不写文件")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not (root / WORKS_CSV).exists():
        print(f"还没有对标数据：{WORKS_CSV.as_posix()} 不存在。先给 AI 几个对标号的链接或截图，让它记录。")
        return 1
    try:
        res = analyze(root, args.days, args.mult, args.min_likes, today_from(args.today))
    except ValueError as e:
        print(e)
        return 1
    text = render(res)
    if args.stdout:
        print(text)
        return 0
    out = root / "02.对标库" / f"选题验证_{res['today'].strftime('%Y%m%d')}.md"
    out.write_text(text, encoding="utf-8")
    strong = [t["topic"] for t in res["topics"] if t["strong"]]
    print(f"已生成 {out.relative_to(root).as_posix()}：{len(res['accounts'])} 个号，近 {args.days} 天爆款 {len(res['hits'])} 条。")
    print("推荐的选题类型：" + ("、".join(strong) if strong else "暂无（样本不够或近期没有被多个号做爆的类型）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
