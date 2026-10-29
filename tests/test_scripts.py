"""creator-brain 脚本测试。运行：python -m unittest discover tests"""
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "creator-brain" / "scripts"
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402
import health_check  # noqa: E402
import init_vault  # noqa: E402
import retro  # noqa: E402
import search  # noqa: E402
import viral_score  # noqa: E402

TODAY = date(2026, 10, 29)


def run(fn, *args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(list(args))
    return code, buf.getvalue()


class VaultCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb_test_"))
        self.vault = self.tmp / "我的知识库"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_vault(self):
        code, _ = run(init_vault.main, "--root", str(self.vault), "--name", "测试号", "--apply", "--date", "2026-10-29")
        self.assertEqual(code, 0)


class TestCommon(unittest.TestCase):
    def test_parse_num(self):
        self.assertEqual(_common.parse_num("1.2万"), 12000)
        self.assertEqual(_common.parse_num("10w+"), 100000)
        self.assertEqual(_common.parse_num("3,456"), 3456)
        self.assertEqual(_common.parse_num("2k"), 2000)
        self.assertIsNone(_common.parse_num(""))
        self.assertIsNone(_common.parse_num("很多"))

    def test_parse_date(self):
        self.assertEqual(_common.parse_date("2026/10/5"), date(2026, 10, 5))
        self.assertEqual(_common.parse_date("2026.10.05"), date(2026, 10, 5))
        self.assertIsNone(_common.parse_date("三天前"))

    def test_classify(self):
        topics = [(n, __import__("re").compile("|".join(w))) for n, w in [("清单推荐", ["必装"]), ("新手入门教程", ["零基础"])]]
        self.assertEqual(_common.classify("5个必装神器 #零基础", topics), "清单推荐")
        self.assertEqual(_common.classify("随便聊聊 #零基础", topics), "新手入门教程")  # 正文没命中再看全文
        self.assertEqual(_common.classify("随便聊聊", topics), _common.OTHER)


class TestInitVault(VaultCase):
    def test_preview_writes_nothing(self):
        code, out = run(init_vault.main, "--root", str(self.vault), "--name", "测试号")
        self.assertEqual(code, 0)
        self.assertIn("预览", out)
        self.assertFalse(self.vault.exists())

    def test_apply_creates_and_fills_placeholders(self):
        self.make_vault()
        agents = (self.vault / "AGENTS.md").read_text("utf-8")
        self.assertIn("测试号", agents)
        self.assertNotIn("{{", agents)
        self.assertIn("2026-10-29", (self.vault / "system" / "日志.md").read_text("utf-8"))
        self.assertTrue((self.vault / "02.对标库" / "数据" / "作品.csv").exists())

    def test_never_overwrites(self):
        self.vault.mkdir(parents=True)
        (self.vault / "AGENTS.md").write_text("我自己的规则", encoding="utf-8")
        (self.vault / "我的旧笔记.md").write_text("旧内容", encoding="utf-8")
        self.make_vault()
        self.assertEqual((self.vault / "AGENTS.md").read_text("utf-8"), "我自己的规则")
        self.assertEqual((self.vault / "我的旧笔记.md").read_text("utf-8"), "旧内容")
        code, out = run(init_vault.main, "--root", str(self.vault), "--apply")
        self.assertIn("新建 0 个文件夹、0 个文件", out)

    def test_refuses_home(self):
        code, _ = run(init_vault.main, "--root", str(Path.home()))
        self.assertEqual(code, 2)


class TestViralScore(VaultCase):
    def test_no_data(self):
        self.vault.mkdir()
        code, out = run(viral_score.main, "--root", str(self.vault))
        self.assertEqual(code, 1)
        self.assertIn("还没有对标数据", out)

    def test_header_only(self):
        self.make_vault()
        code, out = run(viral_score.main, "--root", str(self.vault), "--today", "2026-10-29", "--stdout")
        self.assertEqual(code, 0)
        self.assertIn("暂无达到标准的爆款", out)

    def test_examples(self):
        self.make_vault()
        shutil.copy(EXAMPLES / "作品.csv", self.vault / "02.对标库" / "数据" / "作品.csv")
        res = viral_score.analyze(self.vault, days=45, mult_min=5, likes_min=3000, today=TODAY)
        topics = {t["topic"]: t for t in res["topics"]}
        # 示例里 4 个号在近 30 天做爆了入门教程，应当被推荐
        self.assertIn("新手入门教程", topics)
        self.assertGreaterEqual(topics["新手入门教程"]["accounts"], 4)
        self.assertTrue(topics["新手入门教程"]["strong"])
        # 60 天前的副业爆款不在 45 天窗口里
        self.assertNotIn("赚钱副业", topics)
        # 置顶的老爆款不应拉高"平时一条"
        acc = {a["acc"]: a for a in res["accounts"]}["示例号-设计师日常"]
        self.assertLess(acc["med"], 8000)
        code, out = run(viral_score.main, "--root", str(self.vault), "--today", "2026-10-29")
        self.assertEqual(code, 0)
        self.assertTrue((self.vault / "02.对标库" / "选题验证_20261029.md").exists())

    def test_few_works_no_multiple(self):
        self.make_vault()
        p = self.vault / "02.对标库" / "数据" / "作品.csv"
        with open(p, "a", encoding="utf-8", newline="") as fp:
            for i in range(3):
                fp.write(f"抖音,小号,,1000,零基础教程{i},2026-10-20,90000,1,1,1,否,,2026-10-29,口述\n")
        res = viral_score.analyze(self.vault, today=TODAY)
        self.assertIsNone(res["accounts"][0]["med"])
        self.assertEqual(res["hits"], [])

    def test_latest_record_wins(self):
        self.make_vault()
        p = self.vault / "02.对标库" / "数据" / "作品.csv"
        with open(p, "a", encoding="utf-8", newline="") as fp:
            fp.write("抖音,号,,1000,标题,2026-10-20,100,1,1,1,否,https://x/1,2026-10-21,截图\n")
            fp.write("抖音,号,,1000,标题,2026-10-20,900,1,1,1,否,https://x/1,2026-10-28,截图\n")
        _, rows = viral_score.load_works(self.vault)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["点赞"], "900")


