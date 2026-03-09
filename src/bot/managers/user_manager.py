"""
User management for Korea Stock Alert Bot
"""
import re
import logging
from typing import List, Optional, Tuple
from datetime import datetime

from ..models.database import DatabaseManager
from ..config import MAX_WATCHLIST_SIZE, MESSAGES

logger = logging.getLogger(__name__)

class UserManager:
    """Manages user data and watchlist operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.stock_code_pattern = re.compile(r'^\d{6}$')
    
    def validate_stock_code(self, stock_code: str) -> bool:
        """Validate stock code format (6 digits)"""
        return bool(self.stock_code_pattern.match(stock_code.strip()))
    
    async def register_user(self, user_id: int, username: str = None, 
                           first_name: str = "") -> bool:
        """Register or update user in database"""
        try:
            await self.db_manager.create_or_update_user(
                user_id, username, first_name
            )
            logger.info(f"User {user_id} ({first_name}) registered/updated")
            return True
        except Exception as e:
            logger.error(f"Failed to register user {user_id}: {e}")
            return False
    
    async def add_stock_to_watchlist(self, user_id: int, stock_code: str) -> Tuple[bool, str]:
        """
        Add stock to user's watchlist
        Returns: (success, message)
        """
        try:
            # Validate stock code format
            if not self.validate_stock_code(stock_code):
                return False, MESSAGES["invalid_stock_code"]
            
            # Check watchlist size limit
            current_count = await self.db_manager.get_watchlist_count(user_id)
            if current_count >= MAX_WATCHLIST_SIZE:
                return False, MESSAGES["watchlist_full"].format(
                    max_size=MAX_WATCHLIST_SIZE
                )
            
            # Try to add stock
            success = await self.db_manager.add_to_watchlist(user_id, stock_code)
            if success:
                logger.info(f"User {user_id} added stock {stock_code} to watchlist")
                return True, MESSAGES["stock_added"].format(stock_code=stock_code)
            else:
                return False, MESSAGES["already_watching"].format(stock_code=stock_code)
                
        except Exception as e:
            logger.error(f"Failed to add stock {stock_code} for user {user_id}: {e}")
            return False, MESSAGES["error"]
    
    async def remove_stock_from_watchlist(self, user_id: int, stock_code: str) -> Tuple[bool, str]:
        """
        Remove stock from user's watchlist
        Returns: (success, message)
        """
        try:
            # Validate stock code format
            if not self.validate_stock_code(stock_code):
                return False, MESSAGES["invalid_stock_code"]
            
            # Try to remove stock
            success = await self.db_manager.remove_from_watchlist(user_id, stock_code)
            if success:
                logger.info(f"User {user_id} removed stock {stock_code} from watchlist")
                return True, MESSAGES["stock_removed"].format(stock_code=stock_code)
            else:
                return False, MESSAGES["not_watching"].format(stock_code=stock_code)
                
        except Exception as e:
            logger.error(f"Failed to remove stock {stock_code} for user {user_id}: {e}")
            return False, MESSAGES["error"]
    
    async def get_user_watchlist(self, user_id: int) -> List[str]:
        """Get user's current watchlist"""
        try:
            return await self.db_manager.get_watchlist(user_id)
        except Exception as e:
            logger.error(f"Failed to get watchlist for user {user_id}: {e}")
            return []
    
    async def format_watchlist_message(self, user_id: int) -> str:
        """Format watchlist as message string"""
        try:
            watchlist = await self.get_user_watchlist(user_id)
            
            if not watchlist:
                return MESSAGES["empty_watchlist"]
            
            # Get current alert threshold
            threshold = await self.db_manager.get_user_alert_threshold(user_id)
            
            message = f"📋 **현재 모니터링 중인 종목** ({len(watchlist)}/{MAX_WATCHLIST_SIZE})\n\n"
            
            for i, stock_code in enumerate(watchlist, 1):
                message += f"{i:2d}. {stock_code}\n"
            
            message += f"\n⚙️ 현재 알림 설정: ±{threshold:.1f}% 이상 변동 시"
            return message
            
        except Exception as e:
            logger.error(f"Failed to format watchlist for user {user_id}: {e}")
            return MESSAGES["error"]
    
    async def update_alert_settings(self, user_id: int, threshold: float) -> Tuple[bool, str]:
        """
        Update user's alert threshold
        Returns: (success, message)
        """
        try:
            # Validate threshold range
            if not (1.0 <= threshold <= 50.0):
                return False, MESSAGES["invalid_threshold"]
            
            # Update threshold
            success = await self.db_manager.update_alert_threshold(user_id, threshold)
            if success:
                logger.info(f"User {user_id} updated alert threshold to {threshold}%")
                return True, MESSAGES["settings_updated"]
            else:
                return False, MESSAGES["error"]
                
        except Exception as e:
            logger.error(f"Failed to update alert settings for user {user_id}: {e}")
            return False, MESSAGES["error"]
    
    async def get_alert_settings_message(self, user_id: int) -> str:
        """Get formatted alert settings message"""
        try:
            threshold = await self.db_manager.get_user_alert_threshold(user_id)
            
            message = f"""
⚙️ **알림 설정**

📊 현재 설정: ±{threshold:.1f}% 이상 변동 시 알림

💡 설정 변경:
알림을 받을 급등/급락 기준을 설정하세요.
예: 5% → ±5% 이상 변동 시 알림

📝 사용법: 숫자만 입력하세요 (1-50)
            """.strip()
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to get alert settings for user {user_id}: {e}")
            return MESSAGES["error"]
    
    async def get_user_statistics(self, user_id: int) -> dict:
        """Get user statistics"""
        try:
            watchlist = await self.get_user_watchlist(user_id)
            threshold = await self.db_manager.get_user_alert_threshold(user_id)
            
            return {
                "watchlist_count": len(watchlist),
                "watchlist_limit": MAX_WATCHLIST_SIZE,
                "alert_threshold": threshold,
                "can_add_more": len(watchlist) < MAX_WATCHLIST_SIZE
            }
        except Exception as e:
            logger.error(f"Failed to get statistics for user {user_id}: {e}")
            return {
                "watchlist_count": 0,
                "watchlist_limit": MAX_WATCHLIST_SIZE,
                "alert_threshold": 5.0,
                "can_add_more": True
            }