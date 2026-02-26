## 기능 개요

- **목표**: 기존 네이버 매물 스크래핑 + Streamlit 앱에 `folium` 지도를 연동하여, 검색 탭에서 예를 들어 **"서울시 종로"** 를 검색하면 **종로 전역 지도가 먼저 시각적으로 노출**되도록 한다.
- **배경**: 현재 프로젝트는 네이버 매물 정보를 수집하여, Streamlit 기반으로 매물 정보를 조회할 수 있으나, 지역 단위로 한눈에 보는 인터랙티브 지도가 없다.
- **효과**
  - 사용자가 특정 행정구(예: 서울시 종로구)를 검색했을 때, 해당 구 전역의 지도를 바로 보여 줌으로써 공간 감각을 향상.
  - 스크래핑된 매물의 좌표를 활용해, 향후 매물 마커/클러스터 기능까지 확장 가능.

---

## 변경 사항 요약 (Summary)

1. **검색 탭에 지역 기반 지도 섹션 추가**
   - 검색어에 "서울시 종로", "서울 종로구", "종로구" 등 행정구 단위 검색을 지원.
   - 지역명 파싱 후 행정동/법정동 기준 중심좌표 및 줌 레벨 계산.
2. **`folium` 지도 생성 및 Streamlit 연동**
   - `folium.Map` 을 사용해 기본 지도를 생성하고, `streamlit-folium` 또는 `st.components.v1.html` 로 앱에 임베드.
   - `map.ipynb` 에서 테스트한 TileLayer 구성을 기반으로, 사용자에게 여러 타일 레이어 옵션 제공.
3. **지도에 매물 시각화 (1차 버전: 선택적)**
   - 스크래핑한 매물 데이터 중 위도/경도 정보를 가진 행(row)만 필터링.
   - 선택한 행정구 내부에 포함되는 매물만 추려, folium 마커로 표시 (기본 원형 마커 or 아이콘).

---

## 상세 설계 (Design)

### 1. 지역 검색 흐름

- **입력 형식**
  - 사용자가 검색 탭의 텍스트 입력창에 `"서울시 종로"`, `"서울 종로구"`, `"종로구"` 와 같이 자연어 형태로 입력.
- **파싱 로직 (예상)**
  - 문자열 전처리: 공백/`시`, `도`, `군`, `구` 등의 접미사 제거/통합.
  - 사전(딕셔너리) 또는 별도 테이블(지역명 → 중심좌표, 기본 줌)을 활용해 매핑.
  - 예시: `"서울시 종로"` → key: `"서울 종로구"` → value: `{ "lat": 37.5729, "lng": 126.9793, "zoom": 13 }`.
- **예외 처리**
  - 매핑 테이블에 없는 지역명일 경우:
    - "지원하지 않는 지역입니다" 안내 메시지 출력.
    - 대신 전국/서울시 전체 지도 등 fallback 지도 제공 (옵션).

### 2. folium 지도 생성

- **기본 스펙**
  - `folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level)`
  - `Figure(width=..., height=...)` 로 지도 크기 제어 (`map.ipynb` 참고).
- **타일 레이어 구성**
  - 기본: OpenStreetMap 또는 `cartodbpositron` (밝은 배경).
  - 추가 레이어 (사용자가 토글 가능):
    - `Stamen Terrain`
    - `Stamen Toner`
    - `Stamen Water Color`
    - `cartodbdark_matter`
  - `folium.LayerControl().add_to(m)` 으로 레이어 선택 UI 제공.

### 3. Streamlit 연동 방식

- **대안 1: `streamlit-folium` 사용 (권장)**
  - 의존성에 `streamlit-folium` 추가.
  - 예시 흐름:
    - `m = folium.Map(...)` 로 지도 생성.
    - `from streamlit_folium import st_folium`
    - `st_folium(m, width=..., height=...)` 으로 Streamlit 내에 지도 렌더링.
  - 장점: 상호작용(클릭 이벤트, 지도 이동/확대 정보 등)을 이후 수집하기 쉬움.

- **대안 2: `st.components.v1.html` 로 직접 HTML 임베딩**
  - `m._repr_html_()` 혹은 `m.get_root().render()` 로 HTML 문자열 획득.
  - `st.components.v1.html(html_string, height=..., scrolling=False)` 로 출력.
  - 장점: 외부 패키지 의존성 최소화.  
  - 단점: 인터랙션 결과를 다시 파이썬으로 받는 것은 상대적으로 불편.

