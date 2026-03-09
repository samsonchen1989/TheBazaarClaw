# 大巴扎（The Bazaar）构筑攻略

自动收集 [bazaardb.gg/run](https://bazaardb.gg/run) 的对局数据，每 2 小时自动更新。

## 文件说明

| 文件 | 说明 |
|------|------|
| `bazaar_builds.md` | 最新构筑攻略（按英雄 / 流派分类，含卡牌中文说明） |
| `bazaar_runs.json` | 本地对局数据库（增量累积） |
| `bazaar_update.py` | 自动更新脚本 |

## 数据来源

- 对局数据：[bazaardb.gg](https://bazaardb.gg/run)（仅收录 Gold/Perfect 胜利，胜场 ≥ 8）
- 卡牌翻译 & 效果：[BazaarHelper](https://github.com/Duangi/BazaarHelper) 数据库

## 自动更新

由 OpenClaw 定时任务驱动，每 2 小时抓取最新对局并重新生成攻略。
