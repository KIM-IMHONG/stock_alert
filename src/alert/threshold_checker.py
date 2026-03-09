"""
임계값 검사 시스템

급등/급락 조건을 체크하고 알림 발생 여부를 판단합니다.
"""

import logging
import threading
from typing import Dict, List, Optional, NamedTuple
from datetime import datetime, time as datetime_time, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

# 한국 시간대
KST = timezone(timedelta(hours=9))


class AlertType(Enum):
    """알림 유형"""
    SURGE = "급등"           # 급등
    PLUNGE = "급락"          # 급락
    VOLUME_SURGE = "거래량급증"  # 거래량 급증


@dataclass
class ThresholdConfig:
    """임계값 설정"""
    symbol: str
    surge_threshold: float = 5.0        # 급등 임계값 (%)
    plunge_threshold: float = -3.0      # 급락 임계값 (%)
    volume_threshold: float = 300.0     # 거래량 급증 임계값 (%)
    time_window: int = 5                # 시간 창 (분)
    enabled: bool = True                # 활성화 여부
    
    def __post_init__(self):
        # 급락 임계값이 양수로 입력된 경우 음수로 변환
        if self.plunge_threshold > 0:
            self.plunge_threshold = -self.plunge_threshold


class AlertCondition(NamedTuple):
    """알림 조건 결과"""
    alert_type: AlertType
    symbol: str
    current_value: float
    threshold: float
    message: str
    priority: int = 1  # 1: 높음, 2: 보통, 3: 낮음


class TradingTimeChecker:
    """거래 시간 체크"""
    
    def __init__(self):
        # 한국 주식시장 거래시간: 09:00~15:30 (점심시간 없이 연속 거래)
        self.market_open = datetime_time(9, 0)      # 09:00
        self.market_close = datetime_time(15, 30)   # 15:30

    def is_trading_hours(self, dt: datetime = None) -> bool:
        """거래시간 여부 확인 (KST 기준)"""
        if dt is None:
            dt = datetime.now(KST)

        current_time = dt.time()
        weekday = dt.weekday()  # 0=월요일, 6=일요일

        # 주말 체크
        if weekday >= 5:
            return False

        # 거래시간 체크
        if not (self.market_open <= current_time <= self.market_close):
            return False

        return True
        
    def get_next_trading_time(self, dt: datetime = None) -> datetime:
        """다음 거래시간 반환"""
        if dt is None:
            dt = datetime.now()
            
        # 간단한 구현: 다음 평일 09:00
        next_day = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        
        while next_day.weekday() >= 5 or next_day <= dt:
            next_day = next_day.replace(day=next_day.day + 1)
            
        return next_day


