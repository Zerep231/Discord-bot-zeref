import datetime
import platform
import discord
from discord import app_commands
from discord.ext import commands

from utils import COLOR_INFO, COLOR_SUCCESS, COLOR_ERROR, COIN, ENCHANT_DATA, EnchantPageView


HELP_PAGES = [
    # Page 0 — Tổng quan
    {
        "title": "📖 Zerbot2 — Hướng Dẫn Sử Dụng",
        "color": 0x5865F2,
        "description": (
            "Chào mừng đến với **Zerbot2** — Bot đa năng cho server Minecraft Việt!\n\n"
            "Dùng các nút ◀️ ▶️ để chuyển trang.\n\n"
            "**📚 Danh mục:**\n"
            "> `1` 🔮 Phù phép (AE)\n"
            "> `2` 💰 Kinh tế & Coin\n"
            "> `3` 🛒 Cửa hàng & Đổi đồ\n"
            "> `4` 🧧 Lì xì & Chuyển khoản\n"
            "> `5` 🎮 Mini games\n"
            "> `6` 🎉 Giveaway\n"
            "> `7` 🔨 Kiểm duyệt\n"
            "> `8` ⚙️ Cài đặt server\n"
            "> `9` 🔧 Tiện ích"
        ),
    },
    # Page 1 — Phù phép
    {
        "title": "🔮 Hệ Thống Phù Phép (AE)",
        "color": 0x9B59B6,
        "fields": [
            ("/ec info <tên>",    "Xem thông tin tóm tắt một phù phép"),
            ("/ec detail <tên>",  "Xem chi tiết từng cấp độ phù phép"),
            ("/ec list <loại>",   "Liệt kê phù phép theo loại trang bị (Swords, Bows, ...)"),
            ("/ec search <từ>",   "Tìm kiếm phù phép theo tên/mô tả"),
            ("/ec all",           "Xem toàn bộ phù phép phân theo nhóm"),
            ("/ec add",           "[Admin] Thêm phù phép mới (modal form)"),
            ("/ec remove <tên>",  "[Admin] Xóa phù phép khỏi danh sách"),
        ],
    },
    # Page 2 — Kinh tế
    {
        "title": "💰 Hệ Thống Coin & Kinh Tế",
        "color": 0xFFD700,
        "fields": [
            ("/coin",            "Xem số dư coin của bạn (hoặc người khác)"),
            ("/daily",           f"Điểm danh nhận **{100:,}** coin mỗi ngày"),
            ("/top",             "Bảng xếp hạng đại gia coin toàn server"),
            ("/lichsu",          "Xem lịch sử giao dịch coin của bạn"),
        ],
    },
    # Page 3 — Cửa hàng
    {
        "title": "🛒 Cửa Hàng & Đổi Đồ Minecraft",
        "color": 0x5865F2,
        "fields": [
            ("/shop",              "Xem cửa hàng vật phẩm của server và mua"),
            ("/shop_add",          "[Admin] Thêm vật phẩm vào shop (tên, giá, emoji...)"),
            ("/shop_remove",       "[Admin] Xóa vật phẩm khỏi shop"),
            ("/shop_list",         "[Admin] Xem danh sách vật phẩm trong shop"),
            ("/exchange",          "Đổi coin lấy vật phẩm Minecraft có sẵn"),
            ("/enchant_shop",      "Mua sách phù phép AE bằng coin\n*Lv1=100, Lv2=200, Lv3=400, Lv4=600...*"),
            ("/admin pending",     "[Admin] Xem tất cả đơn hàng đang chờ"),
            ("/admin fulfill #ID", "[Admin] Đánh dấu hoàn thành đơn"),
            ("/admin cancel #ID",  "[Admin] Hủy đơn & hoàn coin"),
        ],
    },
    # Page 4 — Lì xì & Chuyển khoản
    {
        "title": "🧧 Lì Xì & Chuyển Khoản",
        "color": 0xFF0000,
        "fields": [
            ("/lixi <người> <coin>",     "🧧 Gửi lì xì coin với embed đỏ đặc biệt"),
            ("/transfer <người> <coin>", "💸 Chuyển coin cho thành viên khác"),
            ("/admin give <người> <n>",  "[Admin] Cộng coin cho thành viên"),
            ("/admin take <người> <n>",  "[Admin] Trừ coin của thành viên"),
            ("/admin set <người> <n>",   "[Admin] Đặt số coin chính xác"),
            ("/admin coins <người>",     "[Admin] Xem coin của thành viên bất kỳ"),
        ],
    },
    # Page 5 — Games
    {
        "title": "🎮 Mini Games Cá Cược",
        "color": 0xFFD700,
        "fields": [
            ("/tuxi <coin>",  "✂️🔨📄 Mở bàn Tủ Xì (Kéo Búa Bao) — nhiều người tham gia, 60 giây"),
            ("/baucua",       "🦀 Mở ván Bầu Cua Tôm Cá — cược lên 6 con vật, 30 giây"),
        ],
        "note": "💡 Tất cả cược dùng coin trong ví của bạn.",
    },
    # Page 6 — Giveaway
    {
        "title": "🎉 Giveaway",
        "color": 0xFF73FA,
        "fields": [
            ("/giveaway start <tg> <phần thưởng>", "Tạo giveaway (vd: `1h Rank VIP`)"),
            ("/giveaway end <msg_id>",             "[Admin] Kết thúc giveaway sớm"),
            ("/giveaway reroll <msg_id>",          "[Admin] Quay lại để chọn người thắng mới"),
            ("/giveaway list",                     "[Admin] Xem tất cả giveaway đang chạy"),
        ],
        "note": "🧧 Tham gia bằng cách bấm nút 🎉 trên tin nhắn giveaway.",
    },
    # Page 7 — Mod
    {
        "title": "🔨 Kiểm Duyệt (Moderator)",
        "color": 0xEB459E,
        "fields": [
            ("/mod warn <người> <lý do>",     "Cảnh báo thành viên"),
            ("/mod warns <người>",            "Xem danh sách cảnh báo"),
            ("/mod clearwarns <người>",       "[Admin] Xóa toàn bộ cảnh báo"),
            ("/mod kick <người> [lý do]",     "Kick thành viên ra khỏi server"),
            ("/mod ban <người> [lý do]",      "Ban vĩnh viễn thành viên"),
            ("/mod unban <user_id>",          "Gỡ ban thành viên"),
            ("/mod mute <người> <tg> [lý do]","Timeout thành viên (vd: 10m, 1h)"),
            ("/mod unmute <người>",           "Gỡ timeout thành viên"),
            ("/mod purge <số>",               "Xóa hàng loạt tin nhắn (tối đa 100)"),
        ],
    },
    # Page 8 — Setup
    {
        "title": "⚙️ Cài Đặt Server",
        "color": 0x57F287,
        "fields": [
            ("/setup welcome <kênh>",    "Cài kênh chào mừng thành viên mới"),
            ("/setup goodbye <kênh>",   "Cài kênh thông báo thành viên rời"),
            ("/setup autorole <role>",  "Role tự động gán khi thành viên join"),
            ("/setup view",             "Xem cấu hình hiện tại"),
            ("/keyword add <kw> <rep>", "Thêm từ khóa tự động reply"),
            ("/keyword remove <kw>",    "Xóa từ khóa"),
            ("/keyword list",           "Xem tất cả từ khóa"),
            ("/mcstatus add",           "Thêm server Minecraft theo dõi (hỗ trợ nhiều server)"),
            ("/mcstatus remove <tên>",  "Xóa server Minecraft khỏi danh sách"),
            ("/mcstatus list",          "Xem danh sách server đang theo dõi"),
        ],
    },
    # Page 9 — Utilities
    {
        "title": "🔧 Tiện Ích",
        "color": 0x99AAB5,
        "fields": [
            ("/ping",       "Xem độ trễ của bot"),
            ("/serverinfo", "Thông tin chi tiết về server"),
            ("/userinfo [thành viên]", "Thông tin thành viên"),
            ("/avatar [thành viên]",   "Xem avatar kích thước đầy đủ"),
            ("/help",       "Hiển thị menu trợ giúp này"),
        ],
    },
]


