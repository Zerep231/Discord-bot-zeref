import aiosqlite
import logging

logger = logging.getLogger(__name__)
DB_PATH = "zerbot2_economy.db"


class Database:
    def __init__(self):
        self.db: aiosqlite.Connection | None = None

    async def connect(self):
        self.db = await aiosqlite.connect(DB_PATH)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._init_db()
        logger.info("Database connected: %s", DB_PATH)

    async def close(self):
        if self.db is not None:
            await self.db.close()
            self.db = None
            logger.info("Database closed")

    async def _init_db(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      INTEGER PRIMARY KEY,
                username     TEXT    NOT NULL,
                coins        INTEGER NOT NULL DEFAULT 0,
                total_earned INTEGER NOT NULL DEFAULT 0,
                msg_week     INTEGER NOT NULL DEFAULT 0,
                last_daily   TEXT,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                amount     INTEGER NOT NULL,
                type       TEXT    NOT NULL,
                note       TEXT,
                created_at TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS exchange_orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                username     TEXT    NOT NULL,
                guild_id     INTEGER NOT NULL DEFAULT 0,
                coins_spent  INTEGER NOT NULL,
                item_type    TEXT    NOT NULL,
                item_key     TEXT    NOT NULL,
                quantity     INTEGER NOT NULL DEFAULT 1,
                note         TEXT,
                fulfilled    INTEGER NOT NULL DEFAULT 0,
                fulfilled_by TEXT,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_tx_user    ON transactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_guild ON exchange_orders(guild_id, fulfilled);
        """)
        await self.db.commit()

    # ── User ────────────────────────────────────────────────────────────────

    async def ensure_user(self, user_id: int, username: str):
        await self.db.execute("""
            INSERT INTO users (user_id, username, coins) VALUES (?, ?, 100)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, updated_at=datetime('now')
        """, (user_id, username))
        await self.db.commit()

    async def get_user(self, user_id: int) -> dict | None:
        async with self.db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None

    async def get_coins(self, user_id: int) -> int:
        async with self.db.execute("SELECT coins FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return row["coins"] if row else 0

    # ── Coin ops ─────────────────────────────────────────────────────────────

    async def add_coins(self, user_id: int, amount: int, note: str = "reward") -> int:
        await self.db.execute("""
            UPDATE users
            SET coins=coins+?, total_earned=total_earned+MAX(0,?), updated_at=datetime('now')
            WHERE user_id=?
        """, (amount, amount, user_id))
        await self.db.execute(
            "INSERT INTO transactions (user_id,amount,type,note) VALUES (?,?,'add',?)",
            (user_id, amount, note)
        )
        await self.db.commit()
        return await self.get_coins(user_id)

    async def deduct_coins(self, user_id: int, amount: int, note: str = "spend") -> bool:
        cur = await self.db.execute("""
            UPDATE users SET coins=coins-?, updated_at=datetime('now')
            WHERE user_id=? AND coins>=?
        """, (amount, user_id, amount))
        if cur.rowcount == 0:
            return False
        await self.db.execute(
            "INSERT INTO transactions (user_id,amount,type,note) VALUES (?,?,'deduct',?)",
            (user_id, -amount, note)
        )
        await self.db.commit()
        return True

    async def set_coins(self, user_id: int, amount: int, note: str = "admin_set"):
        await self.db.execute(
            "UPDATE users SET coins=?, updated_at=datetime('now') WHERE user_id=?",
            (amount, user_id)
        )
        await self.db.execute(
            "INSERT INTO transactions (user_id,amount,type,note) VALUES (?,?,'set',?)",
            (user_id, amount, note)
        )
        await self.db.commit()

    async def transfer_coins(self, from_id: int, to_id: int, amount: int,
                             note_from: str = "transfer", note_to: str = "transfer") -> bool:
        if amount <= 0:
            return False

        async with self.db.execute("BEGIN IMMEDIATE"):
            cur = await self.db.execute(
                """
                UPDATE users SET coins=coins-?, updated_at=datetime('now')
                WHERE user_id=? AND coins>=?
                """,
                (amount, from_id, amount),
            )
            if cur.rowcount == 0:
                await self.db.rollback()
                return False

            await self.db.execute(
                """
                UPDATE users
                SET coins=coins+?, total_earned=total_earned+?, updated_at=datetime('now')
                WHERE user_id=?
                """,
                (amount, amount, to_id),
            )
            await self.db.execute(
                "INSERT INTO transactions (user_id,amount,type,note) VALUES (?,?,'deduct',?)",
                (from_id, -amount, f"{note_from}→{to_id}"),
            )
            await self.db.execute(
                "INSERT INTO transactions (user_id,amount,type,note) VALUES (?,?,'add',?)",
                (to_id, amount, f"{note_to}←{from_id}"),
            )
            await self.db.commit()
        return True

    async def get_top_coins(self, limit: int = 10) -> list[dict]:
        async with self.db.execute(
            "SELECT user_id,username,coins,total_earned FROM users ORDER BY coins DESC LIMIT ?",
            (limit,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

    # ── Messages / daily ─────────────────────────────────────────────────────

    async def add_message_count(self, user_id: int):
        await self.db.execute("UPDATE users SET msg_week=msg_week+1 WHERE user_id=?", (user_id,))
        await self.db.commit()

    async def get_weekly_top(self) -> tuple | None:
        async with self.db.execute(
            "SELECT user_id,username,msg_week FROM users WHERE msg_week>0 ORDER BY msg_week DESC LIMIT 1"
        ) as c:
            row = await c.fetchone()
            return tuple(row) if row else None

    async def reset_weekly_messages(self):
        await self.db.execute("UPDATE users SET msg_week=0")
        await self.db.commit()

    async def can_claim_daily(self, user_id: int) -> bool:
        async with self.db.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            if not row or not row["last_daily"]:
                return True
            from datetime import datetime, timezone
            last = datetime.fromisoformat(row["last_daily"])
            now  = datetime.now(timezone.utc)
            return (now - last).total_seconds() >= 86400

    async def set_last_daily(self, user_id: int):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute("UPDATE users SET last_daily=? WHERE user_id=?", (now, user_id))
        await self.db.commit()

    # ── Orders ────────────────────────────────────────────────────────────────

    async def create_order(self, user_id: int, username: str, guild_id: int,
                           coins: int, item_type: str, item_key: str,
                           quantity: int, note: str = "") -> int:
        cur = await self.db.execute(
            "INSERT INTO exchange_orders (user_id,username,guild_id,coins_spent,item_type,item_key,quantity,note) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, username, guild_id, coins, item_type, item_key, quantity, note)
        )
        await self.db.commit()
        return cur.lastrowid

    async def get_pending_orders(self, guild_id: int) -> list[dict]:
        async with self.db.execute(
            "SELECT * FROM exchange_orders WHERE guild_id=? AND fulfilled=0 ORDER BY created_at ASC",
            (guild_id,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

    async def fulfill_order(self, order_id: int, admin_name: str) -> bool:
        cur = await self.db.execute(
            "UPDATE exchange_orders SET fulfilled=1, fulfilled_by=? WHERE id=? AND fulfilled=0",
            (admin_name, order_id)
        )
        await self.db.commit()
        return cur.rowcount > 0

    async def cancel_order(self, order_id: int, guild_id: int) -> dict | None:
        async with self.db.execute(
            "SELECT * FROM exchange_orders WHERE id=? AND guild_id=? AND fulfilled=0",
            (order_id, guild_id)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
        await self.db.execute("UPDATE exchange_orders SET fulfilled=2 WHERE id=?", (order_id,))
        await self.db.commit()
        return dict(row)

    async def get_history(self, user_id: int, limit: int = 10) -> list[dict]:
        async with self.db.execute(
            "SELECT amount,type,note,created_at FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as c:
            return [dict(r) for r in await c.fetchall()]