> **결론**: 장기 확장성(지도 클릭, 범위 선택 등)을 고려하면, **대안 1 (`streamlit-folium`) 채택**을 제안.

### 4. 매물 마커 표시 (1차 범위)

- **필터링**
  - 기존 스크래핑 결과 DataFrame (예: `df_listings`) 에서:
    - `latitude`, `longitude` (또는 유사한 컬럼명) 이 존재하는 행만 사용.
    - 선택한 지역(예: 종로구)에 속하는 매물만 필터.
      - 행정구 분류 컬럼이 있으면 해당 컬럼 조건으로 필터.
      - 없으면 좌표 기반 폴리곤(in/out) 판정은 추후 과제로 남기고, 1차 버전에서는 "도시/구" 단위 컬럼 기준 필터를 가정.
- **마커 스타일**
  - 기본: `folium.Marker(location=[lat, lng], popup=요약정보, tooltip=짧은 정보)`
  - 향후: 가격/면적 등에 따라 색/아이콘 차등 표현 (추가 개선 요소).

---

## UI 구상 (와이어프레임 수준)

아래는 Streamlit 앱 기준으로, 상단 검색 탭에 지도를 통합하는 대략적인 구상입니다.

### 1. 전체 레이아웃

- **좌측 사이드바 (기존 유지 + 필요시 옵션 추가)**
  - 검색 타입 선택 (예: "지역 검색", "지하철역 검색", "복합 조건 검색" 등).
  - 필터 옵션 (매매/전세/월세, 가격 범위, 면적 등).

- **메인 영역**
  1. **검색 영역**
     - 상단에 넓은 검색 입력창:
       - placeholder: `"예: 서울시 종로, 서울 종로구, 종로구"`
       - 우측에 "검색" 버튼.
     - 검색 실행 시, 지역 유효성 검사 및 지도/리스트 업데이트.
  2. **지도 영역 (상단 60~70%)**
     - 검색 결과에 해당하는 지역(예: 종로구)을 화면 중앙에 두고 확대된 folium 지도.
     - 상단 우측에 작은 안내 텍스트:
       - `"지도에서 종로구 전역의 매물을 한눈에 확인해보세요."`
     - 지도 우측 상단에 타일 레이어 토글(기본 folium LayerControl).
  3. **매물 리스트 영역 (하단 30~40%)**
     - 현재 지도에 표시된 매물들을 테이블/카드 형식으로 나열.
     - 컬럼 예시: `단지/건물명 | 거래유형 | 가격 | 면적 | 층수 | 등록일`
     - 리스트 행을 클릭하면:
       - 지도에서 해당 매물 마커가 강조되도록 하는 상호작용은 추후 개선 방향으로 남김 (1차 버전에서는 단순 리스트만 제공해도 OK).

### 2. 반응형/해상도 고려

- **데스크톱 기준**
  - 너비 1200px 이상일 때:
    - 지도 높이: 약 550~650px.
    - 하단 리스트: 고정 높이 + 내부 스크롤.
- **노트북/작은 화면**
  - 세로 공간이 좁을 경우:
    - 지도 높이를 400~450px 정도로 축소.
    - 리스트는 페이지네이션 또는 축소된 요약 뷰 제공.

---

## 기술적 변경 포인트 (예상)

- **의존성 추가**
  - `folium` (이미 `map.ipynb` 에서 사용 중)
  - `streamlit-folium` (권장)
  - 지역명 → 좌표 매핑용 데이터 구조 (파이썬 딕셔너리 또는 별도 CSV/JSON 로더)

- **코드 구조 (예상)**
  - `app.py` 또는 기존 Streamlit 엔트리 파일 내에 다음 함수 분리:
    - `parse_region_query(query: str) -> dict | None`  
      - 입력 문자열을 받아 `{ "sido": ..., "sigungu": ..., "lat": ..., "lng": ..., "zoom": ... }` 형태로 반환.
    - `create_region_map(center_lat, center_lng, zoom, listings_df=None) -> folium.Map`  
      - 지도 생성 및 (선택적으로) 매물 마커 추가.
    - `render_region_search_tab()`  
      - 검색 입력 UI + 지도 + 리스트 레이아웃 구성.

