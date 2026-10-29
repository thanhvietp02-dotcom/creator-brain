---
name: creator-brain
description: 自媒体内容大脑：在本地搭一个给 AI 用的自媒体知识库，并用数据帮你找对标、挑选题、写脚本、发布前检查、发布后复盘、做私域引流。用户说"搭自媒体知识库""建内容库""帮我找对标/拆对标""这个号平时多少赞""哪些选题容易爆""帮我挑选题""写口播脚本""发布前帮我检查""记一下这条的数据/复盘""怎么引流到私域""知识库健康检查"，或给出抖音/小红书/视频号/B站的主页或视频链接、数据截图时使用。适用于 Claude Code、Codex、WorkBuddy 等能读写本地文件的 AI。
---

# creator-brain：自媒体内容大脑

把一个本地文件夹变成做自媒体的"第二大脑"：资料有地方放，对标有数据，选题有依据，发出去的每一条都有复盘，经验越用越多。全部是普通 Markdown 和 CSV 文件，存在用户自己电脑上。

## 先找到知识库

1. 当前目录或用户给的路径里有 `AGENTS.md` 且其中写着 `creator-brain`：这就是知识库，先读它和 `INDEX.md`。
2. 没有：进入「搭建」，读 [setup.md](references/setup.md)。
3. 当前目录是用户主目录、磁盘根目录、下载目录：不要在这里建库，请用户指定一个文件夹。

任何操作前先读 [principles.md](references/principles.md)，里面是所有模块都要守的规则。

## 用户要做什么 → 读哪份说明

| 用户的话（举例） | 模块 | 说明 |
|---|---|---|
| 搭知识库、把这个文件夹变成内容库、我是新手从哪开始 | 搭建 | [setup.md](references/setup.md) |
| 这份资料/文章/逐字稿帮我存进去、整理一下收件箱 | 资料接入 | [ingest.md](references/ingest.md) |
| 帮我找对标、看看这个号、这是他主页的截图 | 对标 | [benchmark.md](references/benchmark.md) |
| 哪些选题容易爆、帮我挑选题、这个选题能做吗 | 选题 | [topics.md](references/topics.md) |
| 帮我写脚本、写口播、改得更像人说话 | 脚本 | [script.md](references/script.md) |
| 发布前帮我检查、这个标题会不会违规 | 发布前检查 | [precheck.md](references/precheck.md) |
| 我发了、记一下数据、这条为什么没火、复盘 | 发布与复盘 | [publish-retro.md](references/publish-retro.md) |
| 怎么引流、怎么加粉丝群、免费资料怎么送 | 私域引流 | [private-traffic.md](references/private-traffic.md) |
| 我之前记过 XX 吗、根据我的库回答 | 提问 | [query.md](references/query.md) |
| 检查一下知识库、有没有乱掉 | 健康检查 | [health.md](references/health.md) |

一句话里有多件事时，按"搭建 → 接入 → 对标 → 选题 → 脚本 → 检查 → 发布复盘"的顺序做，每做完一步告诉用户结果再继续。

## 必须停下来等用户点头的 5 个时刻

1. 搭建或改动目录结构之前（先给预览）。
2. 选题方向确定之前。
3. 标题和开头定稿之前。
4. 脚本终稿之前。
5. 任何会对外发出的动作之前（发布、私信、评论）。本 Skill 不代替用户发布任何内容。

## 脚本

脚本在本 Skill 的 `scripts/` 目录，只用 Python 标准库（3.9+）。从 Skill 目录调用，或用绝对路径调用；`--root` 永远指向用户的知识库，不是 Skill 目录。

| 脚本 | 做什么 |
|---|---|
| `init_vault.py --root <库> --name <名字> [--apply]` | 建知识库骨架；不加 `--apply` 只预览；已有文件一律不覆盖 |
| `viral_score.py --root <库> [--days 45]` | 读对标数据，算每个号平时一条多少赞、每条是平时的几倍、哪些选题被多个号反复做爆 |
| `retro.py --root <库>` | 读自己的发布记录，算自己的基线和每条的倍数 |
| `health_check.py --root <库> [--save-state]` | 只读检查断链、孤立笔记、积压、重复终稿、疑似密钥文件 |
| `search.py --root <库> "关键词"` | 本地全文检索，返回 文件:行号 |

Windows 上如果 `python3` 不可用就用 `python`。脚本输出里文件路径都是相对知识库根目录的。
