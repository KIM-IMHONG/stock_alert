"""
Korea Stock Alert Bot - 메인 실행 파일

사용법:
    python main.py
"""
import asyncio
import logging
import os
import signal
import sys
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from telegram import Bot
from telegram.ext import Application

# src를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'bot'))

from bot.models.database import DatabaseManager
from bot.handlers.bot_handler import BotHandler
from bot.managers.alert_sender import AlertSender
from bot.utils.stock_utils import get_stock_name
from bot.utils.stock_search import get_stock_searcher
from bot.config import get_config, BOT_TOKEN

from api.kis_api.client import KISAPIClient
from api.kis_api.config import KISConfig
from api.kis_api.websocket_client import KISWebSocketClient, RealtimeData

# 로깅 설정
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('StockAlertBot')


# ============================================================
# 3분 가격 추적기
# ============================================================
class PriceTracker:
    """종목별 3분 윈도우 가격 변동 추적"""

    def __init__(self, window_seconds: int = 180):
        self._window = window_seconds  # 3분 = 180초
        # {stock_code: deque of (timestamp, price)}
        self._history: Dict[str, deque] = defaultdict(deque)
        # {stock_code: open_price} - 당일 시가 캐시
        self._open_prices: Dict[str, int] = {}

    def update(self, stock_code: str, price: int, open_price: int = 0
               ) -> Tuple[Optional[float], Optional[float]]:
        """
        가격 업데이트 후 변동률 반환

        Returns:
            (3분_변동률, 시가대비_변동률) - 데이터 부족 시 None
        """
        now = time.time()
        history = self._history[stock_code]
        history.append((now, price))

        # 시가 저장 (최초 1회)
        if open_price > 0:
            self._open_prices[stock_code] = open_price

        # 3분 초과 데이터 제거
        cutoff = now - self._window
        while history and history[0][0] < cutoff:
            history.popleft()

        # 3분 변동률 계산
        change_3m = None
        if len(history) >= 2:
            oldest_price = history[0][1]
            if oldest_price > 0:
                change_3m = round(((price - oldest_price) / oldest_price) * 100, 2)

        # 시가 대비 변동률
        change_from_open = None
        op = self._open_prices.get(stock_code)
        if op and op > 0:
            change_from_open = round(((price - op) / op) * 100, 2)

        return change_3m, change_from_open

    def clear(self, stock_code: str = None):
        if stock_code:
            self._history.pop(stock_code, None)
            self._open_prices.pop(stock_code, None)
        else:
            self._history.clear()
            self._open_prices.clear()


