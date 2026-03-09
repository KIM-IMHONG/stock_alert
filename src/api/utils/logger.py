"""
로깅 유틸리티
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

def setup_logger(name: str = 'kis_api', level: str = 'INFO', log_file: str = None) -> logging.Logger:
    """로거 설정"""
    logger = logging.getLogger(name)
    
    # 이미 설정되어 있으면 반환
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # 포매터
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택적)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

class APILogger:
    """API 호출 로깅 클래스"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_api_call(self, method: str, url: str, status_code: int, response_time: float):
        """API 호출 로깅"""
        self.logger.info(f"{method} {url} - {status_code} ({response_time:.3f}s)")
    
    def log_error(self, error: Exception, context: str = ""):
        """에러 로깅"""
        self.logger.error(f"{context}: {type(error).__name__}: {error}")
    
    def log_websocket_event(self, event: str, details: str = ""):
        """WebSocket 이벤트 로깅"""
        self.logger.info(f"WebSocket {event}: {details}")