---

## 테스트 시나리오

1. **정상 검색**
   - 입력: `"서울시 종로"`
   - 기대 결과:
     - 종로구 전역을 포함하는 지도가 적절한 줌 레벨로 렌더링.
     - 기존 스크래핑 데이터 중 종로구에 해당하는 매물이 있을 경우, 마커 또는 리스트에 노출.
2. **지원하지 않는 지역명**
   - 입력: `"서울시 아무구"`
   - 기대 결과:
     - "지원하지 않는 지역입니다" 메시지 노출.
     - 기본 지도(예: 서울 전체 또는 전국 지도) 표시 또는 지도를 숨김.
3. **빈 문자열 또는 너무 짧은 검색어**
   - 입력: `""`, `"서울"`, `"종로"`
   - 기대 결과:
     - 최소 단위(시+구) 이상 입력하도록 안내 메시지 표시.
4. **성능 확인**
   - 매물 데이터가 수천 건 이상일 때:
     - 마커를 전부 찍는 대신, 1차 버전에서는 "현재 필터링된 상위 N개" 만 표시하거나,
     - 후속 작업으로 ClusterMarker 적용 고려.

---

## 향후 확장 아이디어

- 검색창에서 **행정구 + 매물 조건(가격, 면적 등)** 을 동시에 입력받는 자연어 파서 도입.
- 지하철역/버스정류장 단위 검색 시, 해당 역 반경(예: 500m) 내 매물만 지도에 표시.
- 사용자가 지도에서 직접 드래그/줌한 현재 뷰포트 내 매물만 리스트에 자동 반영.
- 선호 지역(북촌, 성수동, 연남동 등)을 즐겨찾기로 저장하고, 한 번에 여러 지역을 비교하는 멀티 맵 뷰.

---

## 정리

- 검색 탭에서 `"서울시 종로"` 와 같은 입력을 받았을 때, **해당 지역 전체를 커버하는 folium 지도를 먼저 보여주는 UX** 를 설계하였다.
- `folium` + `streamlit-folium` 조합을 사용하여, **지역 중심좌표 기반의 인터랙티브 지도** 와 **매물 리스트** 를 같은 화면에 배치한다.
- 1차 버전에서는 **지역 단위 지도 + 매물 기본 마커/리스트** 를 목표로 하고, 이후 점진적으로 **클러스터링, 인터랙션, 자연어 검색 고도화** 를 확장하는 방향을 제안한다.

---

## 매물 사진 기능 (추가 구현)

### 목표 및 배경

- **목표**: 매물 목록에서 건물명을 클릭해 상세로 들어갔을 때, 해당 매물의 **등록 사진**을 화면에 표시한다.
- **배경**: 목록 API(`articleList`)에서는 대표 이미지 URL(`repImgUrl`) 한 개만 제공하고, 상세 페이지에 나오는 **여러 장의 사진**은 별도 API/페이지에서 불러와야 한다. 또한 API가 주는 URL에 `?type=m562` 등이 붙어 있으면 **썸네일**만 받게 되므로, 원본에 가까운 크기로 보이도록 변환해야 한다.

### 변경 사항 요약

1. **데이터**
   - `utils.TABLE_COLUMNS`에 `repImgUrl`(대표이미지URL), `rletTpCd`(매물유형코드), `tradTpCd`(거래유형코드)를 추가해 목록 수집 시 함께 보관.
2. **상세 이미지 조회 (scraper)**
   - **galleryImages API** (`fin.land.naver.com/front-api/v1/article/galleryImages?articleNumber=매물ID`): 매물번호만으로 이미지 목록을 받아 오는 전용 API를 **가장 먼저** 호출. 응답 `result[]` 안의 `imageUrl`을 수집.
   - **basicInfo API** (`fin.land.naver.com/.../article/basicInfo`, `articleId` + `realEstateType` + `tradeType`): galleryImages가 없을 때 상세 정보를 받아 와서, JSON을 재귀 탐색해 이미지 URL을 추출.
   - **m.land articleInfo / 상세 HTML**: 위 두 가지가 실패할 때의 fallback. HTML에서 `landthumb-phinf`, `naver-file.ebunyang` 등 매물 이미지 도메인 URL만 정규식으로 추출.
