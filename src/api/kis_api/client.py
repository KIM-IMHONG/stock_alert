"""
한국투자증권 API 클라이언트 메인 클래스
"""
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .config import KISConfig
from .exceptions import KISAPIError, KISAuthError, KISConnectionError, KISRateLimitError, KISDataError

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StockInfo:
    """종목 정보 데이터 클래스"""
    code: str
    name: str
    current_price: int
    change_rate: float
    change_amount: int
    trading_volume: int
    market_cap: Optional[int] = None
    timestamp: Optional[datetime] = None

class KISAPIClient:
    """한국투자증권 OpenAPI 클라이언트"""
    
    def __init__(self, config: Optional[KISConfig] = None):
        self.config = config or KISConfig()
        if not self.config.validate():
            raise KISAuthError("API 키가 설정되지 않았습니다. KIS_APP_KEY, KIS_APP_SECRET 환경변수를 확인하세요.")
        
        self.session = requests.Session()
        self._access_token = None
        self._token_expires_at = None
        self._last_request_time = 0
        
        # HTTP 기본 헤더 설정
        self.session.headers.update({
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            'User-Agent': 'KIS-StockAlert-Bot/1.0'
        })
        
        logger.info("KIS API 클라이언트 초기화 완료")
    
    def _ensure_rate_limit(self):
        """API 호출 간격 제한"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """HTTP 요청 실행 (재시도 로직 포함)"""
        self._ensure_rate_limit()
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.request(
                    method, 
                    url, 
                    timeout=self.config.timeout,
                    **kwargs
                )
                
                if response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt
                    logger.warning(f"API 호출 제한. {wait_time}초 대기 후 재시도...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt == self.config.max_retries - 1:
                    raise KISConnectionError(f"요청 타임아웃: {url}")
                time.sleep(2 ** attempt)
                
            except requests.exceptions.ConnectionError:
                if attempt == self.config.max_retries - 1:
                    raise KISConnectionError(f"연결 실패: {url}")
                time.sleep(2 ** attempt)
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    raise KISAuthError("인증 실패")
                elif e.response.status_code == 429:
                    continue
                else:
                    raise KISAPIError(f"HTTP 오류: {e.response.status_code}")
        
        raise KISAPIError("최대 재시도 횟수 초과")
    
    def get_access_token(self) -> str:
        """액세스 토큰 발급/갱신"""
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token
        
        logger.info("새로운 액세스 토큰 요청")
        
        url = self.config.BASE_URL + self.config.TOKEN_URL
        data = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret
        }
        
        try:
            response = self._make_request("POST", url, json=data)
            
            if response.get("rt_cd") != "0":
                raise KISAuthError(f"토큰 발급 실패: {response.get('msg1', 'Unknown error')}")
            
            self._access_token = response["access_token"]
            # 토큰 유효시간 (보통 24시간)
            expires_in = response.get("expires_in", 86400)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # 세션 헤더에 토큰 추가
            self.session.headers.update({
                'Authorization': f'Bearer {self._access_token}',
                'appkey': self.config.app_key,
                'appsecret': self.config.app_secret
            })
            
            logger.info("액세스 토큰 발급 완료")
            return self._access_token
            
        except Exception as e:
            logger.error(f"토큰 발급 실패: {e}")
            raise KISAuthError(f"토큰 발급 실패: {e}")
    
    def get_stock_info(self, stock_code: str) -> StockInfo:
        """종목 정보 조회"""
        self.get_access_token()  # 토큰 확인
        
        url = self.config.BASE_URL + self.config.STOCK_INFO_URL
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code
        }
        
        headers = {
            "tr_id": "FHKST01010100",  # 주식현재가 조회 TR ID
            "custtype": "P"  # 개인
        }
        
        try:
            response = self._make_request("GET", url, params=params, headers=headers)
            
            if response.get("rt_cd") != "0":
                raise KISDataError(f"종목 정보 조회 실패: {response.get('msg1', 'Unknown error')}")
            
            output = response.get("output", {})
            
            return StockInfo(
                code=stock_code,
                name=output.get("hts_kor_isnm", ""),
                current_price=int(output.get("stck_prpr", 0)),
                change_rate=float(output.get("prdy_ctrt", 0)),
                change_amount=int(output.get("prdy_vrss", 0)),
                trading_volume=int(output.get("acml_vol", 0)),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"종목 정보 조회 실패 [{stock_code}]: {e}")
            raise KISAPIError(f"종목 정보 조회 실패: {e}")
    
    def get_current_price(self, stock_code: str) -> int:
        """현재가 조회"""
        stock_info = self.get_stock_info(stock_code)
        return stock_info.current_price
    
    def get_multiple_stocks_info(self, stock_codes: List[str]) -> List[StockInfo]:
        """여러 종목 정보 일괄 조회"""
        results = []
        for code in stock_codes:
            try:
                stock_info = self.get_stock_info(code)
                results.append(stock_info)
                time.sleep(self.config.rate_limit_delay)  # API 호출 간격 조절
            except Exception as e:
                logger.error(f"종목 조회 실패 [{code}]: {e}")
                continue
        
        return results
    
    def calculate_change_rate(self, current_price: int, previous_price: int) -> float:
        """가격 변동률 계산"""
        if previous_price == 0:
            return 0.0
        return ((current_price - previous_price) / previous_price) * 100
    
    def is_surge_detected(self, change_rate: float, threshold: float = 5.0) -> bool:
        """급등 감지 (기본 5% 이상)"""
        return change_rate >= threshold
    
    def is_plunge_detected(self, change_rate: float, threshold: float = -5.0) -> bool:
        """급락 감지 (기본 -5% 이하)"""
        return change_rate <= threshold
    
    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()
        logger.info("KIS API 클라이언트 세션 종료")