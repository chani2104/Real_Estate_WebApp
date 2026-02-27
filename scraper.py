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
# 매물 유형 : 아파트(APT), 오피스텔(OPST), 상가주택(JGC), 단독/다가구(ABYG), 빌라(VL), 다세대(DDDGG)
TRAD_TP_CD = "B1:B2:B3"
# 거래 유형 : 매매(B1), 전세(B2), 월세(B3)

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

    # _image_headers() : 사진을 다운로드할 때 씀. 네이버 이미지 서버는 외부 사이트에서 이미지를 무단으로 퍼가는 것을 막기위해 referer를 검사. 그래서 referer에 네이버 주소 (isale.land.naver.com)를 적어서 서버를 속여야함 



def _front_headers() -> Dict[str, str]:
    """fin.land.naver.com Front API 요청용 헤더"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://fin.land.naver.com/",
        "Accept": "application/json",  # 응답을 json형태로 달라!
    }
    # _front_headers() : 매물 상세 정보(JSON)를 조회할 때 씀. 파이썬 프로그램이 아니라 실제 크롬 브라우저(User-agent)로 요청을 보내야함. 응답은 json 형태로 달라고 명시


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
    #네이버 API가 던져주는 반쪽짜리 사진 주소를 온전한 인터넷 주소로 고쳐주는 역할
    # startswith("//") : 주소가 //로 시작하면 https:를 붙여서 온전한 주소로 만듦
    # startswith("/") : 주소가 /로 시작하면 landthumb-phinf.pstatic.net 도메인을 붙여서 온전한 주소로 만듦
    # return u : 주소가 이미 온전하면 그대로 반환


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

    # 데이터를 뒤지다가 키(key) 값에 url, imageUrl, src 등인 것을 발견하면 그 값을 꺼낸다.
    # 꺼낸 주소를 완전한 형태(http...)로 다듬은 뒤, 아래의 필터링 함수를 통과하면 최종 수집 목록(urls)에 추가


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
# 가짜 이미지 거름망
# 찾아낸 주소가 진짜 방 사진인지, 아니면 웹 페이지를 꾸미는 UI 이미지인지 판별 
# 주소에 icon, logo, sprite 등이 들어가면 가짜 이미지로 판단(False)
# 반대로 네이버 이미지 전용 서버(pstatic.net)에 있는 주소이거나 .jpg, .png, .webp 등의 확장자로 끝나면 진짜 매물 사진으로 인정함

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
    # 사진 주소 추출하는 핵심 로직
    # API가 던져준 복잡한 응답(JSON)을 파싱해서 사진 주소만 추출
    # 데이터 안에 있는 result 배열을 돌면서 imageUrl 이나 url 같은 키를 찾음
    # 앞서 보신 _looks_like_image_url로 진짜 매물 사진인지 검사한 후, 중복을 제거하여 깔끔한 리스트로 만듭니다.


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
    # 매물번호(article_id)만 들고 네이버 프론트 api 에 접속해 해당 매물의 모든 목록 요구
    # 네이버 서버 주소가 버전업으로 바뀔 것에 대비해 두 가지 url 후보(candidates)를 순서대로 찔러보는 에외처리
    # 정상적으로 사진 주소들을 받아내면, 마지막에 _thumbnail_to_full_size_url 함수를 통해 썸네일 크기가 아닌 원본 크기의 사진 주소로 변환


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
    # 어떻게든 매물 사진을 얻어내는 집념의 코드.. 
    # 네이버 API가 자주 바뀌거나 응답이 일정하지 않기 때문에, 한 가지 방법이 실패하면 다음 방법으로 시도하는 폴백 주고
    # 1. 갤러리 전용 API를 찔러본다
    # 2. 실패하면, 매물의 '기본 상세 정보(JSON)'을 몽땅 가져와서 그 안에서 사진 주소만 퍼냄 
    # 3. 또 실패하면, 구형 모바일 네이버 API (AJAX)를 호출해서 imageList, photoList 같은 단어를 이 잡듯이 뒤짐
    # 4. 최후의 수단으로 실제 사용자가 보는 웹페이지(html) 자체를 통째로 다운받아 이미지 태그를 강제로 긁어옴



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
# 검색 영역 설정
# 중심 좌표(위도, 경도)룰 기준으로 상하좌우 경계선을 계산해 가상의 사각형 검색 범위를 만듭니다


# 만들어진 사각형 영역과 지역 코드(cortar_no)를 네이버 서버에 보내, 해당 구역 내에
# 매물이 총 몇 개 있는지(tot_cnt)만 먼저 물어보고 가져온다
# 이제 매물 데이터를 하나하나 가져오기 (articleList) 전에 전체 물량을 파악하여 반복횟수(페이지수)를 결정하는데 중요한 포인트
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
    cortar_no: str,                # 검색할 지역의 법정동 코드 (예: 1111011500)
    lat: float,                    # 검색 중심점의 위도 좌표
    lon: float,                    # 검색 중심점의 경도 좌표
    tot_cnt: int,                  # 클러스터 내 전체 매물 개수 (앞선 단계에서 파악한 총량)
    page: int = 1,                 # 서버에 요청할 데이터 페이지 번호 (기본값 1)
    btm: Optional[float] = None,   # 검색 영역 사각형의 하단(남쪽) 위도 경계
    lft: Optional[float] = None,   # 검색 영역 사각형의 좌측(서쪽) 경도 경계
    top: Optional[float] = None,   # 검색 영역 사각형의 상단(북쪽) 위도 경계
    rgt: Optional[float] = None,   # 검색 영역 사각형의 우측(동쪽) 경도 경계
    z: int = 12,                   # 지도 줌(확대) 레벨 (기본값 12)
) -> Dict[str, Any]:
    """articleList 호출"""
    
    # 1. 검색 범위 검사 및 계산
    # 만약 하단 경계값(btm)이 입력되지 않았다면, 중심 좌표(lat, lon)를 기준으로 사각형 범위를 새로 계산합니다.
    if btm is None:
        btm, lft, top, rgt = calc_bounds(lat, lon, z)

    # 2. API 요청 파라미터 구성
    # 네이버 부동산 서버에 보낼 조건들을 딕셔너리로 묶습니다.
    params = {
        "rletTpCd": RLET_TP_CD,    # 가져올 매물 종류 (상단에서 정의한 아파트, 오피스텔 등)
        "tradTpCd": TRAD_TP_CD,    # 가져올 거래 종류 (상단에서 정의한 매매, 전세, 월세 등)
        "z": z,                    # 지도 줌 레벨
        "lat": lat,                # 중심 위도
        "lon": lon,                # 중심 경도
        "btm": btm,                # 하단 위도
        "lft": lft,                # 좌측 경도
        "top": top,                # 상단 위도
        "rgt": rgt,                # 우측 경도
        "showR0": "",              # 네이버 API 내부 규칙에 맞추기 위한 빈 값
        "totCnt": tot_cnt,         # 전체 매물 수 (서버가 페이징 처리 시 참고)
        "cortarNo": cortar_no,     # 지역(법정동) 코드
        "page": page,              # 현재 가져올 페이지 번호
    }

    # 3. 요청 URL 조립
    # 기본 API 주소 뒤에 '?키=값&키=값' 형태(쿼리스트링)로 파라미터를 인코딩하여 붙입니다.
    url = f"{ARTICLE_LIST_URL}?{urlencode(params)}"
    
    # 4. 데이터 요청 (GET)
    # 조립된 URL로 요청을 보냅니다. 봇 차단을 막기 위해 위장 헤더(_headers())를 씌우고, 15초 이상 걸리면 중단(timeout)합니다.
    resp = requests.get(url, headers=_headers(), timeout=15)
    
    # 5. 응답 상태 검증
    # HTTP 상태 코드가 200(정상)이 아니면 에러를 발생시켜 프로그램을 멈춥니다.
    resp.raise_for_status()
    
    # 6. JSON 파싱
    # 정상적으로 받은 응답 문자열을 파이썬에서 다루기 쉬운 딕셔너리 형태로 변환합니다.
    data = resp.json()

    # 7. 네이버 내부 에러 검증
    # HTTP 상태가 정상이더라도, 네이버 자체 API 결과 코드('code')가 'success'가 아니라면 에러를 발생시킵니다.
    if data.get("code") != "success":
        raise RuntimeError(f"articleList API 오류: {data.get('code', 'unknown')}")

    # 8. 최종 결과 반환
    # 전체 데이터 중 다음 처리에 필요한 핵심 정보 3가지만 뽑아서 딕셔너리로 반환합니다.
    return {
        "body": data.get("body", []),    # 실제 매물의 상세 정보들이 담긴 리스트
        "more": data.get("more", False), # 다음 페이지가 더 남아 있는지 여부 (True/False)
        "page": data.get("page", page),  # 방금 가져온 데이터의 페이지 번호
    }



def scrape_articles(
    cortar_no: str,                 # 검색할 지역의 법정동 코드 (예: 1111011500)
    lat: float,                     # 검색 중심점의 위도
    lon: float,                     # 검색 중심점의 경도
    limit: int = 50,                # 최대 수집할 매물 개수 (기본값 50개)
    progress_callback=None,         # Streamlit UI 등에 진행률 바를 업데이트하기 위한 함수
    cancel_check=None,              # 사용자가 '중단' 버튼을 눌렀는지 감지하는 함수
) -> List[Dict[str, Any]]:
    """clusterList → articleList 호출로 매물 수집 및 이미지 저장"""
    
    # 1. 초기 세팅: 전체 매물 개수와 검색 영역 파악
    # 서버 차단 방지를 위해 잠시 대기 후, 매물이 총 몇 개인지(tot_cnt)와 검색 영역(btm, lft 등)을 가져옵니다.
    time.sleep(REQUEST_DELAY)
    cluster = fetch_cluster_list(cortar_no, lat, lon)
    tot_cnt = cluster["tot_cnt"]
    btm, lft, top, rgt = cluster["btm"], cluster["lft"], cluster["top"], cluster["rgt"]

    # 해당 지역에 매물이 0개라면 더 진행할 필요 없이 빈 리스트를 반환합니다.
    if tot_cnt == 0:
        return []

    # 2. 수집 루프 준비
    all_items: List[Dict[str, Any]] = []  # 최종적으로 수집된 매물들을 차곡차곡 담을 빈 상자
    page = 1                              # 네이버 서버에 요청할 시작 페이지 번호

    # UI에 "매물 수집 시작..." 이라는 메시지와 함께 진행률 바를 0%로 초기화합니다.
    if progress_callback:
        progress_callback(0, min(tot_cnt, limit), "매물 수집 시작...")

    # 3. 본격적인 페이지 단위 수집 반복문 (while)
    while True:
        # 사용자가 도중에 검색 취소를 눌렀다면, 루프를 즉시 깨고 나갑니다.
        if cancel_check and cancel_check():
            break

        # 한 페이지를 가져오기 전, 봇 차단을 피하기 위해 매너 타임(0.8초)을 가집니다.
        time.sleep(REQUEST_DELAY)
        
        # 현재 페이지(page)의 매물 목록 데이터를 서버에서 긁어옵니다.
        result = fetch_article_list(
            cortar_no=cortar_no, lat=lat, lon=lon, tot_cnt=tot_cnt, page=page,
            btm=btm, lft=lft, top=top, rgt=rgt
        )

        items = result["body"]  # 서버에서 넘겨준 이번 페이지의 실제 매물 리스트
        
        # ✅ 받아온 매물 목록을 돌면서 대표 이미지(repImgUrl) 다운로드
        for item in items:
            img_url = item.get("repImgUrl")  # 매물의 대표 썸네일 사진 주소
            atcl_no = item.get("atclNo")     # 매물 고유 번호 (파일 이름으로 쓰기 위함)
            
            # 사진 주소와 매물 번호가 둘 다 정상적으로 있는 경우에만 처리합니다.
            if img_url and atcl_no:
                # 썸네일 경로가 /... 형태로 오는 경우가 있어 도메인을 붙여줍니다.
                # 완전한 주소가 아니면 앞에 네이버 이미지 서버 주소를 강제로 결합합니다.
                full_img_url = f"https://landthumb-phinf.pstatic.net{img_url}" if img_url.startswith("/") else img_url
                
                # 내 컴퓨터의 images 폴더 안에 '매물번호.jpg' 형태로 저장할 경로를 만듭니다.
                save_path = os.path.join(IMAGE_DIR, f"{atcl_no}.jpg")
                
                # 중복 다운로드 방지
                # 해당 폴더에 똑같은 이름의 사진이 이미 존재하지 않을 때만 다운로드를 실행합니다.
                if not os.path.exists(save_path):
                    download_image(full_img_url, save_path)
                    time.sleep(0.3) # 너무 잦은 이미지 요청 방지 (사진 1장 받을 때마다 0.3초 휴식)
                    
            # 사진 다운로드가 끝난 매물 데이터를 최종 상자(all_items)에 넣습니다.
            all_items.append(item)
            
            # 여기서 limit 체크
            # 내가 목표로 한 개수(예: 50개)를 다 채웠다면, 더 이상 순회하지 않고 즉시 멈춥니다.
            if len(all_items) >= limit:
                break

        # 한 페이지 수집이 끝날 때마다 UI의 진행률 바를 업데이트해 줍니다.
        if progress_callback:
            progress_callback(min(len(all_items), limit), min(tot_cnt, limit), f"수집 중... ({len(all_items)})")

        # 4. 루프 종료 조건 체크
        # 목표 개수를 다 채웠거나, 서버에서 '이제 다음 페이지 없음(more: False)'이라고 알려주면 전체 루프를 끝냅니다.
        if len(all_items) >= limit or not result["more"]:
            break

        # 다음 바퀴를 돌기 위해 페이지 번호를 1장 넘깁니다.
        page += 1

    # 목표한 개수(limit)만큼만 딱 잘라서 최종 데이터로 반환합니다.
    return all_items[:limit]