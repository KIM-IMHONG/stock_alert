"""
급등/급락 알림 시스템 메인 클래스

모든 컴포넌트를 통합하여 실시간 모니터링 및 알림을 제공합니다.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime
from dataclasses import dataclass

from .price_monitor import PriceMonitor, PriceData
from .threshold_checker import ThresholdChecker, AlertCondition, ThresholdConfig
from .notification_controller import NotificationController, NotificationRecord


@dataclass
class SystemStatus:
    """시스템 상태"""
    is_running: bool
    monitored_symbols_count: int
    active_thresholds_count: int
    total_notifications_24h: int
    uptime_seconds: float
    last_update_time: Optional[float]
    error_count: int


class AlertSystem:
    """급등/급락 알림 시스템 메인 클래스"""
    
    def __init__(self, enable_trading_time_filter: bool = True, 
                 max_history_minutes: int = 30):
        """
        Args:
            enable_trading_time_filter: 거래시간 필터링 활성화 여부
            max_history_minutes: 가격 히스토리 보관 시간 (분)
        """
        self.logger = logging.getLogger(__name__)
        
        # 컴포넌트 초기화
        self.price_monitor = PriceMonitor(max_history_minutes=max_history_minutes)
        self.threshold_checker = ThresholdChecker(enable_trading_time_filter=enable_trading_time_filter)
        self.notification_controller = NotificationController()
        
        # 시스템 상태
        self._is_running = False
        self._start_time: Optional[float] = None
        self._last_update_time: Optional[float] = None
        self._error_count = 0
        
        # 모니터링 루프
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitor_interval = 1.0  # 1초 간격
        
        # 이벤트 핸들러들
        self._price_update_handlers: List[Callable] = []
        self._alert_handlers: List[Callable] = []
        
        # 스레드 안전성을 위한 락
        self._lock = threading.RLock()
        
        # 기본 알림 핸들러 등록
        self.notification_controller.add_notification_handler(self._default_notification_handler)
        
        self.logger.info("AlertSystem 초기화 완료")

    async def start(self) -> None:
        """시스템 시작"""
        if self._is_running:
            self.logger.warning("시스템이 이미 실행 중입니다")
            return
            
        self._is_running = True
        self._start_time = time.time()
        self._error_count = 0
        
        # 모니터링 루프 시작
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info("AlertSystem 시작됨")

    async def stop(self) -> None:
        """시스템 중지"""
        if not self._is_running:
            return
            
        self._is_running = False
        
        # 모니터링 태스크 중지
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        self.logger.info("AlertSystem 중지됨")

    def add_symbol(self, symbol: str, **threshold_kwargs) -> None:
        """모니터링 종목 추가"""
        with self._lock:
            # 가격 모니터에 추가
            self.price_monitor.add_symbol(symbol)
            
            # 임계값 설정
            if threshold_kwargs:
                self.threshold_checker.set_threshold(symbol, **threshold_kwargs)
            else:
                # 기본 임계값 적용
                self.threshold_checker.apply_default_threshold(symbol)
                
        self.logger.info(f"모니터링 종목 추가: {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        """모니터링 종목 제거"""
        with self._lock:
            self.price_monitor.remove_symbol(symbol)
            self.threshold_checker.remove_threshold(symbol)
            
        self.logger.info(f"모니터링 종목 제거: {symbol}")

    def update_price(self, symbol: str, price: float, volume: int = 0) -> None:
        """가격 업데이트"""
        try:
            # 가격 데이터 업데이트
            self.price_monitor.update_price(symbol, price, volume)
            self._last_update_time = time.time()
            
            # 가격 업데이트 이벤트 핸들러 호출
            for handler in self._price_update_handlers:
                try:
                    handler(symbol, price, volume)
                except Exception as e:
                    self.logger.error(f"가격 업데이트 핸들러 오류: {e}", exc_info=True)
                    
        except Exception as e:
            self._error_count += 1
            self.logger.error(f"가격 업데이트 오류: {symbol} - {e}", exc_info=True)

    async def _monitoring_loop(self) -> None:
        """모니터링 메인 루프"""
        self.logger.info("모니터링 루프 시작")
        
        while self._is_running:
            try:
                await self._check_all_symbols()
                await asyncio.sleep(self._monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                self.logger.error(f"모니터링 루프 오류: {e}", exc_info=True)
                await asyncio.sleep(self._monitor_interval)
                
        self.logger.info("모니터링 루프 종료")

    async def _check_all_symbols(self) -> None:
        """모든 종목 체크"""
        monitored_symbols = self.price_monitor.get_monitored_symbols()
        
        for symbol in monitored_symbols:
            try:
                await self._check_symbol_conditions(symbol)
            except Exception as e:
                self.logger.error(f"종목 체크 오류 {symbol}: {e}", exc_info=True)

    async def _check_symbol_conditions(self, symbol: str) -> None:
        """특정 종목의 알림 조건 체크"""
        # 통계 정보 가져오기
        stats = self.price_monitor.get_statistics(symbol)
        if not stats:
            return
            
        price_change_5m = stats.get('price_change_5m')
        volume_change_rate = stats.get('volume_change_rate')
        
        if price_change_5m is None:
            return  # 충분한 데이터가 없음
            
        # 임계값 조건 체크
        conditions = self.threshold_checker.check_all_conditions(
            symbol=symbol,
            price_change_rate=price_change_5m,
            volume_change_rate=volume_change_rate
        )
        
        # 조건에 맞는 알림 발송
        for condition in conditions:
            try:
                record = await self.notification_controller.send_notification(condition)
                
                # 알림 이벤트 핸들러 호출
                for handler in self._alert_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(condition, record)
                        else:
                            handler(condition, record)
                    except Exception as e:
                        self.logger.error(f"알림 핸들러 오류: {e}", exc_info=True)
                        
            except Exception as e:
                self.logger.error(f"알림 발송 오류: {e}", exc_info=True)

    def _default_notification_handler(self, record: NotificationRecord) -> None:
        """기본 알림 핸들러 (로깅)"""
        condition = record.alert_condition
        
        if record.status.value == "발송완료":
            self.logger.info(f"🚨 {condition.alert_type.value} 알림: {condition.message}")
        else:
            self.logger.debug(f"알림 처리: {condition.symbol} - {record.status.value}")

    def add_price_update_handler(self, handler: Callable[[str, float, int], None]) -> None:
        """가격 업데이트 이벤트 핸들러 추가"""
        if handler not in self._price_update_handlers:
            self._price_update_handlers.append(handler)

    def remove_price_update_handler(self, handler: Callable) -> bool:
        """가격 업데이트 이벤트 핸들러 제거"""
        if handler in self._price_update_handlers:
            self._price_update_handlers.remove(handler)
            return True
        return False

    def add_alert_handler(self, handler: Callable[[AlertCondition, NotificationRecord], None]) -> None:
        """알림 이벤트 핸들러 추가"""
        if handler not in self._alert_handlers:
            self._alert_handlers.append(handler)

    def remove_alert_handler(self, handler: Callable) -> bool:
        """알림 이벤트 핸들러 제거"""
        if handler in self._alert_handlers:
            self._alert_handlers.remove(handler)
            return True
        return False

    def set_monitor_interval(self, seconds: float) -> None:
        """모니터링 간격 설정"""
        self._monitor_interval = max(0.1, seconds)  # 최소 0.1초
        self.logger.info(f"모니터링 간격 설정: {seconds}초")

    def get_system_status(self) -> SystemStatus:
        """시스템 상태 조회"""
        with self._lock:
            uptime = time.time() - self._start_time if self._start_time else 0
            
            # 24시간 알림 통계
            notifications_24h = self.notification_controller.get_statistics(hours=24)
            total_notifications = notifications_24h.get('total_notifications', 0)
            
            return SystemStatus(
                is_running=self._is_running,
                monitored_symbols_count=len(self.price_monitor),
                active_thresholds_count=len(self.threshold_checker.get_all_thresholds()),
                total_notifications_24h=total_notifications,
                uptime_seconds=uptime,
                last_update_time=self._last_update_time,
                error_count=self._error_count
            )

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 상세 정보 조회"""
        stats = self.price_monitor.get_statistics(symbol)
        threshold_config = self.threshold_checker.get_threshold(symbol)
        
        if not stats and not threshold_config:
            return None
            
        info = {
            'symbol': symbol,
            'monitoring': symbol in self.price_monitor,
            'threshold_config': threshold_config,
            'price_stats': stats,
            'recent_notifications': self.notification_controller.get_notification_history(
                symbol=symbol, hours=24
            )
        }
        
        return info

    def get_all_symbols_info(self) -> Dict[str, Dict[str, Any]]:
        """모든 종목 정보 조회"""
        symbols = set()
        symbols.update(self.price_monitor.get_monitored_symbols())
        symbols.update(self.threshold_checker.get_all_thresholds().keys())
        
        return {symbol: self.get_symbol_info(symbol) for symbol in symbols}

    def reset_error_count(self) -> int:
        """오류 카운트 리셋"""
        with self._lock:
            old_count = self._error_count
            self._error_count = 0
            return old_count

    async def cleanup_old_data(self) -> None:
        """오래된 데이터 정리"""
        try:
            self.notification_controller.cleanup_old_data()
            self.logger.info("데이터 정리 완료")
        except Exception as e:
            self.logger.error(f"데이터 정리 오류: {e}", exc_info=True)

    def is_running(self) -> bool:
        """실행 상태 확인"""
        return self._is_running

    def is_trading_hours(self) -> bool:
        """현재 거래시간 여부 확인"""
        return self.threshold_checker.is_trading_hours()

    def enable_symbol_alerts(self, symbol: str) -> bool:
        """종목 알림 활성화"""
        return self.threshold_checker.enable_symbol(symbol)

    def disable_symbol_alerts(self, symbol: str) -> bool:
        """종목 알림 비활성화"""
        return self.threshold_checker.disable_symbol(symbol)

    def clear_symbol_cooldown(self, symbol: str, user_id: str = None) -> int:
        """특정 종목의 쿨다운 초기화"""
        return self.notification_controller.clear_cooldown(symbol=symbol, user_id=user_id)

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if self._is_running:
            # 비동기 stop을 동기적으로 실행
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 이미 실행 중인 루프에서는 task 생성
                    loop.create_task(self.stop())
                else:
                    loop.run_until_complete(self.stop())
            except Exception as e:
                self.logger.error(f"시스템 종료 오류: {e}")

    def __del__(self):
        """소멸자"""
        if hasattr(self, '_is_running') and self._is_running:
            self.logger.warning("AlertSystem이 정상적으로 종료되지 않았습니다")