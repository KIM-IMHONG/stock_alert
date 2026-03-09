"""
Configuration settings for Korea Stock Alert Bot
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "bot_database.db")

# User limits
MAX_WATCHLIST_SIZE = 10
MIN_WATCHLIST_SIZE = 0

# Alert configuration
ALERT_COOLDOWN_MINUTES = 15  # 중복 알림 방지를 위한 쿨다운 시간
DEFAULT_ALERT_THRESHOLD = 5.0  # 기본 급등/급락 임계값 (%)

# Message templates
MESSAGES = {
    "welcome": """
🏆 한국 주식 알림봇에 오신 것을 환영합니다!

📈 실시간으로 주식 급등/급락을 모니터링하고 알림을 받아보세요.

📋 사용 가능한 명령어:
• /add - 종목 추가 (이름 검색 가능)
• /remove - 종목 제거
• /list - 내 종목 목록 조회
• /settings - 알림 조건 설정

💡 종목 추가 방법:
• /add 삼성 → 검색 결과에서 선택
• /add 005930 → 종목코드로 직접 추가
• 삼성 → 텍스트만 입력해도 검색
    """.strip(),

    "help": """
📋 명령어 안내:

• /add - 종목 추가 (최대 10개)
• /remove - 종목 제거
• /list - 내 종목 목록 조회
• /settings - 알림 조건 설정 (급등/급락 %)

💡 종목 검색 방법:
• /add 삼성 (이름으로 검색)
• /add 005930 (종목코드로 추가)
• /삼성 (바로 검색)
• 삼성 (텍스트만 입력해도 검색)
    """.strip(),
    
    "stock_added": "✅ {stock_code} 종목이 모니터링 목록에 추가되었습니다.",
    "stock_removed": "🗑️ {stock_code} 종목이 모니터링 목록에서 제거되었습니다.",
    "stock_not_found": "❌ {stock_code} 종목을 찾을 수 없습니다.",
    "already_watching": "⚠️ {stock_code} 종목은 이미 모니터링 중입니다.",
    "not_watching": "⚠️ {stock_code} 종목은 모니터링 목록에 없습니다.",
    "watchlist_full": "⚠️ 모니터링 목록이 가득찼습니다. (최대 {max_size}개)",
    "empty_watchlist": "📋 모니터링 중인 종목이 없습니다.\n종목명 또는 /add 명령어로 종목을 추가해보세요!",
    "invalid_stock_code": "❌ 올바른 종목코드(6자리) 또는 종목명을 입력해주세요.",
    "settings_updated": "✅ 알림 설정이 업데이트되었습니다.",
    "invalid_threshold": "❌ 올바른 퍼센트 값을 입력해주세요. (1-50 범위)",
    "error": "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
}

# Alert message template
ALERT_TEMPLATE = """
🚨 {alert_type} 알림!

📈 종목: {stock_code} {stock_name}
💰 현재가: {current_price:,}원
📊 변동률: {change_rate:+.2f}%
⏰ 시간: {timestamp}

{trend_emoji} {status}
"""

def get_config() -> Dict[str, Any]:
    """Return all configuration as dictionary"""
    return {
        "bot_token": BOT_TOKEN,
        "database_path": DATABASE_PATH,
        "max_watchlist_size": MAX_WATCHLIST_SIZE,
        "alert_cooldown_minutes": ALERT_COOLDOWN_MINUTES,
        "default_alert_threshold": DEFAULT_ALERT_THRESHOLD,
        "messages": MESSAGES,
        "alert_template": ALERT_TEMPLATE,
    }