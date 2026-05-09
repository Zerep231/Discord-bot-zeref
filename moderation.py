import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_MOD,
    add_warn, get_warns, clear_warns, parse_duration,
)


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    mod_group = app_commands.Group(
        name="mod",
        description="🔨 Các lệnh kiểm duyệt của moderator",
        default_permissions=discord.Permissions(manage_messages=True)
    )

    @mod_group.command(name="warn", description="Cảnh báo một thành viên")
    @app_commands.describe(member="Thành viên bị cảnh báo", reason="Lý do cảnh báo")
    async def mod_warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if member.bot:
            return await interaction.response.send_message("❌ Không thể cảnh báo bot!", ephemeral=True)
        if member.id == interaction.user.id:
            return await interaction.response.send_message("❌ Không thể tự cảnh báo bản thân!", ephemeral=True)
        count = add_warn(interaction.guild_id, member.id, reason, str(interaction.user))
        embed = discord.Embed(
            title="⚠️ Cảnh Báo",
            color=COLOR_WARNING,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="👤 Thành viên",  value=member.mention, inline=True)
        embed.add_field(name="📋 Lý do",       value=reason,         inline=True)
        embed.add_field(name="🔢 Lần cảnh báo",value=f"**{count}**", inline=True)
        embed.add_field(name="🛡️ Mod",         value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
        try:
            await member.send(embed=discord.Embed(
                title="⚠️ Bạn đã bị cảnh báo!",
                description=f"**Server:** {interaction.guild.name}\n**Lý do:** {reason}\n**Lần {count}**",
                color=COLOR_WARNING
            ))
        except Exception:
            pass

    @mod_group.command(name="warns", description="Xem danh sách cảnh báo của một thành viên")
    @app_commands.describe(member="Thành viên cần xem")
    async def mod_warns(self, interaction: discord.Interaction, member: discord.Member):
        warns = get_warns(interaction.guild_id, member.id)
        embed = discord.Embed(
            title=f"📋 Cảnh Báo — {member.display_name}",
            color=COLOR_WARNING if warns else COLOR_SUCCESS,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if not warns:
            embed.description = "✅ Không có cảnh báo nào!"
        else:
            for i, w in enumerate(warns, 1):
                embed.add_field(
                    name=f"#{i} — {w['time'][:10]}",
                    value=f"**Lý do:** {w['reason']}\n**Mod:** {w['mod']}",
                    inline=False
                )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @mod_group.command(name="clearwarns", description="Xóa toàn bộ cảnh báo của một thành viên")
    @app_commands.describe(member="Thành viên cần xóa cảnh báo")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def mod_clearwarns(self, interaction: discord.Interaction, member: discord.Member):
        clear_warns(interaction.guild_id, member.id)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ Đã xóa toàn bộ cảnh báo của **{member.display_name}**!",
            color=COLOR_SUCCESS
        ))

    @mod_group.command(name="kick", description="Kick một thành viên ra khỏi server")
    @app_commands.describe(member="Thành viên bị kick", reason="Lý do")
    @app_commands.checks.has_permissions(kick_members=True)
    async def mod_kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Không có lý do"):
        if not interaction.guild.me.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ Bot không có quyền kick!", ephemeral=True)
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ Không thể kick thành viên có role cao hơn bot!", ephemeral=True)
        try:
            await member.send(embed=discord.Embed(
                title="👢 Bạn đã bị kick!",
                description=f"**Server:** {interaction.guild.name}\n**Lý do:** {reason}",
                color=COLOR_MOD
            ))
        except Exception:
            pass
        await member.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=discord.Embed(
            title="👢 Đã Kick!",
            description=f"**{member.display_name}** đã bị kick.\n**Lý do:** {reason}",
            color=COLOR_MOD,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        ))

    @mod_group.command(name="ban", description="Ban một thành viên khỏi server")
    @app_commands.describe(member="Thành viên bị ban", reason="Lý do", delete_days="Xóa tin nhắn (ngày)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def mod_ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Không có lý do",
                      delete_days: int = 0):
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ Bot không có quyền ban!", ephemeral=True)
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ Không thể ban thành viên có role cao hơn bot!", ephemeral=True)
        try:
            await member.send(embed=discord.Embed(
                title="🔨 Bạn đã bị ban!",
                description=f"**Server:** {interaction.guild.name}\n**Lý do:** {reason}",
                color=COLOR_MOD
            ))
        except Exception:
            pass
        await member.ban(reason=f"{interaction.user}: {reason}", delete_message_days=min(delete_days, 7))
        await interaction.response.send_message(embed=discord.Embed(
            title="🔨 Đã Ban!",
            description=f"**{member.display_name}** đã bị ban vĩnh viễn.\n**Lý do:** {reason}",
            color=COLOR_MOD,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        ))

    @mod_group.command(name="unban", description="Gỡ ban một thành viên")
    @app_commands.describe(user_id="ID người dùng bị ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def mod_unban(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
            ban_entry = await interaction.guild.fetch_ban(discord.Object(id=uid))
            await interaction.guild.unban(ban_entry.user, reason=f"Unban by {interaction.user}")
            await interaction.response.send_message(embed=discord.Embed(
                description=f"✅ Đã gỡ ban **{ban_entry.user}**!",
                color=COLOR_SUCCESS
            ))
        except discord.NotFound:
            await interaction.response.send_message("❌ Không tìm thấy user bị ban với ID đó!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ ID không hợp lệ!", ephemeral=True)

    @mod_group.command(name="mute", description="Timeout một thành viên")
    @app_commands.describe(member="Thành viên", duration="Thời gian (vd: 10m, 1h, 2h30m)", reason="Lý do")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mod_mute(self, interaction: discord.Interaction, member: discord.Member,
                       duration: str, reason: str = "Không có lý do"):
        if not interaction.guild.me.guild_permissions.moderate_members:
            return await interaction.response.send_message("❌ Bot không có quyền timeout!", ephemeral=True)
        secs = parse_duration(duration)
        if not secs or secs > 2419200:
            return await interaction.response.send_message(
                "❌ Thời gian không hợp lệ! Dùng: `10m`, `1h`, `1d` (tối đa 28 ngày)", ephemeral=True)
        until = discord.utils.utcnow() + datetime.timedelta(seconds=secs)
        await member.timeout(until, reason=f"{interaction.user}: {reason}")
        duration_fmt = duration.upper()
        await interaction.response.send_message(embed=discord.Embed(
            title="🔇 Đã Timeout!",
            description=f"**{member.display_name}** đã bị timeout **{duration_fmt}**.\n**Lý do:** {reason}",
            color=COLOR_WARNING,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        ))
        try:
            await member.send(embed=discord.Embed(
                title="🔇 Bạn đã bị timeout!",
                description=f"**Server:** {interaction.guild.name}\n**Thời gian:** {duration_fmt}\n**Lý do:** {reason}",
                color=COLOR_WARNING
            ))
        except Exception:
            pass

    @mod_group.command(name="unmute", description="Gỡ timeout một thành viên")
    @app_commands.describe(member="Thành viên", reason="Lý do")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mod_unmute(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "Gỡ timeout bởi mod"):
        await member.timeout(None, reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ Đã gỡ timeout cho **{member.display_name}**!",
            color=COLOR_SUCCESS
        ))

    @mod_group.command(name="purge", description="Xóa hàng loạt tin nhắn trong kênh")
    @app_commands.describe(amount="Số tin nhắn muốn xóa (1–100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def mod_purge(self, interaction: discord.Interaction, amount: int):
        if not 1 <= amount <= 100:
            return await interaction.response.send_message("❌ Số lượng từ **1** đến **100**!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=discord.Embed(
            description=f"🗑️ Đã xóa **{len(deleted)}** tin nhắn!",
            color=COLOR_SUCCESS
        ), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
