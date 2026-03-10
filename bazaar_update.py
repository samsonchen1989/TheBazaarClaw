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
BUILDS_FILE = os.path.join(WORKSPACE, "bazaar_builds.md")          # 汇总文件（保留向后兼容）
BUILDS_DIR  = os.path.join(WORKSPACE, "builds")                      # 按英雄拆分的目录
GITHUB_PUSH_STATE = os.path.join(WORKSPACE, ".github_push_state")    # 记录上次推送日期
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
# 加载 skills_db（用于过滤技能）
# ──────────────────────────────
def load_skills_db():
    skills_path = os.path.join(WORKSPACE, "skills_db.json")
    if not os.path.exists(skills_path):
        print("[INFO] 下载 skills_db.json ...")
        url = "https://raw.githubusercontent.com/Duangi/BazaarHelper/main/src-tauri/resources/skills_db.json"
        subprocess.run(["curl", "-sL", "--max-time", "20", url, "-o", skills_path], capture_output=True)
    if os.path.exists(skills_path):
        with open(skills_path) as f:
            skills = json.load(f)
        return {s.get("name_en", "").strip() for s in skills}
    return set()


def normalize(name: str) -> str:
    """归一化：全小写、去掉连字符/空格/标点，用于模糊匹配"""
    import string
    result = name.lower()
    for ch in string.punctuation + "\u2019\u2018":
        result = result.replace(ch, "")
    return result.replace(" ", "")

