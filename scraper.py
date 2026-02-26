"""
네이버 부동산 API 스크래퍼 (정리본 + 이미지 크롤링 통합)
- clusterList: 지도/지역 범위 내 매물 클러스터 및 totCnt 계산
- articleList: 매물 목록 (페이지네이션)
- download_image: 매물 이미지 다운로드
- get_article_image_urls: 매물 코드(atclNo)로 상세 페이지 이미지 URL 목록 조회

[원리: Network(Fetch/XHR)로 API 찾는 방법]
1. 브라우저에서 매물 상세 페이지를 연다 (예: m.land.naver.com/article/info/12345).
2. F12 → Network 탭 → 상단 필터에서 "Fetch/XHR"만 선택한다.
   (이렇게 하면 페이지가 로드될 때 JavaScript가 호출하는 "데이터 API"만 보인다.)
3. 페이지가 뜨면서 생기는 요청 목록을 본다. 보통 다음처럼 보인다:
   - Request URL: https://fin.land.naver.com/front-api/v1/article/basicInfo?articleId=12345&realEstateType=APT&tradeType=B1
   - Request Method: GET
4. 그 요청을 클릭 → "Response" 탭을 보면 JSON이 나온다. 여기 안에 매물 상세(이미지 URL 목록 포함)가 있다.
5. 정리하면:
   - "누가": fin.land.naver.com (실제 데이터를 주는 서버)
   - "어디": /front-api/v1/article/basicInfo
   - "뭘 넘기나": 쿼리스트링 articleId, realEstateType, tradeType
   - "뭘 받나": JSON → result 안에 이미지 URL들이 들어 있음
6. 그래서 우리 코드는 "브라우저가 하는 그 GET 요청"을 그대로 Python requests로 흉내 내서,
   같은 URL·같은 파라미터로 호출하고, 받은 JSON에서 이미지 URL만 골라 쓰는 것이다.
   (이미지는 Network에서 "Img" 필터로 보면 uploadfile_... 같은 요청으로 따로 로드되는데,
   그건 "이미지 URL을 어디서 얻었는가"가 중요하므로, 먼저 Fetch/XHR에서 URL을 준 API를 찾는 것이다.)
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
# 상세 정보(이미지 포함)는 fin.land.naver.com Front API 사용
FRONT_API_BASE = "https://fin.land.naver.com"
ARTICLE_BASIC_INFO_URL = f"{FRONT_API_BASE}/front-api/v1/article/basicInfo"
# 매물 갤러리 이미지 목록 (articleNumber만 필요, 이미지 전용 API)
ARTICLE_GALLERY_IMAGES_URL = f"{FRONT_API_BASE}/front-api/v1/article/galleryImages"

# 매물/거래 유형 필터 (필요 시 여기만 바꾸면 됨)
RLET_TP_CD = "OR:APT:JGC:OPST:ABYG:OBYG:VL:YR:DSD:JWJT:SGJT:DDDGG"
TRAD_TP_CD = "B1:B2:B3"

REQUEST_DELAY = 0.8  # 차단 방지

# 이미지 저장할 폴더 생성
IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)


def _headers() -> Dict[str, str]:
    """모바일 브라우저처럼 보이게 하는 API 요청용 헤더"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": "https://m.land.naver.com/",
        "Accept": "application/json",
    }


