import asyncio
import random
import datetime
from collections import Counter
import discord
from discord import app_commands
from discord.ext import commands

from utils import COLOR_ERROR, COLOR_SUCCESS, COIN

TUXI_MOVES = {"keo": ("✂️", "Kéo"), "bua": ("🔨", "Búa"), "bao": ("📄", "Bao")}
TUXI_BEATS = {"bua": "keo", "bao": "bua", "keo": "bao"}

BC_SYMBOLS = {
    "nai": ("🦌", "Nai", 0), "bau": ("🎃", "Bầu", 0), "ga": ("🐔", "Gà", 0),
    "ca":  ("🐟", "Cá",  1), "cua": ("🦀", "Cua", 1), "tom": ("🦐", "Tôm", 1),
}
BC_MIN, BC_MAX = 10, 250_000
GAME_WAIT_SECONDS = 60
TAIXIU_WAIT_SECONDS = 80


def tuxi_results(choices: dict[int, str], bet: int) -> dict[int, dict]:
    if not choices:
        return {}
    unique = set(choices.values())
    is_draw = (len(unique) == 1) or (len(unique) == 3)
    pot = bet * len(choices)
    results = {}
    if is_draw:
        for uid, mv in choices.items():
            results[uid] = {"move": mv, "result": "draw", "payout": bet}
        return results
    winning_move = next(
        (m for m in unique if not {k for k, v in TUXI_BEATS.items() if v == m}.intersection(unique)), None)
    winners = [uid for uid, mv in choices.items() if mv == winning_move]
    per_win = pot // len(winners) if winners else 0
    rem = pot - per_win * len(winners)
    for i, (uid, mv) in enumerate(choices.items()):
        if mv == winning_move:
            results[uid] = {"move": mv, "result": "win", "payout": per_win + (rem if i == 0 else 0)}
        else:
            results[uid] = {"move": mv, "result": "lose", "payout": 0}
    return results


class TuxiPickView(discord.ui.View):
    def __init__(self, session: dict, db):
        super().__init__(timeout=None)
        self.db = db
        for key, (emoji, name) in TUXI_MOVES.items():
            btn = discord.ui.Button(label=name, emoji=emoji, style=discord.ButtonStyle.primary, custom_id=f"tx_{key}")
            btn.callback = self._make_cb(key)
            self.add_item(btn)

    def _make_cb(self, key: str):
        async def cb(interaction: discord.Interaction):
            session = interaction.client.active_tuxi.get(interaction.channel_id)
            if not session or session["phase"] != "picking":
                return await interaction.response.send_message("❌ Bàn đã kết thúc!", ephemeral=True)
            uid = interaction.user.id
            if uid in session["choices"]:
                return await interaction.response.send_message("⚠️ Bạn đã chọn rồi!", ephemeral=True)
            await self.db.ensure_user(uid, str(interaction.user))
            if not await self.db.deduct_coins(uid, session["bet"], "tuxi_bet"):
                return await interaction.response.send_message(
                    f"❌ Không đủ **{session['bet']:,}{COIN}** để cược!", ephemeral=True)
            session["choices"][uid] = key
            emoji, name = TUXI_MOVES[key]
            await interaction.response.send_message(f"✅ Đã chọn **{emoji} {name}**!", ephemeral=True)
        return cb


class BetAmountModal(discord.ui.Modal, title="Nhập số Coin để cược"):
    bet_input = discord.ui.TextInput(label="Số coin", placeholder="VD: 100", min_length=1, max_length=10)

    def __init__(self, symbol: str, game: dict, db):
        super().__init__()
        self.symbol = symbol
        self.game   = game
        self.db     = db

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.bet_input.value)
            if not (BC_MIN <= amount <= BC_MAX):
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                f"❌ Nhập số hợp lệ từ {BC_MIN:,} đến {BC_MAX:,}!", ephemeral=True)
        uid = interaction.user.id
        await self.db.ensure_user(uid, str(interaction.user))
        if not await self.db.deduct_coins(uid, amount, f"bet_baucua_{self.symbol}"):
            coins = await self.db.get_coins(uid)
            return await interaction.response.send_message(
                f"❌ Không đủ coin! Bạn chỉ có **{coins:,}{COIN}**", ephemeral=True)
        bets = self.game["bets"]
        bets.setdefault(uid, {})[self.symbol] = bets.get(uid, {}).get(self.symbol, 0) + amount
        emoji, name, _ = BC_SYMBOLS[self.symbol]
        await interaction.response.send_message(f"✅ Cược **{amount:,}{COIN}** vào {emoji} **{name}**!", ephemeral=True)


