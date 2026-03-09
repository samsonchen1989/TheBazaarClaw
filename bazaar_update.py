#!/usr/bin/env python3
"""
大巴扎（The Bazaar）构筑攻略自动更新脚本
- 从 bazaardb.gg/run 抓取最新对局，增量保存到本地
- 根据全量本地数据生成攻略文档
- 卡牌翻译 & 效果来自 items_db.json
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# ──────────────────────────────
# 路径配置
# ──────────────────────────────
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
RUNS_FILE = os.path.join(WORKSPACE, "bazaar_runs.json")
BUILDS_FILE = os.path.join(WORKSPACE, "bazaar_builds.md")
ITEMS_DB = "/tmp/items_db.json"
ITEMS_DB_FALLBACK = os.path.join(WORKSPACE, "items_db.json")

# GitHub 同步配置（token 从 .env 或环境变量读取）
def _load_token():
    env_file = os.path.join(WORKSPACE, ".env")
    if os.path.exists(env_file):
        for line in open(env_file):
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("GITHUB_TOKEN", "")

GITHUB_TOKEN = _load_token()
GITHUB_REPO_BARE = "github.com/samsonchen1989/TheBazaarClaw.git"
REPO_DIR = "/tmp/TheBazaarClaw"

# ──────────────────────────────
# 加载 items_db
# ──────────────────────────────
def load_items_db():
    for path in [ITEMS_DB, ITEMS_DB_FALLBACK]:
        if os.path.exists(path):
            with open(path) as f:
                items = json.load(f)
            return {it["name_en"].strip(): it for it in items if it.get("name_en")}
    print("[WARN] items_db.json not found, downloading...")
    url = "https://raw.githubusercontent.com/Duangi/BazaarHelper/main/src-tauri/resources/items_db.json"
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "30", url, "-o", ITEMS_DB],
        capture_output=True
    )
    if r.returncode != 0 or not os.path.exists(ITEMS_DB):
        print("[ERROR] Failed to download items_db.json")
        return {}
    with open(ITEMS_DB) as f:
        items = json.load(f)
    return {it["name_en"].strip(): it for it in items if it.get("name_en")}

# ──────────────────────────────
# 抓取 bazaardb.gg/run
# ──────────────────────────────
def fetch_runs_page():
    """用 jina reader 抓取页面内容"""
    url = "https://r.jina.ai/https://bazaardb.gg/run"
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "30", url],
        capture_output=True, text=True
    )
    return r.stdout if r.returncode == 0 else ""

def parse_runs(page_text):
    """从页面文本解析对局列表"""
    runs = []

    hero_abbrev = {
        "KAR": "Karnok", "STE": "Stelle", "JUL": "Jules",
        "MAK": "Mak", "DUL": "Duli", "DOO": "Duli", "VAN": "Vanessa",
        "PYG": "Pygmalion",
    }

    card_pattern = re.compile(
        r'bazaardb\.gg/card/[^/]+/([A-Z][A-Za-z0-9\'.]+(?:-[A-Za-z0-9\'.]+)*)'
    )

    # 页面格式（jina 渲染后）：
    # [player](https://bazaardb.gg/run/profile/...) • Xm ago
    # KAR / STE / ...
    # [X wins Gold/Silver/Bronze/Perfect Victory](https://bazaardb.gg/run/<run_id>)
    # card links...
    # [next player]...

    # 按对局 run URL 行分割
    # 每个对局的标志：\[(\d+) wins (Gold|Silver|...) Victory\]\(https://bazaardb\.gg/run/<uuid>\)
    run_block_re = re.compile(
        r'\[(\d+) wins (Gold|Silver|Bronze|Perfect) Victory\]'
        r'\(https://bazaardb\.gg/run/([0-9a-f-]{36})\)'
    )

    player_re = re.compile(
        r'\[([^\]]+)\]\(https://bazaardb\.gg/run/profile/[0-9a-f-]+\)'
    )
    hero_re = re.compile(r'\b(KAR|STE|JUL|MAK|DUL|DOO|VAN|PYG)\b')

    # 找所有对局标志的位置
    match_positions = [(m.start(), m) for m in run_block_re.finditer(page_text)]

    for i, (pos, m) in enumerate(match_positions):
        wins = int(m.group(1))
        victory = m.group(2)
        run_id = m.group(3)

        # 往前找 player 和 hero（在本对局块开始处）
        # 往后找卡牌链接（到下一个对局块）
        prev_pos = match_positions[i - 1][0] if i > 0 else 0
        next_pos = match_positions[i + 1][0] if i + 1 < len(match_positions) else len(page_text)

        # player 在前面 500 字符内
        before = page_text[max(prev_pos, pos - 600):pos]
        after = page_text[pos:next_pos]

        player_m = list(player_re.finditer(before))
        # 取最后一个（最近的 player）
        player = player_m[-1].group(1) if player_m else "(Anonymous)"
        # 过滤掉 "My stats"
        if player == "My stats":
            player = "(Anonymous)"

        hero_m = hero_re.search(before[-200:])  # hero abbrev 紧贴在 run 链接之前
        hero = hero_abbrev.get(hero_m.group(1), "Unknown") if hero_m else "Unknown"

        # 卡牌在 after 中
        card_names_raw = card_pattern.findall(after)
        seen_cards = set()
        items = []
        for cn in card_names_raw:
            name = cn.replace("-", " ").replace("&#39;", "'")
            if name not in seen_cards:
                seen_cards.add(name)
                items.append(name)

        if not items:
            continue

        # 只保留 Gold/Perfect，胜场 >= 8
        if victory not in ("Gold", "Perfect") or wins < 8:
            continue

        runs.append({
            "run_id": run_id,
            "player": player,
            "hero": hero,
            "victory": victory,
            "wins": wins,
            "items": items,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    return runs

# ──────────────────────────────
# 增量保存
# ──────────────────────────────
def load_local_runs():
    if not os.path.exists(RUNS_FILE):
        return {}
    with open(RUNS_FILE) as f:
        data = json.load(f)
    return {r["run_id"]: r for r in data}

def save_runs(runs_dict):
    with open(RUNS_FILE, "w") as f:
        json.dump(list(runs_dict.values()), f, ensure_ascii=False, indent=2)

def merge_runs(local, new_runs):
    added = 0
    for r in new_runs:
        if r["run_id"] not in local:
            local[r["run_id"]] = r
            added += 1
    return local, added

# ──────────────────────────────
# 卡牌工具函数
# ──────────────────────────────
def ms_to_s(text):
    def replace_num(m):
        nums = m.group(1).split("/")
        converted = []
        for n in nums:
            try:
                val = int(n)
                if val >= 500 and val % 500 == 0:
                    s = val / 1000
                    converted.append(str(int(s)) if s == int(s) else f"{s:.1f}")
                else:
                    converted.append(n)
            except:
                converted.append(n)
        return "/".join(converted) + "秒"
    return re.sub(r"(\d+(?:/\d+)*)秒", replace_num, text)

def get_cn(name_en, item_index):
    it = item_index.get(name_en)
    return it["name_cn"] if it and it.get("name_cn") else name_en

def get_full_desc(name_en, item_index):
    it = item_index.get(name_en)
    if not it:
        return ""
    parts = []
    for sk in (it.get("skills") or []):
        cn = sk.get("cn", "").strip()
        if cn:
            parts.append(ms_to_s(cn))
    for sk in (it.get("skills_passive") or []):
        cn = sk.get("cn", "").strip()
        if cn:
            parts.append(f"〔被动〕{ms_to_s(cn)}")
    return " ／ ".join(parts)

def get_size_badge(name_en, item_index):
    it = item_index.get(name_en)
    if not it:
        return ""
    sz = it.get("size", "")
    if "Small" in sz or "小" in sz:
        return "🟦小"
    if "Medium" in sz or "中" in sz:
        return "🟧中"
    if "Large" in sz or "大" in sz:
        return "🟥大"
    return ""

# ──────────────────────────────
# 构筑分析 & 文档生成
# ──────────────────────────────
HERO_CN = {
    "Karnok": "卡诺克", "Stelle": "斯特尔", "Jules": "朱尔斯",
    "Mak": "麦克", "Duli": "杜利", "Vanessa": "瓦内莎",
    "Pygmalion": "皮格马利翁",
}

def cluster_runs_by_hero(runs_dict):
    """
    对每个英雄，按核心卡牌相似度聚类，取最多5个流派，每流派5套阵容
    相似度：两套阵容共享核心卡牌数 / 联合集大小 (Jaccard)
    """
    by_hero = defaultdict(list)
    for r in runs_dict.values():
        by_hero[r["hero"]].append(r)

    result = {}
    for hero, hero_runs in by_hero.items():
        # 按胜场降序，Perfect > Gold
        hero_runs.sort(key=lambda r: (
            0 if r["victory"] == "Perfect" else 1,
            -r.get("wins", 0)
        ))

        clusters = []  # list of (label, [runs])

        for run in hero_runs:
            s = set(run["items"])
            best_cluster = None
            best_jaccard = 0.0
            for i, (_, c_runs) in enumerate(clusters):
                c_core = set(c_runs[0]["items"])
                jaccard = len(s & c_core) / len(s | c_core)
                if jaccard > best_jaccard:
                    best_jaccard = jaccard
                    best_cluster = i

            if best_cluster is not None and best_jaccard >= 0.3:
                if len(clusters[best_cluster][1]) < 5:
                    clusters[best_cluster][1].append(run)
            else:
                if len(clusters) < 5:
                    # 自动生成流派标签
                    label = auto_label(run["items"], hero)
                    clusters.append((label, [run]))

        result[hero] = clusters

    return result

def auto_label(items, hero):
    """根据物品组合自动命名流派"""
    s = {i.lower() for i in items}

    if hero == "Karnok":
        if any(x in s for x in ["flying squirrel", "great eagle", "hunting hawk", "messenger sparrow"]):
            if any(x in s for x in ["beast call", "wild bear"]):
                return "🦅🐻 飞鸟·野兽混合流"
            if any(x in s for x in ["runic claymore"]):
                return "🦅⚔️ 飞鸟·剑流"
            return "🦅 飞鸟流"
        if any(x in s for x in ["karst", "wild boar", "harmadillo", "meat", "stretch pants"]):
            return "🐗 野兽流"
        if any(x in s for x in ["dryad", "signal fire", "warpaint", "tinderbox"]):
            return "🔥 烈焰·自然流"
        if any(x in s for x in ["spiked collar", "anaconda", "bat", "eagle sigil", "vengeful sigil"]):
            return "🐍 毒刺流"
        if any(x in s for x in ["wild bear", "beast call"]):
            return "🐻 野兽流"

    elif hero == "Stelle":
        if any(x in s for x in ["ornithopter", "vortex cannon", "observatory", "radar dome"]):
            return "🚁 科技·飞行流"
        if any(x in s for x in ["ray gun", "laser", "drone"]):
            return "🔫 射线流"

    elif hero == "Jules":
        if any(x in s for x in ["jumbo wok", "caviar", "giant lollipop", "zarlic", "basket"]):
            return "🍳 美食流"
        if any(x in s for x in ["cleaver", "knife", "chopper"]):
            return "🔪 料理刀流"

    elif hero == "Mak":
        if any(x in s for x in ["library", "atmospheric sampler", "makroscope"]):
            return "🔬 科研流"
        if any(x in s for x in ["nitro", "flying potion", "eternal torch"]):
            return "🧪 药剂流"

    return "🎲 综合流"

def generate_markdown(clusters_by_hero, runs_dict, item_index, total_runs):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# 大巴扎（The Bazaar）构筑攻略")
    lines.append(f"\n> 来源：[bazaardb.gg/run](https://bazaardb.gg/run)  |  更新：{now}")
    lines.append(f"> 累计收录对局：{total_runs} 场（仅 🥇 黄金 / 🏆 完美胜利，胜场 ≥ 8）")
    lines.append("> 每英雄最多 5 种流派，每流派最多 5 套阵容")
    lines.append("> **卡牌说明**：来源 [BazaarHelper](https://github.com/Duangi/BazaarHelper) 数据库\n")

    hero_order = ["Karnok", "Stelle", "Jules", "Mak", "Vanessa", "Duli", "Pygmalion"]
    for hero in hero_order:
        if hero not in clusters_by_hero:
            continue
        clusters = clusters_by_hero[hero]
        if not clusters:
            continue

        hero_cn = HERO_CN.get(hero, hero)
        lines.append(f"\n---\n\n## {hero_cn}（{hero}）\n")

        for genre_label, genre_runs in clusters:
            lines.append(f"### {genre_label}\n")

            for idx, r in enumerate(genre_runs, 1):
                vmark = "🏆" if r["victory"] == "Perfect" else "🥇"
                wins_str = f"{r.get('wins','?')}连胜"
                board = " | ".join(get_cn(c, item_index) for c in r["items"])
                lines.append(f"**阵容 {idx}** {vmark} {wins_str} · {r['player']}")
                lines.append(f"> {board}")
                lines.append(f"> [查看详情](https://bazaardb.gg/run/{r['run_id']})\n")

            # 收集本流派全部卡牌（去重保序）
            seen, all_cards = set(), []
            for r in genre_runs:
                for c in r["items"]:
                    if c not in seen:
                        seen.add(c)
                        all_cards.append(c)

            lines.append("**📖 卡牌说明**\n")
            for c in all_cards:
                cn = get_cn(c, item_index)
                desc = get_full_desc(c, item_index)
                badge = get_size_badge(c, item_index)
                if desc:
                    lines.append(f"- **{cn}** {badge}：{desc}")
                else:
                    lines.append(f"- **{cn}** {badge}：（暂无数据）")
            lines.append("")

    return "\n".join(lines)

# ──────────────────────────────
# 主流程
# ──────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始更新...")

    # 1. 加载 items_db
    item_index = load_items_db()
    print(f"  items_db: {len(item_index)} 条物品数据")

    # 2. 抓取最新对局
    print("  抓取 bazaardb.gg/run ...")
    page = fetch_runs_page()
    if not page:
        print("[ERROR] 页面抓取失败")
        sys.exit(1)

    new_runs = parse_runs(page)
    print(f"  解析到 {len(new_runs)} 条有效对局（Gold/Perfect, ≥8胜）")

    # 3. 增量合并
    local_runs = load_local_runs()
    local_runs, added = merge_runs(local_runs, new_runs)
    save_runs(local_runs)
    print(f"  新增 {added} 条，本地累计 {len(local_runs)} 条")

    # 4. 聚类分析
    clusters_by_hero = cluster_runs_by_hero(local_runs)

    # 5. 生成文档
    md = generate_markdown(clusters_by_hero, local_runs, item_index, len(local_runs))
    with open(BUILDS_FILE, "w") as f:
        f.write(md)
    print(f"  攻略文档已更新：{BUILDS_FILE} ({len(md)} 字符)")

    # 打印各英雄对局数
    hero_counts = Counter(r["hero"] for r in local_runs.values())
    for h, cnt in sorted(hero_counts.items(), key=lambda x: -x[1]):
        print(f"    {HERO_CN.get(h, h)}: {cnt} 场")

    return added, len(local_runs)


def push_to_github(added: int):
    """把最新文件同步推送到 GitHub"""
    if not GITHUB_TOKEN:
        print("  GitHub: 未配置 token，跳过推送")
        return

    repo_url = f"https://{GITHUB_TOKEN}@{GITHUB_REPO_BARE}"

    # 确保本地仓库存在
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        subprocess.run(["git", "clone", repo_url, REPO_DIR], capture_output=True)
        subprocess.run(["git", "config", "user.email", "samsonschen@users.noreply.github.com"], cwd=REPO_DIR, capture_output=True)
        subprocess.run(["git", "config", "user.name", "samsonschen"], cwd=REPO_DIR, capture_output=True)
    else:
        # 拉取前先更新 remote url（token 可能刷新）
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], cwd=REPO_DIR, capture_output=True)
        subprocess.run(["git", "pull", "--rebase"], cwd=REPO_DIR, capture_output=True)

    # 复制最新文件（不包含 .env）
    import shutil
    for fname in ["bazaar_builds.md", "bazaar_runs.json", "bazaar_update.py"]:
        src = os.path.join(WORKSPACE, fname)
        if os.path.exists(src):
            shutil.copy2(src, REPO_DIR)

    # 提交并推送
    subprocess.run(["git", "add", "bazaar_builds.md", "bazaar_runs.json", "bazaar_update.py"], cwd=REPO_DIR, capture_output=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"自动更新：{now_str}，新增 {added} 条对局"
    r = subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, capture_output=True, text=True)
    if "nothing to commit" in r.stdout:
        print("  GitHub: 无变更，跳过推送")
        return
    r2 = subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, capture_output=True, text=True)
    if r2.returncode == 0:
        print(f"  GitHub: 推送成功 → https://{GITHUB_REPO_BARE}")
    else:
        print(f"  GitHub: 推送失败 {r2.stderr[:200]}")

if __name__ == "__main__":
    added, total = main()
    push_to_github(added)