class ThresholdChecker:
    """임계값 검사 클래스"""
    
    def __init__(self, enable_trading_time_filter: bool = True):
        self.logger = logging.getLogger(__name__)
        self.enable_trading_time_filter = enable_trading_time_filter
        
        # 종목별 임계값 설정
        self._thresholds: Dict[str, ThresholdConfig] = {}
        
        # 거래시간 체커
        self._trading_time_checker = TradingTimeChecker()
        
        # 스레드 안전성을 위한 락
        self._lock = threading.RLock()
        
        self.logger.info("ThresholdChecker 초기화 완료")

    def set_threshold(self, symbol: str, **kwargs) -> None:
        """종목별 임계값 설정"""
        with self._lock:
            if symbol in self._thresholds:
                # 기존 설정 업데이트
                config = self._thresholds[symbol]
                for key, value in kwargs.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            else:
                # 새로운 설정 생성
                self._thresholds[symbol] = ThresholdConfig(symbol=symbol, **kwargs)
                
        self.logger.info(f"임계값 설정 업데이트: {symbol} - {kwargs}")

    def get_threshold(self, symbol: str) -> Optional[ThresholdConfig]:
        """종목 임계값 조회"""
        with self._lock:
            return self._thresholds.get(symbol)

    def remove_threshold(self, symbol: str) -> bool:
        """종목 임계값 제거"""
        with self._lock:
            if symbol in self._thresholds:
                del self._thresholds[symbol]
                self.logger.info(f"임계값 설정 제거: {symbol}")
                return True
            return False

    def check_price_surge(self, symbol: str, price_change_rate: float) -> Optional[AlertCondition]:
        """급등 조건 체크"""
        threshold_config = self.get_threshold(symbol)
        if not threshold_config or not threshold_config.enabled:
            return None
            
        if price_change_rate >= threshold_config.surge_threshold:
            message = f"{symbol} 급등 감지! {price_change_rate:+.2f}% (임계값: +{threshold_config.surge_threshold:.1f}%)"
            return AlertCondition(
                alert_type=AlertType.SURGE,
                symbol=symbol,
                current_value=price_change_rate,
                threshold=threshold_config.surge_threshold,
                message=message,
                priority=1
            )
        return None

    def check_price_plunge(self, symbol: str, price_change_rate: float) -> Optional[AlertCondition]:
        """급락 조건 체크"""
        threshold_config = self.get_threshold(symbol)
        if not threshold_config or not threshold_config.enabled:
            return None
            
        if price_change_rate <= threshold_config.plunge_threshold:
            message = f"{symbol} 급락 감지! {price_change_rate:+.2f}% (임계값: {threshold_config.plunge_threshold:+.1f}%)"
            return AlertCondition(
                alert_type=AlertType.PLUNGE,
                symbol=symbol,
                current_value=price_change_rate,
                threshold=threshold_config.plunge_threshold,
                message=message,
                priority=1
            )
        return None

    def check_volume_surge(self, symbol: str, volume_change_rate: float) -> Optional[AlertCondition]:
        """거래량 급증 조건 체크"""
        threshold_config = self.get_threshold(symbol)
        if not threshold_config or not threshold_config.enabled:
            return None
            
        if volume_change_rate >= threshold_config.volume_threshold:
            message = f"{symbol} 거래량 급증 감지! {volume_change_rate:.1f}% (임계값: {threshold_config.volume_threshold:.1f}%)"
            return AlertCondition(
                alert_type=AlertType.VOLUME_SURGE,
                symbol=symbol,
                current_value=volume_change_rate,
                threshold=threshold_config.volume_threshold,
                message=message,
                priority=2
            )
        return None

    def check_all_conditions(self, symbol: str, price_change_rate: float, 
                           volume_change_rate: Optional[float] = None) -> List[AlertCondition]:
        """모든 알림 조건 체크"""
        
        # 거래시간 필터링
        if self.enable_trading_time_filter and not self._trading_time_checker.is_trading_hours():
            return []
            
        conditions = []
        
        # 급등 체크
        surge_condition = self.check_price_surge(symbol, price_change_rate)
        if surge_condition:
            conditions.append(surge_condition)
            
        # 급락 체크
        plunge_condition = self.check_price_plunge(symbol, price_change_rate)
        if plunge_condition:
            conditions.append(plunge_condition)
            
        # 거래량 급증 체크 (데이터가 있을 때만)
        if volume_change_rate is not None:
            volume_condition = self.check_volume_surge(symbol, volume_change_rate)
            if volume_condition:
                conditions.append(volume_condition)
                
        return conditions

    def is_trading_hours(self) -> bool:
        """현재 거래시간 여부 확인"""
        return self._trading_time_checker.is_trading_hours()

    def get_all_thresholds(self) -> Dict[str, ThresholdConfig]:
        """모든 임계값 설정 반환"""
        with self._lock:
            return self._thresholds.copy()

    def enable_symbol(self, symbol: str) -> bool:
        """종목 알림 활성화"""
        with self._lock:
            if symbol in self._thresholds:
                self._thresholds[symbol].enabled = True
                self.logger.info(f"종목 알림 활성화: {symbol}")
                return True
            return False

    def disable_symbol(self, symbol: str) -> bool:
        """종목 알림 비활성화"""
        with self._lock:
            if symbol in self._thresholds:
                self._thresholds[symbol].enabled = False
                self.logger.info(f"종목 알림 비활성화: {symbol}")
                return True
            return False

    def set_default_thresholds(self, surge: float = 5.0, plunge: float = -3.0, 
                             volume: float = 300.0, time_window: int = 5) -> None:
        """기본 임계값 설정"""
        self.default_surge = surge
        self.default_plunge = plunge if plunge < 0 else -plunge
        self.default_volume = volume
        self.default_time_window = time_window
        
        self.logger.info(f"기본 임계값 설정: 급등{surge}%, 급락{plunge}%, 거래량{volume}%")

    def apply_default_threshold(self, symbol: str) -> None:
        """종목에 기본 임계값 적용"""
        if not hasattr(self, 'default_surge'):
            self.set_default_thresholds()
            
        self.set_threshold(
            symbol=symbol,
            surge_threshold=self.default_surge,
            plunge_threshold=self.default_plunge,
            volume_threshold=self.default_volume,
            time_window=self.default_time_window
        )

    def get_status_summary(self) -> Dict:
        """상태 요약 정보"""
        with self._lock:
            total_symbols = len(self._thresholds)
            enabled_symbols = sum(1 for config in self._thresholds.values() if config.enabled)
            
            return {
                'total_symbols': total_symbols,
                'enabled_symbols': enabled_symbols,
                'disabled_symbols': total_symbols - enabled_symbols,
                'trading_hours': self.is_trading_hours(),
                'trading_time_filter_enabled': self.enable_trading_time_filter
            }