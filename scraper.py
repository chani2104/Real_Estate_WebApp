"""
네이버 부동산 API 스크래퍼 (정리본 + 이미지 크롤링)
- clusterList: 지도/지역 범위 내 매물 클러스터 및 totCnt 계산
- articleList: 매물 목록 (페이지네이션)
- get_article_image_urls: 매물 코드(atclNo)로 상세 페이지 이미지 URL 목록 조회
"""

import os
import re
import time
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

import requests

BASE_URL = "https://m.land.naver.com"
CLUSTER_LIST_URL = f"{BASE_URL}/cluster/clusterList"
ARTICLE_LIST_URL = f"{BASE_URL}/cluster/ajax/articleList"

# 상세 정보(이미지 포함)는 fin.land.naver.com Front API 사용 (일부 매물은 galleryImages/api만 동작)
FRONT_API_BASE = "https://fin.land.naver.com"
ARTICLE_BASIC_INFO_URL = f"{FRONT_API_BASE}/front-api/v1/article/basicInfo"
ARTICLE_GALLERY_IMAGES_URL = f"{FRONT_API_BASE}/front-api/v1/article/galleryImages"

# 매물/거래 유형 필터 (원하면 여기만 바꿔도 됨)
RLET_TP_CD = "OR:APT:JGC:OPST:ABYG:OBYG:VL:YR:DSD:JWJT:SGJT:DDDGG"
TRAD_TP_CD = "B1:B2:B3"

REQUEST_DELAY = 0.8  # 차단 방지


def _headers() -> Dict[str, str]:
    """모바일 브라우저처럼 보이게 하는 기본 API 헤더"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": "https://m.land.naver.com/",
        "Accept": "application/json",
    }


def _front_headers() -> Dict[str, str]:
    """fin.land.naver.com Front API 요청용 헤더"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://fin.land.naver.com/",
        "Accept": "application/json",
    }


def _normalize_image_url(url: str) -> str:
    """상대 경로 이미지 URL에 도메인 붙이기 (목록 API repImgUrl용)"""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://landthumb-phinf.pstatic.net" + u
    return u