SKILL_NAMES: set = set()       # 延迟加载（原始名，带连字符）
SKILL_NAMES_NORM: set = set()  # 归一化版本（全小写、去连字符）
ITEM_NAMES_NORM: set = set()   # items_db 归一化白名单

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

        # 卡牌在 after 中，双重过滤：
        # 1. 不在 skills_db 里（技能黑名单）
        # 2. 在 items_db 里（物品白名单，比技能黑名单更可靠）
        card_names_raw = card_pattern.findall(after)
        items = []
        for cn in card_names_raw:
            name = cn.replace("-", " ").replace("&#39;", "'")
            name_n = normalize(name)
            # 黑名单：跳过技能
            if name_n in SKILL_NAMES_NORM:
                continue
            # 白名单：必须在 items_db 中（过滤掉页面上展示的技能卡）
            if ITEM_NAMES_NORM and name_n not in ITEM_NAMES_NORM:
                continue
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
    对每个英雄，先用 auto_label 分流派，同流派合并（最多5场），
    最多取5个流派，每流派按胜场降序排列。
    """
    by_hero = defaultdict(list)
    for r in runs_dict.values():
        by_hero[r["hero"]].append(r)

    result = {}
    for hero, hero_runs in by_hero.items():
        # 按 Perfect > Gold，胜场降序
        hero_runs.sort(key=lambda r: (
            0 if r["victory"] == "Perfect" else 1,
            -r.get("wins", 0)
        ))

        # 按 auto_label 分组
        label_map = defaultdict(list)  # label -> [runs]
        for run in hero_runs:
            label = auto_label(run["items"], hero)
            if len(label_map[label]) < 5:
                label_map[label].append(run)

        # 按第一条对局的胜场排序流派，取前5个
        sorted_labels = sorted(
            label_map.items(),
            key=lambda kv: -(kv[1][0].get("wins", 0) if kv[1] else 0)
        )[:5]

        result[hero] = sorted_labels

    return result

def auto_label(items, hero):
    """
    根据物品组合自动命名流派。
    命名规则：核心卡牌 + 英雄专属风格，全部自定义。
    """
    s = {i.lower() for i in items}

    if hero == "Karnok":
        if "flying squirrel" in s:
            if "runic claymore" in s:
                return "⚔️ 飞松鼠·剑流"
            if any(x in s for x in ["honey badger", "beast tooth", "outlands terror", "tree club"]):
                return "🐿️🐾 飞松鼠·野兽流"
            if any(x in s for x in ["langxian", "wand", "spirit diffuser"]):
                return "🐿️✨ 飞松鼠·秘术流"
            return "🐿️ 飞松鼠流"
        if any(x in s for x in ["great eagle", "hunting hawk", "messenger sparrow", "trebuchet"]):
            return "🦅 猛禽流"
        if any(x in s for x in ["dryad", "tinderbox", "warpaint", "signal fire", "torch", "firefly lantern"]):
            return "🔥🌿 烈焰·自然流"
        if any(x in s for x in ["wild boar", "boar mask", "honey badger", "beast tooth", "karst"]):
            return "🐗 野兽流"
        if any(x in s for x in ["waystones", "aurora vista", "hidden lake", "trail markers"]):
            return "🗺️ 探险流"

    elif hero == "Stelle":
        if any(x in s for x in ["lavaroller"]):
            return "🌋 熔岩滚车流"
        if any(x in s for x in ["the big one", "repair drone", "parts picker"]):
            return "💥 自毁炸弹流"
        if any(x in s for x in ["pillbuggy", "radar dome"]):
            return "🐞 瓢虫流"
        if any(x in s for x in ["jetpack", "ornithopter", "levitation pad"]):
            return "🚀 飞行流"
        if any(x in s for x in ["ray gun", "alpha ray", "beta ray"]):
            return "🔫 射线流"

    elif hero == "Jules":
        if any(x in s for x in ["giant lollipop"]):
            return "🍭 巨型棒棒糖流"
        if any(x in s for x in ["walk-in freezer", "sorbet", "slushee"]):
            return "🧊 冷冻流"
        if any(x in s for x in ["fruit press"]):
            return "🍊 水果榨汁流"

    elif hero == "Mak":
        if any(x in s for x in ["runic blade", "runic great axe", "runic daggers"]):
            return "⚡ 符文刃流"
        if any(x in s for x in ["idol of decay", "pendulum"]):
            return "☠️ 腐朽神像毒流"
        if any(x in s for x in ["poppy field", "goop flail"]):
            return "🌸 罂粟田流"
        if any(x in s for x in ["atmospheric sampler", "boiling flask"]):
            return "🧪 炼金流"

    elif hero == "Duli":
        if any(x in s for x in ["harmadillo", "bunker"]):
            return "🛡️ 甲虫护盾流"
        if any(x in s for x in ["dooltron"]):
            return "🤖 杜尔特隆流"
        if any(x in s for x in ["ice 9000", "cooling fan", "fiber optics"]):
            return "❄️ 冰冻9000流"
        if any(x in s for x in ["dinosawer", "trollosaur", "momma-saur", "tanky anky"]):
            return "🦕 恐龙流"

    elif hero == "Vanessa":
        if any(x in s for x in ["anchor", "rowboat"]):
            return "⚓ 船锚流"
        if any(x in s for x in ["oni mask", "incendiary rounds"]):
            return "🔥 缓灼流"
        if any(x in s for x in ["figurehead", "grapeshot", "pistol sword"]):
            return "🔫 全弹速攻流"
        if any(x in s for x in ["pufferfish", "tortuga", "diving helmet"]):
            return "🐡 海洋毒刺流"

    elif hero == "Pygmalion":
        if any(x in s for x in ["landscraper"]):
            return "🌿 园丁护盾流"
        if any(x in s for x in ["cargo shorts"]):
            return "👖 货物短裤流"
        if any(x in s for x in ["crook", "lion cane"]):
            return "🦯 歹徒流"

    return "🎲 混搭流"


def generate_hero_markdown(hero, clusters, item_index, total_runs, now_str):
    """为单个英雄生成 Markdown 内容"""
    hero_cn = HERO_CN.get(hero, hero)
    lines = []
    lines.append(f"# 大巴扎攻略 — {hero_cn}（{hero}）")
    lines.append(f"\n> 来源：[bazaardb.gg/run](https://bazaardb.gg/run)  |  更新：{now_str}")
    lines.append(f"> 累计收录对局：{total_runs} 场（仅 🥇 黄金 / 🏆 完美胜利，胜场 ≥ 8）")
    lines.append("> 每英雄最多 5 种流派，每流派最多 5 套阵容")
    lines.append("> **卡牌说明**：来源 [BazaarHelper](https://github.com/Duangi/BazaarHelper) 数据库\n")

    for genre_label, genre_runs in clusters:
        lines.append(f"## {genre_label}\n")

        for idx, r in enumerate(genre_runs, 1):
            vmark = "🏆" if r["victory"] == "Perfect" else "🥇"
            wins_str = f"{r.get('wins','?')}连胜"
            board = " | ".join(get_cn(c, item_index) for c in r["items"])
            lines.append(f"**阵容 {idx}** {vmark} {wins_str} · {r['player']}")
            lines.append(f"> {board}")
            lines.append(f"> [查看详情](https://bazaardb.gg/run/{r['run_id']})\n")

        # 卡牌说明（去重保序）
        seen_desc, all_cards_unique = set(), []
        for r in genre_runs:
            for c in r["items"]:
                if c not in seen_desc:
                    seen_desc.add(c)
                    all_cards_unique.append(c)

        lines.append("**📖 卡牌说明**\n")
        for c in all_cards_unique:
            cn = get_cn(c, item_index)
            desc = get_full_desc(c, item_index)
            badge = get_size_badge(c, item_index)
            if desc:
                lines.append(f"- **{cn}** {badge}：{desc}")
            else:
                lines.append(f"- **{cn}** {badge}：（暂无数据）")
        lines.append("")

    return "\n".join(lines)


def generate_markdown(clusters_by_hero, runs_dict, item_index, total_runs):
    """生成所有英雄的 Markdown，写入各自文件，同时返回汇总内容（向后兼容）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(BUILDS_DIR, exist_ok=True)

    hero_order = ["Karnok", "Stelle", "Jules", "Mak", "Vanessa", "Duli", "Pygmalion"]
    summary_lines = []
    summary_lines.append("# 大巴扎（The Bazaar）构筑攻略汇总")
    summary_lines.append(f"\n> 来源：[bazaardb.gg/run](https://bazaardb.gg/run)  |  更新：{now}")
    summary_lines.append(f"> 累计收录对局：{total_runs} 场（仅 🥇 黄金 / 🏆 完美胜利，胜场 ≥ 8）\n")

    for hero in hero_order:
        if hero not in clusters_by_hero:
            continue
        clusters = clusters_by_hero[hero]
        if not clusters:
            continue

        hero_cn = HERO_CN.get(hero, hero)
        # 写入单独文件
        hero_md = generate_hero_markdown(hero, clusters, item_index, total_runs, now)
        fname = f"builds_{hero.lower()}.md"
        fpath = os.path.join(BUILDS_DIR, fname)
        with open(fpath, "w") as f:
            f.write(hero_md)

        # 汇总索引
        summary_lines.append(f"- [{hero_cn}（{hero}）](./{fname})：{len(clusters)} 种流派")

    summary_lines.append("")
    return "\n".join(summary_lines)


