"""
Alert sending and management for Korea Stock Alert Bot

알림 조건: 3분 내 변동률이 유저 임계값 초과 시 발동
"""
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from telegram import Bot
from telegram.error import TelegramError

from ..models.database import DatabaseManager
from ..config import ALERT_COOLDOWN_MINUTES

logger = logging.getLogger(__name__)

# 한국 시간대
KST = timezone(timedelta(hours=9))


class AlertSender:
    """알림 발송 관리 (3분 변동률 기반)"""

    def __init__(self, bot: Bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager

        # 인메모리 쿨다운: "user_id:stock_code" → 마지막 발송 epoch
        self._cooldown_cache: Dict[str, float] = {}

        # 스로틀링: stock_code → 마지막 broadcast epoch
        self._last_broadcast: Dict[str, float] = {}
        self._broadcast_interval = 10.0  # 같은 종목 최소 10초 간격

    def _now_kst(self) -> datetime:
        return datetime.now(KST)

    def _is_in_cooldown(self, user_id: int, stock_code: str) -> bool:
        key = f"{user_id}:{stock_code}"
        last = self._cooldown_cache.get(key, 0)
        return (time.time() - last) < (ALERT_COOLDOWN_MINUTES * 60)

    def _set_cooldown(self, user_id: int, stock_code: str):
        self._cooldown_cache[f"{user_id}:{stock_code}"] = time.time()

    def _should_throttle(self, stock_code: str) -> bool:
        now = time.time()
        last = self._last_broadcast.get(stock_code, 0)
        if now - last < self._broadcast_interval:
            return True
        self._last_broadcast[stock_code] = now
        return False

    def format_alert_message(self, stock_code: str, stock_name: str,
                           current_price: int, change_rate_3m: float,
                           change_from_open: Optional[float] = None,
                           open_price: int = 0) -> str:
        """알림 메시지 포맷"""
        # 급등/급락 판정
        if change_rate_3m >= 0:
            alert_emoji = "🚀"
            alert_type = "급등"
            trend_emoji = "📈"
        else:
            alert_emoji = "🔻"
            alert_type = "급락"
            trend_emoji = "📉"

        now_str = self._now_kst().strftime("%H:%M:%S")

        lines = [
            f"{alert_emoji} *{alert_type} 알림!*",
            "",
            f"📌 종목: {stock_name} ({stock_code})",
            f"💰 현재가: {current_price:,}원",
            f"{trend_emoji} 3분 변동: {change_rate_3m:+.2f}%",
        ]

        if change_from_open is not None and open_price > 0:
            open_emoji = "📈" if change_from_open >= 0 else "📉"
            lines.append(f"{open_emoji} 시가대비: {change_from_open:+.2f}% (시가 {open_price:,}원)")

        lines.extend([
            "",
            f"⏰ {now_str}",
        ])

        return "\n".join(lines)

    async def send_alert_to_user(self, user_id: int, stock_code: str,
                               stock_name: str, current_price: int,
                               change_rate_3m: float,
                               change_from_open: Optional[float] = None,
                               open_price: int = 0) -> bool:
        """유저 1명에게 알림 발송"""
        try:
            # 1. 유저 임계값 체크 (3분 변동률 기준)
            user_threshold = await self.db_manager.get_user_alert_threshold(user_id)
            if abs(change_rate_3m) < user_threshold:
                return False

            # 2. 쿨다운 체크
            if self._is_in_cooldown(user_id, stock_code):
                return False

            # 3. 메시지 발송
            message = self.format_alert_message(
                stock_code, stock_name, current_price,
                change_rate_3m, change_from_open, open_price
            )

            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )

            # 4. 쿨다운 설정
            self._set_cooldown(user_id, stock_code)

            # 5. DB 이력 기록
            try:
                alert_type = "상승" if change_rate_3m >= 0 else "하락"
                await self.db_manager.add_alert_history(
                    user_id, stock_code, alert_type, current_price, change_rate_3m
                )
            except Exception as e:
                logger.error(f"알림 이력 저장 실패: {e}")

            logger.info(
                f"알림 발송: user={user_id}, {stock_code}({stock_name}) "
                f"{current_price:,}원 (3분:{change_rate_3m:+.2f}%)"
            )
            return True

        except TelegramError as e:
            logger.error(f"텔레그램 발송 오류 (user {user_id}): {e}")
            return False
        except Exception as e:
            logger.error(f"알림 발송 오류 (user {user_id}): {e}")
            return False

    async def broadcast_stock_alert(self, stock_code: str, stock_name: str,
                                  current_price: int, change_rate_3m: float,
                                  change_from_open: Optional[float] = None,
                                  open_price: int = 0) -> int:
        """
        종목 알림 브로드캐스트

        - 스로틀: 같은 종목 10초 간격
        - 쿨다운: 같은 유저+종목 15분 간격
        - 조건: 3분 변동률 >= 유저 임계값
        """
        if self._should_throttle(stock_code):
            return 0

        try:
            watching_users = await self.db_manager.get_all_users_watching_stock(stock_code)
            if not watching_users:
                return 0

            sent = 0
            for user_id in watching_users:
                try:
                    ok = await self.send_alert_to_user(
                        user_id, stock_code, stock_name, current_price,
                        change_rate_3m, change_from_open, open_price
                    )
                    if ok:
                        sent += 1
                except Exception as e:
                    logger.error(f"유저 {user_id} 알림 실패: {e}")

            return sent

        except Exception as e:
            logger.error(f"브로드캐스트 오류 [{stock_code}]: {e}")
            return 0

    async def send_test_alert(self, user_id: int) -> bool:
        """테스트 알림"""
        try:
            now = self._now_kst().strftime("%H:%M:%S")
            msg = (
                "🧪 *테스트 알림*\n\n"
                "📌 종목: 테스트종목 (000000)\n"
                "💰 현재가: 10,000원\n"
                "📈 3분 변동: +5.00%\n"
                "📈 시가대비: +3.20% (시가 9,689원)\n\n"
                f"⏰ {now}"
            )
            await self.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
            return True
        except Exception as e:
            logger.error(f"테스트 알림 실패: {e}")
            return False
