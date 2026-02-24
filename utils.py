"""
유틸리티: 엑셀 저장, 지역 설정
"""

import os
from datetime import datetime
from typing import List, Dict, Any

# pandas/openpyxl 사용 (없으면 기본 구현으로 대체 시도)
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


# 테이블 표시용 컬럼 정의 (ApiRef.md 기반)
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


def item_to_row(item: Dict[str, Any]) -> List[Any]:
    """API 응답 item을 테이블 행(리스트)로 변환"""
    row = []
    for key, _ in TABLE_COLUMNS:
        val = item.get(key, "")
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val) if val else ""
        row.append(val if val is not None else "")
    return row


def save_to_excel(items: List[Dict[str, Any]], filepath: str) -> str:
    """
    매물 목록을 엑셀 파일로 저장
    Returns: 저장된 파일 경로
    """
    if not items:
        raise ValueError("저장할 매물 데이터가 없습니다.")

    # 컬럼 헤더
    headers = [col[1] for col in TABLE_COLUMNS]
    keys = [col[0] for col in TABLE_COLUMNS]

    rows = []
    for item in items:
        row = []
        for key in keys:
            val = item.get(key, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val) if val else ""
            row.append(val if val is not None else "")
        rows.append(row)

    if HAS_PANDAS:
        df = pd.DataFrame(rows, columns=headers)
        df.to_excel(filepath, index=False, engine="openpyxl")
    elif HAS_OPENPYXL:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "매물목록"
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(filepath)
    else:
        raise ImportError(
            "엑셀 저장을 위해 pandas 또는 openpyxl 패키지가 필요합니다.\n"
            "pip install pandas openpyxl"
        )

    return os.path.abspath(filepath)


def default_filename(region_name: str = "") -> str:
    """기본 파일명 생성: 매물목록_지역명_날짜.xlsx"""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    region = region_name.replace(" ", "_").strip() or "지역"
    return f"매물목록_{region}_{date_str}.xlsx"


# 지역 설정: cortarNo -> (lat, lon, display_name)
# region_config.json 파일이 있으면 병합 (같은 디렉터리)
_DEFAULT_REGIONS: Dict[str, tuple] = {
    "5119000000": (37.164232, 128.985713, "강원도 태백시"),
    "1168010100": (37.5172, 127.0473, "서울 강남구 역삼동"),
    "1168010800": (37.5045, 127.0489, "서울 강남구 삼성동"),
    "1111010100": (37.5704, 126.9853, "서울 종로구 청운동"),
    "2611010100": (35.1028, 129.0403, "부산 해운대구 우동"),
}


def _load_region_config() -> Dict[str, tuple]:
    """기본 설정 + region_config.json 병합"""
    import json
    config = dict(_DEFAULT_REGIONS)
    config_path = os.path.join(os.path.dirname(__file__), "region_config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                extra = json.load(f)
            for cortar_no, v in extra.items():
                if isinstance(v, (list, tuple)) and len(v) >= 3:
                    config[cortar_no] = (float(v[0]), float(v[1]), str(v[2]))
        except Exception:
            pass
    return config


REGION_CONFIG = _load_region_config()
