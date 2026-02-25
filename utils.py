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


def _items_to_tabular(
    items: List[Dict[str, Any]],
) -> tuple[list[str], list[str], list[list[Any]]]:
    """TABLE_COLUMNS 기반으로 헤더/키/행 데이터 생성"""
    if not items:
        raise ValueError("저장할 매물 데이터가 없습니다.")

    headers = [col[1] for col in TABLE_COLUMNS]
    keys = [col[0] for col in TABLE_COLUMNS]

    rows: list[list[Any]] = []
    for item in items:
        row: list[Any] = []
        for key in keys:
            val = item.get(key, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val) if val else ""
            row.append(val if val is not None else "")
        rows.append(row)

    return headers, keys, rows


def items_to_dataframe(items: List[Dict[str, Any]]):
    """매물 목록을 pandas.DataFrame으로 변환 (Streamlit/Jupyter 재사용용)"""
    if not HAS_PANDAS:
        raise ImportError(
            "데이터프레임 생성을 위해 pandas 패키지가 필요합니다.\n"
            "pip install pandas"
        )

    headers, _, rows = _items_to_tabular(items)
    return pd.DataFrame(rows, columns=headers)


def save_to_excel(items: List[Dict[str, Any]], filepath: str) -> str:
    """
    매물 목록을 엑셀 파일로 저장
    Returns: 저장된 파일 경로
    """
    headers, _, rows = _items_to_tabular(items)

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


def save_items_to_ipynb(
    items: List[Dict[str, Any]],
    filepath: str,
    region_name: str = "",
) -> str:
    """
    매물 목록을 Jupyter Notebook(.ipynb) 파일로 저장
    - 첫 코드 셀에서 pandas.DataFrame을 `df` 변수로 생성
    """
    if not HAS_PANDAS:
        raise ImportError(
            "ipynb 저장을 위해 pandas 패키지가 필요합니다.\n"
            "pip install pandas"
        )

    try:
        import nbformat
        from nbformat.v4 import new_notebook, new_code_cell
    except ImportError:
        raise ImportError(
            "ipynb 저장을 위해 nbformat 패키지가 필요합니다.\n"
            "pip install nbformat"
        )

    df = items_to_dataframe(items)
    records = df.to_dict(orient="records")

    code_lines = [
        "import pandas as pd",
        f"# 지역: {region_name}" if region_name else "# 네이버 부동산 매물 목록",
        f"data = {repr(records)}",
        "df = pd.DataFrame(data)",
        "df",
    ]
    code = "\n".join(code_lines)

    nb = new_notebook(cells=[new_code_cell(code)])
    nbformat.write(nb, filepath)
    return os.path.abspath(filepath)


def _load_region_config() -> Dict[str, tuple]:
    """region_config.json 파일에서 지역 설정 로드"""
    import json

    config_path = os.path.join(os.path.dirname(__file__), "region_config.json")
    config = {}

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for cortar_no, v in data.items():
                if isinstance(v, (list, tuple)) and len(v) >= 3:
                    config[cortar_no] = (float(v[0]), float(v[1]), str(v[2]))
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
    
    return config


REGION_CONFIG = _load_region_config()
