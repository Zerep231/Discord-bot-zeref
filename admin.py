import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COIN, MC_ITEMS, to_roman, EnchantPageView


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    admin_group = app_commands.Group(
        name="admin",
        description="🔒 Lệnh quản trị hệ thống coin & đơn hàng",
        default_permissions=discord.Permissions(administrator=True)
    )

    @admin_group.command(name="give", description="Cho coin member")
    @app_commands.describe(member="Thành viên nhận", amount="Số coin")
    async def admin_give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Số coin phải > 0!", ephemeral=True)
        await self.db.ensure_user(member.id, str(member))
        new_bal = await self.db.add_coins(member.id, amount, f"admin_give by {interaction.user}")
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Đã cộng coin",
            description=(f"Cộng **{amount:,}{COIN}** cho **{member.display_name}**\n"
                         f"💰 Số dư mới: **{new_bal:,}{COIN}**"),
            color=COLOR_SUCCESS
        ))
        try:
            await member.send(embed=discord.Embed(
                title=f"{COIN} Bạn nhận được coin!",
                description=f"Admin **{interaction.user.display_name}** đã cộng **{amount:,}{COIN}** cho bạn!",
                color=COLOR_SUCCESS
            ))
        except Exception:
            pass

    @admin_group.command(name="take", description="Trừ coin member")
    @app_commands.describe(member="Thành viên bị trừ", amount="Số coin")
    async def admin_take(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Số coin phải > 0!", ephemeral=True)
        await self.db.ensure_user(member.id, str(member))
        if await self.db.deduct_coins(member.id, amount, f"admin_take by {interaction.user}"):
            bal = await self.db.get_coins(member.id)
            await interaction.response.send_message(embed=discord.Embed(
                description=f"✅ Trừ **{amount:,}{COIN}** của **{member.display_name}** — còn lại: **{bal:,}{COIN}**",
                color=COLOR_SUCCESS
            ))
        else:
            await interaction.response.send_message(embed=discord.Embed(
                description=f"❌ **{member.display_name}** không đủ **{amount:,}** coin!",
                color=COLOR_ERROR
            ), ephemeral=True)

    @admin_group.command(name="set", description="Đặt số coin chính xác cho member")
    @app_commands.describe(member="Thành viên", amount="Số coin mới")
    async def admin_set(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount < 0:
            return await interaction.response.send_message("❌ Số coin không thể âm!", ephemeral=True)
        await self.db.ensure_user(member.id, str(member))
        await self.db.set_coins(member.id, amount, f"admin_set by {interaction.user}")
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ Đặt coin của **{member.display_name}** thành **{amount:,}{COIN}**",
            color=COLOR_SUCCESS
        ))

    @admin_group.command(name="pending", description="Xem đơn đổi đồ đang chờ xử lý")
    async def admin_pending(self, interaction: discord.Interaction):
        orders = await self.db.get_pending_orders(interaction.guild_id)
        if not orders:
            return await interaction.response.send_message(embed=discord.Embed(
                description="✅ Không có đơn nào đang chờ!", color=COLOR_SUCCESS
            ))
        pages = []
        chunk = 5
        for i in range(0, len(orders), chunk):
            embed = discord.Embed(
                title=f"📋 Đơn Đang Chờ ({len(orders)} đơn)",
                color=0xFF6B00,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            for o in orders[i:i+chunk]:
                if o["item_type"] == "enchant_book":
                    item_str  = f"📚 Sách `{o['item_key']}` {to_roman(o['quantity'])}"
                    cmd_hint  = f"`/ae book {o['item_key']} {o['quantity']}`"
                elif o["item_type"] == "shop_item":
                    item_str  = f"🛒 Shop `{o['item_key']}` ×{o['quantity']}"
                    cmd_hint  = "trao vật phẩm trong game"
                else:
                    info      = MC_ITEMS.get(o["item_key"], {})
                    item_str  = f"{info.get('emoji','📦')} {info.get('name', o['item_key'])} ×{o['quantity']}"
                    cmd_hint  = "trao vật phẩm trong game"
                embed.add_field(
                    name=f"#{o['id']} — {o['username']}",
                    value=(f"{item_str}\n"
                           f"💰 Trả: **{o['coins_spent']:,}{COIN}**\n"
                           f"📅 {o['created_at'][:16]}\n"
                           f"⌨️ {cmd_hint}"),
                    inline=False
                )
            pages.append(embed)
        if len(pages) == 1:
            return await interaction.response.send_message(embed=pages[0])
        await interaction.response.send_message(embed=pages[0], view=EnchantPageView(pages, interaction.user.id))

    @admin_group.command(name="fulfill", description="Đánh dấu hoàn thành đơn hàng")
    @app_commands.describe(order_id="Mã đơn #ID")
    async def admin_fulfill(self, interaction: discord.Interaction, order_id: int):
        ok = await self.db.fulfill_order(order_id, str(interaction.user))
        if not ok:
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"❌ Không tìm thấy đơn `#{order_id}` hoặc đã xử lý!", color=COLOR_ERROR),
                ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ Đã đánh dấu hoàn thành đơn `#{order_id}`!", color=COLOR_SUCCESS
        ))

    @admin_group.command(name="cancel", description="Hủy đơn & hoàn coin cho member")
    @app_commands.describe(order_id="Mã đơn #ID")
    async def admin_cancel(self, interaction: discord.Interaction, order_id: int):
        order = await self.db.cancel_order(order_id, interaction.guild_id)
        if not order:
            return await interaction.response.send_message(embed=discord.Embed(
                description="❌ Không tìm thấy đơn hoặc đã xử lý xong!", color=COLOR_ERROR
            ), ephemeral=True)
        await self.db.add_coins(order["user_id"], order["coins_spent"], f"refund order#{order_id}")
        await interaction.response.send_message(embed=discord.Embed(
            description=(f"↩️ Đã hủy đơn `#{order_id}` và hoàn **{order['coins_spent']:,}{COIN}** "
                         f"cho **{order['username']}**."),
            color=COLOR_WARNING
        ))

    @admin_group.command(name="coins", description="Xem coin của một thành viên")
    @app_commands.describe(member="Thành viên")
    async def admin_coins(self, interaction: discord.Interaction, member: discord.Member):
        await self.db.ensure_user(member.id, str(member))
        user = await self.db.get_user(member.id)
        await interaction.response.send_message(embed=discord.Embed(
            description=(f"💰 **{member.display_name}**: **{user['coins']:,}{COIN}**\n"
                         f"📈 Tổng kiếm: **{user['total_earned']:,}{COIN}**"),
            color=0xFFD700
        ), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
