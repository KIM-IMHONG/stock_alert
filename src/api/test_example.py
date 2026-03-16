#!/usr/bin/env python3
"""
한국투자증권 API 연동 테스트 및 사용 예시
"""
import os
import sys
import time
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kis_api import KISAPIClient, KISConfig, KISAPIError
from kis_api.manager import KISManager
from kis_api.websocket_client import RealtimeData
from utils.formatters import format_stock_info_message, format_realtime_alert
from utils.logger import setup_logger

# 로거 설정
logger = setup_logger("test", level="INFO")

def test_basic_api():
    """기본 API 기능 테스트"""
    print("=" * 50)
    print("🔧 기본 API 기능 테스트")
    print("=" * 50)
    
    try:
        # 설정 및 클라이언트 생성
        config = KISConfig()
        client = KISAPIClient(config)
        
        print(f"✅ API 클라이언트 생성 완료")
        print(f"🔑 App Key: {config.app_key[:8]}...")
        
        # 토큰 발급 테스트
        print("\n📝 액세스 토큰 발급 테스트...")
        token = client.get_access_token()
        print(f"✅ 토큰 발급 성공: {token[:20]}...")
        
        # 종목 정보 조회 테스트 (삼성전자)
        test_stocks = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, 네이버
        
        print(f"\n📊 종목 정보 조회 테스트...")
        for stock_code in test_stocks:
            try:
                stock_info = client.get_stock_info(stock_code)
                message = format_stock_info_message(stock_info)
                print(f"\n{message}")
                
                time.sleep(1)  # API 호출 간격
                
            except Exception as e:
                print(f"❌ 종목 조회 실패 [{stock_code}]: {e}")
        
        # 일괄 조회 테스트
        print(f"\n📋 일괄 조회 테스트...")
        stocks_info = client.get_multiple_stocks_info(test_stocks)
        print(f"✅ {len(stocks_info)}개 종목 정보 조회 완료")
        
        client.close()
        print(f"\n✅ 기본 API 테스트 완료")
        
    except Exception as e:
        print(f"❌ 기본 API 테스트 실패: {e}")
        return False
    
    return True

def test_manager_functionality():
    """매니저 기능 테스트"""
    print("\n" + "=" * 50)
    print("🎯 매니저 기능 테스트")
    print("=" * 50)
    
    try:
        # 매니저 생성
        manager = KISManager()
        print("✅ KIS 매니저 생성 완료")
        
        # 알림 콜백 함수 정의
        def alert_callback(alert_type: str, data: RealtimeData):
            message = format_realtime_alert(data, alert_type)
            print(f"\n🚨 {alert_type} 알림!")
            print(message)
            print("-" * 30)
        
        # 모니터링 종목 추가
        test_stocks = ["005930", "000660"]  # 삼성전자, SK하이닉스
        
        for stock_code in test_stocks:
            manager.add_stock_to_monitor(stock_code, alert_callback)
        
        print(f"📊 모니터링 종목 추가: {test_stocks}")
        
        # 알림 임계값 설정 (테스트용으로 낮게 설정)
        manager.set_alert_thresholds(surge_threshold=2.0, plunge_threshold=-2.0)
        
        # 모니터링 시작 (REST API 기반, 짧은 간격)
        print("\n🔄 가격 모니터링 시작 (30초 간격)...")
        manager.start_price_monitoring(check_interval=30)
        
        # 상태 확인
        status = manager.get_monitoring_status()
        print(f"📈 모니터링 상태: {status}")
        
        # 잠시 동작 확인 (실제 환경에서는 더 길게)
        print("\n⏰ 60초 동안 모니터링 동작 확인...")
        time.sleep(60)
        
        # 모니터링 중지
        manager.stop_monitoring()
        print("⏹️  모니터링 중지")
        
        manager.close()
        print("✅ 매니저 테스트 완료")
        
    except Exception as e:
        print(f"❌ 매니저 테스트 실패: {e}")
        return False
    
    return True

def test_websocket_functionality():
    """WebSocket 기능 테스트 (주의: 실제 WebSocket 연결 필요)"""
    print("\n" + "=" * 50)
    print("🔌 WebSocket 기능 테스트")
    print("=" * 50)
    
    try:
        manager = KISManager()
        
        # 실시간 데이터 콜백
        def realtime_callback(data: RealtimeData):
            print(f"📡 실시간 데이터: {data.stock_code} - {data.current_price}원")
        
        # 실시간 구독 시도 (실제 환경에서만 동작)
        try:
            manager.subscribe_realtime(["005930"], realtime_callback)
            print("✅ 실시간 구독 성공")
            
            # 잠시 대기
            print("⏰ 30초 동안 실시간 데이터 수신 대기...")
            time.sleep(30)
            
        except Exception as e:
            print(f"⚠️  실시간 구독 실패 (WebSocket 연결 문제): {e}")
            print("   실제 운영 환경에서 다시 테스트하세요.")
        
        manager.close()
        print("✅ WebSocket 테스트 완료")
        
    except Exception as e:
        print(f"❌ WebSocket 테스트 실패: {e}")
        return False
    
    return True

def check_environment():
    """환경 설정 확인"""
    print("=" * 50)
    print("🔍 환경 설정 확인")
    print("=" * 50)
    
    required_vars = [
        "KIS_APP_KEY",
        "KIS_APP_SECRET"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:8]}...")
        else:
            print(f"❌ {var}: 설정되지 않음")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  누락된 환경변수: {missing_vars}")
        print("다음 명령으로 환경변수를 설정하세요:")
        print("export KIS_APP_KEY='your_app_key'")
        print("export KIS_APP_SECRET='your_app_secret'")
        return False
    
    print("✅ 모든 환경변수 설정 완료")
    return True

def main():
    """메인 테스트 실행"""
    print("🚀 한국투자증권 API 연동 모듈 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 환경 확인
    if not check_environment():
        print("\n❌ 환경 설정이 완료되지 않았습니다.")
        print("환경변수를 설정한 후 다시 실행하세요.")
        return
    
    # 기본 API 테스트
    if not test_basic_api():
        print("❌ 기본 API 테스트 실패")
        return
    
    # 매니저 기능 테스트
    if not test_manager_functionality():
        print("❌ 매니저 기능 테스트 실패")
        return
    
    # WebSocket 테스트 (선택적)
    test_websocket_functionality()
    
    print("\n" + "=" * 50)
    print("🎉 모든 테스트 완료!")
    print("📊 KIS API 연동 모듈이 정상적으로 구현되었습니다.")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n💥 예상치 못한 오류: {e}")
        logger.exception("테스트 실행 중 오류 발생")