class BauCuaView(discord.ui.View):
    def __init__(self, game: dict, db):
        super().__init__(timeout=None)
        self.game = game
        self.db   = db
        for key, (emoji, name, row) in BC_SYMBOLS.items():
            btn = discord.ui.Button(label=name, emoji=emoji, style=discord.ButtonStyle.primary,
                                    custom_id=f"bc_{key}", row=row)
            btn.callback = self._make_cb(key)
            self.add_item(btn)

    def _make_cb(self, key: str):
        async def cb(interaction: discord.Interaction):
            if self.game.get("phase") != "betting":
                return await interaction.response.send_message("❌ Đã hết thời gian cược!", ephemeral=True)
            await self.db.ensure_user(interaction.user.id, str(interaction.user))
            await interaction.response.send_modal(BetAmountModal(key, self.game, self.db))
        return cb


class TaiXiuBetModal(discord.ui.Modal, title="Nhập số coin cược Tài Xỉu"):
    amount_input = discord.ui.TextInput(label="Số coin", placeholder="VD: 100", min_length=1, max_length=10)

    def __init__(self, game: dict, db, choice: str):
        super().__init__()
        self.game = game
        self.db = db
        self.choice = choice

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
            if not (BC_MIN <= amount <= BC_MAX):
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                f"❌ Nhập số hợp lệ từ {BC_MIN:,} đến {BC_MAX:,}!", ephemeral=True)
        if self.game.get("phase") != "betting":
            return await interaction.response.send_message("❌ Đã hết thời gian cược!", ephemeral=True)

        uid = interaction.user.id
        await self.db.ensure_user(uid, str(interaction.user))
        if not await self.db.deduct_coins(uid, amount, f"bet_taixiu_{self.choice}"):
            bal = await self.db.get_coins(uid)
            return await interaction.response.send_message(
                f"❌ Không đủ coin! Bạn có **{bal:,}{COIN}**", ephemeral=True)

        bets = self.game["bets"].setdefault(uid, {})
        bets[self.choice] = bets.get(self.choice, 0) + amount
        await interaction.response.send_message(
            f"✅ Đã cược **{amount:,}{COIN}** vào **{self.choice.upper()}**", ephemeral=True)


