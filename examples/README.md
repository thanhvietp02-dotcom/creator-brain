# 示例数据

这两份是**虚构的示例数据**，账号和数字都是编的，只用来试用脚本和跑测试。

- `作品.csv`：6 个示例对标号的作品数据，格式和知识库里的 `02.对标库/数据/作品.csv` 一样。
- `发布记录.csv`：一个示例账号 6 条内容的发布数据，格式和 `07.发布与复盘/发布记录.csv` 一样。

试用方法：建好一个知识库后，把这两个文件复制到对应位置，再运行：

```bash
python skills/creator-brain/scripts/viral_score.py --root "<知识库>" --today 2026-10-29 --stdout
python skills/creator-brain/scripts/retro.py --root "<知识库>" --today 2026-10-29 --stdout
```

示例数据是按 2026-10-29 生成的，所以加了 `--today 2026-10-29`。
