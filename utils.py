"""
유틸리티: DataFrame 변환 / 가격 파싱 / 엑셀 저장
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# 표시/저장에 사용할 컬럼 정의 (네이버 item(dict)의 key → 표 헤더)
TABLE_COLUMNS = [
    ("atclNo", "매물ID"),
    ("atclNm", "단지/건물명"),
    ("bildNm", "동/호"),
    ("rletTpNm", "매물유형"),
    ("tradTpNm", "거래유형"),
    ("hanPrc", "가격"),
    ("spc2", "면적(㎡)"),
    ("flrInfo", "층"),
    ("direction", "방향"),
    ("rltrNm", "중개사"),
    ("directTradYn", "직거래"),
    ("atclCfmYmd", "확인일"),
    ("atclFetrDesc", "특징"),
    # 지도 시각화를 위한 좌표 컬럼 (있으면 사용, 없으면 빈 문자열)
    ("lat", "위도"),
    ("lng", "경도"),
]


def _norm_value(v: Any) -> str:
    """리스트/None 처리 포함해서 표에 넣기 좋은 문자열로 정규화"""
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(map(str, v)) if v else ""
    return str(v)


def items_to_dataframe(items: List[Dict[str, Any]]):
    """
    네이버 articleList의 body(items)를 TABLE_COLUMNS 기준으로 DataFrame으로 변환
    """
    if not HAS_PANDAS:
        raise ImportError("pandas가 필요합니다. pip install pandas")

    keys = [k for k, _ in TABLE_COLUMNS]
    headers = [h for _, h in TABLE_COLUMNS]

    rows = []
    for it in items:
        rows.append([_norm_value(it.get(k)) for k in keys])

    return pd.DataFrame(rows, columns=headers)


def parse_price_to_manwon(text: Any) -> Optional[int]:
    """
    가격 문자열(hanPrc)을 '만원 단위 정수'로 변환 (정렬/구간 나눔용)
    예:
      '4,800' -> 4800
      '5억' -> 50000
      '12억 3,000' -> 123000
    """
    if text is None:
        return None

    s = str(text).replace(" ", "").replace(",", "")
    if s in ("", "-", "없음"):
        return None

    # "12억3000" / "12억" / "12억3" 같은 케이스
    m = re.match(r"(?P<eok>\d+)억(?P<rest>\d+)?", s)
    if m:
        eok = int(m.group("eok"))
        rest = m.group("rest")
        rest_manwon = int(rest) if rest else 0
        return eok * 10000 + rest_manwon

    # "4800" 같은 만원 단위 숫자
    if s.isdigit():
        return int(s)

    return None


def price_bucket(manwon: Optional[int]) -> str:
    """
    가격 구간 분류 (요구사항)
      - 5,000만 미만
      - 5,000만 ~ 5억
      - 5억 초과
    ※ 단위: 만원
      - 5,000만원 = 5000
      - 5억 = 50000
    """
    if manwon is None:
        return "가격정보없음"
    if manwon < 5000:
        return "5,000만 미만"
    if manwon <= 50000:
        return "5,000만 ~ 5억"
    return "5억 초과"


def default_filename(region_name: str = "") -> str:
    """기본 파일명 생성: 매물목록_지역명_날짜.xlsx"""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    region = (region_name or "지역").replace(" ", "_").strip()
    return f"매물목록_{region}_{date_str}.xlsx"


def save_to_excel(items: List[Dict[str, Any]], filepath: str) -> str:
    """TABLE_COLUMNS 기반으로 엑셀 저장"""
    if not items:
        raise ValueError("저장할 매물 데이터가 없습니다.")

    headers = [h for _, h in TABLE_COLUMNS]
    keys = [k for k, _ in TABLE_COLUMNS]
    rows = [[_norm_value(it.get(k)) for k in keys] for it in items]

    if HAS_PANDAS:
        df = pd.DataFrame(rows, columns=headers)
        df.to_excel(filepath, index=False, engine="openpyxl")
    elif HAS_OPENPYXL:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "매물목록"
        ws.append(headers)
        for r in rows:
            ws.append(r)
        wb.save(filepath)
    else:
        raise ImportError("pip install pandas openpyxl 중 하나가 필요합니다.")

    return os.path.abspath(filepath)

def sqm_to_pyeong(sqm: Any) -> Optional[float]:
    """㎡ → 평 변환 (1평 = 3.305785㎡)"""
    try:
        v = float(str(sqm).strip())
        return v / 3.305785
    except Exception:
        return None

def parse_price_to_manwon(text: Any) -> Optional[int]:
    """
    hanPrc 같은 가격 문자열을 만원 단위 정수로 변환
    예: '12억 3,000' -> 123000, '4,800' -> 4800
    """
    if text is None:
        return None
    s = str(text).replace(" ", "").replace(",", "")
    if s in ("", "-", "없음"):
        return None

    m = re.match(r"(?P<eok>\d+)억(?P<rest>\d+)?", s)
    if m:
        eok = int(m.group("eok"))
        rest = int(m.group("rest")) if m.group("rest") else 0
        return eok * 10000 + rest

    if s.isdigit():
        return int(s)

    return None