"""
한국투자증권 WebSocket 실시간 데이터 클라이언트
"""
import json
import time
import threading
import websocket
import logging
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .config import KISConfig
from .exceptions import KISConnectionError, KISDataError

logger = logging.getLogger(__name__)

@dataclass
class RealtimeData:
    """실시간 데이터 구조"""
    stock_code: str
    current_price: int
    change_rate: float
    change_amount: int
    trading_volume: int
    bid_price: int  # 매수호가
    ask_price: int  # 매도호가
    timestamp: datetime

class KISWebSocketClient:
    """한국투자증권 WebSocket 실시간 데이터 클라이언트"""
    
    def __init__(self, config: KISConfig, access_token: str):
        self.config = config
        self.access_token = access_token
        self.ws = None
        self.is_connected = False
        self.subscribed_stocks = set()
        self.callbacks = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        
        # 데이터 파싱용 필드 매핑
        self.field_mapping = {
            'MKSC_SHRN_ISCD': 'stock_code',      # 종목코드
            'STCK_PRPR': 'current_price',        # 현재가
            'PRDY_VRSS_SIGN': 'sign',            # 전일대비부호
            'PRDY_VRSS': 'change_amount',        # 전일대비
            'PRDY_CTRT': 'change_rate',          # 전일대비율
            'ACML_VOL': 'trading_volume',        # 누적거래량
            'STCK_BIDP': 'bid_price',            # 매수호가
            'STCK_ASKP': 'ask_price'             # 매도호가
        }
    
    def connect(self):
        """WebSocket 연결"""
        try:
            # WebSocket 연결
            ws_url = f"{self.config.WEBSOCKET_URL}"
            self.ws = websocket.WebSocketApp(
                ws_url,
                header={
                    "authorization": f"Bearer {self.access_token}",
                    "appkey": self.config.app_key,
                    "secretkey": self.config.app_secret
                },
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 별도 스레드에서 연결 실행
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # 연결 대기
            timeout = 10
            start_time = time.time()
            while not self.is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.is_connected:
                raise KISConnectionError("WebSocket 연결 타임아웃")
            
            logger.info("WebSocket 연결 성공")
            self.reconnect_attempts = 0
            
        except Exception as e:
            logger.error(f"WebSocket 연결 실패: {e}")
            raise KISConnectionError(f"WebSocket 연결 실패: {e}")
    
    def _on_open(self, ws):
        """연결 성공시 호출"""
        self.is_connected = True
        logger.info("WebSocket 연결 성공")
        
        # 기존 구독 종목들 재구독
        for stock_code in self.subscribed_stocks.copy():
            self._subscribe_stock(stock_code)
    
    def _on_message(self, ws, message):
        """메시지 수신시 호출"""
        try:
            # 메시지 파싱
            data = self._parse_message(message)
            if data:
                stock_code = data.stock_code
                
                # 콜백 실행
                if stock_code in self.callbacks:
                    for callback in self.callbacks[stock_code]:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"콜백 실행 오류 [{stock_code}]: {e}")
                
        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
    
    def _on_error(self, ws, error):
        """오류 발생시 호출"""
        logger.error(f"WebSocket 오류: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """연결 종료시 호출"""
        self.is_connected = False
        logger.warning(f"WebSocket 연결 종료: {close_status_code}, {close_msg}")
        
        # 자동 재연결 시도
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"재연결 시도 {self.reconnect_attempts}/{self.max_reconnect_attempts}")
            time.sleep(self.reconnect_delay)
            try:
                self.connect()
            except Exception as e:
                logger.error(f"재연결 실패: {e}")
    
    def _parse_message(self, message: str) -> Optional[RealtimeData]:
        """수신된 메시지 파싱"""
        try:
            # KIS WebSocket 메시지 형식에 따라 파싱
            # 실제 형식은 API 문서 참조 필요
            if isinstance(message, str):
                # 파이프(|) 구분자로 되어 있는 경우가 많음
                fields = message.split('|')
                if len(fields) < 10:
                    return None
                
                # 기본적인 파싱 (실제 필드 위치는 API 문서 확인 필요)
                try:
                    stock_code = fields[0]
                    current_price = int(fields[2]) if fields[2].isdigit() else 0
                    change_amount = int(fields[4]) if fields[4] else 0
                    change_rate = float(fields[5]) if fields[5] else 0.0
                    trading_volume = int(fields[6]) if fields[6].isdigit() else 0
                    bid_price = int(fields[7]) if fields[7].isdigit() else 0
                    ask_price = int(fields[8]) if fields[8].isdigit() else 0
                    
                    return RealtimeData(
                        stock_code=stock_code,
                        current_price=current_price,
                        change_rate=change_rate,
                        change_amount=change_amount,
                        trading_volume=trading_volume,
                        bid_price=bid_price,
                        ask_price=ask_price,
                        timestamp=datetime.now()
                    )
                    
                except (ValueError, IndexError) as e:
                    logger.debug(f"메시지 파싱 실패: {e}")
                    return None
            
        except Exception as e:
            logger.error(f"메시지 파싱 오류: {e}")
        
        return None
    
    def subscribe_realtime(self, stock_codes: List[str], callback: Callable[[RealtimeData], None]):
        """실시간 데이터 구독"""
        for stock_code in stock_codes:
            self.subscribed_stocks.add(stock_code)
            
            if stock_code not in self.callbacks:
                self.callbacks[stock_code] = []
            self.callbacks[stock_code].append(callback)
            
            if self.is_connected:
                self._subscribe_stock(stock_code)
        
        logger.info(f"실시간 구독 등록: {stock_codes}")
    
    def _subscribe_stock(self, stock_code: str):
        """개별 종목 구독"""
        if not self.is_connected:
            logger.warning("WebSocket이 연결되지 않음")
            return
        
        try:
            # 구독 메시지 전송
            subscribe_msg = {
                "header": {
                    "approval_key": self.access_token,
                    "custtype": "P",
                    "tr_type": "1",  # 등록
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",  # 주식 현재가 실시간
                        "tr_key": stock_code
                    }
                }
            }
            
            self.ws.send(json.dumps(subscribe_msg))
            logger.debug(f"종목 구독 요청: {stock_code}")
            
        except Exception as e:
            logger.error(f"종목 구독 실패 [{stock_code}]: {e}")
    
    def unsubscribe_stock(self, stock_code: str):
        """종목 구독 해제"""
        if stock_code in self.subscribed_stocks:
            self.subscribed_stocks.remove(stock_code)
        
        if stock_code in self.callbacks:
            del self.callbacks[stock_code]
        
        if self.is_connected:
            try:
                # 구독 해제 메시지
                unsubscribe_msg = {
                    "header": {
                        "approval_key": self.access_token,
                        "custtype": "P",
                        "tr_type": "2",  # 해제
                        "content-type": "utf-8"
                    },
                    "body": {
                        "input": {
                            "tr_id": "H0STCNT0",
                            "tr_key": stock_code
                        }
                    }
                }
                
                self.ws.send(json.dumps(unsubscribe_msg))
                logger.info(f"종목 구독 해제: {stock_code}")
                
            except Exception as e:
                logger.error(f"종목 구독 해제 실패 [{stock_code}]: {e}")
    
    def disconnect(self):
        """WebSocket 연결 종료"""
        self.is_connected = False
        if self.ws:
            self.ws.close()
        logger.info("WebSocket 연결 종료")