"""
한국투자증권 WebSocket 실시간 데이터 클라이언트 (Async)
"""
import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime

import websockets

from .config import KISConfig
from .exceptions import KISConnectionError

logger = logging.getLogger(__name__)


@dataclass
class RealtimeData:
    """실시간 체결 데이터"""
    stock_code: str
    current_price: int
    change_rate: float
    change_amount: int
    trading_volume: int
    accumulated_volume: int
    timestamp: datetime


class KISWebSocketClient:
    """한국투자증권 WebSocket 실시간 데이터 클라이언트 (Async)"""

    # H0STCNT0 필드 인덱스 (주식체결)
    F_STOCK_CODE = 0       # 종목코드
    F_TIME = 1             # 체결시간
    F_CURRENT_PRICE = 2    # 현재가
    F_SIGN = 3             # 전일대비부호 (1:상한,2:상승,3:보합,4:하한,5:하락)
    F_CHANGE_AMOUNT = 4    # 전일대비
    F_CHANGE_RATE = 5      # 전일대비율
    F_VOLUME = 12          # 체결거래량
    F_ACC_VOLUME = 13      # 누적거래량

    def __init__(self, ws_url: str, approval_key: str):
        self.ws_url = ws_url
        self.approval_key = approval_key
        self.ws = None
        self.is_connected = False
        self.subscribed_stocks: Set[str] = set()
        self._callbacks: List[Callable] = []
        self._reconnect_delay = 5
        self._max_reconnects = 50
        self._should_run = False
        self._connect_task: Optional[asyncio.Task] = None

    def add_callback(self, callback: Callable):
        """실시간 데이터 수신 콜백 등록"""
        self._callbacks.append(callback)

    async def start(self):
        """WebSocket 연결 시작 (백그라운드 태스크)"""
        self._should_run = True
        self._connect_task = asyncio.create_task(self._connection_loop())
        logger.info("WebSocket 클라이언트 시작")

    async def _connection_loop(self):
        """연결 루프 (자동 재연결 포함)"""
        reconnect_count = 0

        while self._should_run and reconnect_count < self._max_reconnects:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self.ws = ws
                    self.is_connected = True
                    reconnect_count = 0
                    logger.info("KIS WebSocket 연결 성공")

                    # 기존 구독 종목 재구독
                    for code in list(self.subscribed_stocks):
                        await self._send_subscribe(code)

                    # 메시지 수신 루프
                    async for message in ws:
                        if not self._should_run:
                            break
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket 연결 끊김: {e}")
            except asyncio.CancelledError:
                logger.info("WebSocket 태스크 취소됨")
                break
            except Exception as e:
                logger.error(f"WebSocket 오류: {e}")
            finally:
                self.is_connected = False

            if self._should_run:
                reconnect_count += 1
                logger.info(f"재연결 시도 {reconnect_count}/{self._max_reconnects} "
                           f"({self._reconnect_delay}초 후)")
                await asyncio.sleep(self._reconnect_delay)

        if reconnect_count >= self._max_reconnects:
            logger.error("최대 재연결 횟수 초과")

    async def subscribe(self, stock_code: str):
        """종목 실시간 구독"""
        self.subscribed_stocks.add(stock_code)
        if self.is_connected:
            await self._send_subscribe(stock_code)
        logger.info(f"종목 구독 등록: {stock_code}")

    async def unsubscribe(self, stock_code: str):
        """종목 구독 해제"""
        self.subscribed_stocks.discard(stock_code)
        if self.is_connected:
            await self._send_unsubscribe(stock_code)
        logger.info(f"종목 구독 해제: {stock_code}")

    async def _send_subscribe(self, stock_code: str):
        """구독 요청 전송"""
        msg = json.dumps({
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0",
                    "tr_key": stock_code
                }
            }
        })
        await self.ws.send(msg)
        logger.debug(f"구독 요청 전송: {stock_code}")

    async def _send_unsubscribe(self, stock_code: str):
        """구독 해제 요청 전송"""
        msg = json.dumps({
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "2",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0",
                    "tr_key": stock_code
                }
            }
        })
        await self.ws.send(msg)
        logger.debug(f"구독 해제 전송: {stock_code}")

    async def _handle_message(self, message: str):
        """수신 메시지 처리"""
        # JSON 응답 (구독 확인 등)
        if message.startswith('{'):
            try:
                data = json.loads(message)
                header = data.get("header", {})
                tr_id = header.get("tr_id", "")
                msg_cd = header.get("msg_cd", "")
                msg1 = data.get("body", {}).get("msg1", "")
                logger.info(f"WebSocket 응답: tr_id={tr_id}, msg_cd={msg_cd}, msg={msg1}")
            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패: {message[:100]}")
            return

        # 실시간 데이터 (파이프 구분)
        try:
            parts = message.split('|')
            if len(parts) < 4:
                return

            # parts[0]: 암호화여부 (0:평문, 1:암호화)
            # parts[1]: tr_id
            # parts[2]: 데이터 건수
            # parts[3]: 데이터 (^ 구분)
            encrypted = parts[0]
            tr_id = parts[1]
            data_count = int(parts[2])

            if encrypted == "1":
                logger.debug("암호화 데이터 수신 (복호화 미지원)")
                return

            if tr_id == "H0STCNT0":
                await self._parse_stock_data(parts[3], data_count)

        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")

    async def _parse_stock_data(self, data_str: str, data_count: int):
        """주식 체결 데이터 파싱"""
        fields = data_str.split('^')

        # H0STCNT0 필드 수 (약 46개)
        fields_per_record = len(fields) // data_count if data_count > 0 else len(fields)

        for i in range(data_count):
            offset = i * fields_per_record
            try:
                if offset + self.F_ACC_VOLUME >= len(fields):
                    break

                # 전일대비부호에 따라 가격 부호 결정
                sign = fields[offset + self.F_SIGN]
                price = int(fields[offset + self.F_CURRENT_PRICE])
                change_amount = int(fields[offset + self.F_CHANGE_AMOUNT])

                # 하락(4,5)일 때 변동금액은 음수
                if sign in ('4', '5'):
                    change_amount = -abs(change_amount)

                change_rate = float(fields[offset + self.F_CHANGE_RATE])
                if sign in ('4', '5'):
                    change_rate = -abs(change_rate)

                realtime_data = RealtimeData(
                    stock_code=fields[offset + self.F_STOCK_CODE],
                    current_price=price,
                    change_rate=change_rate,
                    change_amount=change_amount,
                    trading_volume=int(fields[offset + self.F_VOLUME]),
                    accumulated_volume=int(fields[offset + self.F_ACC_VOLUME]),
                    timestamp=datetime.now()
                )

                # 콜백 실행
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(realtime_data)
                        else:
                            callback(realtime_data)
                    except Exception as e:
                        logger.error(f"콜백 실행 오류 [{realtime_data.stock_code}]: {e}")

            except (ValueError, IndexError) as e:
                logger.debug(f"데이터 파싱 실패 (record {i}): {e}")

    async def stop(self):
        """WebSocket 연결 종료"""
        self._should_run = False
        if self._connect_task and not self._connect_task.done():
            self._connect_task.cancel()
            try:
                await self._connect_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        self.is_connected = False
        logger.info("WebSocket 클라이언트 종료")
