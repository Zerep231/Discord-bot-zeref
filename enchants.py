import re
import yaml
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    ENCHANT_DATA, ENCHANTS_FILE, COLOR_ERROR, COLOR_WARNING, COLOR_SUCCESS,
    get_enchant_display, get_vi_desc, get_type_color, get_type_emoji, is_curse,
    to_roman, _enchant_header_bar, _trigger_label, format_effects, format_conditions,
    clean_mc_text, get_all_item_types, EnchantPageView,
)


async def enchant_autocomplete(interaction: discord.Interaction, current: str):
    results = []
    for key, data in ENCHANT_DATA.items():
        display = get_enchant_display(key, data)
        if current.lower() in key.lower() or current.lower() in display.lower():
            results.append(app_commands.Choice(name=f"{display} [{key}]", value=key))
        if len(results) >= 25:
            break
    return results


async def item_type_autocomplete(interaction: discord.Interaction, current: str):
    types = get_all_item_types()
    return [app_commands.Choice(name=t, value=t) for t in types if current.lower() in t.lower()][:25]


class AddEnchantModal(discord.ui.Modal, title="✦ Thêm Phù Phép Mới"):
    enc_key     = discord.ui.TextInput(label="ID phù phép (key)", placeholder="vd: thunderstrike", max_length=40)
    enc_display = discord.ui.TextInput(label="Tên hiển thị (tiếng Anh)", placeholder="vd: Thunder Strike", max_length=60)
    enc_desc    = discord.ui.TextInput(label="Mô tả (tiếng Việt)", style=discord.TextStyle.paragraph,
                                       placeholder="Gây sét đánh vào kẻ địch khi tấn công.", max_length=200)
    enc_applies = discord.ui.TextInput(label="Áp dụng cho (applies-to)", placeholder="vd: Swords, Axes", max_length=80)
    enc_type    = discord.ui.TextInput(label="Loại kích hoạt (type)", placeholder="vd: ATTACK  hoặc  ATTACK;ATTACK_MOB", max_length=60)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.enc_key.value.strip().lower().replace(" ", "_")
        if not key or not re.match(r"^[a-z0-9_]+$", key):
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ ID không hợp lệ!", description="Chỉ dùng chữ thường, số và dấu gạch dưới (_).", color=COLOR_ERROR
            ), ephemeral=True)
        if key in ENCHANT_DATA:
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ ID đã tồn tại!", description=f"Phù phép `{key}` đã có. Dùng ID khác.", color=COLOR_ERROR
            ), ephemeral=True)
        new_entry = {
            "display":    f"%group-color%{self.enc_display.value.strip()}",
            "description": self.enc_desc.value.strip(),
            "applies-to": self.enc_applies.value.strip(),
            "type":       self.enc_type.value.strip().upper(),
            "group":      "VANILLA", "applies": [],
            "levels": {"1": {"chance": 50, "cooldown": 5, "effects": ["# TODO"]}},
        }
        try:
            with open(ENCHANTS_FILE, "r", encoding="utf-8") as f:
                raw_yaml = yaml.safe_load(f) or {}
            raw_yaml[key] = new_entry
            with open(ENCHANTS_FILE, "w", encoding="utf-8") as f:
                yaml.dump(raw_yaml, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            ENCHANT_DATA[key] = new_entry
        except Exception as e:
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ Lỗi ghi file!", description=str(e), color=COLOR_ERROR
            ), ephemeral=True)
        trigger = self.enc_type.value.strip().upper()
        embed = discord.Embed(
            title=f"✅ Đã thêm: {self.enc_display.value.strip()}",
            color=get_type_color(trigger),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="🔑 ID",          value=f"`{key}`",                    inline=True)
        embed.add_field(name="📦 Áp dụng cho", value=self.enc_applies.value.strip(), inline=True)
        embed.add_field(name="⚡ Kích hoạt",   value=_trigger_label(trigger),       inline=True)
        embed.add_field(name="📝 Mô tả",       value=self.enc_desc.value.strip(),   inline=False)
        embed.set_footer(text=f"Tổng: {len(ENCHANT_DATA)} phù phép  ·  Chỉnh hiệu ứng trong enchantments.yml")
        await interaction.response.send_message(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Lỗi!", description=str(error), color=COLOR_ERROR
        ), ephemeral=True)


class EnchantsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    ec_group = app_commands.Group(name="ec", description="📖 Tra cứu hệ thống phù phép Advanced Enchantments")

    @ec_group.command(name="info", description="Xem thông tin tóm tắt của một phù phép.")
    @app_commands.describe(name="Tên phù phép (ví dụ: blast_mining, drain)")
    @app_commands.autocomplete(name=enchant_autocomplete)
    async def ec_info(self, interaction: discord.Interaction, name: str):
        data = ENCHANT_DATA.get(name)
        if not data:
            close = [k for k in ENCHANT_DATA if name.lower() in k.lower()]
            suggestion = f"\n> Ý bạn muốn nói: **{close[0]}**?" if close else ""
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ Không tìm thấy!", description=f"Không có phù phép `{name}`.{suggestion}", color=COLOR_ERROR
            ), ephemeral=True)
        display  = get_enchant_display(name, data)
        vi_desc  = get_vi_desc(name, data)
        levels   = data.get("levels", {}) or {}
        max_lv   = len(levels)
        applies_to = str(data.get("applies-to", "Không rõ"))
        trigger  = str(data.get("type", "Không rõ"))
        curse    = is_curse(name, data)
        color    = 0x992D22 if curse else get_type_color(trigger)
        t_emoji  = get_type_emoji(trigger)
        lvl_vals = [v for v in levels.values() if isinstance(v, dict)]
        chances  = [v["chance"] for v in lvl_vals if v.get("chance") is not None]
        cooldowns= [v["cooldown"] for v in lvl_vals if v.get("cooldown") is not None]
        curse_badge = "  ☠️ **[NGUYỀN]**" if curse else ""
        embed = discord.Embed(
            title=f"{'☠️' if curse else '✦'} {display}{curse_badge}",
            description=f"```\n{vi_desc}\n```\n{_enchant_header_bar(max_lv)}",
            color=color, timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="📦 Áp dụng cho", value=f"`{applies_to}`", inline=True)
        embed.add_field(name=f"{t_emoji} Kích hoạt", value=_trigger_label(trigger), inline=True)
        embed.add_field(name="🏅 Cấp tối đa", value=f"**{max_lv}** ({to_roman(max_lv)})", inline=True)
        stats = []
        if chances:
            mn, mx = min(chances), max(chances)
            stats.append(f"🎲 Tỉ lệ: **{mn}%**{'  →  **' + str(mx) + '%**' if mn != mx else ''}")
        if cooldowns:
            mn, mx = min(cooldowns), max(cooldowns)
            stats.append(f"⏳ Hồi chiêu: **{mn}s**{'  →  **' + str(mx) + 's**' if mn != mx else ''}")
        if stats:
            embed.add_field(name="📊 Chỉ số", value="\n".join(stats), inline=False)
        applies_items = data.get("applies", [])
        if applies_items:
            items_str = "  ".join(f"`{i}`" for i in applies_items[:12])
            if len(applies_items) > 12:
                items_str += f"  *+{len(applies_items)-12}*"
            embed.add_field(name="🔧 Vật phẩm hỗ trợ", value=items_str, inline=False)
        embed.set_footer(text=f"ID: {name}  ·  /ec detail {name} để xem từng cấp")
        await interaction.response.send_message(embed=embed)

    @ec_group.command(name="detail", description="Xem chi tiết từng cấp độ của phù phép.")
    @app_commands.describe(name="Tên phù phép")
    @app_commands.autocomplete(name=enchant_autocomplete)
    async def ec_detail(self, interaction: discord.Interaction, name: str):
        data = ENCHANT_DATA.get(name)
        if not data:
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ Không tìm thấy!", color=COLOR_ERROR, description=f"Không có phù phép `{name}`."
            ), ephemeral=True)
        display = get_enchant_display(name, data)
        vi_desc = get_vi_desc(name, data)
        levels  = data.get("levels", {}) or {}
        trigger = str(data.get("type", ""))
        curse   = is_curse(name, data)
        color   = 0x992D22 if curse else get_type_color(trigger)
        if not levels:
            return await interaction.response.send_message(embed=discord.Embed(
                title="⚠️ Không có dữ liệu cấp độ!", color=COLOR_WARNING
            ), ephemeral=True)
        await interaction.response.defer()
        embed = discord.Embed(
            title=f"📜 {display}", description=f"```\n{vi_desc}\n```",
            color=color, timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"ID: {name}  ·  {len(levels)} cấp độ  ·  /ec info {name}")
        for lvl_key, lvl_data in levels.items():
            if not isinstance(lvl_data, dict):
                continue
            chance   = lvl_data.get("chance")
            cooldown = lvl_data.get("cooldown")
            per_desc = lvl_data.get("description")
            conds    = lvl_data.get("conditions")
            effects  = lvl_data.get("effects")
            parts = []
            row1 = []
            if chance is not None:  row1.append(f"🎲 **{chance}%**")
            if cooldown is not None: row1.append(f"⏳ **{cooldown}s** hồi chiêu")
            if row1: parts.append("  ·  ".join(row1))
            if per_desc: parts.append(f"📝 {clean_mc_text(per_desc)}")
            if conds:
                ct = format_conditions(conds)
                if ct: parts.append(f"🔒 **Điều kiện:**\n{ct}")
            if effects:
                parts.append(f"⚙️ **Hiệu ứng:**\n{format_effects(effects)}")
            field_val = "\n".join(parts) if parts else "*Không có dữ liệu*"
            if len(field_val) > 1020:
                field_val = field_val[:1020] + "…"
            embed.add_field(name=f"✦ Cấp {to_roman(lvl_key)}", value=field_val, inline=len(levels) > 5)
            if len(embed.fields) >= 24:
                embed.add_field(name="⚠️", value=f"Còn {len(levels)-24} cấp không hiển thị.", inline=False)
                break
        await interaction.followup.send(embed=embed)

    @ec_group.command(name="list", description="Liệt kê tất cả phù phép theo loại trang bị.")
    @app_commands.describe(item="Loại trang bị (vd: Swords, Pickaxes, Armor, Bows...)")
    @app_commands.autocomplete(item=item_type_autocomplete)
    async def ec_list(self, interaction: discord.Interaction, item: str):
        matched = []
        for key, data in ENCHANT_DATA.items():
            if item.lower() in str(data.get("applies-to", "")).lower():
                display = get_enchant_display(key, data)
                max_lv  = len(data.get("levels", {}) or {})
                vi_desc = get_vi_desc(key, data)
                trigger = str(data.get("type", ""))
                curse   = is_curse(key, data)
                matched.append((display, key, max_lv, vi_desc, trigger, curse))
        if not matched:
            all_types = get_all_item_types()
            suggest = "  ".join(f"`{t}`" for t in all_types[:12])
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ Không tìm thấy!",
                description=f"Không có phù phép nào cho **{item}**.\n\n**Loại có thể dùng:**\n{suggest}",
                color=COLOR_ERROR
            ), ephemeral=True)
        matched.sort(key=lambda x: x[0])
        PAGE_SIZE = 8
        total_pages = max(1, (len(matched) + PAGE_SIZE - 1) // PAGE_SIZE)
        pages = []
        for pg in range(total_pages):
            chunk = matched[pg * PAGE_SIZE:(pg + 1) * PAGE_SIZE]
            embed = discord.Embed(
                title=f"📖 Phù phép cho: {item.title()}",
                description=f"Tìm thấy **{len(matched)}** phù phép  ·  Trang {pg+1}/{total_pages}",
                color=0x9B59B6, timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            for display, key, max_lv, vi_desc, trigger, curse in chunk:
                emoji = "☠️" if curse else get_type_emoji(trigger)
                short = vi_desc[:85] + "…" if len(vi_desc) > 85 else vi_desc
                embed.add_field(name=f"{emoji} {display}  [Lv.{max_lv}]", value=f"*{short}*\n`/ec info {key}`", inline=False)
            embed.set_footer(text="◀️ ▶️ để chuyển trang  ·  /ec info <tên> để xem chi tiết")
            pages.append(embed)
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0])
        else:
            await interaction.response.send_message(embed=pages[0], view=EnchantPageView(pages, interaction.user.id))

    @ec_group.command(name="search", description="Tìm kiếm phù phép theo từ khóa.")
    @app_commands.describe(query="Từ khóa tìm kiếm")
    async def ec_search(self, interaction: discord.Interaction, query: str):
        q = query.lower()
        results = []
        for key, data in ENCHANT_DATA.items():
            display = get_enchant_display(key, data)
            vi_desc = get_vi_desc(key, data)
            if q in key.lower() or q in display.lower() or q in vi_desc.lower() or \
               q in str(data.get("applies-to", "")).lower() or q in str(data.get("type", "")).lower():
                curse = is_curse(key, data)
                results.append((display, key, len(data.get("levels", {}) or {}), vi_desc, str(data.get("type", "")), curse))
        if not results:
            return await interaction.response.send_message(embed=discord.Embed(
                title="🔍 Không tìm thấy kết quả",
                description=f"Không có phù phép nào khớp với **\"{query}\"**.", color=COLOR_ERROR
            ), ephemeral=True)
        results.sort(key=lambda x: x[0])
        embed = discord.Embed(
            title=f"🔍 Kết quả: \"{query}\"",
            description=f"Tìm thấy **{len(results)}** phù phép",
            color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        for display, key, max_lv, vi_desc, trigger, curse in results[:18]:
            emoji = "☠️" if curse else get_type_emoji(trigger)
            short = vi_desc[:80] + "…" if len(vi_desc) > 80 else vi_desc
            embed.add_field(name=f"{emoji} {display}  [Lv.{max_lv}]", value=f"*{short}*\n`/ec info {key}`", inline=False)
        if len(results) > 18:
            embed.set_footer(text=f"Hiển thị 18/{len(results)} kết quả  ·  Hãy tìm kiếm cụ thể hơn")
        await interaction.response.send_message(embed=embed)

    @ec_group.command(name="all", description="Xem toàn bộ phù phép phân theo loại kích hoạt.")
    async def ec_all(self, interaction: discord.Interaction):
        total = len(ENCHANT_DATA)
        TRIGGER_CATS = [
            ("ATTACK","⚔️","Tấn công",0xE74C3C), ("DEFENSE","🛡️","Phòng thủ",0x3498DB),
            ("MINING","⛏️","Khai thác",0x2ECC71), ("SHOOT","🏹","Cung & Nỏ",0xE67E22),
            ("ARROW_HIT","🎯","Mũi tên trúng",0xE67E22), ("RIGHT_CLICK","🖱️","Chuột phải",0x9B59B6),
            ("HELD","✋","Thường trực",0x1ABC9C), ("EFFECT_STATIC","✨","Luôn hoạt động",0x1ABC9C),
            ("FALL_DAMAGE","🪂","Ngã",0x7F8C8D), ("HOOK_ENTITY","🎣","Móc câu",0x16A085),
            ("CATCH_FISH","🐟","Câu cá",0x16A085), ("BITE_HOOK","🪝","Cá cắn câu",0x16A085),
            ("SWING","💫","Vung vũ khí",0xF1C40F),
        ]
        cat_enchants: dict[str, list] = {}
        for key, data in ENCHANT_DATA.items():
            trigger = str(data.get("type", "")).upper()
            display = get_enchant_display(key, data)
            vi_desc = get_vi_desc(key, data)
            curse   = is_curse(key, data)
            max_lv  = len(data.get("levels", {}) or {})
            placed  = False
            for tk, *_ in TRIGGER_CATS:
                if tk in trigger:
                    cat_enchants.setdefault(tk, []).append((display, key, max_lv, vi_desc, curse))
                    placed = True; break
            if not placed:
                cat_enchants.setdefault("OTHER", []).append((display, key, max_lv, vi_desc, curse))
        cat_keys_with_data = [tk for tk, *_ in TRIGGER_CATS if cat_enchants.get(tk)]
        if cat_enchants.get("OTHER"): cat_keys_with_data.append("OTHER")
        total_pages = 1 + len(cat_keys_with_data)
        pages = []
        overview = discord.Embed(
            title=f"📚 Toàn bộ Phù Phép  ·  {total} enchants",
            description="Phân loại theo cơ chế kích hoạt\n**Bấm ▶️ để duyệt từng nhóm**",
            color=0x9B59B6, timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        for tk, emoji, label, _ in TRIGGER_CATS:
            lst = cat_enchants.get(tk, [])
            if not lst: continue
            overview.add_field(
                name=f"{emoji} {label}  ({len(lst)})",
                value=", ".join(e[0] for e in lst[:6]) + (f" *+{len(lst)-6}*" if len(lst) > 6 else ""),
                inline=False
            )
        if cat_enchants.get("OTHER"):
            lst = cat_enchants["OTHER"]
            overview.add_field(name=f"🔮 Khác  ({len(lst)})", value=", ".join(e[0] for e in lst[:6]), inline=False)
        overview.set_footer(text=f"Trang 1 / {total_pages}  ·  ◀️ ▶️ để chuyển nhóm")
        pages.append(overview)
        all_cats = [(tk, emoji, label, color) for tk, emoji, label, color in TRIGGER_CATS] + [("OTHER","🔮","Khác",0x7F8C8D)]
        for pg_idx, (tk, emoji, label, color) in enumerate(all_cats, start=2):
            lst = cat_enchants.get(tk, [])
            if not lst: continue
            lst.sort(key=lambda x: x[0])
            page_embed = discord.Embed(
                title=f"{emoji} {label}  ·  {len(lst)} phù phép",
                color=color, timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            for display, key, max_lv, vi_desc, curse in lst:
                badge = "☠️ " if curse else ""
                short = vi_desc[:80] + "…" if len(vi_desc) > 80 else vi_desc
                page_embed.add_field(name=f"{badge}{display}  [Lv.{max_lv}]", value=f"*{short}*\n`/ec info {key}`", inline=False)
                if len(page_embed.fields) >= 15:
                    page_embed.add_field(name="…", value=f"+{len(lst)-15} phù phép khác.", inline=False); break
            page_embed.set_footer(text=f"Trang {len(pages)+1} / {total_pages}  ·  ◀️ ▶️")
            pages.append(page_embed)
        await interaction.response.send_message(embed=pages[0], view=EnchantPageView(pages, interaction.user.id))

    @ec_group.command(name="add", description="[Admin] Thêm phù phép mới vào danh sách.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ec_add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddEnchantModal())

    @ec_group.command(name="remove", description="[Admin] Xóa một phù phép khỏi danh sách.")
    @app_commands.describe(name="ID phù phép muốn xóa")
    @app_commands.autocomplete(name=enchant_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ec_remove(self, interaction: discord.Interaction, name: str):
        data = ENCHANT_DATA.get(name)
        if not data:
            return await interaction.response.send_message(embed=discord.Embed(
                title="❌ Không tìm thấy!", description=f"Không có phù phép `{name}`.", color=COLOR_ERROR
            ), ephemeral=True)
        display = get_enchant_display(name, data)
        vi_desc = get_vi_desc(name, data)

        class ConfirmRemoveView(discord.ui.View):
            def __init__(self_v):
                super().__init__(timeout=30)

            @discord.ui.button(label="✅ Xác nhận xóa", style=discord.ButtonStyle.danger)
            async def confirm(self_v, itx: discord.Interaction, button: discord.ui.Button):
                if itx.user.id != interaction.user.id:
                    return await itx.response.send_message("❌ Chỉ người dùng lệnh mới xác nhận được!", ephemeral=True)
                try:
                    with open(ENCHANTS_FILE, "r", encoding="utf-8") as f:
                        raw_yaml = yaml.safe_load(f) or {}
                    raw_yaml.pop(name, None)
                    with open(ENCHANTS_FILE, "w", encoding="utf-8") as f:
                        yaml.dump(raw_yaml, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                    ENCHANT_DATA.pop(name, None)
                    for item in self_v.children: item.disabled = True
                    await itx.response.edit_message(embed=discord.Embed(
                        title=f"🗑️ Đã xóa: {display}",
                        description=f"Còn lại **{len(ENCHANT_DATA)}** phù phép.", color=COLOR_SUCCESS,
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    ), view=self_v)
                except Exception as e:
                    await itx.response.send_message(embed=discord.Embed(title="❌ Lỗi!", description=str(e), color=COLOR_ERROR), ephemeral=True)

            @discord.ui.button(label="❌ Hủy", style=discord.ButtonStyle.secondary)
            async def cancel(self_v, itx: discord.Interaction, button: discord.ui.Button):
                if itx.user.id != interaction.user.id:
                    return await itx.response.send_message("❌ Không phải lượt của bạn!", ephemeral=True)
                for item in self_v.children: item.disabled = True
                await itx.response.edit_message(embed=discord.Embed(
                    title="↩️ Đã hủy", description=f"Không xóa `{name}`.", color=COLOR_WARNING
                ), view=self_v)

        await interaction.response.send_message(embed=discord.Embed(
            title=f"⚠️ Xác nhận xóa: {display}",
            description=f"```\n{vi_desc}\n```\nBạn có chắc muốn xóa `{name}` không?",
            color=COLOR_WARNING, timestamp=datetime.datetime.now(datetime.timezone.utc)
        ).set_footer(text="Tự hủy sau 30 giây"), view=ConfirmRemoveView(), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EnchantsCog(bot))
