"""
네이버 부동산 API 스크래퍼 (정리본)
- clusterList: 지도/지역 범위 내 매물 클러스터 및 totCnt 계산
- articleList: 매물 목록 (페이지네이션)
"""

import time
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlencode

import requests

BASE_URL = "https://m.land.naver.com"
CLUSTER_LIST_URL = f"{BASE_URL}/cluster/clusterList"
ARTICLE_LIST_URL = f"{BASE_URL}/cluster/ajax/articleList"

# 매물/거래 유형 필터 (필요 시 여기만 바꾸면 됨)
RLET_TP_CD = "OR:APT:JGC:OPST:ABYG:OBYG:VL:YR:DSD:JWJT:SGJT:DDDGG"
TRAD_TP_CD = "B1:B2:B3"

REQUEST_DELAY = 0.8  # 차단 방지


def _headers() -> Dict[str, str]:
    """모바일 브라우저처럼 보이게 하는 헤더"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": "https://m.land.naver.com/",
        "Accept": "application/json",
    }


def calc_bounds(lat: float, lon: float, z: int = 12) -> Tuple[float, float, float, float]:
    """
    중심좌표 기반 지도 범위(btm, lft, top, rgt) 계산
    - 현재는 고정 delta 사용 (원하면 z에 따라 delta를 조정하도록 바꿀 수 있음)
    """
    delta_lat = 0.09
    delta_lon = 0.18
    return (lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def fetch_cluster_list(cortar_no: str, lat: float, lon: float, z: int = 12) -> Dict[str, Any]:
    """
    clusterList 호출
    반환:
      - tot_cnt: 클러스터 count 합 (총 매물 수 추정)
      - region_name: 지역명 (가능한 경우)
      - bounds: btm/lft/top/rgt
    """
    btm, lft, top, rgt = calc_bounds(lat, lon, z)

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
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "success":
        raise RuntimeError(f"clusterList API 오류: {data.get('code', 'unknown')}")

    # tot_cnt 계산: ARTICLE 배열의 count 합
    articles = data.get("data", {}).get("ARTICLE", [])
    tot_cnt = sum(a.get("count", 1) for a in articles)

    # regionName 추출
    region_name = (
        data.get("data", {})
        .get("cortar", {})
        .get("detail", {})
        .get("regionName", "")
    )

    return {
        "tot_cnt": tot_cnt,
        "region_name": region_name,
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
) -> Dict[str, Any]:
    """
    articleList 호출
    반환:
      - body: 매물 리스트 (List[dict])
      - more: 다음 페이지 존재 여부
      - page: 현재 페이지
    """
    if btm is None:
        btm, lft, top, rgt = calc_bounds(lat, lon, z)

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
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "success":
        raise RuntimeError(f"articleList API 오류: {data.get('code', 'unknown')}")

    return {
        "body": data.get("body", []),
        "more": data.get("more", False),
        "page": data.get("page", page),
    }


def scrape_articles(
    cortar_no: str,
    lat: float,
    lon: float,
    limit: int = 50,
    progress_callback=None,
    cancel_check=None,
) -> List[Dict[str, Any]]:
    """
    clusterList → articleList 호출로 매물 수집
    - limit 만큼만 모이면 중단 (대시보드용 빠른 수집)
    """
    time.sleep(REQUEST_DELAY)
    cluster = fetch_cluster_list(cortar_no, lat, lon)
    tot_cnt = cluster["tot_cnt"]
    btm, lft, top, rgt = cluster["btm"], cluster["lft"], cluster["top"], cluster["rgt"]

    if tot_cnt == 0:
        return []

    all_items: List[Dict[str, Any]] = []
    page = 1

    if progress_callback:
        progress_callback(0, min(tot_cnt, limit), "매물 수집 시작...")

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

        items = result["body"]
        all_items.extend(items)

        if progress_callback:
            progress_callback(min(len(all_items), limit), min(tot_cnt, limit), f"수집 중... ({len(all_items)})")

        # ✅ limit만 모이면 중단
        if len(all_items) >= limit:
            break

        if not result["more"]:
            break

        page += 1

    return all_items[:limit]