3. **썸네일 → 원본 크기 변환**
   - 네이버 `landthumb-phinf.pstatic.net` URL은 쿼리 `?type=m562` 등이 있으면 작은 크기로 내려준다. **`type`, `udate` 쿼리를 제거**한 URL로 다시 요청하면 원본에 가까운 크기를 받을 수 있음.
   - `_thumbnail_to_full_size_url(url)`: URL 파싱 후 해당 쿼리만 제거해 반환. galleryImages/basicInfo/HTML에서 나온 모든 이미지 URL과, 앱에서 쓰는 대표이미지 URL에 적용.
4. **앱 (app.py)**
   - 상세 보기 진입 시: 행의 `대표이미지URL`을 `get_full_size_image_url`로 변환해 목록에 넣고, `get_article_image_urls(매물ID, 매물유형코드, 거래유형코드)`로 상세 이미지 URL 목록을 받아와 합친 뒤, 중복 제거하여 `st.image()`로 3열 그리드 표시. 목록 API에서 코드가 없으면 한글명(아파트→APT, 매매→B1 등)으로 추정해 basicInfo fallback에 사용.

### 원리 (Network / API 관점)

- 브라우저에서 매물 **상세 페이지**를 열면, JavaScript가 **Fetch/XHR**로 데이터 API를 호출한다. F12 → Network → Fetch/XHR에서 `fin.land.naver.com` 또는 `galleryImages`, `basicInfo` 같은 요청을 보면, 그 요청의 **Request URL·파라미터**와 **Response JSON**이 곧 “어디서 무엇을 넘기고, 어떤 필드에 이미지 URL이 들어 있는지”에 해당한다.
- 우리 코드는 그 **GET 요청을 그대로 Python `requests`로 재현**하고, 응답 JSON에서 `result`, `imageUrl` 등 이미지 URL이 들어 있는 필드만 파싱한다. 이미지 파일 자체는 Network의 “Img” 탭에서 로드되지만, **그 이미지의 URL을 주는 것은 Fetch/XHR 응답**이므로, 이미지 목록을 얻으려면 Fetch/XHR에서 호출하는 API를 찾아 그걸 흉내 내면 된다.
- 상세 페이지 HTML(Next.js 등)에는 가끔 **서버가 넣어 둔 JSON**이 `<script>` 안에 들어 있다. 그 안에 `GET /article/galleryImages` 결과가 포함되어 있으면, `imageUrl` 검색으로 같은 구조를 확인할 수 있고, 우리는 동일한 API를 직접 호출해 같은 데이터를 받는다.

### 기술적 포인트

- **scraper**
  - `fetch_article_gallery_images(article_id)`: galleryImages URL 후보 2종 호출, `result[].imageUrl` 수집 후 `_thumbnail_to_full_size_url` 적용해 반환.
  - `fetch_article_basic_info(article_id, real_estate_type, trade_type)`: basicInfo 호출, `result`만 반환.
  - `_extract_image_urls_from_json(obj)`: dict/list 재귀 탐색, `url` / `imageUrl` / `imgUrl` 등 문자열이면서 `http`로 시작하고 매물 이미지 도메인 패턴이면 수집.
  - `get_article_image_urls(atcl_no, rlet_tp_cd, trad_tp_cd)`: galleryImages → basicInfo → m.land articleInfo → 상세 HTML 순으로 시도하고, 각 단계에서 나온 URL에 썸네일→원본 변환을 적용한 뒤 반환.
  - `get_full_size_image_url(url)`: 앱에서 대표이미지 등 단일 URL을 쓸 때 호출. 내부적으로 `_thumbnail_to_full_size_url` 사용.
- **app**
  - 상세 보기에서 `대표이미지URL`을 `get_full_size_image_url`로 변환한 뒤, `get_article_image_urls`로 받은 목록과 합쳐서 중복 제거, `st.image(url)`로 표시. 로컬에 저장된 `images/{매물ID}.jpg`가 있으면 URL 실패 시 대표 이미지로만 사용.

### 정리

- 매물 상세 진입 시 **galleryImages(우선) → basicInfo → m.land/HTML** 순으로 이미지 URL을 구하고, **썸네일 쿼리 제거**로 원본에 가까운 크기를 요청하도록 구현했다.
- F12 Network에서 “어떤 API가 이미지 URL을 주는지”를 확인한 뒤, 그 요청을 그대로 재현하고 응답만 파싱하는 방식으로 동작한다.