# ============================================================
# 메인 봇 클래스
# ============================================================
class KoreaStockAlertBot:
    """한국 주식 급등/급락 알림봇 (통합 서비스)"""

    def __init__(self):
        self.config = get_config()
        self.db_manager = DatabaseManager(self.config["database_path"])

        # KIS API
        self.kis_config = KISConfig()
        self.kis_client: Optional[KISAPIClient] = None
        self.ws_client: Optional[KISWebSocketClient] = None

        # Telegram
        self.bot_handler: Optional[BotHandler] = None
        self.alert_sender: Optional[AlertSender] = None

        # 3분 가격 추적
        self.price_tracker = PriceTracker(window_seconds=180)

        # 종료 이벤트
        self._stop_event = asyncio.Event()

    async def initialize(self):
        """모든 컴포넌트 초기화"""
        # 0. 종목 리스트 로드 (KRX)
        logger.info("종목 리스트 로드 중...")
        searcher = get_stock_searcher()
        logger.info(f"종목 리스트: {searcher.count}개 로드 완료")

        # 1. DB
        logger.info("데이터베이스 초기화...")
        await self.db_manager.initialize()

        # 2. 텔레그램 봇
        logger.info("텔레그램 봇 초기화...")
        self.bot_handler = BotHandler(BOT_TOKEN, self.db_manager)
        self.bot_handler.on_stock_added = self._on_stock_added
        self.bot_handler.on_stock_removed = self._on_stock_removed

        await self.bot_handler.application.initialize()
        bot = self.bot_handler.application.bot

        # 3. 알림 발송기
        self.alert_sender = AlertSender(bot, self.db_manager)
        self.bot_handler.set_alert_sender(self.alert_sender)

        # 4. KIS API
        if self.kis_config.validate():
            await self._init_kis_api()
        else:
            logger.warning(
                "KIS API 키 미설정 - 봇만 실행됩니다.\n"
                "  .env 파일에 KIS_APP_KEY, KIS_APP_SECRET 을 설정하세요."
            )

        logger.info("초기화 완료!")

    async def _init_kis_api(self):
        """한국투자증권 API 초기화"""
        try:
            self.kis_client = KISAPIClient(self.kis_config)
            approval_key = self.kis_client.get_approval_key()

            self.ws_client = KISWebSocketClient(
                self.kis_config.WEBSOCKET_URL, approval_key
            )
            self.ws_client.add_callback(self._on_realtime_data)

            logger.info("KIS API 초기화 완료")
        except Exception as e:
            logger.error(f"KIS API 초기화 실패: {e}")
            logger.warning("KIS API 없이 봇만 실행합니다.")
            self.kis_client = None
            self.ws_client = None

    async def _on_realtime_data(self, data: RealtimeData):
        """
        WebSocket 실시간 체결 데이터 수신

        1) PriceTracker에 가격 기록
        2) 3분 변동률 계산
        3) 임계값 초과 시 알림 브로드캐스트
        """
        # 가격 추적 & 변동률 계산
        change_3m, change_from_open = self.price_tracker.update(
            stock_code=data.stock_code,
            price=data.current_price,
            open_price=data.open_price
        )

        # 3분 데이터가 아직 부족하면 스킵
        if change_3m is None:
            return

        stock_name = get_stock_name(data.stock_code) or data.stock_code

        logger.debug(
            f"[{data.stock_code}] {stock_name} "
            f"{data.current_price:,}원 | "
            f"3분:{change_3m:+.2f}% | "
            f"시가대비:{change_from_open:+.2f}%" if change_from_open else ""
        )

        # 알림 발송 (3분 변동률 기준)
        try:
            await self.alert_sender.broadcast_stock_alert(
                stock_code=data.stock_code,
                stock_name=stock_name,
                current_price=data.current_price,
                change_rate_3m=change_3m,
                change_from_open=change_from_open,
                open_price=data.open_price,
            )
        except Exception as e:
            logger.error(f"알림 발송 오류 [{data.stock_code}]: {e}")

    async def _on_stock_added(self, stock_code: str):
        if self.ws_client:
            await self.ws_client.subscribe(stock_code)

    async def _on_stock_removed(self, stock_code: str):
        if not self.ws_client:
            return
        watchers = await self.db_manager.get_all_users_watching_stock(stock_code)
        if not watchers:
            await self.ws_client.unsubscribe(stock_code)
            self.price_tracker.clear(stock_code)

    async def _subscribe_existing_stocks(self):
        if not self.ws_client:
            return
        stocks = await self.db_manager.get_all_watched_stocks()
        if stocks:
            logger.info(f"기존 관심종목 {len(stocks)}개 구독: {stocks}")
            for code in stocks:
                await self.ws_client.subscribe(code)
        else:
            logger.info("관심종목 없음 - 유저가 /add 로 추가하면 자동 구독됩니다.")

    async def run(self):
        try:
            await self.initialize()

            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._stop_event.set)

            # 텔레그램 봇 시작
            logger.info("텔레그램 봇 polling 시작...")
            await self.bot_handler.application.start()
            await self.bot_handler.application.updater.start_polling(
                drop_pending_updates=True
            )
            await self.bot_handler._set_bot_commands(self.bot_handler.application)

            # WebSocket 시작
            if self.ws_client:
                logger.info("KIS WebSocket 연결 시작...")
                await self.ws_client.start()
                await self._subscribe_existing_stocks()

            logger.info("=" * 55)
            logger.info("  한국 주식 급등/급락 알림봇이 실행 중입니다!")
            logger.info("  텔레그램에서 봇을 찾아 /start 를 입력하세요.")
            logger.info("  알림 조건: 3분 내 급변동 감지")
            if self.ws_client:
                logger.info("  실시간 WebSocket 연결: 활성")
            else:
                logger.info("  실시간 WebSocket 연결: 비활성 (KIS API 키 필요)")
            logger.info("=" * 55)

            await self._stop_event.wait()

        except Exception as e:
            logger.error(f"봇 실행 오류: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        logger.info("종료 중...")

        if self.ws_client:
            await self.ws_client.stop()
        if self.kis_client:
            self.kis_client.close()
        if self.bot_handler:
            try:
                await self.bot_handler.application.updater.stop()
                await self.bot_handler.application.stop()
                await self.bot_handler.application.shutdown()
            except Exception as e:
                logger.error(f"봇 종료 오류: {e}")

        logger.info("종료 완료")


def main():
    if not BOT_TOKEN:
        print("=" * 55)
        print("  오류: TELEGRAM_BOT_TOKEN이 설정되지 않았습니다!")
        print()
        print("  설정 방법:")
        print("    1. cp .env.example .env")
        print("    2. .env 파일 편집하여 토큰 입력")
        print("=" * 55)
        sys.exit(1)

    bot = KoreaStockAlertBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중지됨")


if __name__ == "__main__":
    main()
