import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_INFO,
    COIN, MC_ITEMS, ENCHANT_DATA,
    book_price, get_enchant_display, get_vi_desc, is_curse, get_type_color, to_roman,
    get_guild_shop, save_guild_shop,
)
from cogs.enchants import enchant_autocomplete


class ExchangeItemModal(discord.ui.Modal, title="Đổi vật phẩm Minecraft"):
    quantity = discord.ui.TextInput(label="Số lượng muốn đổi", placeholder="VD: 5", min_length=1, max_length=4)

    def __init__(self, item_key: str, info: dict, guild_id: int):
        super().__init__()
        self.item_key = item_key
        self.info     = info
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        db = interaction.client.db
        try:
            qty = int(self.quantity.value)
            if qty <= 0: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Số lượng không hợp lệ!", ephemeral=True)
        total = self.info["cost"] * qty
        await db.ensure_user(interaction.user.id, str(interaction.user))
        if not await db.deduct_coins(interaction.user.id, total, f"exchange:{self.item_key}x{qty}"):
            return await interaction.response.send_message(
                f"❌ Không đủ coin! Cần **{total:,}{COIN}**", ephemeral=True)
        order_id = await db.create_order(
            interaction.user.id, str(interaction.user), self.guild_id,
            total, "mc_item", self.item_key, qty, f"{self.info['name']} x{qty}"
        )
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Đơn đổi đã tạo!",
            description=(f"{self.info['emoji']} **{self.info['name']} ×{qty}**\n"
                         f"{COIN} Đã trừ: **{total:,} coin**\n📋 Mã đơn: `#{order_id}`\n\n"
                         "Admin sẽ trao vật phẩm trong game sau khi xử lý!"),
            color=COLOR_SUCCESS
        ), ephemeral=True)


class ExchangeShopView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        for key, info in MC_ITEMS.items():
            btn = discord.ui.Button(
                label=f"{info['name']} ({info['cost']:,}{COIN})",
                emoji=info["emoji"], custom_id=f"shop_{key}")
            btn.callback = self._make_cb(key, info)
            self.add_item(btn)

    def _make_cb(self, key, info):
        async def cb(interaction: discord.Interaction):
            await interaction.response.send_modal(ExchangeItemModal(key, info, self.guild_id))
        return cb


