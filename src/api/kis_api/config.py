"""
한국투자증권 API 설정 관리
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class KISConfig:
    """한국투자증권 API 설정"""
    
    # 기본 API 엔드포인트
    BASE_URL: str = "https://openapi.koreainvestment.com:9443"
    WEBSOCKET_URL: str = "ws://ops.koreainvestment.com:21000"
    
    # API 엔드포인트
    TOKEN_URL: str = "/oauth2/tokenP"  # 토큰 발급
    STOCK_INFO_URL: str = "/uapi/domestic-stock/v1/quotations/inquire-price"  # 종목 정보
    REALTIME_URL: str = "/uapi/domestic-stock/v1/quotations/inquire-ccnl"  # 실시간 현재가
    
    # 인증 정보 (환경변수에서 가져오기)
    app_key: str = ""
    app_secret: str = ""
    
    # 계좌 정보
    account_no: str = ""
    account_prefix: str = ""
    
    # API 호출 설정
    max_retries: int = 3
    timeout: int = 30
    rate_limit_delay: float = 0.1  # API 호출 간격 (초)
    
    def __post_init__(self):
        """환경변수에서 설정 로드"""
        if not self.app_key:
            self.app_key = os.getenv('KIS_APP_KEY', '')
        if not self.app_secret:
            self.app_secret = os.getenv('KIS_APP_SECRET', '')
        if not self.account_no:
            self.account_no = os.getenv('KIS_ACCOUNT_NO', '')
        if not self.account_prefix:
            self.account_prefix = os.getenv('KIS_ACCOUNT_PREFIX', '50')
    
    def validate(self) -> bool:
        """필수 설정 값 검증"""
        required_fields = [self.app_key, self.app_secret]
        return all(field for field in required_fields)