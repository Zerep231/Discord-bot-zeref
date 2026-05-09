import asyncio
import random
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_GIVEAWAY, COIN,
    parse_duration, load_giveaways, save_giveaways,
)


def _ga_embed(host: discord.Member, prize: str, end_dt: datetime.datetime, winners: int,
              coin_prize: int, entries: list, ended: bool = False) -> discord.Embed:
    color = 0x808080 if ended else COLOR_GIVEAWAY
    title = "🎉 KẾT QUẢ GIVEAWAY" if ended else "🎉 GIVEAWAY!"
    embed = discord.Embed(title=title, description=f"**{prize}**", color=color, timestamp=end_dt)
    embed.add_field(name="🏆 Số người thắng",  value=f"**{winners}** người", inline=True)
    embed.add_field(name="⏰ Kết thúc",        value=f"<t:{int(end_dt.timestamp())}:R>", inline=True)
    embed.add_field(name="👥 Đang tham gia",   value=f"**{len(entries)}** người", inline=True)
    if coin_prize > 0:
        embed.add_field(name=f"{COIN} Thưởng thêm", value=f"**{coin_prize:,} coin** mỗi người thắng", inline=True)
    if not ended:
        embed.set_footer(text=f"Bấm 🎉 để tham gia!  ·  Host: {host.display_name}")
    else:
        embed.set_footer(text=f"Kết thúc  ·  Host: {host.display_name}")
    return embed


class JoinGiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="🎉 Tham gia", style=discord.ButtonStyle.primary, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaways = load_giveaways()
        ga = giveaways.get(self.giveaway_id)
        if not ga:
            return await interaction.response.send_message("❌ Giveaway không còn tồn tại!", ephemeral=True)
        if ga.get("ended"):
            return await interaction.response.send_message("❌ Giveaway đã kết thúc!", ephemeral=True)
        uid = str(interaction.user.id)
        if uid in ga["entries"]:
            ga["entries"].remove(uid)
            save_giveaways(giveaways)
            await interaction.response.send_message("↩️ Bạn đã rút khỏi giveaway!", ephemeral=True)
        else:
            ga["entries"].append(uid)
            save_giveaways(giveaways)
            await interaction.response.send_message(
                f"✅ Đã tham gia giveaway! Hiện có **{len(ga['entries'])}** người.", ephemeral=True)


