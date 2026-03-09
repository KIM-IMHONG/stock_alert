"""
데이터 포매팅 유틸리티
"""
from typing import Union

def format_price(price: Union[int, float]) -> str:
    """가격 포매팅 (천단위 콤마)"""
    try:
        return f"{int(price):,}원"
    except (ValueError, TypeError):
        return "0원"

def format_change_rate(rate: Union[int, float], include_sign: bool = True) -> str:
    """변동률 포매팅"""
    try:
        rate_float = float(rate)
        sign = ""
        
        if include_sign:
            if rate_float > 0:
                sign = "+"
            elif rate_float < 0:
                sign = "-"
                rate_float = abs(rate_float)
        
        return f"{sign}{rate_float:.2f}%"
    except (ValueError, TypeError):
        return "0.00%"

def format_change_amount(amount: Union[int, float]) -> str:
    """변동금액 포매팅"""
    try:
        amount_int = int(amount)
        sign = "+" if amount_int > 0 else ""
        return f"{sign}{amount_int:,}"
    except (ValueError, TypeError):
        return "0"

def format_volume(volume: Union[int, float]) -> str:
    """거래량 포매팅 (만주, 억주 단위)"""
    try:
        vol = int(volume)
        
        if vol >= 100_000_000:  # 1억 이상
            return f"{vol / 100_000_000:.1f}억주"
        elif vol >= 10_000:  # 1만 이상
            return f"{vol / 10_000:.1f}만주"
        else:
            return f"{vol:,}주"
    except (ValueError, TypeError):
        return "0주"

def format_stock_info_message(stock_info) -> str:
    """종목 정보를 메시지 형태로 포매팅"""
    try:
        message_parts = [
            f"📈 {stock_info.name} ({stock_info.code})",
            f"💰 현재가: {format_price(stock_info.current_price)}",
            f"📊 변동: {format_change_amount(stock_info.change_amount)} ({format_change_rate(stock_info.change_rate)})",
            f"📦 거래량: {format_volume(stock_info.trading_volume)}"
        ]
        
        if hasattr(stock_info, 'timestamp') and stock_info.timestamp:
            message_parts.append(f"🕐 {stock_info.timestamp.strftime('%H:%M:%S')}")
        
        return "\n".join(message_parts)
    
    except AttributeError as e:
        return f"❌ 데이터 포매팅 오류: {e}"

def format_realtime_alert(data, alert_type: str = "변동") -> str:
    """실시간 알림 메시지 포매팅"""
    try:
        icon = "🔥" if alert_type == "급등" else "❄️" if alert_type == "급락" else "📊"
        
        message = f"{icon} {alert_type} 감지!\n"
        message += f"종목: {data.stock_code}\n"
        message += f"현재가: {format_price(data.current_price)}\n"
        message += f"변동률: {format_change_rate(data.change_rate)}\n"
        message += f"시간: {data.timestamp.strftime('%H:%M:%S')}"
        
        return message
    
    except AttributeError as e:
        return f"❌ 알림 메시지 생성 오류: {e}"