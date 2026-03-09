"""
Stock-related utility functions
"""
import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Korean stock code pattern (6 digits)
STOCK_CODE_PATTERN = re.compile(r'^\d{6}$')

# Common Korean stock codes and names (for validation/demo)
KNOWN_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "035720": "카카오",
    "068270": "셀트리온",
    "207940": "삼성바이오로직스",
    "373220": "LG에너지솔루션",
    "005380": "현대차",
    "012330": "현대모비스",
    "000270": "기아",
    "018260": "삼성에스디에스",
    "028260": "삼성물산",
    "032830": "삼성생명",
    "009150": "삼성전기",
    "010950": "S-Oil",
    "066570": "LG전자",
    "003550": "LG",
    "017670": "SK텔레콤",
    "034020": "두산에너빌리티",
    "003490": "대한항공",
    "011200": "HMM",
    "028050": "삼성엔지니어링",
    "096770": "SK이노베이션",
    "034730": "SK",
    "326030": "SK바이오팜",
    "241560": "두산밥캣",
    "009540": "HD한국조선해양"
}

def validate_stock_code(stock_code: str) -> bool:
    """Validate Korean stock code format"""
    if not stock_code:
        return False
    
    cleaned_code = stock_code.strip()
    return bool(STOCK_CODE_PATTERN.match(cleaned_code))

def get_stock_name(stock_code: str) -> Optional[str]:
    """Get stock name from code (StockSearcher 우선, 폴백으로 KNOWN_STOCKS)"""
    try:
        from .stock_search import get_stock_searcher
        searcher = get_stock_searcher()
        name = searcher.get_name(stock_code)
        if name:
            return name
    except Exception:
        pass
    return KNOWN_STOCKS.get(stock_code)

def format_price(price: float) -> str:
    """Format price with comma separators"""
    return f"{int(price):,}"

def format_change_rate(change_rate: float) -> str:
    """Format change rate with appropriate sign and color indication"""
    if change_rate > 0:
        return f"+{change_rate:.2f}%"
    elif change_rate < 0:
        return f"{change_rate:.2f}%"
    else:
        return "0.00%"

def get_trend_emoji(change_rate: float) -> str:
    """Get emoji based on stock trend"""
    if change_rate > 5:
        return "🚀"
    elif change_rate > 0:
        return "📈"
    elif change_rate < -5:
        return "💥"
    elif change_rate < 0:
        return "📉"
    else:
        return "➡️"

def format_stock_info(stock_code: str, current_price: float, 
                     change_rate: float, volume: Optional[int] = None) -> str:
    """Format stock information as readable string"""
    stock_name = get_stock_name(stock_code)
    price_str = format_price(current_price)
    change_str = format_change_rate(change_rate)
    trend_emoji = get_trend_emoji(change_rate)
    
    info = f"{trend_emoji} {stock_code} {stock_name}\n"
    info += f"💰 {price_str}원 ({change_str})"
    
    if volume:
        info += f"\n📊 거래량: {format_price(volume)}"
    
    return info

def is_significant_change(change_rate: float, threshold: float) -> bool:
    """Check if change rate is significant enough for alert"""
    return abs(change_rate) >= threshold

def categorize_change(change_rate: float) -> str:
    """Categorize price change"""
    if change_rate >= 10:
        return "급등"
    elif change_rate >= 5:
        return "상승"
    elif change_rate > 0:
        return "소폭상승"
    elif change_rate <= -10:
        return "급락"
    elif change_rate <= -5:
        return "하락"
    elif change_rate < 0:
        return "소폭하락"
    else:
        return "보합"

def get_alert_priority(change_rate: float) -> str:
    """Get alert priority based on change rate"""
    abs_change = abs(change_rate)
    
    if abs_change >= 15:
        return "high"
    elif abs_change >= 10:
        return "medium"
    elif abs_change >= 5:
        return "normal"
    else:
        return "low"

def validate_stock_list(stock_codes: List[str]) -> List[str]:
    """Validate list of stock codes, return valid ones"""
    valid_codes = []
    for code in stock_codes:
        if validate_stock_code(code):
            valid_codes.append(code.strip())
        else:
            logger.warning(f"Invalid stock code: {code}")
    
    return valid_codes

def parse_stock_code_from_text(text: str) -> Optional[str]:
    """Extract stock code from user input text"""
    if not text:
        return None
    
    # Remove common prefixes/suffixes and clean text
    cleaned = text.strip().upper()
    
    # Look for 6-digit pattern
    match = STOCK_CODE_PATTERN.search(cleaned)
    if match:
        return match.group(0)
    
    return None

def get_market_status_emoji(market_hour: bool) -> str:
    """Get emoji indicating market status"""
    if market_hour:
        return "🟢"  # Market open
    else:
        return "🔴"  # Market closed

def create_stock_summary(stocks_data: List[Dict]) -> str:
    """Create summary of multiple stocks"""
    if not stocks_data:
        return "데이터가 없습니다."
    
    summary = "📈 **주식 현황 요약**\n\n"
    
    for i, stock in enumerate(stocks_data, 1):
        stock_code = stock.get("code", "")
        price = stock.get("price", 0)
        change_rate = stock.get("change_rate", 0)
        
        trend = get_trend_emoji(change_rate)
        name = get_stock_name(stock_code)
        price_str = format_price(price)
        change_str = format_change_rate(change_rate)
        
        summary += f"{i}. {trend} {stock_code} {name}\n"
        summary += f"   💰 {price_str}원 ({change_str})\n\n"
    
    return summary