# ──────────────────────────────
# 主流程
# ──────────────────────────────
def main():
    global SKILL_NAMES, SKILL_NAMES_NORM, ITEM_NAMES_NORM
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始更新...")

    # 1. 加载 items_db & skills_db
    item_index = load_items_db()
    SKILL_NAMES = load_skills_db()
    SKILL_NAMES_NORM = {normalize(s) for s in SKILL_NAMES}
    ITEM_NAMES_NORM = {normalize(name) for name in item_index.keys()}
    print(f"  items_db: {len(item_index)} 条物品 | skills_db: {len(SKILL_NAMES)} 条技能（将被过滤）")

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

    # 5. 生成文档（按英雄拆分写入 builds/ 目录）
    generate_markdown(clusters_by_hero, local_runs, item_index, len(local_runs))
    hero_files = [f for f in os.listdir(BUILDS_DIR) if f.endswith(".md")]
    print(f"  攻略文档已更新：builds/ 目录，共 {len(hero_files)} 个英雄文件")

    # 打印各英雄对局数
    hero_counts = Counter(r["hero"] for r in local_runs.values())
    for h, cnt in sorted(hero_counts.items(), key=lambda x: -x[1]):
        print(f"    {HERO_CN.get(h, h)}: {cnt} 场")

    return added, len(local_runs)


