"""
한국투자증권 API 통합 관리 클래스
"""
import asyncio
import threading
from typing import List, Callable, Dict, Any, Optional
from datetime import datetime, timedelta

from .client import KISAPIClient, StockInfo
from .websocket_client import KISWebSocketClient, RealtimeData
from .config import KISConfig
from .exceptions import KISAPIError
from ..utils.logger import setup_logger
from ..utils.validators import validate_stock_codes
from ..utils.formatters import format_realtime_alert

logger = setup_logger(__name__)

class KISManager:
    """한국투자증권 API 통합 관리자"""
    
    def __init__(self, config: Optional[KISConfig] = None):
        self.config = config or KISConfig()
        self.rest_client = KISAPIClient(self.config)
        self.ws_client = None
        
        # 감시 설정
        self.monitored_stocks = {}  # {stock_code: {"last_price": int, "callbacks": [callable]}}
        self.alert_thresholds = {
            "surge": 5.0,   # 급등 기준 (%)
            "plunge": -5.0  # 급락 기준 (%)
        }
        
        # 모니터링 스레드
        self.monitor_thread = None
        self.is_monitoring = False
        
        logger.info("KIS Manager 초기화 완료")
    
    def initialize_websocket(self):
        """WebSocket 클라이언트 초기화"""
        try:
            if not self.ws_client:
                access_token = self.rest_client.get_access_token()
                self.ws_client = KISWebSocketClient(self.config, access_token)
                self.ws_client.connect()
                logger.info("WebSocket 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"WebSocket 초기화 실패: {e}")
            raise KISAPIError(f"WebSocket 초기화 실패: {e}")
    
    def get_stock_info(self, stock_code: str) -> StockInfo:
        """종목 정보 조회"""
        return self.rest_client.get_stock_info(stock_code)
    
    def get_current_price(self, stock_code: str) -> int:
        """현재가 조회"""
        return self.rest_client.get_current_price(stock_code)
    
    def get_multiple_stocks_info(self, stock_codes: List[str]) -> List[StockInfo]:
        """여러 종목 정보 일괄 조회"""
        valid_codes = validate_stock_codes(stock_codes)
        if not valid_codes:
            raise KISAPIError("유효한 종목코드가 없습니다")
        
        return self.rest_client.get_multiple_stocks_info(valid_codes)
    
    def subscribe_realtime(self, stock_codes: List[str], 
                          callback: Callable[[RealtimeData], None] = None):
        """실시간 데이터 구독"""
        valid_codes = validate_stock_codes(stock_codes)
        if not valid_codes:
            raise KISAPIError("유효한 종목코드가 없습니다")
        
        # WebSocket 클라이언트 초기화
        if not self.ws_client:
            self.initialize_websocket()
        
        # 기본 콜백 함수
        def default_callback(data: RealtimeData):
            self._handle_realtime_data(data)
        
        # 구독 실행
        callback_func = callback or default_callback
        self.ws_client.subscribe_realtime(valid_codes, callback_func)
        
        # 모니터링 대상에 추가
        for code in valid_codes:
            if code not in self.monitored_stocks:
                self.monitored_stocks[code] = {
                    "last_price": 0,
                    "callbacks": []
                }
        
        logger.info(f"실시간 구독 완료: {valid_codes}")
    
    def add_alert_callback(self, stock_code: str, callback: Callable[[str, RealtimeData], None]):
        """알림 콜백 추가"""
        if stock_code in self.monitored_stocks:
            self.monitored_stocks[stock_code]["callbacks"].append(callback)
        else:
            logger.warning(f"모니터링 중이지 않은 종목: {stock_code}")
    
    def set_alert_thresholds(self, surge_threshold: float = 5.0, 
                           plunge_threshold: float = -5.0):
        """알림 임계값 설정"""
        self.alert_thresholds["surge"] = surge_threshold
        self.alert_thresholds["plunge"] = plunge_threshold
        logger.info(f"알림 임계값 설정: 급등 {surge_threshold}%, 급락 {plunge_threshold}%")
    
    def _handle_realtime_data(self, data: RealtimeData):
        """실시간 데이터 처리"""
        stock_code = data.stock_code
        
        if stock_code in self.monitored_stocks:
            stock_info = self.monitored_stocks[stock_code]
            last_price = stock_info["last_price"]
            
            # 가격 변동률 계산
            if last_price > 0:
                change_rate = self.rest_client.calculate_change_rate(
                    data.current_price, last_price
                )
                
                # 급등/급락 감지
                alert_type = None
                if change_rate >= self.alert_thresholds["surge"]:
                    alert_type = "급등"
                elif change_rate <= self.alert_thresholds["plunge"]:
                    alert_type = "급락"
                
                # 알림 콜백 실행
                if alert_type:
                    for callback in stock_info["callbacks"]:
                        try:
                            callback(alert_type, data)
                        except Exception as e:
                            logger.error(f"알림 콜백 실행 오류: {e}")
            
            # 마지막 가격 업데이트
            stock_info["last_price"] = data.current_price
    
    def start_price_monitoring(self, check_interval: int = 30):
        """가격 모니터링 시작 (REST API 기반)"""
        if self.is_monitoring:
            logger.warning("이미 모니터링이 실행 중입니다")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._price_monitor_worker,
            args=(check_interval,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info(f"가격 모니터링 시작 (간격: {check_interval}초)")
    
    def _price_monitor_worker(self, check_interval: int):
        """가격 모니터링 워커"""
        while self.is_monitoring:
            try:
                for stock_code in list(self.monitored_stocks.keys()):
                    if not self.is_monitoring:
                        break
                    
                    try:
                        stock_info = self.get_stock_info(stock_code)
                        
                        # 실시간 데이터로 변환
                        realtime_data = RealtimeData(
                            stock_code=stock_info.code,
                            current_price=stock_info.current_price,
                            change_rate=stock_info.change_rate,
                            change_amount=stock_info.change_amount,
                            trading_volume=stock_info.trading_volume,
                            bid_price=0,  # REST API에서는 호가 정보 없음
                            ask_price=0,
                            timestamp=datetime.now()
                        )
                        
                        self._handle_realtime_data(realtime_data)
                        
                    except Exception as e:
                        logger.error(f"종목 모니터링 오류 [{stock_code}]: {e}")
                
                # 대기
                for _ in range(check_interval):
                    if not self.is_monitoring:
                        break
                    import time
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"모니터링 워커 오류: {e}")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("가격 모니터링 중지")
    
    def add_stock_to_monitor(self, stock_code: str, 
                           callback: Callable[[str, RealtimeData], None] = None):
        """모니터링 종목 추가"""
        if not validate_stock_codes([stock_code]):
            raise KISAPIError(f"유효하지 않은 종목코드: {stock_code}")
        
        if stock_code not in self.monitored_stocks:
            self.monitored_stocks[stock_code] = {
                "last_price": 0,
                "callbacks": []
            }
        
        if callback:
            self.monitored_stocks[stock_code]["callbacks"].append(callback)
        
        logger.info(f"모니터링 종목 추가: {stock_code}")
    
    def remove_stock_from_monitor(self, stock_code: str):
        """모니터링 종목 제거"""
        if stock_code in self.monitored_stocks:
            del self.monitored_stocks[stock_code]
            
            # WebSocket 구독 해제
            if self.ws_client:
                self.ws_client.unsubscribe_stock(stock_code)
            
            logger.info(f"모니터링 종목 제거: {stock_code}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 조회"""
        return {
            "is_monitoring": self.is_monitoring,
            "monitored_stocks": list(self.monitored_stocks.keys()),
            "websocket_connected": self.ws_client.is_connected if self.ws_client else False,
            "alert_thresholds": self.alert_thresholds
        }
    
    def close(self):
        """모든 연결 종료"""
        self.stop_monitoring()
        
        if self.ws_client:
            self.ws_client.disconnect()
        
        if self.rest_client:
            self.rest_client.close()
        
        logger.info("KIS Manager 종료 완료")