def build_help_embed(page: dict, page_num: int, total: int) -> discord.Embed:
    embed = discord.Embed(
        title=page["title"],
        description=page.get("description", ""),
        color=page.get("color", 0x5865F2),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    for field in page.get("fields", []):
        if isinstance(field, tuple):
            embed.add_field(name=f"• `{field[0]}`", value=field[1], inline=False)
        else:
            embed.add_field(name=field, value="\u200b", inline=False)
    note = page.get("note")
    if note:
        embed.add_field(name="\u200b", value=note, inline=False)
    embed.set_footer(text=f"Zerbot2  ·  Trang {page_num+1}/{total}  ·  ◀️ ▶️ để chuyển trang")
    return embed


class UtilitiesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="📖 Xem hướng dẫn sử dụng bot đầy đủ")
    async def cmd_help(self, interaction: discord.Interaction):
        total  = len(HELP_PAGES)
        pages  = [build_help_embed(pg, i, total) for i, pg in enumerate(HELP_PAGES)]
        await interaction.response.send_message(embed=pages[0], view=EnchantPageView(pages, interaction.user.id))

    @app_commands.command(name="ping", description="🏓 Xem độ trễ của bot")
    async def cmd_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color   = 0x57F287 if latency < 100 else (0xFEE75C if latency < 200 else 0xED4245)
        embed   = discord.Embed(
            title="🏓 Pong!",
            description=f"Độ trễ: **{latency}ms**",
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="🏰 Xem thông tin server")
    async def cmd_serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"🏰 {guild.name}",
            color=COLOR_INFO,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.with_format("png").url)
        total_members = guild.member_count
        bots    = sum(1 for m in guild.members if m.bot)
        humans  = total_members - bots
        online  = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
        embed.add_field(name="👑 Chủ server",  value=guild.owner.mention if guild.owner else "?", inline=True)
        embed.add_field(name="🆔 ID",          value=str(guild.id), inline=True)
        embed.add_field(name="🌐 Region",      value=str(guild.preferred_locale), inline=True)
        embed.add_field(name="👥 Thành viên",  value=f"**{humans}** người  +  **{bots}** bot", inline=True)
        embed.add_field(name="🟢 Online",      value=f"**{online}** người", inline=True)
        embed.add_field(name="📅 Ngày tạo",   value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="💬 Kênh",        value=(
            f"📝 {len([c for c in guild.channels if isinstance(c, discord.TextChannel)])} text  "
            f"🔊 {len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])} voice"
        ), inline=True)
        embed.add_field(name="🎭 Roles",  value=f"**{len(guild.roles)-1}** role", inline=True)
        embed.add_field(name="😄 Emojis", value=f"**{len(guild.emojis)}** emoji", inline=True)
        boost_bar = "⭐" * guild.premium_subscription_count + " " + f"Level {guild.premium_tier}"
        embed.add_field(name="✨ Boost", value=boost_bar or "Chưa boost", inline=False)
        embed.set_footer(text="Zerbot2 | Server Info")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="👤 Xem thông tin thành viên")
    @app_commands.describe(member="Thành viên muốn xem (để trống = bản thân)")
    async def cmd_userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        roles  = [r.mention for r in reversed(target.roles) if r.name != "@everyone"][:10]
        now    = datetime.datetime.now(datetime.timezone.utc)
        join_rank = sorted(interaction.guild.members, key=lambda m: m.joined_at or now).index(target) + 1
        account_age = (now - target.created_at.replace(tzinfo=datetime.timezone.utc)).days

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=target.color if target.color.value else COLOR_INFO,
            timestamp=now
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        if hasattr(target, "banner") and target.banner:
            embed.set_image(url=target.banner.url)

        embed.add_field(name="🏷️ Tag",        value=str(target),         inline=True)
        embed.add_field(name="🆔 ID",          value=str(target.id),     inline=True)
        embed.add_field(name="🤖 Bot",         value="✅" if target.bot else "❌", inline=True)
        embed.add_field(name="📅 Tạo tài khoản",
                        value=f"<t:{int(target.created_at.timestamp())}:D>\n*{account_age} ngày trước*", inline=True)
        embed.add_field(name="📥 Tham gia server",
                        value=f"<t:{int(target.joined_at.timestamp())}:D>\n*Thành viên thứ #{join_rank}*", inline=True)
        if target.premium_since:
            embed.add_field(name="✨ Booster",
                            value=f"<t:{int(target.premium_since.timestamp())}:D>", inline=True)
        if target.activity:
            embed.add_field(name="🎮 Hoạt động", value=str(target.activity.name)[:64], inline=True)
        status_map = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Rảnh rỗi",
            discord.Status.dnd: "🔴 Bận",
            discord.Status.offline: "⚫ Offline",
        }
        embed.add_field(name="💫 Trạng thái", value=status_map.get(target.status, "?"), inline=True)
        if roles:
            embed.add_field(name=f"🎭 Roles ({len(target.roles)-1})",
                            value=" ".join(roles[:8]) + ("..." if len(roles) > 8 else ""),
                            inline=False)
        embed.set_footer(text=f"Zerbot2 | User Info  ·  {interaction.guild.name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="🖼️ Xem avatar của thành viên")
    @app_commands.describe(member="Thành viên (để trống = bản thân)")
    async def cmd_avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        embed  = discord.Embed(
            title=f"🖼️ Avatar — {target.display_name}",
            color=COLOR_INFO,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_image(url=target.display_avatar.with_size(4096).url)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Tải xuống (PNG)", url=target.display_avatar.replace(format="png", size=4096).url))
        if target.display_avatar.is_animated():
            view.add_item(discord.ui.Button(label="Tải xuống (GIF)", url=target.display_avatar.replace(format="gif", size=4096).url))
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilitiesCog(bot))