class TestRetro(VaultCase):
    def test_no_file(self):
        self.vault.mkdir()
        code, out = run(retro.main, "--root", str(self.vault))
        self.assertEqual(code, 1)

    def test_header_only(self):
        self.make_vault()
        code, out = run(retro.main, "--root", str(self.vault), "--stdout", "--today", "2026-10-29")
        self.assertEqual(code, 0)
        self.assertIn("还没有点赞数据", out)

    def test_examples(self):
        self.make_vault()
        shutil.copy(EXAMPLES / "发布记录.csv", self.vault / "07.发布与复盘" / "发布记录.csv")
        res = retro.analyze(self.vault, TODAY)
        self.assertEqual(len(res["posts"]), 6)            # 同一条记两次只算最新一次
        self.assertTrue(res["mature"])                     # 只用发布满 3 天的算基线
        best = max(res["posts"], key=lambda p: p["mult"])
        self.assertEqual(best["topic"], "新手入门教程")
        self.assertEqual(res["by_form"][0][0], "深度教程")


class TestHealth(VaultCase):
    def test_fresh_vault_is_clean(self):
        self.make_vault()
        res = health_check.check(self.vault)
        self.assertEqual(res["issues"], [], res["issues"])

    def test_detects_problems(self):
        self.make_vault()
        (self.vault / "05.选题池" / "孤儿.md").write_text("链接到 [[不存在的笔记]]", encoding="utf-8")
        (self.vault / "06.内容生产" / "定稿" / "脚本最终版.md").write_text("a", encoding="utf-8")
        (self.vault / "06.内容生产" / "定稿" / "脚本最终版2.md").write_text("b", encoding="utf-8")
        (self.vault / ".env").write_text("SECRET=1", encoding="utf-8")
        old = self.vault / "00.收件箱" / "旧资料.txt"
        old.write_text("x", encoding="utf-8")
        t = time.time() - 10 * 86400
        os.utime(old, (t, t))
        with open(self.vault / "02.对标库" / "数据" / "作品.csv", "a", encoding="utf-8") as fp:
            fp.write("抖音,号,,很多,标题,2026-10-20,一万,1,1,1,否,,2026-10-29,口述\n")
        kinds = {i["kind"] for i in health_check.check(self.vault)["issues"]}
        for k in ("断链", "孤立笔记", "重复终稿", "疑似敏感文件", "收件箱积压", "数据读不出数字"):
            self.assertIn(k, kinds)

    def test_save_state(self):
        self.make_vault()
        run(health_check.main, "--root", str(self.vault), "--save-state")
        self.assertTrue((self.vault / "system" / "健康状态.json").exists())


class TestSearch(VaultCase):
    def test_search(self):
        self.make_vault()
        (self.vault / "04.素材库" / "知识库案例.md").write_text("第一行\n搭个人知识库的三个坑\n", encoding="utf-8")
        hits = search.search(self.vault, "知识库")
        self.assertTrue(hits)
        self.assertEqual(hits[0][1], "04.素材库/知识库案例.md")
        partial = search.search(self.vault, "个人知识")   # 拆成两字一组也能找到
        self.assertTrue(any(h[1] == "04.素材库/知识库案例.md" for h in partial))

    def test_no_hit(self):
        self.make_vault()
        code, out = run(search.main, "--root", str(self.vault), "完全不存在的词zzz")
        self.assertIn("没有找到", out)


if __name__ == "__main__":
    unittest.main()
