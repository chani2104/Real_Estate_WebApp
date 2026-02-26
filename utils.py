"""
유틸리티: items -> DataFrame / 가격 파싱 / 면적(평) 변환
"""

import re
from typing import List, Dict, Any, Optional

import pandas as pd


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
]


def _norm(v: Any) -> str:
    """표에 넣기 좋은 문자열로 정규화(None/list 처리)"""
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(map(str, v)) if v else ""
    return str(v)


def items_to_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
    """네이버 items(list[dict])를 TABLE_COLUMNS 기준으로 DF로 변환"""
    keys = [k for k, _ in TABLE_COLUMNS]
    headers = [h for _, h in TABLE_COLUMNS]
    rows = [[_norm(it.get(k)) for k in keys] for it in items]
    return pd.DataFrame(rows, columns=headers)


def parse_price_to_manwon(text: Any) -> Optional[int]:
    """
    가격 문자열을 '만원 단위 정수'로 변환
    예: '12억 3,000' -> 123000, '4,800' -> 4800, '5억' -> 50000
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
    """㎡ -> 평 (1평 = 3.305785㎡)"""
    try:
        v = float(str(sqm).strip())
        return v / 3.305785
    except Exception:
        return None


def price_bucket(manwon: Optional[int]) -> str:
    """
    가격 구간 분류(요구사항)
      - 5,000만 미만 / 5,000만 ~ 5억 / 5억 초과
    단위: 만원 (5000, 50000 기준)
    """
    if manwon is None:
        return "가격정보없음"
    if manwon < 5000:
        return "5,000만 미만"
    if manwon <= 50000:
        return "5,000만 ~ 5억"
    return "5억 초과"