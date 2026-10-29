"""creator-brain 脚本共用的小工具：读写 CSV、解析数字、中位数、选题分类。只用标准库。"""
import csv
import json
import re
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

WORKS_CSV = Path("02.对标库") / "数据" / "作品.csv"
WORKS_HEADER = ["平台", "账号", "账号链接", "粉丝", "作品标题", "发布日期", "点赞", "收藏", "评论", "分享",
                "是否置顶", "作品链接", "记录日期", "数据来源"]
PUBLISH_CSV = Path("07.发布与复盘") / "发布记录.csv"
PUBLISH_HEADER = ["发布日期", "平台", "标题", "选题类型", "形式", "链接", "记录日期", "发布后天数", "播放", "点赞",
                  "收藏", "评论", "分享", "涨粉", "备注"]
TOPICS_JSON = Path("system") / "选题分类.json"

# 没有 system/选题分类.json 时用这份
DEFAULT_TOPICS = {
    "第一件事 / 避坑": ["第一件事", "避坑", "踩坑", "千万别", "别再", "不要再", "后悔"],
    "清单推荐": ["必装", "必备", "神器", "推荐", "清单", "合集", "宝藏", r"(?<!第)\d+\s*个", "(?<!第)[一二两三四五六七八九十]个"],
    "新手入门教程": ["零基础", "保姆级", "入门", "速通", "手把手", "新手", "小白", "教程", "从0到1", "从零"],
    "技巧方法": ["技巧", "方法", "秘诀", "一招", "一句话", "提示词", "指令", "公式", "模板"],
    "对比测评": ["对比", "测评", "实测", "横评", "哪个好", r"\bvs\b", "PK"],
    "赚钱副业": ["赚钱", "副业", "月入", "变现", "搞钱", "收入"],
    "经历案例": ["我用", "我做了", "我花了", "经历", "复盘", "记录"],
    "资讯热点": ["发布", "更新", "来了", "最新", "刚刚", "重磅"],
    "观点认知": ["为什么", "真相", "认知", "本质", "思考", "底层逻辑"],
}
OTHER = "其他"


def utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def read_csv(path):
    """读 CSV，返回 (表头, 行字典列表)；文件不存在返回 (None, [])。"""
    path = Path(path)
    if not path.exists():
        return None, []
    with open(path, encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        rows = [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in reader]
        return [h.strip() for h in (reader.fieldnames or [])], rows


def parse_num(text):
    """'1.2万' → 12000，'10w+' → 100000，'3,456' → 3456；空或读不出返回 None。"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("，", "").rstrip("+").strip()
    if not s:
        return None
    mult = 1
    if s[-1] in "万wW":
        mult, s = 10000, s[:-1]
    elif s[-1] == "亿":
        mult, s = 100000000, s[:-1]
    elif s[-1] in "千kK":
        mult, s = 1000, s[:-1]
    try:
        return round(float(s) * mult)
    except ValueError:
        return None


def parse_date(text):
    """支持 2026-10-05 / 2026/10/5 / 2026.10.05 / 20261005；读不出返回 None。"""
    if not text:
        return None
    s = str(text).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def load_topics(root):
    """读知识库里的选题分类（关键词可以是普通词，也可以是正则），返回 [(类型, 编译后的正则)]。"""
    path = Path(root) / TOPICS_JSON
    cats = DEFAULT_TOPICS
    if path.exists():
        try:
            data = json.loads(path.read_text("utf-8-sig"))
            if isinstance(data, dict) and data:
                cats = data
        except json.JSONDecodeError:
            print(f"提示：{TOPICS_JSON} 格式不对，先用默认分类", file=sys.stderr)
    out = []
    for name, words in cats.items():
        parts = []
        for w in words:
            try:
                re.compile(w)
                parts.append(w)
            except re.error:
                parts.append(re.escape(w))
        if parts:
            out.append((name, re.compile("|".join(parts), re.I)))
    return out


def classify(title, topics):
    """先看话题标签之前的正文，没命中再看全文；都没命中归"其他"。"""
    head = (title or "").split("#")[0]
    for text in (head, title or ""):
        for name, rx in topics:
            if rx.search(text):
                return name
    return OTHER


def fmt_num(n):
    if n is None:
        return "—"
    return f"{n / 10000:.1f}万" if n >= 10000 else f"{int(round(n))}"


def today_from(arg):
    return parse_date(arg) if arg else date.today()


def md_cell(text, limit=40):
    s = (text or "").replace("\n", " ").replace("|", "｜").strip()
    return s[:limit] + ("…" if len(s) > limit else "")
