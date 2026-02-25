"""
유틸리티: DataFrame 변환 / 가격 파싱 / 거리 계산 / 엑셀 저장
"""

import os
import re
import math
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
    ("lat", "lat"),
    ("lng", "lng"),
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


def sqm_to_pyeong(sqm: Any) -> Optional[float]:
    """㎡ → 평 변환 (1평 = 3.305785㎡)"""
    try:
        v = float(str(sqm).strip())
        return v / 3.305785
    except Exception:
        return None


def haversine_distance(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 직선 거리 (km) 계산"""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def estimate_walking_minutes(distance_km, speed_kmh=4.8):
    """거리 기반 도보 분 계산 (평균 시속 4.8km 기준)"""
    return (distance_km / speed_kmh) * 60


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
    else:
        raise ImportError("pip install pandas openpyxl이 필요합니다.")

    return os.path.abspath(filepath)
