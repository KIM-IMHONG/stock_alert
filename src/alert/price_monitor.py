"""
실시간 가격 모니터링 시스템

주식의 실시간 가격을 추적하고 변동률을 계산합니다.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading


class PriceData:
    """가격 데이터를 저장하는 클래스"""
    
    def __init__(self, symbol: str, price: float, volume: int = 0, timestamp: float = None):
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.timestamp = timestamp or time.time()
        
    def __repr__(self):
        return f"PriceData(symbol={self.symbol}, price={self.price}, volume={self.volume})"


class PriceMonitor:
    """실시간 가격 모니터링 클래스"""
    
    def __init__(self, max_history_minutes: int = 30):
        self.logger = logging.getLogger(__name__)
        self.max_history_minutes = max_history_minutes
        
        # 종목별 가격 히스토리 (deque로 메모리 효율성 확보)
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 현재 가격 저장
        self._current_prices: Dict[str, PriceData] = {}
        
        # 스레드 안전성을 위한 락
        self._lock = threading.RLock()
        
        # 감시 중인 종목 리스트
        self._monitored_symbols: set = set()
        
        self.logger.info("PriceMonitor 초기화 완료")

    def add_symbol(self, symbol: str) -> None:
        """모니터링할 종목 추가"""
        with self._lock:
            self._monitored_symbols.add(symbol)
            self.logger.info(f"모니터링 종목 추가: {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        """모니터링 종목 제거"""
        with self._lock:
            self._monitored_symbols.discard(symbol)
            if symbol in self._current_prices:
                del self._current_prices[symbol]
            if symbol in self._price_history:
                del self._price_history[symbol]
            self.logger.info(f"모니터링 종목 제거: {symbol}")

    def update_price(self, symbol: str, price: float, volume: int = 0) -> None:
        """가격 업데이트"""
        if symbol not in self._monitored_symbols:
            return
            
        price_data = PriceData(symbol, price, volume)
        
        with self._lock:
            # 현재 가격 업데이트
            self._current_prices[symbol] = price_data
            
            # 히스토리에 추가
            self._price_history[symbol].append(price_data)
            
            # 오래된 데이터 정리
            self._cleanup_old_data(symbol)
            
        self.logger.debug(f"가격 업데이트: {symbol} = {price:,.0f}원 (거래량: {volume:,})")

    def _cleanup_old_data(self, symbol: str) -> None:
        """오래된 가격 데이터 정리"""
        if symbol not in self._price_history:
            return
            
        cutoff_time = time.time() - (self.max_history_minutes * 60)
        history = self._price_history[symbol]
        
        # 오래된 데이터 제거
        while history and history[0].timestamp < cutoff_time:
            history.popleft()

    def get_current_price(self, symbol: str) -> Optional[PriceData]:
        """현재 가격 조회"""
        with self._lock:
            return self._current_prices.get(symbol)

    def get_price_history(self, symbol: str, minutes: int = 5) -> List[PriceData]:
        """지정된 시간 동안의 가격 히스토리 조회"""
        with self._lock:
            if symbol not in self._price_history:
                return []
                
            cutoff_time = time.time() - (minutes * 60)
            return [
                price_data for price_data in self._price_history[symbol]
                if price_data.timestamp >= cutoff_time
            ]

    def calculate_price_change_rate(self, symbol: str, minutes: int = 5) -> Optional[float]:
        """지정된 시간 동안의 가격 변동률 계산 (백분율)"""
        history = self.get_price_history(symbol, minutes)
        
        if len(history) < 2:
            return None
            
        oldest_price = history[0].price
        current_price = history[-1].price
        
        if oldest_price <= 0:
            return None
            
        change_rate = ((current_price - oldest_price) / oldest_price) * 100
        return round(change_rate, 2)

    def calculate_volume_change_rate(self, symbol: str, minutes: int = 30) -> Optional[float]:
        """거래량 변동률 계산 (평균 대비)"""
        history = self.get_price_history(symbol, minutes)
        
        if len(history) < 10:  # 최소 10개 데이터 필요
            return None
            
        # 최근 거래량 평균 (최근 5분)
        recent_history = [h for h in history if h.timestamp >= time.time() - 300]
        if not recent_history:
            return None
            
        recent_avg_volume = sum(h.volume for h in recent_history) / len(recent_history)
        
        # 전체 기간 평균 거래량
        total_avg_volume = sum(h.volume for h in history) / len(history)
        
        if total_avg_volume <= 0:
            return None
            
        volume_change_rate = (recent_avg_volume / total_avg_volume) * 100
        return round(volume_change_rate, 2)

    def get_monitored_symbols(self) -> List[str]:
        """모니터링 중인 종목 리스트 반환"""
        with self._lock:
            return list(self._monitored_symbols)

    def get_statistics(self, symbol: str) -> Dict[str, Any]:
        """종목 통계 정보 반환"""
        with self._lock:
            current_price = self.get_current_price(symbol)
            if not current_price:
                return {}
                
            history_5m = self.get_price_history(symbol, 5)
            history_30m = self.get_price_history(symbol, 30)
            
            stats = {
                'symbol': symbol,
                'current_price': current_price.price,
                'current_volume': current_price.volume,
                'timestamp': current_price.timestamp,
                'price_change_5m': self.calculate_price_change_rate(symbol, 5),
                'price_change_30m': self.calculate_price_change_rate(symbol, 30),
                'volume_change_rate': self.calculate_volume_change_rate(symbol, 30),
                'data_points_5m': len(history_5m),
                'data_points_30m': len(history_30m)
            }
            
            return stats

    def clear_data(self, symbol: str = None) -> None:
        """데이터 정리 (특정 종목 또는 전체)"""
        with self._lock:
            if symbol:
                if symbol in self._current_prices:
                    del self._current_prices[symbol]
                if symbol in self._price_history:
                    del self._price_history[symbol]
                self.logger.info(f"종목 데이터 정리: {symbol}")
            else:
                self._current_prices.clear()
                self._price_history.clear()
                self.logger.info("모든 가격 데이터 정리")

    def __len__(self) -> int:
        """모니터링 중인 종목 수 반환"""
        return len(self._monitored_symbols)

    def __contains__(self, symbol: str) -> bool:
        """종목이 모니터링 중인지 확인"""
        return symbol in self._monitored_symbols