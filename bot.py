import os
import json
import random
import datetime
import discord
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="--", intents=intents, help_command=None)

KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), "keywords.json")
WELCOME_CHANNEL = "general"
FAREWELL_CHANNEL = "general"


def load_keywords() -> dict:
    if not os.path.exists(KEYWORDS_FILE):
        return {}
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_keywords(data: dict):
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_reply(content: str, name: str) -> str | None:
    keywords = load_keywords()
    content_lower = content.lower().strip()
    matched_replies = []
    for keyword, data in keywords.items():
        replies = data.get("replies", [])
        match_type = data.get("match", "chua")
        if match_type == "chinh_xac":
            if content_lower == keyword.lower():
                matched_replies.extend(replies)
        else:
            if keyword.lower() in content_lower:
                matched_replies.extend(replies)
    if matched_replies:
        reply = random.choice(matched_replies)
        return reply.replace("{name}", name)
    return None


@bot.event
async def on_ready():
    await bot.tree.sync()
    keywords = load_keywords()
    print(f"✅ Bot đã đăng nhập: {bot.user} (ID: {bot.user.id})")
    print(f"📡 Đang hoạt động trên {len(bot.guilds)} server(s)")
    print(f"🔑 Đang theo dõi {len(keywords)} từ khóa")
    print(f"⚡ Slash commands đã được sync!")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="các thành viên 👀"
        )
    )


