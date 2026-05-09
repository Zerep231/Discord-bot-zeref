import datetime
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from utils import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_INFO, COIN, DAILY_AMOUNT


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @app_commands.command(name="coin", description="💰 Xem ví coin của bạn hoặc người khác")
    @app_commands.describe(member="Thành viên muốn xem (để trống = bản thân)")
    async def cmd_coin(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await self.db.ensure_user(target.id, str(target))
        user = await self.db.get_user(target.id)
        history = await self.db.get_history(target.id, 5)
        embed = discord.Embed(
            title=f"{COIN} Ví Coin — {target.display_name}",
            color=0xFFD700,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💰 Số dư",     value=f"**{user['coins']:,}** coin", inline=True)
        embed.add_field(name="📈 Tổng kiếm", value=f"**{user['total_earned']:,}** coin", inline=True)
        embed.add_field(name="💬 Tin nhắn",  value=f"**{user['msg_week']:,}** tuần này", inline=True)
        if history:
            lines = []
            for h in history:
                sign = "+" if h["amount"] > 0 else ""
                lines.append(f"`{h['created_at'][:10]}` {sign}{h['amount']:,} — {h['note'] or h['type']}")
            embed.add_field(name="📋 Lịch sử gần đây", value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="🎁 Điểm danh nhận coin mỗi ngày")
    async def cmd_daily(self, interaction: discord.Interaction):
        await self.db.ensure_user(interaction.user.id, str(interaction.user))
        if not await self.db.can_claim_daily(interaction.user.id):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"⏳ Bạn đã điểm danh hôm nay rồi!\nQuay lại sau **24 giờ**.",
                    color=COLOR_WARNING
                ), ephemeral=True)
        await self.db.add_coins(interaction.user.id, DAILY_AMOUNT, "daily")
        await self.db.set_last_daily(interaction.user.id)
        user = await self.db.get_user(interaction.user.id)
        embed = discord.Embed(
            title="🎁 Điểm Danh Thành Công!",
            description=(f"Bạn nhận được **{DAILY_AMOUNT:,}{COIN}** hôm nay!\n"
                         f"💰 Số dư hiện tại: **{user['coins']:,}{COIN}**"),
            color=COLOR_SUCCESS,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="top", description="🏆 Bảng xếp hạng đại gia coin")
    async def cmd_top(self, interaction: discord.Interaction):
        data = await self.db.get_top_coins(10)
        embed = discord.Embed(
            title=f"{COIN} Bảng Xếp Hạng Coin",
            color=0xFFD700,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        medals = ["🥇", "🥈", "🥉"]
        lines = [
            f"{medals[i] if i < 3 else f'`{i+1}.`'} **{r['username']}** — {r['coins']:,}{COIN}"
            for i, r in enumerate(data)
        ]
        embed.description = "\n".join(lines) if lines else "Chưa có dữ liệu."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="transfer", description="💸 Chuyển coin cho thành viên khác")
    @app_commands.describe(member="Người nhận", amount="Số coin muốn chuyển")
    async def cmd_transfer(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ Số lượng phải > 0!", color=COLOR_ERROR), ephemeral=True)
        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ Không thể tự chuyển cho chính mình!", color=COLOR_ERROR), ephemeral=True)
        if member.bot:
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ Không thể chuyển coin cho bot!", color=COLOR_ERROR), ephemeral=True)
        await self.db.ensure_user(interaction.user.id, str(interaction.user))
        await self.db.ensure_user(member.id, str(member))
        if not await self.db.transfer_coins(interaction.user.id, member.id, amount):
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"❌ Bạn không đủ coin! Cần **{amount:,}{COIN}**", color=COLOR_ERROR), ephemeral=True)
        sender_bal = await self.db.get_coins(interaction.user.id)
        embed = discord.Embed(
            title=f"{COIN} Chuyển Thành Công",
            description=(f"Đã chuyển **{amount:,}{COIN}** cho {member.mention}\n"
                         f"💰 Số dư của bạn còn: **{sender_bal:,}{COIN}**"),
            color=COLOR_SUCCESS,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Từ {interaction.user.display_name} → {member.display_name}")
        await interaction.response.send_message(embed=embed)
        try:
            await member.send(embed=discord.Embed(
                title=f"🧧 Bạn nhận được {amount:,}{COIN}!",
                description=f"{interaction.user.mention} vừa chuyển coin cho bạn tại **{interaction.guild.name}**.",
                color=COLOR_SUCCESS
            ))
        except Exception:
            pass

    @app_commands.command(name="lixi", description="🧧 Mở phong bao lì xì công khai cho mọi người trong kênh")
    @app_commands.describe(amount="Tổng số coin lì xì")
    async def cmd_lixi(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ Số coin phải > 0!", color=COLOR_ERROR), ephemeral=True)

        await self.db.ensure_user(interaction.user.id, str(interaction.user))

        if not await self.db.deduct_coins(interaction.user.id, amount, note="lixi_pool"):
            bal = await self.db.get_coins(interaction.user.id)
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"❌ Không đủ coin! Bạn chỉ có **{bal:,}{COIN}**", color=COLOR_ERROR
                ), ephemeral=True)

        claimers: list[int] = []
        lock = asyncio.Lock()
        expire_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)

        class LiXiView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="Nhận lì xì", emoji="🧧", style=discord.ButtonStyle.danger)
            async def claim(self, itx: discord.Interaction, _: discord.ui.Button):
                if itx.user.bot:
                    return await itx.response.send_message("❌ Bot không thể nhận lì xì.", ephemeral=True)
                async with lock:
                    if itx.user.id == interaction.user.id:
                        return await itx.response.send_message("❌ Người tạo lì xì không thể tự nhận.", ephemeral=True)
                    if itx.user.id in claimers:
                        return await itx.response.send_message("⚠️ Bạn đã bấm nhận rồi!", ephemeral=True)
                    claimers.append(itx.user.id)
                    await itx.response.send_message("✅ Bạn đã vào danh sách nhận lì xì!", ephemeral=True)

        view = LiXiView()
        embed = discord.Embed(
            title="🧧 Lì Xì Công Khai",
            description=(
                f"{interaction.user.mention} mở phong bao **{amount:,}{COIN}** cho cả kênh!\n"
                f"Ai bấm nút **🧧 Nhận lì xì** trong vòng **60 giây** sẽ được chia đều.\n\n"
                f"⏰ Kết thúc: <t:{int(expire_at.timestamp())}:R>"
            ),
            color=0xFF0000,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="🧧 Hệ thống Lì Xì Zerbot2")
        await interaction.response.send_message(embed=embed, view=view)

        await asyncio.sleep(60)
        for item in view.children:
            item.disabled = True

        if not claimers:
            await self.db.add_coins(interaction.user.id, amount, note="lixi_refund")
            embed.description += "\n\n😴 Không ai nhận lì xì, tiền đã hoàn về chủ bao."
            await interaction.edit_original_response(embed=embed, view=view)
            return

        share = amount // len(claimers)
        rem = amount % len(claimers)
        payout_lines = []
        for idx, uid in enumerate(claimers):
            bonus = 1 if idx < rem else 0
            payout = share + bonus
            if payout <= 0:
                continue
            member = interaction.guild.get_member(uid)
            username = str(member) if member else f"user_{uid}"
            await self.db.ensure_user(uid, username)
            await self.db.add_coins(uid, payout, note=f"lixi_from:{interaction.user.id}")
            name = member.mention if member else f"<@{uid}>"
            payout_lines.append(f"• {name}: **{payout:,}{COIN}**")

        result_embed = discord.Embed(
            title="🧧 Kết quả lì xì",
            description=(
                f"Tổng quỹ: **{amount:,}{COIN}**\n"
                f"Số người nhận: **{len(claimers)}**\n"
                f"Mỗi người tối thiểu: **{share:,}{COIN}**\n\n" + "\n".join(payout_lines[:20])
            ),
            color=COLOR_SUCCESS,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if len(payout_lines) > 20:
            result_embed.set_footer(text=f"... và {len(payout_lines)-20} người khác")
        await interaction.edit_original_response(embed=result_embed, view=view)

    @app_commands.command(name="lichsu", description="📋 Xem lịch sử giao dịch coin của bạn")
    async def cmd_lichsu(self, interaction: discord.Interaction):
        await self.db.ensure_user(interaction.user.id, str(interaction.user))
        history = await self.db.get_history(interaction.user.id, 15)
        if not history:
            return await interaction.response.send_message(
                embed=discord.Embed(description="Chưa có giao dịch nào.", color=COLOR_INFO), ephemeral=True)
        embed = discord.Embed(
            title=f"📋 Lịch sử giao dịch — {interaction.user.display_name}",
            color=COLOR_INFO,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        lines = []
        for h in history:
            sign = "➕" if h["amount"] > 0 else "➖"
            amt  = abs(h["amount"])
            lines.append(f"{sign} **{amt:,}{COIN}** · {h['note'] or h['type']} · `{h['created_at'][:10]}`")
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
