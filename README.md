# The Bazaar 构筑攻略数据库

> 基于 [bazaardb.gg](https://bazaardb.gg) 的高胜场对局数据，自动生成的构筑攻略。

---

## 📊 数据统计

- **总对局数**：1692 场（Gold/Perfect，≥8 胜）
- **数据来源**：bazaardb.gg/run
- **更新频率**：每 2 小时自动抓取
- **最后更新**：2026-03-18

---

## 📚 英雄攻略

| 英雄 | 对局数 | 攻略文件 |
|------|--------|----------|
| 🦅 卡诺克（Karnok） | 576+ | [查看攻略](./builds/karnok/builds_karnok.md) |
| 🤖 杜利（Duli） | 211+ | [查看攻略](./builds/duli/builds_duli.md) |
| 🍰 朱尔斯（Jules） | 181+ | [查看攻略](./builds/jules/builds_jules.md) |
| 🦇 凡妮莎（Vanessa） | 114+ | [查看攻略](./builds/vanessa/builds_vanessa.md) |
| 🗡️ 麦克（Mak） | 110+ | [查看攻略](./builds/mak/builds_mak.md) |
| 🎨 皮格马利翁（Pygmalien） | 87+ | [查看攻略](./builds/pygmalion/builds_pygmalion.md) |
| ⭐ 史黛拉（Stelle） | 67+ | [查看攻略](./builds/stelle/builds_stelle.md) |

---

## 📂 目录结构

```
TheBazaarClaw/
├── README.md                    # 本文件
├── bazaar_runs.json             # 原始对局数据
├── bazaar_update.py             # 数据抓取和攻略生成脚本
├── items_db.json                # 卡牌数据库（1071 张卡）
├── skills_db.json               # 技能数据库（478 个技能）
└── builds/                      # 攻略文件目录
    ├── GUIDE_RULES.md           # 攻略生成规则
    ├── karnok/
    │   ├── README.md            # 卡诺克流派定义
    │   └── builds_karnok.md     # 卡诺克攻略
    ├── duli/
    ├── jules/
    ├── mak/
    ├── pygmalion/
    ├── stelle/
    └── vanessa/
```

---

## 📋 数据来源

- **对局数据**：[bazaardb.gg/run](https://bazaardb.gg/run)
- **卡牌数据**：[duang.work/tools](https://www.duang.work/tools)（中文卡牌库）
- **技能数据**：[BazaarHelper](https://github.com/Duangi/BazaarHelper)

---

## 🔗 相关链接

- [The Bazaar 官网](https://playthebazaar.com/)
- [bazaardb.gg](https://bazaardb.gg) - 对局数据库
- [duang.work](https://www.duang.work/tools) - 中文卡牌库
- [BazaarHelper](https://github.com/Duangi/BazaarHelper) - 游戏辅助工具

---

**最后更新**：2026-03-18 14:29  
**维护者**：samsonschen