class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending_tasks: dict[str, asyncio.Task] = {}

    @property
    def db(self):
        return self.bot.db

    async def cog_load(self):
        giveaways = load_giveaways()
        for gid, ga in giveaways.items():
            if ga.get("ended"):
                continue
            end_dt = datetime.datetime.fromisoformat(ga["end_time"])
            remaining = (end_dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
            if remaining > 0:
                task = asyncio.create_task(self._giveaway_timer(gid, remaining))
                self._pending_tasks[gid] = task

    async def _giveaway_timer(self, giveaway_id: str, delay: float):
        await asyncio.sleep(max(delay, 1))
        await self._end_giveaway(giveaway_id)

    async def _end_giveaway(self, giveaway_id: str):
        giveaways = load_giveaways()
        ga = giveaways.get(giveaway_id)
        if not ga or ga.get("ended"):
            return
        ga["ended"] = True
        save_giveaways(giveaways)

        channel = self.bot.get_channel(int(ga["channel_id"]))
        if not channel:
            return
        guild = self.bot.get_guild(int(ga["guild_id"]))
        if not guild:
            return

        entries = ga.get("entries", [])
        num_winners = int(ga.get("winners", 1))
        coin_prize  = int(ga.get("coin_prize", 0))
        prize       = ga.get("prize", "??")
        host_id     = int(ga.get("host_id", 0))
        host_member = guild.get_member(host_id)
        host_name   = host_member.display_name if host_member else "Ẩn danh"
        end_dt      = datetime.datetime.fromisoformat(ga["end_time"])

        valid_members = []
        for uid in entries:
            m = guild.get_member(int(uid))
            if m and not m.bot:
                valid_members.append(m)

        if not valid_members:
            try:
                msg = await channel.fetch_message(int(ga["message_id"]))
                await msg.edit(embed=discord.Embed(
                    title="🎉 GIVEAWAY KẾT THÚC",
                    description=f"**{prize}**\n\n😴 Không có ai tham gia!",
                    color=0x808080, timestamp=end_dt
                ), view=None)
            except Exception:
                pass
            return

        winners = random.sample(valid_members, min(num_winners, len(valid_members)))
        mentions = " ".join(w.mention for w in winners)
        names    = ", ".join(w.display_name for w in winners)

        if coin_prize > 0:
            for w in winners:
                await self.db.ensure_user(w.id, str(w))
                await self.db.add_coins(w.id, coin_prize, f"giveaway:{prize}")

        result_embed = discord.Embed(
            title="🎉 KẾT QUẢ GIVEAWAY!",
            description=f"**{prize}**\n\n🏆 Người thắng: {mentions}",
            color=COLOR_GIVEAWAY, timestamp=end_dt
        )
        if coin_prize > 0:
            result_embed.add_field(name=f"{COIN} Coin thưởng", value=f"**{coin_prize:,} coin** × {len(winners)} người", inline=False)
        result_embed.set_footer(text=f"Host: {host_name}  ·  {len(valid_members)} người tham gia")

        try:
            msg = await channel.fetch_message(int(ga["message_id"]))
            await msg.edit(embed=result_embed, view=None)
        except Exception:
            pass
        await channel.send(f"🎊 Chúc mừng **{names}**! Đã thắng **{prize}**! {mentions}")

    ga_group = app_commands.Group(name="giveaway", description="🎉 Quản lý giveaway")

    @ga_group.command(name="start", description="Tạo giveaway mới")
    @app_commands.describe(
        duration="Thời gian (vd: 1h, 30m, 1d)", prize="Phần thưởng",
        winners="Số người thắng", coin_prize="Coin thưởng thêm (0 = không có)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ga_start(self, interaction: discord.Interaction, duration: str, prize: str,
                       winners: int = 1, coin_prize: int = 0):
        secs = parse_duration(duration)
        if not secs or secs < 10:
            return await interaction.response.send_message(
                "❌ Thời gian không hợp lệ! Ví dụ: `30m`, `1h`, `1d`", ephemeral=True)
        if winners < 1:
            return await interaction.response.send_message("❌ Số người thắng phải ≥ 1!", ephemeral=True)
        if coin_prize < 0:
            return await interaction.response.send_message("❌ Coin thưởng không thể âm!", ephemeral=True)

        end_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=secs)
        ga_id  = f"{interaction.guild_id}_{int(end_dt.timestamp())}"

        embed = _ga_embed(interaction.user, prize, end_dt, winners, coin_prize, [])
        view  = JoinGiveawayView(ga_id)
        await interaction.response.send_message("🎉 Giveaway đã bắt đầu!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        giveaways = load_giveaways()
        giveaways[ga_id] = {
            "guild_id":   str(interaction.guild_id),
            "channel_id": str(interaction.channel_id),
            "message_id": str(msg.id),
            "host_id":    str(interaction.user.id),
            "prize":      prize,
            "winners":    winners,
            "coin_prize": coin_prize,
            "end_time":   end_dt.isoformat(),
            "entries":    [],
            "ended":      False,
        }
        save_giveaways(giveaways)
        task = asyncio.create_task(self._giveaway_timer(ga_id, secs))
        self._pending_tasks[ga_id] = task

    @ga_group.command(name="end", description="Kết thúc sớm một giveaway")
    @app_commands.describe(message_id="ID tin nhắn giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ga_end(self, interaction: discord.Interaction, message_id: str):
        giveaways = load_giveaways()
        found_id  = None
        for gid, ga in giveaways.items():
            if ga.get("message_id") == message_id and not ga.get("ended"):
                found_id = gid; break
        if not found_id:
            return await interaction.response.send_message("❌ Không tìm thấy giveaway đang chạy!", ephemeral=True)
        task = self._pending_tasks.pop(found_id, None)
        if task: task.cancel()
        await interaction.response.send_message("✅ Đang kết thúc giveaway...", ephemeral=True)
        await self._end_giveaway(found_id)

    @ga_group.command(name="reroll", description="Quay lại để chọn người thắng mới")
    @app_commands.describe(message_id="ID tin nhắn giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ga_reroll(self, interaction: discord.Interaction, message_id: str):
        giveaways = load_giveaways()
        ga = None
        for g in giveaways.values():
            if g.get("message_id") == message_id and g.get("ended"):
                ga = g; break
        if not ga:
            return await interaction.response.send_message(
                "❌ Không tìm thấy giveaway đã kết thúc với ID đó!", ephemeral=True)
        entries = ga.get("entries", [])
        guild   = interaction.guild
        valid   = [guild.get_member(int(u)) for u in entries if guild.get_member(int(u)) and not guild.get_member(int(u)).bot]
        if not valid:
            return await interaction.response.send_message("❌ Không có ai tham gia!", ephemeral=True)
        num_winners = int(ga.get("winners", 1))
        winners = random.sample(valid, min(num_winners, len(valid)))
        mentions = " ".join(w.mention for w in winners)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔄 Reroll Giveaway!",
                description=f"Người thắng mới: {mentions}\n🏆 **{ga.get('prize', '??')}**",
                color=COLOR_GIVEAWAY
            )
        )

    @ga_group.command(name="list", description="Xem danh sách giveaway đang chạy")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ga_list(self, interaction: discord.Interaction):
        giveaways = load_giveaways()
        active = [ga for ga in giveaways.values()
                  if ga.get("guild_id") == str(interaction.guild_id) and not ga.get("ended")]
        if not active:
            return await interaction.response.send_message(
                embed=discord.Embed(description="Không có giveaway nào đang chạy.", color=COLOR_WARNING),
                ephemeral=True)
        embed = discord.Embed(title="🎉 Giveaway đang chạy", color=COLOR_GIVEAWAY,
                              timestamp=datetime.datetime.now(datetime.timezone.utc))
        for ga in active[:10]:
            end_dt = datetime.datetime.fromisoformat(ga["end_time"])
            embed.add_field(
                name=f"🎁 {ga['prize']}",
                value=(f"🏆 {ga['winners']} người thắng\n"
                       f"👥 {len(ga['entries'])} tham gia\n"
                       f"⏰ <t:{int(end_dt.timestamp())}:R>"),
                inline=True
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))
