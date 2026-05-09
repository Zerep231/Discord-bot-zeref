import os
import re
import json
import yaml
import random
import datetime

import discord
from discord import app_commands

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
KEYWORDS_FILE  = os.path.join(BASE_DIR, "keywords.json")
GIVEAWAYS_FILE = os.path.join(BASE_DIR, "giveaways.json")
SETTINGS_FILE  = os.path.join(BASE_DIR, "settings.json")
WARNS_FILE     = os.path.join(BASE_DIR, "warns.json")
ENCHANTS_FILE  = os.path.join(BASE_DIR, "enchantments.yml")
SHOP_FILE      = os.path.join(BASE_DIR, "shop.json")
MC_CONFIG_FILE = os.path.join(BASE_DIR, "mc_config.json")

COLOR_SUCCESS  = 0x57F287
COLOR_ERROR    = 0xED4245
COLOR_WARNING  = 0xFEE75C
COLOR_INFO     = 0x5865F2
COLOR_GIVEAWAY = 0xFF73FA
COLOR_FAREWELL = 0x99AAB5
COLOR_MOD      = 0xEB459E
COLOR_ENCHANT  = 0xF0A500

COIN         = "🪙"
DAILY_AMOUNT = 100

MC_ITEMS: dict[str, dict] = {
    "diamond":   {"cost": 500,  "emoji": "💎", "name": "Diamond"},
    "gold":      {"cost": 150,  "emoji": "🥇", "name": "Gold Ingot"},
    "emerald":   {"cost": 400,  "emoji": "💚", "name": "Emerald"},
    "iron":      {"cost": 80,   "emoji": "⚙️",  "name": "Iron Ingot"},
    "netherite": {"cost": 3000, "emoji": "🖤", "name": "Netherite Ingot"},
}

ENCHANT_TIER: dict[str, float] = {
    "thor": 2.0, "shura": 2.0, "vanish": 2.0, "resonate": 2.0, "rebounding": 2.0,
    "charge": 1.8, "arcticfreeze": 1.8, "acceleration": 1.8,
    "ninja": 1.5, "aura": 1.5, "end_affinity": 1.5, "nether_affinity": 1.5,
    "endurance": 1.4, "frost": 1.3, "explosive": 1.3, "multishot": 1.3,
    "zombiecrusher": 0.8, "skullcrusher": 0.8, "incinerate": 0.8,
    "cubism": 0.8, "enderbane": 0.8, "blazereaper": 0.8,
}

