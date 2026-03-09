"""
알림 제어 시스템

알림 발송을 제어하고 중복 방지, 히스토리 관리를 수행합니다.
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum

from .threshold_checker import AlertCondition, AlertType


class NotificationStatus(Enum):
    """알림 상태"""
    PENDING = "대기중"      # 대기 중
    SENT = "발송완료"       # 발송 완료  
    FAILED = "발송실패"     # 발송 실패
    COOLDOWN = "쿨다운"     # 쿨다운 중
    FILTERED = "필터됨"     # 필터로 제외


@dataclass
class NotificationRecord:
    """알림 기록"""
    id: str
    alert_condition: AlertCondition
    status: NotificationStatus
    timestamp: float
    user_id: Optional[str] = None
    channel: Optional[str] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def formatted_timestamp(self) -> str:
        """포맷된 시간 문자열"""
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class UserNotificationSettings:
    """사용자별 알림 설정"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.enabled = True
        self.enabled_alert_types: Set[AlertType] = {AlertType.SURGE, AlertType.PLUNGE}
        self.min_priority = 1  # 최소 우선순위 (1: 높음, 2: 보통, 3: 낮음)
        self.max_notifications_per_hour = 20
        self.cooldown_minutes = 10  # 동일 종목 쿨다운 시간
        
    def should_notify(self, alert_condition: AlertCondition) -> bool:
        """알림 발송 여부 판단"""
        if not self.enabled:
            return False
            
        if alert_condition.alert_type not in self.enabled_alert_types:
            return False
            
        if alert_condition.priority > self.min_priority:
            return False
            
        return True


