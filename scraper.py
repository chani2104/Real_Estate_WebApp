"""
네이버 부동산 API 스크래퍼
- clusterList: 클러스터 정보 및 totCnt 획득
- articleList: 매물 상세 목록 (페이지네이션)
"""

import time
import requests
from typing import Optional, List, Tuple
from urllib.parse import urlencode


# API 상수
BASE_URL = "https://m.land.naver.com"
CLUSTER_LIST_URL = f"{BASE_URL}/cluster/clusterList"
ARTICLE_LIST_URL = f"{BASE_URL}/cluster/ajax/articleList"

# 매물/거래 유형 (ApiRef.md 기준)
RLET_TP_CD = "OR:APT:JGC:OPST:ABYG:OBYG:VL:YR:DSD:JWJT:SGJT:DDDGG"
TRAD_TP_CD = "B1:B2:B3"

# 요청 간격 (초) - 차단 방지
REQUEST_DELAY = 0.8


def _get_headers() -> dict:
    """모바일 브라우저 UA 및 Referer 설정 (ApiRef 권장)"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": "https://m.land.naver.com/",
        "Accept": "application/json",
    }


def _calc_bounds(lat: float, lon: float, z: int = 12) -> Tuple[float, float, float, float]:
    """중심 좌표로부터 지도 범위(btm, lft, top, rgt) 계산"""
    delta_lat = 0.09
    delta_lon = 0.18
    return (
        lat - delta_lat,  # btm
        lon - delta_lon,   # lft
        lat + delta_lat,   # top
        lon + delta_lon,   # rgt
    )


def fetch_cluster_list(
    cortar_no: str,
    lat: float,
    lon: float,
    z: int = 12,
) -> dict:
    """
    clusterList API 호출
    Returns: {"tot_cnt": int, "region_name": str, "data": dict} or raises
    """
    btm, lft, top, rgt = _calc_bounds(lat, lon, z)
    params = {
        "view": "atcl",
        "cortarNo": cortar_no,
        "rletTpCd": RLET_TP_CD,
        "tradTpCd": TRAD_TP_CD,
        "z": z,
        "lat": lat,
        "lon": lon,
        "btm": btm,
        "lft": lft,
        "top": top,
        "rgt": rgt,
        "pCortarNo": "",
    }
    url = f"{CLUSTER_LIST_URL}?{urlencode(params)}"
    resp = requests.get(url, headers=_get_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "success":
        raise RuntimeError(f"clusterList API 오류: {data.get('code', 'unknown')}")

    articles = data.get("data", {}).get("ARTICLE", [])
    tot_cnt = sum(item.get("count", 1) for item in articles)

    region_name = ""
    cortar = data.get("data", {}).get("cortar", {})
    if cortar:
        detail = cortar.get("detail", {})
        region_name = detail.get("regionName", "")

    return {
        "tot_cnt": tot_cnt,
        "region_name": region_name,
        "data": data,
        "btm": btm,
        "lft": lft,
        "top": top,
        "rgt": rgt,
    }


def fetch_article_list(
    cortar_no: str,
    lat: float,
    lon: float,
    tot_cnt: int,
    page: int = 1,
    btm: Optional[float] = None,
    lft: Optional[float] = None,
    top: Optional[float] = None,
    rgt: Optional[float] = None,
    z: int = 12,
) -> dict:
    """
    articleList API 호출
    Returns: {"body": list, "more": bool, "page": int}
    """
    if btm is None:
        btm, lft, top, rgt = _calc_bounds(lat, lon, z)

    params = {
        "rletTpCd": RLET_TP_CD,
        "tradTpCd": TRAD_TP_CD,
        "z": z,
        "lat": lat,
        "lon": lon,
        "btm": btm,
        "lft": lft,
        "top": top,
        "rgt": rgt,
        "showR0": "",
        "totCnt": tot_cnt,
        "cortarNo": cortar_no,
        "page": page,
    }
    url = f"{ARTICLE_LIST_URL}?{urlencode(params)}"
    resp = requests.get(url, headers=_get_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "success":
        raise RuntimeError(f"articleList API 오류: {data.get('code', 'unknown')}")

    return {
        "body": data.get("body", []),
        "more": data.get("more", False),
        "page": data.get("page", page),
    }


def scrape_all_articles(
    cortar_no: str,
    lat: float,
    lon: float,
    progress_callback=None,
    cancel_check=None,
) -> List[dict]:
    """
    clusterList → articleList 순차 호출로 전체 매물 수집
    progress_callback(current, total, message)
    cancel_check() -> True면 중단
    """
    # 1. clusterList
    time.sleep(REQUEST_DELAY)
    cluster = fetch_cluster_list(cortar_no, lat, lon)
    tot_cnt = cluster["tot_cnt"]
    btm, lft, top, rgt = cluster["btm"], cluster["lft"], cluster["top"], cluster["rgt"]

    if progress_callback:
        progress_callback(0, tot_cnt, "매물 목록 조회 중...")

    if tot_cnt == 0:
        return []

    all_items = []
    page = 1

    while True:
        if cancel_check and cancel_check():
            break

        time.sleep(REQUEST_DELAY)
        result = fetch_article_list(
            cortar_no=cortar_no,
            lat=lat,
            lon=lon,
            tot_cnt=tot_cnt,
            page=page,
            btm=btm,
            lft=lft,
            top=top,
            rgt=rgt,
        )

        items = result.get("body", [])
        all_items.extend(items)

        if progress_callback:
            progress_callback(len(all_items), tot_cnt, f"수집 중... ({len(all_items)}/{tot_cnt})")

        if not result.get("more", False):
            break

        page += 1

    return all_items
