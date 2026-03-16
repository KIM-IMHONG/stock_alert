"""
KRX 전종목 리스트 로드 및 종목 검색
- 시작 시 KRX에서 전종목 리스트를 가져와 캐싱
- 종목명 부분 검색 지원
"""
import logging
import json
import os
from typing import Dict, List, Tuple, Optional

import io

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# 캐시 파일 경로
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '.cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'krx_stocks.json')


class StockSearcher:
    """KRX 전종목 검색기"""

    def __init__(self):
        # {종목코드: 종목명}
        self._stocks: Dict[str, str] = {}
        # {종목명: 종목코드} - 역방향 검색용
        self._name_to_code: Dict[str, str] = {}
        self._loaded = False

    @property
    def count(self) -> int:
        return len(self._stocks)

    def load(self):
        """종목 리스트 로드 (KRX → 캐시 → 폴백 순서)"""
        # 1. KRX에서 가져오기
        if self._fetch_from_krx():
            self._save_cache()
            return

        # 2. 캐시 파일에서 로드
        if self._load_cache():
            return

        # 3. 내장 리스트 사용
        self._load_builtin()

    def _fetch_from_krx(self) -> bool:
        """KRX 데이터에서 전종목 리스트 가져오기"""
        try:
            logger.info("KRX에서 종목 리스트 가져오는 중...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            }

            all_stocks = {}
            for mkt_type, mkt_name in [('stockMkt', 'KOSPI'), ('kosdaqMkt', 'KOSDAQ')]:
                url = 'https://kind.krx.co.kr/corpgeneral/corpList.do'
                params = {'method': 'download', 'marketType': mkt_type}
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()

                dfs = pd.read_html(io.StringIO(resp.text), encoding='euc-kr')
                df = dfs[0]
                count = 0
                for _, row in df.iterrows():
                    code = str(row['종목코드']).zfill(6)
                    name = str(row['회사명']).strip()
                    if code and name and len(code) == 6 and code.isdigit():
                        all_stocks[code] = name
                        count += 1

                logger.info(f"  {mkt_name}: {count}개 종목 로드")

            if all_stocks:
                self._stocks = all_stocks
                self._build_reverse_index()
                self._loaded = True
                logger.info(f"KRX 종목 리스트 로드 완료: 총 {len(all_stocks)}개")
                return True

        except Exception as e:
            logger.warning(f"KRX 종목 리스트 가져오기 실패: {e}")

        return False

    def _save_cache(self):
        """캐시 파일로 저장"""
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._stocks, f, ensure_ascii=False, indent=2)
            logger.info(f"종목 캐시 저장: {CACHE_FILE}")
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")

    def _load_cache(self) -> bool:
        """캐시 파일에서 로드"""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    self._stocks = json.load(f)
                self._build_reverse_index()
                self._loaded = True
                logger.info(f"캐시에서 종목 리스트 로드: {len(self._stocks)}개")
                return True
        except Exception as e:
            logger.warning(f"캐시 로드 실패: {e}")
        return False

    def _load_builtin(self):
        """내장 종목 리스트 (폴백)"""
        from .stock_utils import KNOWN_STOCKS
        self._stocks = dict(KNOWN_STOCKS)
        self._build_reverse_index()
        self._loaded = True
        logger.info(f"내장 종목 리스트 사용: {len(self._stocks)}개")

    def _build_reverse_index(self):
        """역방향 인덱스 생성"""
        self._name_to_code = {name: code for code, name in self._stocks.items()}

    def get_name(self, code: str) -> Optional[str]:
        """종목코드 → 종목명"""
        return self._stocks.get(code)

    def get_code(self, name: str) -> Optional[str]:
        """종목명(정확일치) → 종목코드"""
        return self._name_to_code.get(name)

    def search(self, query: str, limit: int = 8) -> List[Tuple[str, str]]:
        """
        종목 검색 (부분 매칭)

        Args:
            query: 검색어 (종목명 일부)
            limit: 최대 결과 수

        Returns:
            [(종목코드, 종목명), ...]
            - 이름이 query로 시작하는 종목 우선
            - 그 다음 query를 포함하는 종목
        """
        if not query:
            return []

        query = query.strip()
        starts_with = []
        contains = []

        for code, name in self._stocks.items():
            if name.startswith(query):
                starts_with.append((code, name))
            elif query in name:
                contains.append((code, name))

        # 시작하는 것 우선, 이름순 정렬
        starts_with.sort(key=lambda x: x[1])
        contains.sort(key=lambda x: x[1])

        results = starts_with + contains
        return results[:limit]

    def is_valid_code(self, code: str) -> bool:
        """유효한 종목코드인지 확인"""
        return code in self._stocks


# 싱글턴 인스턴스
_searcher: Optional[StockSearcher] = None


def get_stock_searcher() -> StockSearcher:
    """전역 StockSearcher 인스턴스 반환"""
    global _searcher
    if _searcher is None:
        _searcher = StockSearcher()
        _searcher.load()
    return _searcher