def should_push_today():
    """判断今天是否已推送过，返回 True 表示需要推送"""
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(GITHUB_PUSH_STATE):
        with open(GITHUB_PUSH_STATE) as f:
            last = f.read().strip()
        if last == today:
            return False
    return True


def mark_pushed():
    """记录今天已推送"""
    today = datetime.now().strftime("%Y-%m-%d")
    with open(GITHUB_PUSH_STATE, "w") as f:
        f.write(today)


def push_to_github(added: int, force: bool = False):
    """把最新文件同步推送到 GitHub（默认每天最多一次）"""
    if not GITHUB_TOKEN:
        print("  GitHub: 未配置 token，跳过推送")
        return

    if not force and not should_push_today():
        print("  GitHub: 今日已推送，跳过（每天一次）")
        return

    repo_url = f"https://{GITHUB_TOKEN}@{GITHUB_REPO_BARE}"

    # 确保本地仓库存在
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        subprocess.run(["git", "clone", repo_url, REPO_DIR], capture_output=True)
        subprocess.run(["git", "config", "user.email", "samsonschen@users.noreply.github.com"], cwd=REPO_DIR, capture_output=True)
        subprocess.run(["git", "config", "user.name", "samsonschen"], cwd=REPO_DIR, capture_output=True)
    else:
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], cwd=REPO_DIR, capture_output=True)
        subprocess.run(["git", "pull", "--rebase"], cwd=REPO_DIR, capture_output=True)

    import shutil

    # 复制主文件（不再包含 bazaar_builds.md）
    for fname in ["bazaar_runs.json", "bazaar_update.py"]:
        src = os.path.join(WORKSPACE, fname)
        if os.path.exists(src):
            shutil.copy2(src, REPO_DIR)

    # 复制数据库文件
    for src_path, fname in [
        ("/tmp/items_db.json",                      "items_db.json"),
        (os.path.join(WORKSPACE, "skills_db.json"), "skills_db.json"),
    ]:
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(REPO_DIR, fname))

    # 复制按英雄拆分的 builds/ 目录
    repo_builds = os.path.join(REPO_DIR, "builds")
    os.makedirs(repo_builds, exist_ok=True)
    if os.path.exists(BUILDS_DIR):
        for fname in os.listdir(BUILDS_DIR):
            if fname.endswith(".md"):
                shutil.copy2(os.path.join(BUILDS_DIR, fname), os.path.join(repo_builds, fname))

    subprocess.run(
        ["git", "add", "bazaar_runs.json", "bazaar_update.py",
         "items_db.json", "skills_db.json", "builds/", "README.md"],
        cwd=REPO_DIR, capture_output=True
    )
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"自动更新：{now_str}，新增 {added} 条对局"
    r = subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, capture_output=True, text=True)
    if "nothing to commit" in r.stdout:
        print("  GitHub: 无变更，跳过推送")
        return
    r2 = subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, capture_output=True, text=True)
    if r2.returncode == 0:
        print(f"  GitHub: 推送成功 → https://{GITHUB_REPO_BARE}")
        mark_pushed()
    else:
        print(f"  GitHub: 推送失败 {r2.stderr[:200]}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="大巴扎构筑攻略更新工具")
    parser.add_argument("--fetch", action="store_true", help="抓取新对局并更新攻略文档")
    parser.add_argument("--push",  action="store_true", help="将本地数据推送到 GitHub（每天一次）")
    parser.add_argument("--force-push", action="store_true", help="强制推送到 GitHub（忽略频率限制）")
    args = parser.parse_args()

    if args.fetch:
        added, total = main()
        # fetch 后顺带检查是否该推送（每天一次）
        push_to_github(added)
    elif args.push:
        push_to_github(added=0)
    elif args.force_push:
        push_to_github(added=0, force=True)
    else:
        # 默认：两件都做（向后兼容）
        added, _ = main()
        push_to_github(added)
