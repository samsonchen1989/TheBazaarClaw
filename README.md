# 大巴扎（The Bazaar）构筑攻略

自动收集 [bazaardb.gg/run](https://bazaardb.gg/run) 的对局数据，每 2 小时自动更新，每天同步一次到 GitHub。

## 各英雄攻略

| 英雄 | 文件 |
|------|------|
| 卡诺克（Karnok） | [builds/builds_karnok.md](builds/builds_karnok.md) |
| 斯特尔（Stelle） | [builds/builds_stelle.md](builds/builds_stelle.md) |
| 朱尔斯（Jules） | [builds/builds_jules.md](builds/builds_jules.md) |
| 麦克（Mak） | [builds/builds_mak.md](builds/builds_mak.md) |
| 瓦内莎（Vanessa） | [builds/builds_vanessa.md](builds/builds_vanessa.md) |
| 杜利（Duli） | [builds/builds_duli.md](builds/builds_duli.md) |
| 皮格马利翁（Pygmalion） | [builds/builds_pygmalion.md](builds/builds_pygmalion.md) |

## 文件说明

| 文件 | 说明 |
|------|------|
| `builds/builds_<hero>.md` | 各英雄构筑攻略（按流派分类，含卡牌中文说明） |
| `bazaar_runs.json` | 本地对局数据库（增量累积） |
| `bazaar_update.py` | 自动更新脚本 |

## 数据来源

- 对局数据：[bazaardb.gg](https://bazaardb.gg/run)（仅收录 Gold/Perfect 胜利，胜场 ≥ 8）
- 卡牌翻译 & 效果：[BazaarHelper](https://github.com/Duangi/BazaarHelper) 数据库

## 自动更新

由 OpenClaw 定时任务驱动，每 2 小时抓取最新对局并重新生成攻略，每天同步一次到 GitHub。