def _thumbnail_to_full_size_url(url: str) -> str:
    """
    네이버 landthumb/phinf 이미지 URL에서 size 제한을 제거해 원본에 가까운 크기로 요청.
    ?type=, udate 등 썸네일/캐시 관련 쿼리를 제거.
    """
    if not url or not isinstance(url, str):
        return url or ""
    u = url.strip()
    if "landthumb-phinf.pstatic.net" not in u and "phinf.pstatic.net" not in u:
        return u
    try:
        parsed = urlparse(u)
        if not parsed.query:
            return u
        q = parse_qs(parsed.query, keep_blank_values=True)
        q.pop("type", None)
        q.pop("udate", None)
        new_query = urlencode(q, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        return u


def _looks_like_image_url(s: str) -> bool:
    """매물 이미지로 보이는 URL인지 (아이콘/로고 등은 제외)"""
    s = s.lower()
    if any(x in s for x in ("sp2x", "loading", "openhand", "icon", "logo", "sprite")):
        return False
    return (
        "pstatic.net" in s
        or "naver-file" in s
        or "ebunyang" in s
        or "uploadfile_" in s
        or s.endswith(".jpg")
        or s.endswith(".jpeg")
        or s.endswith(".png")
        or s.endswith(".webp")
    )


def _extract_image_urls_from_html(html: str) -> List[str]:
    """HTML 문자열에서 매물 관련 이미지 URL만 추출 (네이버/부동산 도메인 위주, 최대한 관대하게)"""
    urls: List[str] = []
    patterns = (
        # img/data-src 속성
        r'<(?:img|Image)[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
        # 네이버 부동산 이미지 도메인
        r'["\'](https?://(?:landthumb-phinf\.pstatic\.net|naver-file\.ebunyang\.co\.kr|phinf\.pstatic\.net)[^"\']+)["\']',
        # uploadfile_ 패턴
        r'["\'](https?://[^"\']*uploadfile_[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
        # 마지막으로, 페이지 내의 모든 jpg/png/webp URL (필터로 한번 더 거름)
        r'["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
    )
    for pattern in patterns:
        for m in re.finditer(pattern, html, re.I):
            u = m.group(1).strip()
            if not u:
                continue
            if u.startswith("//"):
                u = "https:" + u
            if not _looks_like_image_url(u):
                continue
            urls.append(u)
    # 중복 제거 유지
    return list(dict.fromkeys(urls))


def _extract_image_urls_from_json(obj: Any) -> List[str]:
    """JSON 객체를 재귀적으로 탐색해 이미지 URL 문자열만 수집"""
    urls: List[str] = []
    if isinstance(obj, list):
        for x in obj:
            urls.extend(_extract_image_urls_from_json(x))
    elif isinstance(obj, dict):
        for key in ("url", "src", "imageUrl", "imgUrl", "imgSrc", "path"):
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                u = _normalize_image_url(v) if v.startswith("/") else v.strip()
                if u.startswith("http") and _looks_like_image_url(u):
                    urls.append(u)
        for v in obj.values():
            urls.extend(_extract_image_urls_from_json(v))
    elif isinstance(obj, str) and obj.strip().startswith("http") and _looks_like_image_url(obj):
        urls.append(obj.strip())
    return urls


def _parse_gallery_result(data: Any) -> List[str]:
    """galleryImages API 응답에서 imageUrl 목록만 추출"""
    if not isinstance(data, dict):
        return []
    result = data.get("result")
    if not isinstance(result, list):
        return []
    urls: List[str] = []
    for item in result:
        if isinstance(item, dict):
            u = item.get("imageUrl") or item.get("url") or item.get("imgUrl")
            if u and isinstance(u, str) and u.strip().startswith("http") and _looks_like_image_url(u):
                urls.append(u.strip())
    # 중복 제거
    return list(dict.fromkeys(urls))


def fetch_article_gallery_images(article_id: str) -> List[str]:
    """
    fin.land.naver.com galleryImages API로 매물 사진 URL 목록 조회.
    articleNumber만 필요하므로 basicInfo보다 빠르고 단순.
    """
    if not article_id:
        return []
    article_id = str(article_id).strip()
    params = {"articleNumber": article_id}
    candidates = [
        ARTICLE_GALLERY_IMAGES_URL,
        f"{FRONT_API_BASE}/api/article/galleryImages",  # 일부 구버전 대응
    ]
    for url in candidates:
        try:
            resp = requests.get(url, params=params, headers=_front_headers(), timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not isinstance(data, dict):
                continue
            urls = _parse_gallery_result(data)
            if urls:
                return [_thumbnail_to_full_size_url(u) for u in urls]
            if data.get("isSuccess") is False:
                continue
        except Exception:
            continue
    return []


def fetch_article_basic_info(
    article_id: str,
    real_estate_type: str,
    trade_type: str,
) -> Optional[Dict[str, Any]]:
    """
    fin.land.naver.com Front API로 매물 상세 정보 조회.
    real_estate_type: 매물유형코드 (APT, OPST, VL 등)
    trade_type: 거래유형코드 (B1=매매, B2=전세, B3=월세)
    """
    if not article_id or not real_estate_type or not trade_type:
        return None
    try:
        resp = requests.get(
            ARTICLE_BASIC_INFO_URL,
            params={
                "articleId": article_id,
                "realEstateType": real_estate_type.strip(),
                "tradeType": trade_type.strip(),
            },
            headers=_front_headers(),
            timeout=12,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, dict) and data.get("isSuccess") and isinstance(data.get("result"), dict):
            return data["result"]
    except Exception:
        pass
    return None


def get_article_image_urls(
    atcl_no: str,
    rlet_tp_cd: Optional[str] = None,
    trad_tp_cd: Optional[str] = None,
) -> List[str]:
    """
    매물 코드(atclNo)로 해당 매물 상세에 등록된 이미지 URL 목록을 조회합니다.
    rlet_tp_cd, trad_tp_cd를 알면 fin.land basicInfo까지 병행 시도.

    ⚠️ 주의: 네이버 쪽 정책/차단 상황에 따라
    - galleryImages / basicInfo API는 실패할 수 있고
    - 이 함수는 "가능하면" 방 사진(원본/갤러리)을 가져오는 용도입니다.
    확실한 대표 썸네일은 목록 API의 repImgUrl을 사용하는 것이 안전합니다.
    """
    if not atcl_no:
        return []
    atcl_no = str(atcl_no).strip()

    # 1) fin.land galleryImages API (매물번호만으로 이미지 목록 조회, 우선 시도)
    urls = fetch_article_gallery_images(atcl_no)
    if urls:
        return urls

    # 2) fin.land basicInfo API (상세 정보에서 이미지 추출, 매물/거래 유형 코드 필요)
    if rlet_tp_cd and trad_tp_cd:
        result = fetch_article_basic_info(atcl_no, rlet_tp_cd, trad_tp_cd)
        if result:
            urls = _extract_image_urls_from_json(result)
            if urls:
                return [_thumbnail_to_full_size_url(u) for u in dict.fromkeys(urls)]

    # 3) m.land articleInfo/ajax 시도
    try:
        resp = requests.get(
            f"{BASE_URL}/article/ajax/articleInfo",
            params={"articleNo": atcl_no},
            headers={**_headers(), "Accept": "application/json, text/plain, */*"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                for key in ("imageList", "imgList", "images", "photoList", "atclImgList"):
                    lst = data.get(key)
                    if isinstance(lst, list) and lst:
                        cand: List[str] = []
                        for x in lst:
                            if isinstance(x, str):
                                u = x.strip()
                                if u.startswith("/"):
                                    u = _normalize_image_url(u)
                                if u.startswith("http") and _looks_like_image_url(u):
                                    cand.append(u)
                            elif isinstance(x, dict):
                                u = x.get("url") or x.get("src") or x.get("imageUrl") or x.get("imgUrl")
                                if u:
                                    u = _normalize_image_url(u) if u.startswith("/") else u
                                    if u.startswith("http") and _looks_like_image_url(u):
                                        cand.append(u)
                        if cand:
                            return [_thumbnail_to_full_size_url(u) for u in dict.fromkeys(cand)]

                # JSON 전체에서 이미지 URL 긁기
                urls = _extract_image_urls_from_json(data)
                if urls:
                    return [_thumbnail_to_full_size_url(u) for u in dict.fromkeys(urls)]

                body = data.get("body") or data.get("html") or ""
                if isinstance(body, str) and ("img" in body or "uploadfile" in body):
                    urls = _extract_image_urls_from_html(body)
                    if urls:
                        return [_thumbnail_to_full_size_url(u) for u in urls]
    except Exception:
        pass

    # 4) m.land 상세 페이지 HTML에서 직접 img src 추출
    try:
        resp = requests.get(f"{BASE_URL}/article/info/{atcl_no}", headers=_headers(), timeout=10)
        if resp.status_code == 200:
            urls = _extract_image_urls_from_html(resp.text)
            if urls:
                return [_thumbnail_to_full_size_url(u) for u in urls]
    except Exception:
        pass

    return []


def calc_bounds(lat: float, lon: float, z: int = 12) -> Tuple[float, float, float, float]:
    """
    중심좌표 기반 지도 범위(btm, lft, top, rgt) 계산
    - 고정 delta 사용(원하면 z에 따라 가변으로 변경 가능)
    """
    delta_lat = 0.09
    delta_lon = 0.18
    return (lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def fetch_cluster_list(cortar_no: str, lat: float, lon: float, z: int = 12) -> Dict[str, Any]:
    """
    clusterList 호출
    반환:
      - tot_cnt: 클러스터 count 합(총 매물 수 추정)
      - region_name: 지역명(가능한 경우)
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

    # totCnt 계산: ARTICLE 배열의 count 합
    articles = data.get("data", {}).get("ARTICLE", [])
    tot_cnt = sum(a.get("count", 1) for a in articles)

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
    """articleList 호출"""
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
    clusterList → articleList 순서로 매물 수집
    - limit 만큼만 모이면 중단(빠른 UI용)
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

        if len(all_items) >= limit:
            break
        if not result["more"]:
            break

        page += 1

    return all_items[:limit]