class NotificationController:
    """알림 제어 클래스"""
    
    def __init__(self, max_history_hours: int = 24):
        self.logger = logging.getLogger(__name__)
        self.max_history_hours = max_history_hours
        
        # 알림 기록 저장 (최근 24시간)
        self._notification_history: deque = deque(maxlen=10000)
        
        # 종목별 마지막 알림 시간 (쿨다운 관리)
        self._last_notification_time: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # 사용자별 설정
        self._user_settings: Dict[str, UserNotificationSettings] = {}
        
        # 시간당 알림 카운트 (사용자별, 종목별)
        self._hourly_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._hourly_reset_time: Dict[str, float] = {}
        
        # 알림 발송 핸들러들
        self._notification_handlers: List[Callable] = []
        
        # 스레드 안전성을 위한 락
        self._lock = threading.RLock()
        
        # 백그라운드 정리 작업
        self._cleanup_task = None
        
        self.logger.info("NotificationController 초기화 완료")

    def add_notification_handler(self, handler: Callable[[NotificationRecord], None]) -> None:
        """알림 핸들러 추가"""
        with self._lock:
            if handler not in self._notification_handlers:
                self._notification_handlers.append(handler)
                self.logger.info("알림 핸들러 추가됨")

    def remove_notification_handler(self, handler: Callable) -> bool:
        """알림 핸들러 제거"""
        with self._lock:
            if handler in self._notification_handlers:
                self._notification_handlers.remove(handler)
                self.logger.info("알림 핸들러 제거됨")
                return True
            return False

    def get_user_settings(self, user_id: str) -> UserNotificationSettings:
        """사용자 설정 조회 (없으면 기본값으로 생성)"""
        with self._lock:
            if user_id not in self._user_settings:
                self._user_settings[user_id] = UserNotificationSettings(user_id)
            return self._user_settings[user_id]

    def update_user_settings(self, user_id: str, **kwargs) -> None:
        """사용자 설정 업데이트"""
        settings = self.get_user_settings(user_id)
        
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
                
        self.logger.info(f"사용자 설정 업데이트: {user_id} - {kwargs}")

    def _generate_notification_id(self, alert_condition: AlertCondition, user_id: str) -> str:
        """알림 ID 생성"""
        timestamp_ms = int(time.time() * 1000)
        return f"{alert_condition.symbol}_{alert_condition.alert_type.name}_{user_id}_{timestamp_ms}"

    def _is_in_cooldown(self, symbol: str, alert_type: AlertType, user_id: str, 
                       cooldown_minutes: int) -> bool:
        """쿨다운 상태 확인"""
        key = f"{symbol}_{alert_type.name}"
        
        if user_id not in self._last_notification_time:
            return False
            
        if key not in self._last_notification_time[user_id]:
            return False
            
        last_time = self._last_notification_time[user_id][key]
        cooldown_seconds = cooldown_minutes * 60
        
        return (time.time() - last_time) < cooldown_seconds

    def _update_cooldown(self, symbol: str, alert_type: AlertType, user_id: str) -> None:
        """쿨다운 시간 업데이트"""
        key = f"{symbol}_{alert_type.name}"
        self._last_notification_time[user_id][key] = time.time()

    def _check_hourly_limit(self, user_id: str, symbol: str) -> bool:
        """시간당 알림 제한 확인"""
        current_time = time.time()
        current_hour = int(current_time / 3600)
        
        # 시간이 바뀌었으면 카운트 리셋
        if (user_id not in self._hourly_reset_time or 
            self._hourly_reset_time[user_id] < current_hour * 3600):
            self._hourly_counts[user_id].clear()
            self._hourly_reset_time[user_id] = current_hour * 3600
            
        settings = self.get_user_settings(user_id)
        current_count = self._hourly_counts[user_id][symbol]
        
        return current_count < settings.max_notifications_per_hour

    def _increment_hourly_count(self, user_id: str, symbol: str) -> None:
        """시간당 알림 카운트 증가"""
        self._hourly_counts[user_id][symbol] += 1

    async def send_notification(self, alert_condition: AlertCondition, 
                              user_id: str = "default", 
                              channel: str = None) -> NotificationRecord:
        """알림 발송"""
        
        notification_id = self._generate_notification_id(alert_condition, user_id)
        
        # 기본 알림 기록 생성
        record = NotificationRecord(
            id=notification_id,
            alert_condition=alert_condition,
            status=NotificationStatus.PENDING,
            timestamp=time.time(),
            user_id=user_id,
            channel=channel
        )
        
        with self._lock:
            # 사용자 설정 확인
            settings = self.get_user_settings(user_id)
            
            # 알림 발송 여부 판단
            if not settings.should_notify(alert_condition):
                record.status = NotificationStatus.FILTERED
                record.error_message = "사용자 설정에 의해 필터됨"
                self._notification_history.append(record)
                return record
                
            # 쿨다운 확인
            if self._is_in_cooldown(alert_condition.symbol, alert_condition.alert_type, 
                                  user_id, settings.cooldown_minutes):
                record.status = NotificationStatus.COOLDOWN
                record.error_message = f"쿨다운 중 ({settings.cooldown_minutes}분)"
                self._notification_history.append(record)
                return record
                
            # 시간당 제한 확인
            if not self._check_hourly_limit(user_id, alert_condition.symbol):
                record.status = NotificationStatus.FILTERED
                record.error_message = "시간당 알림 제한 초과"
                self._notification_history.append(record)
                return record
                
            # 알림 발송 시도
            try:
                # 핸들러들에게 알림 전달
                for handler in self._notification_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(record)
                        else:
                            handler(record)
                    except Exception as e:
                        self.logger.error(f"알림 핸들러 오류: {e}", exc_info=True)
                        
                # 성공 처리
                record.status = NotificationStatus.SENT
                self._update_cooldown(alert_condition.symbol, alert_condition.alert_type, user_id)
                self._increment_hourly_count(user_id, alert_condition.symbol)
                
                self.logger.info(f"알림 발송 완료: {alert_condition.symbol} - {alert_condition.message}")
                
            except Exception as e:
                record.status = NotificationStatus.FAILED
                record.error_message = str(e)
                self.logger.error(f"알림 발송 실패: {e}", exc_info=True)
                
            finally:
                self._notification_history.append(record)
                
        return record

    def get_notification_history(self, symbol: str = None, user_id: str = None, 
                               hours: int = 24) -> List[NotificationRecord]:
        """알림 히스토리 조회"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self._lock:
            filtered_history = []
            
            for record in self._notification_history:
                # 시간 필터
                if record.timestamp < cutoff_time:
                    continue
                    
                # 종목 필터
                if symbol and record.alert_condition.symbol != symbol:
                    continue
                    
                # 사용자 필터  
                if user_id and record.user_id != user_id:
                    continue
                    
                filtered_history.append(record)
                
        return sorted(filtered_history, key=lambda x: x.timestamp, reverse=True)

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """통계 정보 조회"""
        history = self.get_notification_history(hours=hours)
        
        stats = {
            'total_notifications': len(history),
            'by_status': defaultdict(int),
            'by_alert_type': defaultdict(int),
            'by_symbol': defaultdict(int),
            'by_user': defaultdict(int),
            'success_rate': 0.0
        }
        
        sent_count = 0
        
        for record in history:
            stats['by_status'][record.status.value] += 1
            stats['by_alert_type'][record.alert_condition.alert_type.value] += 1
            stats['by_symbol'][record.alert_condition.symbol] += 1
            if record.user_id:
                stats['by_user'][record.user_id] += 1
                
            if record.status == NotificationStatus.SENT:
                sent_count += 1
                
        if len(history) > 0:
            stats['success_rate'] = (sent_count / len(history)) * 100
            
        return dict(stats)

    def clear_cooldown(self, symbol: str = None, alert_type: AlertType = None, 
                      user_id: str = None) -> int:
        """쿨다운 초기화"""
        cleared_count = 0
        
        with self._lock:
            if user_id:
                user_cooldowns = self._last_notification_time.get(user_id, {})
                keys_to_remove = []
                
                for key in user_cooldowns:
                    symbol_name, type_name = key.split('_', 1)
                    
                    if symbol and symbol_name != symbol:
                        continue
                    if alert_type and type_name != alert_type.name:
                        continue
                        
                    keys_to_remove.append(key)
                    
                for key in keys_to_remove:
                    del user_cooldowns[key]
                    cleared_count += 1
            else:
                # 모든 사용자의 쿨다운 초기화
                for user_id, user_cooldowns in self._last_notification_time.items():
                    keys_to_remove = []
                    
                    for key in user_cooldowns:
                        symbol_name, type_name = key.split('_', 1)
                        
                        if symbol and symbol_name != symbol:
                            continue
                        if alert_type and type_name != alert_type.name:
                            continue
                            
                        keys_to_remove.append(key)
                        
                    for key in keys_to_remove:
                        del user_cooldowns[key]
                        cleared_count += 1
                        
        self.logger.info(f"쿨다운 {cleared_count}개 항목 초기화")
        return cleared_count

    def cleanup_old_data(self) -> None:
        """오래된 데이터 정리"""
        cutoff_time = time.time() - (self.max_history_hours * 3600)
        
        with self._lock:
            # 히스토리 정리
            original_length = len(self._notification_history)
            self._notification_history = deque(
                (record for record in self._notification_history 
                 if record.timestamp >= cutoff_time),
                maxlen=self._notification_history.maxlen
            )
            
            cleaned_count = original_length - len(self._notification_history)
            
            if cleaned_count > 0:
                self.logger.info(f"오래된 알림 기록 {cleaned_count}개 정리")

    def get_cooldown_status(self, user_id: str = None) -> Dict[str, Dict[str, float]]:
        """쿨다운 상태 조회"""
        with self._lock:
            if user_id:
                return {user_id: self._last_notification_time.get(user_id, {}).copy()}
            else:
                return {
                    uid: cooldowns.copy() 
                    for uid, cooldowns in self._last_notification_time.items()
                }

    def __len__(self) -> int:
        """알림 기록 개수"""
        return len(self._notification_history)

    def __del__(self):
        """소멸자 - 정리 작업"""
        if hasattr(self, '_cleanup_task') and self._cleanup_task:
            try:
                self._cleanup_task.cancel()
            except:
                pass