@bot.event
async def on_member_join(member: discord.Member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL)
    if not channel:
        channel = member.guild.system_channel
    if not channel:
        return
    account_age = (datetime.datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
    embed = discord.Embed(
        title="🎉 Chào mừng thành viên mới!",
        description=(
            f"Hey {member.mention}, chào mừng bạn đến với **{member.guild.name}**! 🥳\n\n"
            f"Chúng ta đã có **{member.guild.member_count}** thành viên! Hãy giới thiệu bản thân nhé!"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 Thành viên", value=str(member), inline=True)
    embed.add_field(name="📅 Tuổi tài khoản", value=f"{account_age} ngày", inline=True)
    embed.set_footer(text=f"ID: {member.id}")
    await channel.send(embed=embed)


@bot.event
async def on_member_remove(member: discord.Member):
    channel = discord.utils.get(member.guild.text_channels, name=FAREWELL_CHANNEL)
    if not channel:
        channel = member.guild.system_channel
    if not channel:
        return
    embed = discord.Embed(
        title="👋 Tạm biệt thành viên!",
        description=(
            f"**{member.display_name}** đã rời server 😢\n"
            f"Cảm ơn vì những kỷ niệm đẹp! Hẹn gặp lại nhé 💙"
        ),
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Server còn lại {member.guild.member_count} thành viên")
    await channel.send(embed=embed)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)
    if message.content.startswith("--"):
        return
    reply = find_reply(message.content, message.author.display_name)
    if reply:
        await message.channel.send(reply)


@bot.event
async def on_error(event, *args, **kwargs):
    print(f"⚠️ Lỗi tại event '{event}'")


# ─── SLASH COMMANDS ────────────────────────────────────────────────────────────

@bot.tree.command(name="them_phan_hoi", description="Thêm từ khóa và phản hồi cho bot")
@app_commands.describe(
    tu_khoa="Từ khóa kích hoạt (phân cách bằng dấu phẩy nếu nhiều từ khóa)",
    phan_hoi="Nội dung bot sẽ phản hồi. Dùng {name} để điền tên người nhắn",
    kieu_kiem_tra="Kiểu kiểm tra từ khóa (mặc định: chứa)",
)
@app_commands.choices(kieu_kiem_tra=[
    app_commands.Choice(name="Chứa (tin nhắn có chứa từ khóa)", value="chua"),
    app_commands.Choice(name="Chính xác (tin nhắn phải khớp hoàn toàn)", value="chinh_xac"),
])
@app_commands.checks.has_permissions(manage_messages=True)
async def them_phan_hoi(
    interaction: discord.Interaction,
    tu_khoa: str,
    phan_hoi: str,
    kieu_kiem_tra: str = "chua",
):
    keywords = load_keywords()
    ds_tu_khoa = [k.strip().lower() for k in tu_khoa.split(",") if k.strip()]
    if not ds_tu_khoa:
        await interaction.response.send_message("❌ Từ khóa không được để trống!", ephemeral=True)
        return
    added = []
    for kw in ds_tu_khoa:
        if kw not in keywords:
            keywords[kw] = {"replies": [], "match": kieu_kiem_tra}
        keywords[kw]["replies"].append(phan_hoi)
        keywords[kw]["match"] = kieu_kiem_tra
        added.append(kw)
    save_keywords(keywords)
    kieu_label = "Chính xác" if kieu_kiem_tra == "chinh_xac" else "Chứa"
    embed = discord.Embed(title="✅ Đã thêm phản hồi!", color=discord.Color.green())
    embed.add_field(name="🔑 Từ khóa", value="\n".join(f"`{k}`" for k in added), inline=True)
    embed.add_field(name="💬 Phản hồi", value=phan_hoi, inline=True)
    embed.add_field(name="🔍 Kiểu kiểm tra", value=kieu_label, inline=True)
    embed.set_footer(text=f"Thêm bởi {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="xoa_tu_khoa", description="Xóa một từ khóa khỏi danh sách")
@app_commands.describe(tu_khoa="Từ khóa muốn xóa")
@app_commands.checks.has_permissions(manage_messages=True)
async def xoa_tu_khoa(interaction: discord.Interaction, tu_khoa: str):
    keyword = tu_khoa.strip().lower()
    keywords = load_keywords()
    if keyword not in keywords:
        await interaction.response.send_message(f"❌ Không tìm thấy từ khóa `{keyword}`!", ephemeral=True)
        return
    del keywords[keyword]
    save_keywords(keywords)
    embed = discord.Embed(
        title="🗑️ Đã xóa từ khóa!",
        description=f"Từ khóa `{keyword}` đã được xóa.",
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"Xóa bởi {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ds_tu_khoa", description="Xem danh sách tất cả từ khóa đang hoạt động")
async def ds_tu_khoa(interaction: discord.Interaction):
    keywords = load_keywords()
    if not keywords:
        await interaction.response.send_message("📭 Chưa có từ khóa nào!", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"🔑 Danh sách từ khóa ({len(keywords)})",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow(),
    )
    items = list(keywords.items())
    for i in range(0, len(items), 20):
        chunk = items[i:i + 20]
        value = "\n".join(
            f"`{kw}` — {len(data['replies'])} phản hồi · {'Chính xác' if data.get('match') == 'chinh_xac' else 'Chứa'}"
            for kw, data in chunk
        )
        embed.add_field(name="\u200b" if i > 0 else "Từ khóa", value=value, inline=False)
    embed.set_footer(text="Dùng /them_phan_hoi để thêm | /xoa_tu_khoa để xóa")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="xem_tu_khoa", description="Xem tất cả phản hồi của một từ khóa")
@app_commands.describe(tu_khoa="Từ khóa muốn xem chi tiết")
async def xem_tu_khoa(interaction: discord.Interaction, tu_khoa: str):
    keyword = tu_khoa.strip().lower()
    keywords = load_keywords()
    if keyword not in keywords:
        await interaction.response.send_message(f"❌ Không tìm thấy từ khóa `{keyword}`!", ephemeral=True)
        return
    data = keywords[keyword]
    replies = data.get("replies", [])
    match_type = "Chính xác" if data.get("match") == "chinh_xac" else "Chứa"
    embed = discord.Embed(
        title=f"🔍 Từ khóa: `{keyword}`",
        description=f"Kiểu kiểm tra: **{match_type}** · Có **{len(replies)}** phản hồi",
        color=discord.Color.blue(),
    )
    for i, reply in enumerate(replies, 1):
        embed.add_field(name=f"Phản hồi #{i}", value=reply, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ping", description="Kiểm tra độ trễ của bot")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Độ trễ: **{latency}ms**",
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Bạn cần quyền **Manage Messages** để dùng lệnh này!", ephemeral=True
        )
    else:
        print(f"⚠️ Lỗi slash command: {error}")
        try:
            await interaction.response.send_message("❌ Đã xảy ra lỗi!", ephemeral=True)
        except Exception:
            pass


TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("Thiếu DISCORD_TOKEN trong biến môi trường!")

bot.run(TOKEN, reconnect=True)
