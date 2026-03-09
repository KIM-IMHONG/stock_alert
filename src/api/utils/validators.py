"""
데이터 검증 유틸리티
"""
import re
from typing import List

def validate_stock_code(stock_code: str) -> bool:
    """종목코드 유효성 검증"""
    if not stock_code:
        return False
    
    # 한국 주식 종목코드는 6자리 숫자
    pattern = r'^[0-9]{6}$'
    return bool(re.match(pattern, stock_code))

def validate_stock_codes(stock_codes: List[str]) -> List[str]:
    """여러 종목코드 검증 후 유효한 것만 반환"""
    valid_codes = []
    for code in stock_codes:
        if validate_stock_code(code):
            valid_codes.append(code)
    return valid_codes

def validate_price(price: any) -> bool:
    """가격 유효성 검증"""
    try:
        price_int = int(price)
        return price_int >= 0
    except (ValueError, TypeError):
        return False

def validate_change_rate(rate: any) -> bool:
    """변동률 유효성 검증"""
    try:
        rate_float = float(rate)
        # 일일 상한가/하한가는 보통 ±30% 내외
        return -50.0 <= rate_float <= 50.0
    except (ValueError, TypeError):
        return False

def sanitize_stock_code(stock_code: str) -> str:
    """종목코드 정규화"""
    # 공백 제거
    code = stock_code.strip()
    
    # 앞자리 0 패딩 (4자리나 5자리인 경우)
    if len(code) < 6 and code.isdigit():
        code = code.zfill(6)
    
    return code