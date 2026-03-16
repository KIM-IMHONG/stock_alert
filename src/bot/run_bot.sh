#!/bin/bash
# Korea Stock Alert Bot 실행 스크립트

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== 한국 주식 알림봇 시작 ==="

# 가상환경 생성/활성화
if [ ! -d "venv" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv venv
fi
source venv/bin/activate

# 의존성 설치
echo "의존성 설치 중..."
pip install -q -r requirements.txt

# .env 확인
if [ ! -f ".env" ]; then
    echo ".env 파일이 없습니다!"
    echo "  cp .env.example .env"
    echo "  그 후 .env 파일에 토큰과 API 키를 설정하세요."
    exit 1
fi

echo "봇 실행 중..."
python3 main.py
