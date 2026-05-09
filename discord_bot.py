import os
import asyncio
import logging
import datetime
from pathlib import Path

import discord
from discord.ext import commands

from database import Database
from utils import find_reply, get_guild_settings, set_guild_setting, ENCHANT_DATA

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("zerbot2")

# ── Bot setup ────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members         = True

bot    = commands.Bot(command_prefix="--", intents=intents, help_command=None)
db     = Database()
bot.db = db
bot.logger = logger

COGS = [
    "cogs.enchants",
    "cogs.economy",
    "cogs.shop",
    "cogs.admin",
    "cogs.games",
    "cogs.moderation",
    "cogs.giveaway",
    "cogs.setup_cog",
    "cogs.utilities",
]

# ── Events ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info("✅ %s | %d server(s) | %d enchants loaded", bot.user, len(bot.guilds), len(ENCHANT_DATA))
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name=f"các thành viên 👀 | {len(ENCHANT_DATA)} enchants"
    ))


@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        await bot.tree.sync(guild=guild)
    except Exception as e:
        logger.warning("tree.sync guild=%s: %s", guild.id, e)


@bot.event
async def on_member_join(member: discord.Member):
    guild    = member.guild
    settings = get_guild_settings(guild.id)

    # Auto role
    auto_role_id = settings.get("auto_role")
    if auto_role_id:
        role = guild.get_role(auto_role_id)
        if role:
            try:
                await member.add_roles(role, reason="Auto-role on join")
            except discord.Forbidden:
                pass

    # Welcome channel
    ch_id = settings.get("welcome_channel")
    if not ch_id:
        return
    channel = guild.get_channel(ch_id)
    if not channel:
        return

    # Account age
    now         = datetime.datetime.now(datetime.timezone.utc)
    account_age = (now - member.created_at.replace(tzinfo=datetime.timezone.utc)).days
    joined_members = sorted((m for m in guild.members if m.joined_at), key=lambda m: m.joined_at)
    join_rank = next((idx for idx, m in enumerate(joined_members, 1) if m.id == member.id), guild.member_count)

    embed = discord.Embed(
        title=f"👋 Chào mừng đến với {guild.name}!",
        description=(
            f"Xin chào {member.mention}, rất vui khi bạn gia nhập!\n\n"
            f"📋 Hãy đọc nội quy và giới thiệu bản thân nhé 😊"
        ),
        color=0x57F287,
        timestamp=now,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if guild.banner:
        embed.set_image(url=guild.banner.with_format("png").url)

    embed.add_field(name="👤 Thành viên",       value=f"**{member.display_name}**", inline=True)
    embed.add_field(name="🎂 Tuổi tài khoản",  value=f"**{account_age}** ngày",   inline=True)
    embed.add_field(name="🔢 Thành viên thứ",  value=f"**#{join_rank}**",          inline=True)
    embed.add_field(name="👥 Tổng thành viên", value=f"**{guild.member_count}** người", inline=True)

    embed.set_footer(text=f"{guild.name} • Zerbot2", icon_url=guild.icon.url if guild.icon else None)
    await channel.send(embed=embed)


@bot.event
async def on_member_remove(member: discord.Member):
    guild    = member.guild
    settings = get_guild_settings(guild.id)

    ch_id = settings.get("goodbye_channel")
    if not ch_id:
        return
    channel = guild.get_channel(ch_id)
    if not channel:
        return

    now         = datetime.datetime.now(datetime.timezone.utc)
    # How long they were in the server
    if member.joined_at:
        stay_days = (now - member.joined_at.replace(tzinfo=datetime.timezone.utc)).days
        stay_text = f"**{stay_days}** ngày"
    else:
        stay_text = "Không rõ"

    embed = discord.Embed(
        title="👋 Tạm biệt!",
        description=(
            f"**{member.display_name}** đã rời khỏi server.\n"
            f"Cảm ơn vì khoảng thời gian cùng nhau 🙏"
        ),
        color=0x99AAB5,
        timestamp=now,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 Thành viên",        value=f"{member} (`{member.id}`)", inline=True)
    embed.add_field(name="⏳ Thời gian ở lại",   value=stay_text,                   inline=True)
    embed.add_field(name="👥 Còn lại",            value=f"**{guild.member_count}** thành viên", inline=True)
    embed.set_footer(text=f"{guild.name} • Zerbot2", icon_url=guild.icon.url if guild.icon else None)
    await channel.send(embed=embed)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    await db.ensure_user(message.author.id, str(message.author))
    await db.add_message_count(message.author.id)
    if not message.content.startswith("--"):
        reply = find_reply(message.guild.id, message.content, message.author.display_name)
        if reply:
            await message.channel.send(reply)
    await bot.process_commands(message)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    msg = "❌ Đã xảy ra lỗi!"
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "❌ Bạn không có quyền dùng lệnh này!"
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
        msg = "❌ Bot thiếu quyền để thực hiện hành động này!"
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        msg = f"⏳ Lệnh đang trong thời gian hồi. Thử lại sau **{error.retry_after:.1f}s**!"
    else:
        logger.error("App command error: %s", error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    base_dir = Path(__file__).resolve().parent
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        search_files = [
            base_dir / "token.txt",
            base_dir / ".token",
            base_dir / "discord_token.txt",
            base_dir.parent / "token.txt",
            base_dir.parent / ".token",
            base_dir.parent / "discord_token.txt",
        ]
        for p in search_files:
            if p.exists():
                token = p.read_text(encoding="utf-8").strip()
                if token:
                    break
    if not token:
        raise ValueError("Thiếu token! Tạo token.txt trong /home/container/Discord-bot hoặc /home/container.")

    await db.connect()
    bot.db = db

    try:
        async with bot:
            for cog in COGS:
                try:
                    await bot.load_extension(cog)
                    logger.info("Loaded cog: %s", cog)
                except Exception as e:
                    logger.error("Failed to load cog %s: %s", cog, e)
                    raise
            await bot.start(token, reconnect=True)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