ENCHANT_VI: dict[str, str] = {
    "abrasion":         "Có cơ hội làm hỏng giáp của kẻ địch mỗi khi tấn công.",
    "adrenaline":       "Nhận Hấp Thụ (Absorption) khi bị mob tấn công.",
    "ascend":           "Bay lên không trung. Chuột phải để kích hoạt, sau đó rơi chậm.",
    "aura":             "Giảm sát thương nhận được cho các người chơi đứng gần bạn.",
    "blackout":         "Có cơ hội làm mù đối thủ khi tấn công.",
    "blast_mining":     "Đào khối theo vùng 3×3 khi khai thác.",
    "drain":            "Gây hiệu ứng Chảy Máu liên tục lên đối thủ.",
    "caffeinated":      "Có cơ hội nhận Speed khi đang chạy và tấn công.",
    "charge":           "Phóng bản thân về phía trước với tốc độ cao.",
    "critical":         "Tăng sát thương khi đánh chí mạng (critical hit).",
    "cubism":           "Tăng sát thương ngẫu nhiên khi đánh Slime và Magma Cube.",
    "enderbane":        "Tăng sát thương ngẫu nhiên khi đánh Enderman và Ender Dragon.",
    "escape":           "Nhận Speed trong thời gian ngắn sau khi bị tấn công.",
    "finishing":        "Tăng sát thương khi kẻ địch có dưới 5 HP (gần chết).",
    "first_strike":     "Tăng sát thương khi kẻ địch còn nguyên máu (trên 18 HP).",
    "flashbang":        "Có cơ hội làm mù đối thủ khi mũi tên trúng.",
    "foraging":         "Có cơ hội nhân đôi loot khi phá lá cây.",
    "frost":            "Có cơ hội đóng băng đối thủ khi mũi tên trúng.",
    "postpone":         "Có cơ hội triệt tiêu knockback lên mob khi tấn công.",
    "brightness":       "Có cơ hội gây thêm sát thương cho Warden trong bóng tối.",
    "breaklessness":    "Nguyền: Có cơ hội không thể phá khối khi đang khai thác.",
    "carve":            "Gây sát thương cho tất cả thực thể trong bán kính khi vung vũ khí.",
    "contagion":        "Có cơ hội tạo đám mây hư không tại nơi mũi tên rơi xuống.",
    "end_affinity":     "Giảm sát thương nhận được khi chiến đấu trong thế giới End.",
    "ninja":            "Có cơ hội tăng sát thương khi đang núp (sneak).",
    "feather_step":     "Có cơ hội hủy toàn bộ sát thương ngã.",
    "getaway":          "Có cơ hội nhận Speed khi HP xuống dưới 20%.",
    "harmlessness":     "Nguyền: Có cơ hội làm cho đòn tấn công của bạn không gây sát thương.",
    "infernaltouch":    "Có cơ hội tự động nấu chín khối khi khai thác.",
    "nether_affinity":  "Giảm sát thương nhận được khi chiến đấu trong thế giới Nether.",
    "nether_prospector":"Có cơ hội nhân đôi loot khi đào Ancient Debris.",
    "blazereaper":      "Tăng sát thương ngẫu nhiên khi đánh các sinh vật Nether.",
    "replenish":        "Tự động trồng lại hạt giống sau khi thu hoạch cây.",
    "blow":             "Có cơ hội gây sát thương gấp đôi khi ném Trident.",
    "waterborne":       "Cho phép thở dưới nước vô thời hạn.",
    "experience":       "Có cơ hội nhận thêm EXP khi đào quặng.",
    "haste":            "Nhận Haste liên tục, tăng tốc độ sử dụng công cụ.",
    "alacrity":         "Nhận Haste liên tục, cho phép dùng công cụ nhanh hơn.",
    "repel":            "Có cơ hội đẩy ngược đối thủ ra xa khi tấn công.",
    "starvation":       "Có cơ hội gây hiệu ứng Đói (Hunger) cho đối thủ.",
    "resonate":         "Có cơ hội phản lại toàn bộ sát thương nhận cho kẻ tấn công.",
    "explosive":        "Có cơ hội khiến mũi tên phát nổ khi trúng mục tiêu.",
    "sharpnesshook":    "Gây thêm sát thương bằng móc câu khi câu trúng.",
    "poisonedhook":     "Có cơ hội đầu độc (Poison) mục tiêu khi câu trúng.",
    "firehook":         "Có cơ hội đốt cháy mục tiêu khi câu trúng.",
    "scorching":        "Có cơ hội đốt cháy kẻ tấn công sau khi bị tấn công.",
    "ravenous":         "Có cơ hội hồi phục điểm đói ngẫu nhiên khi chiến đấu.",
    "zombiecrusher":    "Tăng sát thương ngẫu nhiên khi đánh Zombie.",
    "skullcrusher":     "Tăng sát thương ngẫu nhiên khi đánh Skeleton.",
    "incinerate":       "Tăng sát thương ngẫu nhiên khi đánh Spider.",
    "allurement":       "Có cơ hội nhận gấp đôi loot khi câu cá.",
    "arcticfreeze":     "Có cơ hội gây chảy máu và làm chậm (Slowness) đối thủ.",
    "rebounding":       "Có cơ hội hủy sát thương và phản lại cho kẻ tấn công.",
    "rumble":           "Có cơ hội gây sát thương lại cho tất cả thực thể xung quanh.",
    "shura":            "Tăng sát thương chí mạng ngẫu nhiên khi HP dưới 50%.",
    "thor":             "Có cơ hội gọi sét đánh vào đối thủ.",
    "multishot":        "Có cơ hội mưa nhiều mũi tên vào đối thủ.",
    "vanish":           "Có cơ hội tàng hình trong vài giây sau khi bị tấn công.",
    "harvest":          "Tự động thu hoạch cây trồng trong vùng 3×3 bằng cuốc.",
    "ulshovel":         "Đào đất/cát theo vùng 3×3 bằng xẻng (Excavation).",
    "autoreel":         "Tự động kéo cần câu khi có cá cắn câu.",
    "endurance":        "Có cơ hội tự sửa chữa vật phẩm khi đang sử dụng.",
    "agro_replanter":   "Tự động thu hoạch và trồng lại cây khi chín.",
    "acceleration":     "Tích lũy tốc độ di chuyển (Speed) khi chạy liên tục.",
}