class ShopBuyModal(discord.ui.Modal, title="Mua từ Shop"):
    qty_input = discord.ui.TextInput(label="Số lượng (để 1 nếu không có số lượng)", placeholder="1", min_length=1, max_length=4)

    def __init__(self, item_key: str, item: dict, guild_id: int):
        super().__init__()
        self.item_key = item_key
        self.item     = item
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        db = interaction.client.db
        try:
            qty = int(self.qty_input.value)
            if qty <= 0: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Số lượng không hợp lệ!", ephemeral=True)
        total = self.item["price"] * qty
        await db.ensure_user(interaction.user.id, str(interaction.user))
        if not await db.deduct_coins(interaction.user.id, total, f"shop:{self.item_key}x{qty}"):
            bal = await db.get_coins(interaction.user.id)
            return await interaction.response.send_message(
                f"❌ Không đủ coin! Cần **{total:,}{COIN}**, bạn có **{bal:,}{COIN}**", ephemeral=True)
        order_id = await db.create_order(
            interaction.user.id, str(interaction.user), self.guild_id,
            total, "shop_item", self.item_key, qty,
            f"{self.item.get('emoji','')} {self.item['name']} x{qty}"
        )
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Mua thành công!",
            description=(f"{self.item.get('emoji','')} **{self.item['name']} ×{qty}**\n"
                         f"{COIN} Đã trừ: **{total:,} coin**\n📋 Mã đơn: `#{order_id}`\n\n"
                         "Admin sẽ trao vật phẩm trong game sau khi xử lý!"),
            color=COLOR_SUCCESS
        ), ephemeral=True)


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /exchange — đổi MC vật phẩm ──────────────────────────────────────────

    @app_commands.command(name="exchange", description="⛏️ Đổi coin lấy vật phẩm Minecraft")
    async def cmd_exchange(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⛏️ Cửa Hàng Minecraft",
            description="Chọn vật phẩm bạn muốn đổi. Admin sẽ trao trong game!",
            color=0x5865F2,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        for key, info in MC_ITEMS.items():
            embed.add_field(name=f"{info['emoji']} {info['name']}", value=f"**{info['cost']:,}{COIN}** / 1 cái", inline=True)
        await interaction.response.send_message(embed=embed, view=ExchangeShopView(interaction.guild_id))

    # ── /enchant_shop — mua sách phù phép ────────────────────────────────────

    @app_commands.command(name="enchant_shop", description="📚 Đổi coin lấy sách phù phép Advanced Enchantments")
    @app_commands.describe(enchant="Tên phù phép (gõ để tìm)", level="Cấp độ sách muốn mua")
    @app_commands.autocomplete(enchant=enchant_autocomplete)
    async def cmd_enchant_shop(self, interaction: discord.Interaction, enchant: str, level: int = 1):
        data = ENCHANT_DATA.get(enchant)
        if not data:
            return await interaction.response.send_message(
                embed=discord.Embed(title="❌ Không tìm thấy phù phép!", description=f"`{enchant}`", color=COLOR_ERROR),
                ephemeral=True)
        max_lv = len(data.get("levels", {}) or {})
        if level < 1 or level > max_lv:
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"❌ Cấp hợp lệ: 1 – {max_lv}", color=COLOR_ERROR), ephemeral=True)

        display = get_enchant_display(enchant, data)
        vi_desc = get_vi_desc(enchant, data)
        price   = book_price(enchant, level)
        trigger = str(data.get("type", ""))
        color   = 0x992D22 if is_curse(enchant, data) else get_type_color(trigger)

        await self.db.ensure_user(interaction.user.id, str(interaction.user))
        user = await self.db.get_user(interaction.user.id)
        can_afford = user["coins"] >= price

        embed = discord.Embed(
            title=f"📚 Mua Sách: {display} {to_roman(level)}",
            description=f"```\n{vi_desc}\n```",
            color=color, timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="🏅 Cấp",          value=f"**{to_roman(level)}** / {to_roman(max_lv)}", inline=True)
        embed.add_field(name="💰 Giá",           value=f"**{price:,}{COIN}**", inline=True)
        embed.add_field(name="👛 Số dư",          value=f"**{user['coins']:,}{COIN}**", inline=True)
        embed.add_field(name="📦 Áp dụng cho",    value=str(data.get("applies-to", "?")), inline=False)

        lv_prices = [f"Lv.{i}: **{book_price(enchant, i):,}{COIN}**" for i in range(1, min(max_lv+1, 6))]
        embed.add_field(name="💡 Bảng giá (x2 mỗi cấp)", value="  ➜  ".join(lv_prices), inline=False)
        embed.add_field(
            name="🧮 Công thức giá",
            value="`Giá = 100 × 2^(level-1)`  →  Lv1=100, Lv2=200, Lv3=400, Lv4=800",
            inline=False,
        )

        if not can_afford:
            embed.set_footer(text=f"⚠️ Bạn thiếu {price - user['coins']:,} coin!")

        db = self.db

        class ConfirmBuyView(discord.ui.View):
            def __init__(self_v):
                super().__init__(timeout=30)

            @discord.ui.button(label=f"✅ Mua ({price:,} coin)", style=discord.ButtonStyle.success, disabled=not can_afford)
            async def confirm(self_v, itx: discord.Interaction, btn: discord.ui.Button):
                if itx.user.id != interaction.user.id:
                    return await itx.response.send_message("❌ Không phải lượt của bạn!", ephemeral=True)
                await db.ensure_user(itx.user.id, str(itx.user))
                if not await db.deduct_coins(itx.user.id, price, f"book:{enchant}:{level}"):
                    for c in self_v.children: c.disabled = True
                    return await itx.response.edit_message(
                        embed=discord.Embed(description=f"❌ Không đủ coin! Cần **{price:,}{COIN}**", color=COLOR_ERROR), view=self_v)
                order_id = await db.create_order(
                    itx.user.id, str(itx.user), interaction.guild_id,
                    price, "enchant_book", enchant, level, f"{display} {to_roman(level)}")
                for c in self_v.children: c.disabled = True
                await itx.response.edit_message(embed=discord.Embed(
                    title="✅ Đơn đặt sách thành công!",
                    description=(f"📚 **{display} {to_roman(level)}**\n"
                                 f"{COIN} Đã trừ: **{price:,} coin**\n📋 Mã đơn: `#{order_id}`\n\n"
                                 f"Admin dùng `/ae book {enchant} {level}` để trao sách!"),
                    color=COLOR_SUCCESS), view=self_v)

            @discord.ui.button(label="❌ Hủy", style=discord.ButtonStyle.secondary)
            async def cancel(self_v, itx: discord.Interaction, btn: discord.ui.Button):
                if itx.user.id != interaction.user.id:
                    return await itx.response.send_message("❌ Không phải lượt của bạn!", ephemeral=True)
                for c in self_v.children: c.disabled = True
                await itx.response.edit_message(embed=discord.Embed(description="↩️ Đã hủy.", color=COLOR_WARNING), view=self_v)

        await interaction.response.send_message(embed=embed, view=ConfirmBuyView(), ephemeral=True)

    # ── /shop — cửa hàng động ────────────────────────────────────────────────

    @app_commands.command(name="shop", description="🛒 Xem cửa hàng vật phẩm của server")
    async def cmd_shop(self, interaction: discord.Interaction):
        items = get_guild_shop(interaction.guild_id)
        if not items:
            return await interaction.response.send_message(embed=discord.Embed(
                title="🛒 Cửa hàng trống!",
                description="Admin chưa thêm vật phẩm nào.\nDùng `/shop_add` để thêm.",
                color=COLOR_INFO
            ), ephemeral=True)
        embed = discord.Embed(
            title=f"🛒 Cửa hàng — {interaction.guild.name}",
            description="Bấm nút để mua vật phẩm. Admin sẽ trao trong game!",
            color=0x5865F2,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        for key, item in list(items.items())[:20]:
            stock_txt = "Không giới hạn" if item.get("stock", -1) == -1 else f"{item['stock']} còn lại"
            embed.add_field(
                name=f"{item.get('emoji','📦')} {item['name']}",
                value=f"💰 **{item['price']:,}{COIN}**\n{item.get('description','')}\n*{stock_txt}*",
                inline=True
            )

        class ShopView(discord.ui.View):
            def __init__(self_v):
                super().__init__(timeout=60)
                for key, item in list(items.items())[:5]:
                    btn = discord.ui.Button(
                        label=f"{item['name']} ({item['price']:,}{COIN})",
                        emoji=item.get("emoji", "📦"),
                        custom_id=f"shopbuy_{key}"
                    )
                    btn.callback = self_v._make_cb(key, item)
                    self_v.add_item(btn)

            def _make_cb(self_v, key, item):
                async def cb(itx: discord.Interaction):
                    await itx.response.send_modal(ShopBuyModal(key, item, itx.guild_id))
                return cb

        await interaction.response.send_message(embed=embed, view=ShopView())

    @app_commands.command(name="shop_add", description="[Admin] Thêm vật phẩm vào cửa hàng")
    @app_commands.describe(key="Mã vật phẩm (không dấu, không khoảng trắng)", name="Tên hiển thị",
                           price="Giá coin", emoji="Emoji", description="Mô tả ngắn")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_shop_add(self, interaction: discord.Interaction, key: str, name: str, price: int,
                            emoji: str = "📦", description: str = ""):
        if price <= 0:
            return await interaction.response.send_message("❌ Giá phải > 0!", ephemeral=True)
        key = key.lower().replace(" ", "_")
        items = get_guild_shop(interaction.guild_id)
        items[key] = {"name": name, "price": price, "emoji": emoji, "description": description, "stock": -1}
        save_guild_shop(interaction.guild_id, items)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Đã thêm vật phẩm!",
            description=f"{emoji} **{name}** — **{price:,}{COIN}**\nKey: `{key}`",
            color=COLOR_SUCCESS
        ))

    @app_commands.command(name="shop_remove", description="[Admin] Xóa vật phẩm khỏi cửa hàng")
    @app_commands.describe(key="Mã vật phẩm muốn xóa")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_shop_remove(self, interaction: discord.Interaction, key: str):
        items = get_guild_shop(interaction.guild_id)
        if key not in items:
            return await interaction.response.send_message("❌ Không tìm thấy vật phẩm!", ephemeral=True)
        removed = items.pop(key)
        save_guild_shop(interaction.guild_id, items)
        await interaction.response.send_message(embed=discord.Embed(
            title="🗑️ Đã xóa!",
            description=f"Đã xóa **{removed['name']}** (`{key}`) khỏi cửa hàng.",
            color=COLOR_WARNING
        ))

    @app_commands.command(name="shop_list", description="[Admin] Xem danh sách vật phẩm trong shop")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_shop_list(self, interaction: discord.Interaction):
        items = get_guild_shop(interaction.guild_id)
        if not items:
            return await interaction.response.send_message("Cửa hàng trống!", ephemeral=True)
        lines = [f"`{k}` — {v.get('emoji','')} **{v['name']}** — **{v['price']:,}{COIN}**" for k, v in items.items()]
        await interaction.response.send_message(embed=discord.Embed(
            title="📋 Danh sách shop",
            description="\n".join(lines),
            color=COLOR_INFO
        ), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
