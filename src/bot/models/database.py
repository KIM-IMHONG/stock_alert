"""
Database models and initialization for Korea Stock Alert Bot
"""
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class User:
    """User data model"""
    user_id: int
    username: Optional[str]
    first_name: str
    alert_threshold: float
    created_at: datetime
    updated_at: datetime

@dataclass
class WatchlistItem:
    """Watchlist item data model"""
    user_id: int
    stock_code: str
    added_at: datetime

@dataclass
class AlertHistory:
    """Alert history data model"""
    user_id: int
    stock_code: str
    alert_type: str
    price: float
    change_rate: float
    sent_at: datetime

class DatabaseManager:
    """Database manager for bot data"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def initialize(self):
        """Initialize database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    alert_threshold REAL DEFAULT 5.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Watchlist table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    user_id INTEGER,
                    stock_code TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, stock_code),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Alert history table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    stock_code TEXT,
                    alert_type TEXT,
                    price REAL,
                    change_rate REAL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Create indexes for performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_user 
                ON watchlist(user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_history_user_time 
                ON alert_history(user_id, stock_code, sent_at)
            """)
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def create_or_update_user(self, user_id: int, username: str = None, 
                                   first_name: str = "") -> User:
        """Create or update user in database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if user exists
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
            if row:
                # Update existing user
                await db.execute("""
                    UPDATE users 
                    SET username = ?, first_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (username, first_name, user_id))
            else:
                # Create new user
                await db.execute("""
                    INSERT INTO users (user_id, username, first_name)
                    VALUES (?, ?, ?)
                """, (user_id, username, first_name))
                
            await db.commit()
            
            # Return updated user
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return User(
                    user_id=row[0],
                    username=row[1],
                    first_name=row[2],
                    alert_threshold=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5])
                )
    
    async def add_to_watchlist(self, user_id: int, stock_code: str) -> bool:
        """Add stock to user's watchlist"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO watchlist (user_id, stock_code)
                    VALUES (?, ?)
                """, (user_id, stock_code))
                await db.commit()
                return True
        except aiosqlite.IntegrityError:
            # Stock already in watchlist
            return False
    
    async def remove_from_watchlist(self, user_id: int, stock_code: str) -> bool:
        """Remove stock from user's watchlist"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM watchlist 
                WHERE user_id = ? AND stock_code = ?
            """, (user_id, stock_code))
            await db.commit()
            return cursor.rowcount > 0
    
    async def get_watchlist(self, user_id: int) -> List[str]:
        """Get user's watchlist"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT stock_code FROM watchlist 
                WHERE user_id = ? 
                ORDER BY added_at
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_watchlist_count(self, user_id: int) -> int:
        """Get count of stocks in user's watchlist"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM watchlist WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0]
    
    async def update_alert_threshold(self, user_id: int, threshold: float) -> bool:
        """Update user's alert threshold"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE users 
                SET alert_threshold = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (threshold, user_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def get_user_alert_threshold(self, user_id: int) -> float:
        """Get user's alert threshold"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT alert_threshold FROM users WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 5.0
    
    async def add_alert_history(self, user_id: int, stock_code: str, 
                               alert_type: str, price: float, change_rate: float):
        """Add alert to history"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO alert_history 
                (user_id, stock_code, alert_type, price, change_rate)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, stock_code, alert_type, price, change_rate))
            await db.commit()
    
    async def can_send_alert(self, user_id: int, stock_code: str, 
                            cooldown_minutes: int) -> bool:
        """Check if alert can be sent (cooldown check)"""
        cutoff_time = datetime.now() - timedelta(minutes=cooldown_minutes)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM alert_history 
                WHERE user_id = ? AND stock_code = ? AND sent_at > ?
            """, (user_id, stock_code, cutoff_time.isoformat())) as cursor:
                row = await cursor.fetchone()
                return row[0] == 0
    
    async def get_all_users_watching_stock(self, stock_code: str) -> List[int]:
        """Get all user IDs watching a specific stock"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id FROM watchlist WHERE stock_code = ?
            """, (stock_code,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_all_watched_stocks(self) -> List[str]:
        """Get all stocks being watched by any user"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT DISTINCT stock_code FROM watchlist
            """) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]