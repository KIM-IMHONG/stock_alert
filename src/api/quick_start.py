#!/usr/bin/env python3
"""
한국투자증권 API 연동 모듈 - 빠른 시작 가이드
"""
import os
import time
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

from kis_api import KISManager, KISAPIError
from kis_api.websocket_client import RealtimeData
from utils.formatters import format_realtime_alert, format_stock_info_message

def simple_stock_info():
    """간단한 종목 정보 조회 예시"""
    print("📊 종목 정보 조회 예시")
    print("-" * 40)
    
    try:
        manager = KISManager()
        
        # 삼성전자 정보 조회
        stock_info = manager.get_stock_info("005930")
        message = format_stock_info_message(stock_info)
        print(message)
        
        manager.close()
        
    except KISAPIError as e:
        print(f"❌ API 오류: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

def simple_monitoring():
    """간단한 급등/급락 모니터링 예시"""
    print("\n🚨 급등/급락 모니터링 예시")
    print("-" * 40)
    
    try:
        manager = KISManager()
        
        # 알림 콜백 함수
        def alert_callback(alert_type: str, data: RealtimeData):
            alert_message = format_realtime_alert(data, alert_type)
            print(f"\n{alert_message}")
            
            # 여기서 텔레그램, 이메일 등으로 알림 발송 가능
            # send_telegram_message(alert_message)
        
        # 모니터링할 종목들
        watch_list = [
            "005930",  # 삼성전자
            "000660",  # SK하이닉스
            "035420"   # 네이버
        ]
        
        # 종목별로 모니터링 설정
        for stock_code in watch_list:
            manager.add_stock_to_monitor(stock_code, alert_callback)
            print(f"✅ {stock_code} 모니터링 추가")
        
        # 알림 임계값 설정 (급등 3%, 급락 -3%)
        manager.set_alert_thresholds(surge_threshold=3.0, plunge_threshold=-3.0)
        print(f"⚡ 알림 임계값: 급등 3%, 급락 -3%")
        
        # 모니터링 시작 (30초 간격)
        print(f"🔄 모니터링 시작 (30초 간격)")
        manager.start_price_monitoring(check_interval=30)
        
        print(f"⏰ 2분 동안 모니터링합니다...")
        print(f"💡 Ctrl+C로 중단할 수 있습니다.")
        
        # 2분 대기
        time.sleep(120)
        
        # 모니터링 중지
        manager.stop_monitoring()
        manager.close()
        print(f"\n✅ 모니터링 완료")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  사용자에 의해 중단되었습니다.")
        manager.stop_monitoring()
        manager.close()
    except KISAPIError as e:
        print(f"❌ API 오류: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

def check_environment_setup():
    """환경 설정 확인"""
    print("🔧 환경 설정 확인")
    print("-" * 40)
    
    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')
    
    if not app_key or not app_secret:
        print("❌ 환경변수가 설정되지 않았습니다.")
        print("\n다음 단계를 따라 설정하세요:")
        print("1. .env 파일을 생성하세요:")
        print("   cp .env.example .env")
        print("\n2. .env 파일을 편집하여 KIS API 정보를 입력하세요:")
        print("   KIS_APP_KEY=your_app_key_here")
        print("   KIS_APP_SECRET=your_app_secret_here")
        print("\n3. KIS API 키는 다음에서 발급받을 수 있습니다:")
        print("   https://developers.koreainvestment.com")
        return False
    
    print(f"✅ KIS_APP_KEY: {app_key[:8]}...")
    print(f"✅ KIS_APP_SECRET: {app_secret[:8]}...")
    print("✅ 환경 설정 완료")
    return True

def main():
    """메인 실행 함수"""
    print("🚀 한국투자증권 API 연동 모듈 - 빠른 시작")
    print("=" * 50)
    
    # 환경 설정 확인
    if not check_environment_setup():
        return
    
    # 종목 정보 조회 예시
    simple_stock_info()
    
    # 사용자에게 모니터링 실행 여부 확인
    try:
        response = input("\n🚨 급등/급락 모니터링을 실행하시겠습니까? (y/N): ").lower()
        if response in ['y', 'yes']:
            simple_monitoring()
        else:
            print("📝 모니터링을 건너뜁니다.")
    except KeyboardInterrupt:
        print("\n⏹️  프로그램이 중단되었습니다.")
    
    print("\n🎉 빠른 시작 가이드 완료!")
    print("\n📚 더 많은 기능을 원하시면 다음을 참고하세요:")
    print("   - README.md: 상세 사용법")
    print("   - test_example.py: 전체 기능 테스트")

if __name__ == "__main__":
    main()