def get_type_color(trigger: str) -> int:
    t = trigger.upper()
    if "CURSE" in trigger.lower(): return 0x992D22
    if any(x in t for x in ["ATTACK", "SWING"]): return 0xE74C3C
    if any(x in t for x in ["DEFENSE"]): return 0x3498DB
    if any(x in t for x in ["MINING"]): return 0x2ECC71
    if any(x in t for x in ["RIGHT_CLICK"]): return 0x9B59B6
    if any(x in t for x in ["ARROW_HIT", "SHOOT"]): return 0xE67E22
    if any(x in t for x in ["HELD", "EFFECT_STATIC"]): return 0x1ABC9C
    if any(x in t for x in ["FALL_DAMAGE"]): return 0x7F8C8D
    if any(x in t for x in ["HOOK_ENTITY", "CATCH_FISH", "BITE_HOOK"]): return 0x16A085
    return 0x9B59B6


def get_type_emoji(trigger: str) -> str:
    t = trigger.upper()
    if "ATTACK_MOB" in t: return "⚔️🐾"
    if "ATTACK" in t:     return "⚔️"
    if "DEFENSE_MOB" in t: return "🛡️🐾"
    if "DEFENSE" in t:    return "🛡️"
    if "MINING" in t:     return "⛏️"
    if "RIGHT_CLICK" in t: return "🖱️"
    if "ARROW_HIT" in t:  return "🎯"
    if "SHOOT" in t:      return "🏹"
    if "HELD" in t:       return "✋"
    if "EFFECT_STATIC" in t: return "✨"
    if "FALL_DAMAGE" in t: return "🪂"
    if "HOOK_ENTITY" in t: return "🎣"
    if "CATCH_FISH" in t: return "🐟"
    if "BITE_HOOK" in t:  return "🪝"
    if "SWING" in t:      return "💫"
    return "🔮"


def is_curse(key: str, data: dict) -> bool:
    display = str(data.get("display", "")).lower()
    return "curse" in display or "curse" in key.lower()