class TaiXiuView(discord.ui.View):
    def __init__(self, game: dict, db):
        super().__init__(timeout=None)
        self.game = game
        self.db = db

        for label, style, row in [("xiu", discord.ButtonStyle.success, 0), ("tai", discord.ButtonStyle.success, 0),
                                  ("chan", discord.ButtonStyle.danger, 1), ("le", discord.ButtonStyle.danger, 1)]:
            btn = discord.ui.Button(label=label.upper(), custom_id=f"txu_{label}", style=style, row=row)
            btn.callback = self._make_cb(label)
            self.add_item(btn)

        for n in range(3, 19):
            # Discord chỉ hỗ trợ tối đa 5 hàng (0..4) trong một View.
            # Gom số vào 3 hàng cuối để tránh vượt giới hạn row=5.
            row = 2 + ((n - 3) % 3)
            btn = discord.ui.Button(label=f"Số {n}", custom_id=f"txu_num_{n}", style=discord.ButtonStyle.primary, row=row)
            btn.callback = self._make_cb(str(n))
            self.add_item(btn)

    def _make_cb(self, choice: str):
        async def cb(interaction: discord.Interaction):
            if self.game.get("phase") != "betting":
                return await interaction.response.send_message("❌ Ván đã khóa cược.", ephemeral=True)
            await interaction.response.send_modal(TaiXiuBetModal(self.game, self.db, choice))
        return cb


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    async def cog_load(self):
        if not hasattr(self.bot, "active_tuxi"):
            self.bot.active_tuxi = {}
        if not hasattr(self.bot, "active_baucua"):
            self.bot.active_baucua = {}
        if not hasattr(self.bot, "active_taixiu"):
            self.bot.active_taixiu = {}

    # ── /tuxi ────────────────────────────────────────────────────────────────

    @app_commands.command(name="tuxi", description="✂️🔨📄 Mở bàn Tủ Xì (Kéo Búa Bao) cược coin")
    @app_commands.describe(bet="Số coin cược mỗi người (10 – 10,000)")
    async def cmd_tuxi(self, interaction: discord.Interaction, bet: int):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Lệnh chỉ dùng trong server.", ephemeral=True)
        if bet < 10 or bet > 10000:
            return await interaction.response.send_message("❌ Coin cược từ **10** đến **10,000**!", ephemeral=True)
        if interaction.channel_id in self.bot.active_tuxi:
            return await interaction.response.send_message("⚠️ Đang có bàn Tủ Xì trong kênh này!", ephemeral=True)
        await self.db.ensure_user(interaction.user.id, str(interaction.user))
        if await self.db.get_coins(interaction.user.id) < bet:
            return await interaction.response.send_message(
                f"❌ Bạn không đủ **{bet:,}{COIN}** để mở bàn!", ephemeral=True)

        session = {"host": interaction.user.id, "bet": bet, "choices": {}, "phase": "picking"}
        self.bot.active_tuxi[interaction.channel_id] = session

        def build_embed(remaining: int):
            return discord.Embed(
                title="✂️🔨📄 Tủ Xì | Kéo Búa Bao",
                description=(f"⏱️ Còn lại: **{remaining}s**\n"
                             f"💰 Cược: **{bet:,}{COIN}**\n\n"
                             f"Luật: 🔨 > ✂️ > 📄 > 🔨\n"
                             f"👥 **{len(session['choices'])}** người đã chọn"),
                color=0x5865F2
            )

        try:
            view = TuxiPickView(session, self.db)
            await interaction.response.send_message(embed=build_embed(GAME_WAIT_SECONDS), view=view)
            msg = await interaction.original_response()
            for rem in range(GAME_WAIT_SECONDS - 5, 0, -5):
                await asyncio.sleep(5)
                if session["phase"] != "picking":
                    break
                await msg.edit(embed=build_embed(rem), view=view)

            session["phase"] = "reveal"
            view.stop()
            for item in view.children:
                item.disabled = True
            await msg.edit(view=view)

            if not session["choices"]:
                self.bot.active_tuxi.pop(interaction.channel_id, None)
                return await interaction.channel.send(embed=discord.Embed(
                    description="😴 Không có ai tham gia, bàn giải tán.", color=0x808080
                ))

            await asyncio.sleep(1)
            results = tuxi_results(session["choices"], bet)
            lines = []
            for uid, data in results.items():
                member = interaction.guild.get_member(uid)
                name   = member.display_name if member else "Unknown"
                emoji  = TUXI_MOVES[data["move"]][0]
                if data["payout"] > 0:
                    await self.db.add_coins(uid, data["payout"], "tuxi_payout")
                if data["result"] == "win":
                    profit = data["payout"] - bet
                    lines.append(f"🏆 **{name}** {emoji} +{profit:,}{COIN}")
                elif data["result"] == "lose":
                    lines.append(f"💀 **{name}** {emoji} -{bet:,}{COIN}")
                else:
                    lines.append(f"🤝 **{name}** {emoji} Hoà (hoàn tiền)")

            all_draw = all(v["result"] == "draw" for v in results.values())
            title = "🤝 Hoà! Mọi người được hoàn tiền." if all_draw else "🏆 Kết quả Tủ Xì!"
            color = 0x808080 if all_draw else 0xFFD700
            await interaction.channel.send(embed=discord.Embed(
                title=title, description="\n".join(lines), color=color
            ))
        except Exception as e:
            self.bot.logger.error("Lỗi Tủ Xì: %s", e)
            try:
                await interaction.channel.send("❌ Đã xảy ra lỗi, bàn Tủ Xì bị hủy.")
            except Exception:
                pass
        finally:
            self.bot.active_tuxi.pop(interaction.channel_id, None)

    # ── /baucua ───────────────────────────────────────────────────────────────

    @app_commands.command(name="baucua", description="🦀 Bắt đầu ván Bầu Cua Tôm Cá!")
    async def cmd_baucua(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Lệnh chỉ dùng trong server.", ephemeral=True)
        if interaction.channel_id in self.bot.active_baucua:
            return await interaction.response.send_message(
                "⚠️ Đang có ván Bầu Cua trong kênh này!", ephemeral=True)

        game = {"bets": {}, "phase": "betting", "result": None}
        self.bot.active_baucua[interaction.channel_id] = game

        try:
            embed = discord.Embed(
                title="🎲 Bầu Cua Tôm Cá",
                description=(
                    f"Chọn linh vật để đặt cược (mỗi lần từ **{BC_MIN:,}** đến **{BC_MAX:,}{COIN}**).\n"
                    f"Bạn có **{GAME_WAIT_SECONDS} giây** để xuống tiền.\n"
                    "Kết quả sẽ xóc 3 mặt, trúng bao nhiêu mặt ăn bấy nhiêu lần cược."
                ),
                color=0x5865F2,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            view = BauCuaView(game, self.db)
            await interaction.response.send_message(embed=embed, view=view)
            cd_msg = await interaction.channel.send("⏱️ Đếm ngược: **60 giây**")

            for rem in range(GAME_WAIT_SECONDS - 5, 0, -5):
                await asyncio.sleep(5)
                if game["phase"] != "betting":
                    break
                players = len(game["bets"])
                total_pot = sum(sum(b.values()) for b in game["bets"].values())
                await cd_msg.edit(content=f"⏱️ Còn **{rem}s** • 👥 **{players}** người chơi • 💰 Pot: **{total_pot:,}{COIN}**")

            game["phase"] = "rolling"
            view.stop()
            for item in view.children:
                item.disabled = True
            await cd_msg.edit(content="🎲 Đang xóc đĩa...")

            spin_frames = ["🎲 🎲 🎲", "🦌 🦐 🦀", "🐟 🎃 🐔", "🦀 🦌 🐟", "🐔 🦐 🎃"]
            spin_embed = discord.Embed(title="🎲 Nhà cái đang xóc...", description="```\n🎲 🎲 🎲\n```", color=0xFF6B00)
            spin_msg = await interaction.channel.send(embed=spin_embed)
            for _ in range(5):
                spin_embed.description = f"```\n{random.choice(spin_frames)}\n```"
                await spin_msg.edit(embed=spin_embed)
                await asyncio.sleep(0.6)

            result = [random.choice(list(BC_SYMBOLS.keys())) for _ in range(3)]
            game["result"] = result
            game["phase"]  = "done"
            result_display = "  ".join(BC_SYMBOLS[k][0] for k in result)
            await spin_msg.delete()
            cnt = Counter(result)

            total_pot = sum(sum(b.values()) for b in game["bets"].values())
            result_embed = discord.Embed(
                title="🎲 Kết Quả Bầu Cua!",
                description=f"# {result_display}\n💰 Tổng tiền cược: **{total_pot:,}{COIN}**",
                color=0xFFD700,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            if not game["bets"]:
                result_embed.add_field(name="😴 Không có ai cược", value="Nhà cái vơ vét đĩa trống...", inline=False)
            else:
                lines = []
                for uid, bets in game["bets"].items():
                    total_bet = sum(bets.values())
                    payout = sum(
                        (bet + bet * cnt.get(sym, 0)) if cnt.get(sym, 0) > 0 else 0
                        for sym, bet in bets.items()
                    )
                    member = interaction.guild.get_member(uid)
                    mname  = member.display_name if member else f"User {uid}"
                    if payout > 0:
                        await self.db.add_coins(uid, payout, "baucua_payout")
                        profit = payout - total_bet
                        lines.append(f"🏆 **{mname}**: +{profit:,}{COIN}")
                    else:
                        lines.append(f"💀 **{mname}**: -{total_bet:,}{COIN}")
                result_embed.add_field(name="📊 Kết quả:", value="\n".join(lines), inline=False)

            result_embed.set_footer(text="  |  ".join(f"{BC_SYMBOLS[k][0]}×{v}" for k, v in cnt.items()))
            if cd_msg:
                await cd_msg.delete()
            await interaction.channel.send(embed=result_embed)

        except Exception as e:
            self.bot.logger.error("Lỗi Bầu Cua: %s", e)
            try:
                await interaction.channel.send("❌ Đã xảy ra lỗi, ván cược bị hủy.")
            except Exception:
                pass
        finally:
            self.bot.active_baucua.pop(interaction.channel_id, None)

    @app_commands.command(name="taixiu", description="🎲 Mở bàn Tài Xỉu (Tài/Xỉu/Chẵn/Lẻ/Số)")
    async def cmd_taixiu(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Lệnh chỉ dùng trong server.", ephemeral=True)
        if interaction.channel_id in self.bot.active_taixiu:
            return await interaction.response.send_message("⚠️ Đang có ván Tài Xỉu trong kênh này!", ephemeral=True)

        game = {"bets": {}, "phase": "betting", "result": None}
        self.bot.active_taixiu[interaction.channel_id] = game

        try:
            embed = discord.Embed(
                title="🎲 Tài Xỉu Neko",
                description=(
                    "Chọn **Tài (11-18)**, **Xỉu (3-10)**, **Chẵn/Lẻ** hoặc **Số cụ thể (3-18)**.\n"
                    f"Bấm nút để mở form nhập coin cược. Thời gian cược: **{TAIXIU_WAIT_SECONDS}s**.\n"
                    "Tỉ lệ: Tài/Xỉu/Chẵn/Lẻ = **1:1**, Số cụ thể = **1:10**."
                ),
                color=0x00A8FF,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            view = TaiXiuView(game, self.db)
            await interaction.response.send_message(embed=embed, view=view)
            cd_msg = await interaction.channel.send(f"⏱️ Còn **{TAIXIU_WAIT_SECONDS}s** để đặt cược")

            for rem in range(TAIXIU_WAIT_SECONDS - 5, 0, -5):
                await asyncio.sleep(5)
                if game["phase"] != "betting":
                    break
                players = len(game["bets"])
                pot = sum(sum(v.values()) for v in game["bets"].values())
                await cd_msg.edit(content=f"⏱️ Còn **{rem}s** • 👥 **{players}** người • 💰 Pot: **{pot:,}{COIN}**")

            game["phase"] = "rolling"
            for item in view.children:
                item.disabled = True
            await interaction.edit_original_response(view=view)
            await cd_msg.edit(content="🎲 Đang lắc xúc xắc...")

            dices = [random.randint(1, 6) for _ in range(3)]
            total = sum(dices)
            parity = "chan" if total % 2 == 0 else "le"
            size = "tai" if total >= 11 else "xiu"
            game["result"] = {"dices": dices, "total": total, "parity": parity, "size": size}

            lines = []
            for uid, user_bets in game["bets"].items():
                member = interaction.guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                total_bet = sum(user_bets.values())
                payout = 0
                for choice, amt in user_bets.items():
                    if choice in {size, parity}:
                        payout += amt * 2
                    elif choice.isdigit() and int(choice) == total:
                        payout += amt * 10
                if payout > 0:
                    await self.db.add_coins(uid, payout, "taixiu_payout")
                    lines.append(f"🏆 **{name}**: +{payout - total_bet:,}{COIN}")
                else:
                    lines.append(f"💀 **{name}**: -{total_bet:,}{COIN}")

            result_embed = discord.Embed(
                title="🎲 Kết quả Tài Xỉu",
                description=(
                    f"🎯 Xúc xắc: **{dices[0]} - {dices[1]} - {dices[2]}**\n"
                    f"Tổng: **{total}**  |  {'TÀI' if size=='tai' else 'XỈU'}  |  {'CHẴN' if parity=='chan' else 'LẺ'}"
                ),
                color=0xFFD700,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            result_embed.add_field(name="📊 Kết toán", value="\n".join(lines) if lines else "Không có ai tham gia", inline=False)
            await cd_msg.delete()
            await interaction.channel.send(embed=result_embed)
        finally:
            self.bot.active_taixiu.pop(interaction.channel_id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