def _image_headers() -> Dict[str, str]:
    """이미지 다운로드 차단 우회용 헤더 (Network 탭 참고)"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Referer": "https://isale.land.naver.com/",
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


def download_image(img_url: str, save_path: str) -> bool:
    """단일 이미지 다운로드"""
    if not img_url:
        return False
    
    try:
        resp = requests.get(img_url, headers=_image_headers(), timeout=10)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as e:
        print(f"이미지 다운로드 에러 ({img_url}): {e}")
        return False


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


def get_full_size_image_url(url: str) -> str:
    """
    썸네일 URL을 원본에 가까운 크기 URL로 변환 (앱에서 대표이미지 등 표시용).
    네이버 landthumb/phinf는 ?type= 제거 시 큰 이미지를 반환함.
    """
    return _thumbnail_to_full_size_url(url or "")


def _thumbnail_to_full_size_url(url: str) -> str:
    """
    네이버 landthumb/phinf 이미지 URL에서 size 제한을 제거해 원본에 가까운 크기로 요청.
    ?type=m562 같은 쿼리를 제거하면 썸네일이 아닌 큰 이미지를 받을 수 있음.
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
        # type, udate 등 크기/캐시 관련 파라미터 제거 → 원본(또는 최대 크기) 반환
        q.pop("type", None)
        q.pop("udate", None)
        new_query = urlencode(q, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        return u


def _extract_image_urls_from_json(obj: Any) -> List[str]:
    """JSON 객체를 재귀적으로 탐색해 이미지 URL 문자열만 수집"""
    urls: List[str] = []
    if isinstance(obj, list):
        for x in obj:
            urls.extend(_extract_image_urls_from_json(x))
    elif isinstance(obj, dict):
        # 객체에 url/src/imageUrl 등이 있으면 수집
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


def _looks_like_image_url(s: str) -> bool:
    """매물 이미지로 보이는 URL인지 (아이콘/로고 제외)"""
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


def _parse_gallery_result(data: Any) -> List[str]:
    """galleryImages API 응답에서 imageUrl 목록만 추출"""
    if not isinstance(data, dict):
        return []
    result = data.get("result")
    if not isinstance(result, list):
        return []
    urls = []
    for item in result:
        if isinstance(item, dict):
            u = item.get("imageUrl") or item.get("url") or item.get("imgUrl")
            if u and isinstance(u, str) and u.strip().startswith("http") and _looks_like_image_url(u):
                urls.append(u.strip())
    return list(dict.fromkeys(urls))


def fetch_article_gallery_images(article_id: str) -> List[str]:
    """
    fin.land.naver.com galleryImages API로 매물 사진 URL 목록만 조회.
    articleNumber만 필요하므로 basicInfo보다 먼저 시도하는 것이 좋음.
    응답: result 배열 → 각 항목의 imageUrl
    """
    if not article_id:
        return []
    article_id = str(article_id).strip()
    params = {"articleNumber": article_id}
    # 시도할 URL 후보 (경로가 서비스 버전에 따라 다를 수 있음)
    candidates = [
        ARTICLE_GALLERY_IMAGES_URL,
        f"{FRONT_API_BASE}/api/article/galleryImages",
    ]
    for url in candidates:
        try:
            resp = requests.get(url, params=params, headers=_front_headers(), timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not isinstance(data, dict):
                continue
            # isSuccess 없어도 result만 있으면 파싱 시도
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
    real_estate_type: 매물유형코드 (예: APT, OPST, VL)
    trade_type: 거래유형코드 (예: B1=매매, B2=전세, B3=월세)
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
    rlet_tp_cd, trad_tp_cd가 있으면 fin.land.naver.com Front API(basicInfo)를 먼저 시도합니다.
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
                        urls = []
                        for x in lst:
                            if isinstance(x, str) and x.startswith("http") and _looks_like_image_url(x):
                                urls.append(x)
                            elif isinstance(x, dict):
                                u = x.get("url") or x.get("src") or x.get("imageUrl") or x.get("imgUrl")
                                if u:
                                    urls.append(_normalize_image_url(u) if u.startswith("/") else u)
                        if urls:
                            return [_thumbnail_to_full_size_url(u) for u in dict.fromkeys(urls)]
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

    # 4) 상세 페이지 HTML에서 img src 추출
    try:
        resp = requests.get(f"{BASE_URL}/article/info/{atcl_no}", headers=_headers(), timeout=10)
        if resp.status_code == 200:
            urls = _extract_image_urls_from_html(resp.text)
            if urls:
                return [_thumbnail_to_full_size_url(u) for u in urls]
    except Exception:
        pass

    return []


def _extract_image_urls_from_html(html: str) -> List[str]:
    """HTML 문자열에서 매물 관련 이미지 URL만 추출 (네이버/부동산 도메인)"""
    urls = []
    # data-src, src 등
    for pattern in (
        r'<(?:img|Image)[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
        r'["\'](https?://(?:landthumb-phinf\.pstatic\.net|naver-file\.ebunyang\.co\.kr|phinf\.pstatic\.net)[^"\']+)["\']',
        r'["\'](https?://[^"\']*uploadfile_[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
    ):
        for m in re.finditer(pattern, html, re.I):
            u = m.group(1).strip()
            if u and not any(x in u for x in ("sp2x", "loading", "openhand", "icon", "logo")):
                if u.startswith("//"):
                    u = "https:" + u
                urls.append(u)
    return list(dict.fromkeys(urls))


def calc_bounds(lat: float, lon: float, z: int = 12) -> Tuple[float, float, float, float]:
    """중심좌표 기반 지도 범위(btm, lft, top, rgt) 계산"""
    delta_lat = 0.09
    delta_lon = 0.18
    return (lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def fetch_cluster_list(cortar_no: str, lat: float, lon: float, z: int = 12) -> Dict[str, Any]:
    """clusterList 호출"""
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
    """clusterList → articleList 호출로 매물 수집 및 이미지 저장"""
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
            cortar_no=cortar_no, lat=lat, lon=lon, tot_cnt=tot_cnt, page=page,
            btm=btm, lft=lft, top=top, rgt=rgt
        )

        items = result["body"]
        
        # ✅ 받아온 매물 목록을 돌면서 대표 이미지(repImgUrl) 다운로드
        for item in items:
            img_url = item.get("repImgUrl")
            atcl_no = item.get("atclNo") # 매물 번호
            
            if img_url and atcl_no:
                # 썸네일 경로가 /... 형태로 오는 경우가 있어 도메인을 붙여줍니다.
                full_img_url = f"https://landthumb-phinf.pstatic.net{img_url}" if img_url.startswith("/") else img_url
                save_path = os.path.join(IMAGE_DIR, f"{atcl_no}.jpg")
                
                # 중복 다운로드 방지
                if not os.path.exists(save_path):
                    download_image(full_img_url, save_path)
                    time.sleep(0.3) # 너무 잦은 이미지 요청 방지
                    
            all_items.append(item)
            
            # 여기서 limit 체크
            if len(all_items) >= limit:
                break

        if progress_callback:
            progress_callback(min(len(all_items), limit), min(tot_cnt, limit), f"수집 중... ({len(all_items)})")

        if len(all_items) >= limit or not result["more"]:
            break

        page += 1

    return all_items[:limit]