def load_enchantments() -> dict:
    if not os.path.exists(ENCHANTS_FILE):
        return {}
    with open(ENCHANTS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


ENCHANT_DATA: dict = load_enchantments()

ROMAN = {1:"I",2:"II",3:"III",4:"IV",5:"V",6:"VI",7:"VII",8:"VIII",9:"IX",10:"X"}


def to_roman(n) -> str:
    try:
        return ROMAN.get(int(n), str(n))
    except Exception:
        return str(n)


def clean_mc_text(text) -> str:
    if not text:
        return ""
    return re.sub(r"%group-color%|&[0-9a-fk-orA-FK-OR]", "", str(text)).strip()


def get_enchant_display(key: str, data: dict) -> str:
    return clean_mc_text(data.get("display", key.replace("_", " ").title()))


def get_vi_desc(key: str, data: dict) -> str:
    if key in ENCHANT_VI:
        return ENCHANT_VI[key]
    raw = clean_mc_text(data.get("description", ""))
    return raw if raw else "Không có mô tả."


def get_all_item_types() -> list[str]:
    types = set()
    for data in ENCHANT_DATA.values():
        raw = str(data.get("applies-to", ""))
        for part in re.split(r"[,/]", raw):
            part = part.strip().title()
            if part:
                types.add(part)
    return sorted(types)


def _trigger_label(trigger: str) -> str:
    mapping = {
        "ATTACK": "Tấn công người chơi", "ATTACK_MOB": "Tấn công mob",
        "DEFENSE": "Phòng thủ từ người chơi", "DEFENSE_MOB": "Phòng thủ từ mob",
        "MINING": "Khai thác", "RIGHT_CLICK": "Chuột phải",
        "ARROW_HIT": "Mũi tên trúng", "SHOOT": "Bắn (người chơi)", "SHOOT_MOB": "Bắn (mob)",
        "HELD": "Cầm trên tay", "EFFECT_STATIC": "Hiệu ứng thường trực",
        "FALL_DAMAGE": "Nhận sát thương ngã", "HOOK_ENTITY": "Câu trúng sinh vật",
        "CATCH_FISH": "Câu được cá", "BITE_HOOK": "Cá cắn câu", "SWING": "Vung vũ khí",
    }
    parts = [t.strip() for t in trigger.split(";")]
    return " / ".join(mapping.get(p, p) for p in parts)


def book_price(enchant_key: str, level: int) -> int:
    # Bảng giá chuẩn: mỗi level x2 (100, 200, 400, 800, ...)
    # Giữ nhất quán cho toàn bộ enchant để người chơi dễ dự đoán chi phí.
    lv = max(1, int(level))
    return 100 * (2 ** (lv - 1))


def format_effect_line(e: str) -> str:
    e = str(e)
    e = re.sub(r"<random number>(\d+)-(\d+)</random number>", r"[\1–\2]", e)
    return f"`{e}`"


def format_effects(effects) -> str:
    if not effects:
        return "*Không có*"
    lines = []
    for e in effects:
        if isinstance(e, list):
            lines.extend([format_effect_line(x) for x in e])
        else:
            lines.append(format_effect_line(e))
    shown = lines[:8]
    result = "\n".join(shown)
    if len(lines) > 8:
        result += f"\n*...+{len(lines)-8} hiệu ứng khác*"
    return result


def format_conditions(conds: list) -> str:
    if not conds:
        return ""
    cleaned = []
    for c in conds[:4]:
        c = re.sub(r"%(\w[\w\s]*)%", r"[\1]", str(c))
        cleaned.append(f"• {c}")
    return "\n".join(cleaned)


def _enchant_header_bar(max_lv: int) -> str:
    filled = min(max_lv, 10)
    return "▰" * filled + "▱" * (10 - filled) + f"  Lv.{max_lv}"


def parse_duration(time_str: str) -> int | None:
    time_str = time_str.strip().lower()
    if not time_str:
        return None
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    matches = re.findall(r"(\d+)([dhms])", time_str)
    if not matches or "".join(n + u for n, u in matches) != time_str:
        return None
    total = sum(int(n) * units[u] for n, u in matches)
    return total if total > 0 else None


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_settings() -> dict:   return _load_json(SETTINGS_FILE)
def save_settings(d: dict):    _save_json(SETTINGS_FILE, d)
def load_keywords() -> dict:   return _load_json(KEYWORDS_FILE)
def save_keywords(d: dict):    _save_json(KEYWORDS_FILE, d)
def load_warns() -> dict:      return _load_json(WARNS_FILE)
def save_warns(d: dict):       _save_json(WARNS_FILE, d)
def load_giveaways() -> dict:  return _load_json(GIVEAWAYS_FILE)
def save_giveaways(d: dict):   _save_json(GIVEAWAYS_FILE, d)
def load_shop() -> dict:       return _load_json(SHOP_FILE)
def save_shop(d: dict):        _save_json(SHOP_FILE, d)
def load_mc_config() -> dict:  return _load_json(MC_CONFIG_FILE)
def save_mc_config(d: dict):   _save_json(MC_CONFIG_FILE, d)


def get_guild_settings(guild_id: int) -> dict:
    return load_settings().get(str(guild_id), {})


def set_guild_setting(guild_id: int, key: str, value):
    data = load_settings()
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {}
    data[gid][key] = value
    save_settings(data)


def get_guild_keywords(guild_id: int) -> dict:
    return load_keywords().get(str(guild_id), {})


def save_guild_keywords(guild_id: int, keywords: dict):
    data = load_keywords()
    data[str(guild_id)] = keywords
    save_keywords(data)


def find_reply(guild_id: int, content: str, name: str) -> str | None:
    keywords = get_guild_keywords(guild_id)
    content_lower = content.lower().strip()
    exact, contains = [], []
    for kw, info in keywords.items():
        replies = info.get("replies", [])
        if not replies:
            continue
        if info.get("match") == "chinh_xac":
            if content_lower == kw.lower():
                exact.extend(replies)
        else:
            if kw.lower() in content_lower:
                contains.extend(replies)
    pool = exact or contains
    return random.choice(pool).replace("{name}", name) if pool else None


def add_warn(guild_id: int, user_id: int, reason: str, mod: str) -> int:
    data = load_warns()
    gid, uid = str(guild_id), str(user_id)
    if gid not in data:
        data[gid] = {}
    if uid not in data[gid]:
        data[gid][uid] = []
    data[gid][uid].append({
        "reason": reason, "mod": mod,
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    save_warns(data)
    return len(data[gid][uid])


def get_warns(guild_id: int, user_id: int) -> list:
    return load_warns().get(str(guild_id), {}).get(str(user_id), [])


def clear_warns(guild_id: int, user_id: int):
    data = load_warns()
    gid, uid = str(guild_id), str(user_id)
    if gid in data and uid in data[gid]:
        data[gid][uid] = []
    save_warns(data)


def get_guild_shop(guild_id: int) -> dict:
    data = load_shop()
    return data.get(str(guild_id), {})


def save_guild_shop(guild_id: int, items: dict):
    data = load_shop()
    data[str(guild_id)] = items
    save_shop(data)


class EnchantPageView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], author_id: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.pages     = pages
        self.current   = 0
        self.author_id = author_id
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled  = self.current == 0
        self.next_btn.disabled  = self.current >= len(self.pages) - 1
        self.page_label.label   = f"  {self.current + 1} / {len(self.pages)}  "

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Chỉ người gọi lệnh mới bấm được!", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="  1 / 1  ", style=discord.ButtonStyle.grey, disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
