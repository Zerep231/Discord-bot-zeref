import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from utils import (
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_INFO,
    get_guild_settings, set_guild_setting, get_guild_keywords, save_guild_keywords,
    load_mc_config, save_mc_config,
)


def _get_mc_status(ip: str, port: int) -> dict:
    try:
        from mcstatus import JavaServer
        server = JavaServer.lookup(f"{ip}:{port}", timeout=5)
        status = server.status()
        return {
            "online": True,
            "players": f"{status.players.online}/{status.players.max}",
            "version": status.version.name,
            "online_count": status.players.online,
        }
    except Exception:
        return {"online": False, "players": "0/0", "version": "N/A", "online_count": 0}


def _build_mc_embed(guild_name: str, servers_data: list[dict]) -> discord.Embed:
    any_online = any(s.get("online") for s in servers_data)
    embed = discord.Embed(
        title=f"⛏️ Trạng Thái Server Minecraft — {guild_name}",
        color=discord.Color.green() if any_online else discord.Color.red(),
    )
    for sd in servers_data:
        status_emoji = "🟢 ONLINE" if sd["online"] else "🔴 OFFLINE"
        label = sd.get("name") or sd.get("ip", "Server")
        ip    = sd.get("ip", "?")
        port  = sd.get("port", 25565)
        info  = sd.get("info", {})
        val   = f"**{status_emoji}**\n🌐 `{ip}:{port}`"
        if info.get("online"):
            val += f"\n👥 **{info['players']}**  |  📦 `{info['version']}`"
        embed.add_field(name=f"🏠 {label}", value=val, inline=True)
    embed.set_footer(text=f"🔄 Cập nhật lúc {datetime.datetime.now().strftime('%H:%M:%S | %d/%m/%Y')}")
    return embed


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mc_status_loop.start()

    def cog_unload(self):
        self.mc_status_loop.cancel()

    # ── Setup group ───────────────────────────────────────────────────────────

    setup_group = app_commands.Group(
        name="setup",
        description="⚙️ Cài đặt bot cho server",
        default_permissions=discord.Permissions(manage_guild=True)
    )

    @setup_group.command(name="welcome", description="Cài đặt kênh chào mừng thành viên")
    @app_commands.describe(channel="Kênh gửi tin chào mừng")
    async def setup_welcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_guild_setting(interaction.guild_id, "welcome_channel", channel.id)
        embed = discord.Embed(
            title="✅ Đã cài Welcome Channel!",
            description=f"Kênh chào mừng: {channel.mention}",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @setup_group.command(name="goodbye", description="Cài đặt kênh thông báo thành viên rời")
    @app_commands.describe(channel="Kênh gửi tin tạm biệt")
    async def setup_goodbye(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_guild_setting(interaction.guild_id, "goodbye_channel", channel.id)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Đã cài Goodbye Channel!",
            description=f"Kênh tạm biệt: {channel.mention}",
            color=COLOR_SUCCESS
        ))

    @setup_group.command(name="autorole", description="Cài đặt role tự động khi thành viên mới join")
    @app_commands.describe(role="Role sẽ gán tự động")
    async def setup_autorole(self, interaction: discord.Interaction, role: discord.Role):
        set_guild_setting(interaction.guild_id, "auto_role", role.id)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ Auto-role đã đặt thành {role.mention}",
            color=COLOR_SUCCESS
        ))

    @setup_group.command(name="view", description="Xem cấu hình hiện tại của bot")
    async def setup_view(self, interaction: discord.Interaction):
        s = get_guild_settings(interaction.guild_id)
        guild = interaction.guild
        welcome_ch  = guild.get_channel(s.get("welcome_channel", 0))
        goodbye_ch  = guild.get_channel(s.get("goodbye_channel", 0))
        auto_role   = guild.get_role(s.get("auto_role", 0))
        embed = discord.Embed(
            title=f"⚙️ Cấu hình — {guild.name}",
            color=COLOR_INFO,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="👋 Welcome", value=welcome_ch.mention if welcome_ch else "Chưa cài", inline=True)
        embed.add_field(name="👋 Goodbye", value=goodbye_ch.mention if goodbye_ch else "Chưa cài", inline=True)
        embed.add_field(name="🎭 Auto Role", value=auto_role.mention if auto_role else "Chưa cài", inline=True)
        mc_conf = load_mc_config().get(str(interaction.guild_id), {})
        mc_servers = mc_conf.get("servers", [])
        if mc_servers:
            mc_lines = "\n".join(f"• **{s.get('name','?')}** `{s['ip']}:{s.get('port',25565)}`" for s in mc_servers)
            embed.add_field(name="⛏️ MC Servers", value=mc_lines, inline=False)
        else:
            embed.add_field(name="⛏️ MC Servers", value="Chưa cài", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Keywords group ────────────────────────────────────────────────────────

    kw_group = app_commands.Group(
        name="keyword",
        description="💬 Quản lý từ khóa tự động trả lời",
        default_permissions=discord.Permissions(manage_messages=True)
    )

    @kw_group.command(name="add", description="Thêm từ khóa tự động reply")
    @app_commands.describe(
        keyword="Từ khóa kích hoạt",
        reply="Nội dung trả lời ({name} = tên người dùng)",
        match="Kiểu khớp"
    )
    @app_commands.choices(match=[
        app_commands.Choice(name="Chứa từ khóa", value="chua"),
        app_commands.Choice(name="Chính xác",    value="chinh_xac"),
    ])
    async def kw_add(self, interaction: discord.Interaction, keyword: str, reply: str, match: str = "chua"):
        keywords = get_guild_keywords(interaction.guild_id)
        kw_lower = keyword.lower()
        if kw_lower not in keywords:
            keywords[kw_lower] = {"match": match, "replies": []}
        if reply not in keywords[kw_lower]["replies"]:
            keywords[kw_lower]["replies"].append(reply)
            keywords[kw_lower]["match"] = match
        save_guild_keywords(interaction.guild_id, keywords)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Đã thêm từ khóa!",
            description=f"**Từ khóa:** `{keyword}`\n**Reply:** {reply}\n**Kiểu:** {match}",
            color=COLOR_SUCCESS
        ), ephemeral=True)

    @kw_group.command(name="remove", description="Xóa từ khóa tự động reply")
    @app_commands.describe(keyword="Từ khóa muốn xóa")
    async def kw_remove(self, interaction: discord.Interaction, keyword: str):
        keywords = get_guild_keywords(interaction.guild_id)
        if keyword.lower() not in keywords:
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"❌ Không tìm thấy từ khóa `{keyword}`!", color=COLOR_ERROR),
                ephemeral=True)
        del keywords[keyword.lower()]
        save_guild_keywords(interaction.guild_id, keywords)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"🗑️ Đã xóa từ khóa `{keyword}`!",
            color=COLOR_SUCCESS
        ), ephemeral=True)

    @kw_group.command(name="list", description="Xem tất cả từ khóa tự động reply")
    async def kw_list(self, interaction: discord.Interaction):
        keywords = get_guild_keywords(interaction.guild_id)
        if not keywords:
            return await interaction.response.send_message(embed=discord.Embed(
                description="Chưa có từ khóa nào!",
                color=COLOR_INFO
            ), ephemeral=True)
        lines = []
        for kw, info in keywords.items():
            replies = info.get("replies", [])
            match   = info.get("match", "chua")
            lines.append(f"**`{kw}`** [{match}] — {len(replies)} reply")
        await interaction.response.send_message(embed=discord.Embed(
            title=f"💬 Từ khóa — {interaction.guild.name}",
            description="\n".join(lines[:30]),
            color=COLOR_INFO
        ), ephemeral=True)

    # ── MC Status group ───────────────────────────────────────────────────────

    mc_group = app_commands.Group(
        name="mcstatus",
        description="⛏️ Quản lý theo dõi server Minecraft",
        default_permissions=discord.Permissions(manage_guild=True)
    )

    @mc_group.command(name="add", description="Thêm server Minecraft để theo dõi")
    @app_commands.describe(name="Tên server", ip="Địa chỉ IP", port="Cổng (mặc định 25565)",
                           channel="Kênh hiển thị trạng thái")
    async def mc_add(self, interaction: discord.Interaction, name: str, ip: str,
                     channel: discord.TextChannel, port: int = 25565):
        mc_conf  = load_mc_config()
        gid      = str(interaction.guild_id)
        if gid not in mc_conf:
            mc_conf[gid] = {"channel_id": channel.id, "message_id": None, "servers": []}
        mc_conf[gid]["channel_id"] = channel.id
        mc_conf[gid]["message_id"] = None
        servers = mc_conf[gid].get("servers", [])
        for s in servers:
            if s["ip"] == ip and s["port"] == port:
                return await interaction.response.send_message(
                    f"⚠️ Server `{ip}:{port}` đã có trong danh sách!", ephemeral=True)
        servers.append({"name": name, "ip": ip, "port": port})
        mc_conf[gid]["servers"] = servers
        save_mc_config(mc_conf)
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ Đã thêm server!",
            description=f"🏠 **{name}** — `{ip}:{port}`\n📢 Kênh: {channel.mention}\nBot cập nhật mỗi 60 giây.",
            color=COLOR_SUCCESS
        ))

    @mc_group.command(name="remove", description="Xóa server Minecraft khỏi danh sách theo dõi")
    @app_commands.describe(name="Tên server muốn xóa")
    async def mc_remove(self, interaction: discord.Interaction, name: str):
        mc_conf = load_mc_config()
        gid     = str(interaction.guild_id)
        if gid not in mc_conf:
            return await interaction.response.send_message("❌ Chưa cài server nào!", ephemeral=True)
        servers = mc_conf[gid].get("servers", [])
        new_servers = [s for s in servers if s["name"].lower() != name.lower()]
        if len(new_servers) == len(servers):
            return await interaction.response.send_message(f"❌ Không tìm thấy server `{name}`!", ephemeral=True)
        mc_conf[gid]["servers"]    = new_servers
        mc_conf[gid]["message_id"] = None
        save_mc_config(mc_conf)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"🗑️ Đã xóa server **{name}** khỏi danh sách.",
            color=COLOR_WARNING
        ))

    @mc_group.command(name="list", description="Xem danh sách server đang theo dõi")
    async def mc_list(self, interaction: discord.Interaction):
        mc_conf = load_mc_config()
        gid     = str(interaction.guild_id)
        conf    = mc_conf.get(gid, {})
        servers = conf.get("servers", [])
        if not servers:
            return await interaction.response.send_message("Chưa có server nào được cấu hình.", ephemeral=True)
        channel = interaction.guild.get_channel(conf.get("channel_id", 0))
        lines   = [f"• **{s['name']}** `{s['ip']}:{s.get('port',25565)}`" for s in servers]
        embed   = discord.Embed(
            title="⛏️ Danh sách MC Server",
            description="\n".join(lines),
            color=COLOR_INFO
        )
        embed.add_field(name="📢 Kênh hiển thị", value=channel.mention if channel else "Chưa cài", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── MC Status loop ────────────────────────────────────────────────────────

    @tasks.loop(seconds=60)
    async def mc_status_loop(self):
        await self.bot.wait_until_ready()
        mc_conf = load_mc_config()
        for gid_str, conf in mc_conf.items():
            try:
                guild = self.bot.get_guild(int(gid_str))
                if not guild:
                    continue
                channel = guild.get_channel(conf.get("channel_id", 0))
                if not channel:
                    continue
                servers  = conf.get("servers", [])
                if not servers:
                    continue

                servers_data = []
                for srv in servers:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, _get_mc_status, srv["ip"], srv.get("port", 25565)
                    )
                    servers_data.append({**srv, "info": info, "online": info["online"]})

                embed = _build_mc_embed(guild.name, servers_data)
                msg_id = conf.get("message_id")
                if msg_id:
                    try:
                        msg = await channel.fetch_message(int(msg_id))
                        await msg.edit(embed=embed)
                        continue
                    except discord.NotFound:
                        pass
                msg = await channel.send(embed=embed)
                mc_conf[gid_str]["message_id"] = msg.id
                save_mc_config(mc_conf)
            except Exception as e:
                self.bot.logger.warning("mc_status_loop error guild=%s: %s", gid_str, e)

    @mc_status_loop.before_loop
    async def before_mc_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
