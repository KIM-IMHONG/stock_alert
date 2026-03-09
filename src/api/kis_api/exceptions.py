"""
한국투자증권 API 예외 클래스들
"""

class KISAPIError(Exception):
    """한국투자증권 API 기본 예외"""
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

class KISAuthError(KISAPIError):
    """인증 관련 예외"""
    pass

class KISConnectionError(KISAPIError):
    """연결 관련 예외"""
    pass

class KISRateLimitError(KISAPIError):
    """API 호출 제한 예외"""
    pass

class KISDataError(KISAPIError):
    """데이터 파싱/형식 관련 예외"""
    pass