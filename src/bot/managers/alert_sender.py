"""
Alert sending and management for Korea Stock Alert Bot
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Bot
from telegram.error import TelegramError

from ..models.database import DatabaseManager
from ..config import ALERT_TEMPLATE, ALERT_COOLDOWN_MINUTES

logger = logging.getLogger(__name__)

class AlertSender:
    """Manages alert sending and cooldown logic"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
    
    def format_alert_message(self, stock_code: str, stock_name: str,
                           current_price: float, change_rate: float) -> str:
        """Format alert message using template"""
        
        # Determine alert type and emoji
        if change_rate >= 0:
            alert_type = "🚀 급등"
            trend_emoji = "📈"
            status = f"{change_rate:+.2f}% 상승했습니다!"
        else:
            alert_type = "⚠️ 급락"
            trend_emoji = "📉"
            status = f"{change_rate:.2f}% 하락했습니다!"
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message
        message = ALERT_TEMPLATE.format(
            alert_type=alert_type,
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=int(current_price),
            change_rate=change_rate,
            timestamp=timestamp,
            trend_emoji=trend_emoji,
            status=status
        )
        
        return message
    
    async def can_send_alert(self, user_id: int, stock_code: str) -> bool:
        """Check if alert can be sent (considering cooldown)"""
        try:
            return await self.db_manager.can_send_alert(
                user_id, stock_code, ALERT_COOLDOWN_MINUTES
            )
        except Exception as e:
            logger.error(f"Error checking alert cooldown for user {user_id}, stock {stock_code}: {e}")
            return False
    
    async def send_alert_to_user(self, user_id: int, stock_code: str, 
                               stock_name: str, current_price: float, 
                               change_rate: float) -> bool:
        """Send alert to a specific user"""
        try:
            # Check if alert should be sent (threshold and cooldown)
            user_threshold = await self.db_manager.get_user_alert_threshold(user_id)
            
            if abs(change_rate) < user_threshold:
                return False
            
            if not await self.can_send_alert(user_id, stock_code):
                logger.debug(f"Alert cooldown active for user {user_id}, stock {stock_code}")
                return False
            
            # Format and send message
            message = self.format_alert_message(
                stock_code, stock_name, current_price, change_rate
            )
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            # Record alert in history
            alert_type = "상승" if change_rate >= 0 else "하락"
            await self.db_manager.add_alert_history(
                user_id, stock_code, alert_type, current_price, change_rate
            )
            
            logger.info(f"Alert sent to user {user_id} for {stock_code} ({change_rate:+.2f}%)")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error sending alert to user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending alert to user {user_id}: {e}")
            return False
    
    async def broadcast_stock_alert(self, stock_code: str, stock_name: str,
                                  current_price: float, change_rate: float) -> int:
        """
        Broadcast alert for a stock to all users watching it
        Returns: number of alerts sent successfully
        """
        try:
            # Get all users watching this stock
            watching_users = await self.db_manager.get_all_users_watching_stock(stock_code)
            
            if not watching_users:
                return 0
            
            successful_sends = 0
            
            # Send alerts to each user
            for user_id in watching_users:
                try:
                    success = await self.send_alert_to_user(
                        user_id, stock_code, stock_name, current_price, change_rate
                    )
                    if success:
                        successful_sends += 1
                        
                except Exception as e:
                    logger.error(f"Failed to send alert to user {user_id}: {e}")
                    continue
            
            logger.info(f"Sent {successful_sends}/{len(watching_users)} alerts for {stock_code}")
            return successful_sends
            
        except Exception as e:
            logger.error(f"Error broadcasting alert for stock {stock_code}: {e}")
            return 0
    
    async def process_price_updates(self, price_updates: List[Dict]) -> int:
        """
        Process multiple price updates and send alerts
        
        Expected format for price_updates:
        [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "current_price": 75000,
                "change_rate": 5.2
            },
            ...
        ]
        
        Returns: total number of alerts sent
        """
        total_alerts_sent = 0
        
        for update in price_updates:
            try:
                stock_code = update.get("stock_code")
                stock_name = update.get("stock_name", stock_code)
                current_price = update.get("current_price", 0)
                change_rate = update.get("change_rate", 0)
                
                if not stock_code:
                    continue
                
                # Send alerts for this stock
                alerts_sent = await self.broadcast_stock_alert(
                    stock_code, stock_name, current_price, change_rate
                )
                total_alerts_sent += alerts_sent
                
            except Exception as e:
                logger.error(f"Error processing price update: {update}, error: {e}")
                continue
        
        if total_alerts_sent > 0:
            logger.info(f"Total alerts sent: {total_alerts_sent}")
        
        return total_alerts_sent
    
    async def send_test_alert(self, user_id: int) -> bool:
        """Send a test alert to verify functionality"""
        try:
            test_message = """
🧪 **테스트 알림**

📈 종목: 000000 테스트종목
💰 현재가: 10,000원
📊 변동률: +5.00%
⏰ 시간: 테스트

📈 이것은 테스트 알림입니다!
            """.strip()
            
            await self.bot.send_message(
                chat_id=user_id,
                text=test_message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Test alert sent to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send test alert to user {user_id}: {e}")
            return False
    
    async def get_alert_statistics(self) -> Dict:
        """Get alert sending statistics"""
        try:
            # This would be expanded based on specific analytics needs
            watched_stocks = await self.db_manager.get_all_watched_stocks()
            
            stats = {
                "total_watched_stocks": len(watched_stocks),
                "alert_cooldown_minutes": ALERT_COOLDOWN_MINUTES,
                "watched_stocks": watched_stocks[:10]  # Show first 10
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {
                "total_watched_stocks": 0,
                "alert_cooldown_minutes": ALERT_COOLDOWN_MINUTES,
                "watched_stocks": []
            }