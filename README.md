# The Bazaar 构筑攻略数据库

> 基于 [bazaardb.gg](https://bazaardb.gg) 的高胜场对局数据，自动生成的构筑攻略。

---

## 📊 数据统计

- **总对局数**：1346 场（Gold/Perfect，≥8 胜）
- **数据来源**：bazaardb.gg/run
- **更新频率**：每 2 小时自动抓取
- **最后更新**：2026-03-17

---

## 📚 英雄攻略

### 完整攻略（流派分类）

| 英雄 | 对局数 | 流派数 | 攻略文件 |
|------|--------|--------|----------|
| 🦅 卡诺克（Karnok） | 576 | 7 | [查看攻略](./builds/karnok/builds_karnok.md) |

### 简化攻略（Top 5 高胜场）

| 英雄 | 对局数 | 攻略文件 |
|------|--------|----------|
| 🤖 杜利（Duli） | 211 | [查看攻略](./builds/duli/builds_duli.md) |
| 🍰 朱尔斯（Jules） | 181 | [查看攻略](./builds/jules/builds_jules.md) |
| 🦇 凡妮莎（Vanessa） | 114 | [查看攻略](./builds/vanessa/builds_vanessa.md) |
| 🗡️ 麦克（Mak） | 110 | [查看攻略](./builds/mak/builds_mak.md) |
| 🎨 皮格马利翁（Pygmalien） | 87 | [查看攻略](./builds/pygmalion/builds_pygmalion.md) |
| ⭐ 史黛拉（Stelle） | 67 | [查看攻略](./builds/stelle/builds_stelle.md) |

---

## 📂 目录结构

```
TheBazaarClaw/
├── README.md                    # 本文件
├── bazaar_runs.json             # 原始对局数据（1346 场）
├── bazaar_update.py             # 数据抓取和攻略生成脚本
├── items_db.json                # 卡牌数据库（1071 张卡）
├── skills_db.json               # 技能数据库（478 个技能）
└── builds/                      # 攻略文件目录
    ├── GUIDE_RULES.md           # 攻略生成规则（通用）
    ├── karnok/
    │   ├── README.md            # 卡诺克流派定义
    │   └── builds_karnok.md     # 卡诺克完整攻略
    ├── duli/
    │   ├── README.md            # 杜利说明文件（待补充）
    │   └── builds_duli.md       # 杜利简化攻略
    ├── jules/
    │   ├── README.md            # 朱尔斯说明文件（待补充）
    │   └── builds_jules.md      # 朱尔斯简化攻略
    ├── mak/
    │   ├── README.md            # 麦克说明文件（待补充）
    │   └── builds_mak.md        # 麦克简化攻略
    ├── pygmalion/
    │   ├── README.md            # 皮格马利翁说明文件（待补充）
    │   └── builds_pygmalion.md  # 皮格马利翁简化攻略
    ├── stelle/
    │   ├── README.md            # 史黛拉说明文件（待补充）
    │   └── builds_stelle.md     # 史黛拉简化攻略
    └── vanessa/
        ├── README.md            # 凡妮莎说明文件（待补充）
        └── builds_vanessa.md    # 凡妮莎简化攻略
```

---

## 🎯 卡诺克流派说明（示例）

卡诺克完整攻略包含 7 个流派，共 33 场对局：

1. **霰弹枪流**（53 场对局 → 输出 5 场）
   - 核心卡：霰弹枪
   - 机制：快速装填+多重释放，爆发输出

2. **减速流**（43 场对局 → 输出 5 场）
   - 核心卡：锁链、雾菇、夜视仪、帐篷、猎人之靴
   - 机制：主动/被动减速触发增益

3. **盾击流**（26 场对局 → 输出 5 场）
   - 核心卡：野猪、喀斯特、弹力裤
   - 机制：护盾转化伤害

4. **防御反击流**（4 场对局 → 输出 4 场）
   - 核心卡：捕兽夹
   - 机制：受击反伤

5. **灼烧流**（38 场对局 → 输出 5 场）
   - 核心卡：灼烧疤痕、烽火台、喷泉
   - 机制：持续伤害

6. **毒流**（4 场对局 → 输出 4 场）
   - 核心卡：蚺蛇、蛙鸣洞穴、陷阱藤
   - 机制：中毒叠加

7. **飞行流**（408 场对局 → 输出 5 场）
   - 辅助卡：飞鼠、猎鹰、信使麻雀
   - 机制：通用构筑（兜底流派）

---

## 📖 攻略格式说明

### 完整攻略（卡诺克）

每个流派包含：
- **对局信息**：玩家名、胜场、对局链接
- **卡牌列表**：保留原始顺序（A | B | C | ...）
- **技能列表**：中文技能名（技能1、技能2、...）
- **卡牌详情**：每张卡的中英文名、大小、技能描述

### 简化攻略（其他英雄）

- **Top 5 高胜场对局**
- 包含完整的对局信息和卡牌详情
- 暂无流派分类（待补充 README.md 说明文件）

---

## 🔧 使用方法

### 手动更新数据

```bash
# 抓取新对局并更新攻略
python3 bazaar_update.py --fetch

# 推送到 GitHub（每天一次）
python3 bazaar_update.py --push

# 强制推送（忽略频率限制）
python3 bazaar_update.py --force-push
```

### 自动更新（Cron）

脚本会每 2 小时自动运行 `--fetch`，抓取新对局并更新攻略文件。

---

## 📋 数据来源

- **对局数据**：[bazaardb.gg/run](https://bazaardb.gg/run)
- **卡牌数据**：[duang.work/tools](https://www.duang.work/tools)（中文卡牌库）
- **技能数据**：[BazaarHelper](https://github.com/Duangi/BazaarHelper)

---

## 📝 贡献指南

### 补充英雄说明文件

如果你想为某个英雄添加流派定义，请编辑对应的 `builds/{hero}/README.md` 文件，参考 [卡诺克说明文件](./builds/karnok/README.md)。

### 提交 PR

1. Fork 本仓库
2. 创建分支：`git checkout -b feature/hero-guides`
3. 编辑 `builds/{hero}/README.md`
4. 提交：`git commit -m "添加 XXX 英雄流派说明"`
5. 推送：`git push origin feature/hero-guides`
6. 创建 Pull Request

---

## 📜 许可证

本项目数据来源于公开网站，仅供学习交流使用。

---

## 🔗 相关链接

- [The Bazaar 官网](https://playthebazaar.com/)
- [bazaardb.gg](https://bazaardb.gg) - 对局数据库
- [duang.work](https://www.duang.work/tools) - 中文卡牌库
- [BazaarHelper](https://github.com/Duangi/BazaarHelper) - 游戏辅助工具

---

**最后更新**：2026-03-17 16:05  
**维护者**：samsonschen
