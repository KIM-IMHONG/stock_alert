"""
Korea Stock Alert Bot - 봇 모듈 엔트리포인트

이 파일 대신 프로젝트 루트의 main.py를 실행하세요:
    cd /path/to/korea-stock-alert-bot
    python main.py
"""
import os
import sys

# 프로젝트 루트의 main.py로 위임
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    from main import main
    main()
