# 프로젝트 소개

이 프로젝트는 공공데이터 포털, 카카오맵, 네이버 부동산 데이터를 활용하여 지역 탐색과 조건 기반 매물 검색을 지원하는 Streamlit 기반 부동산 웹 애플리케이션입니다.

주요 기능은 다음과 같습니다.

* 공공데이터 및 지도 기반 지역 분석
* 카카오맵 기반 생활 인프라 수집 및 점수화
* 네이버 부동산 기반 매물 정보 수집
* 조건 기반 매물 필터링 및 상세 조회
* 지도, 차트, 테이블을 활용한 시각화 제공

# 전체 디렉터리 구조

```bash
project/
├─ app.py                    # Streamlit 메인 실행 파일
├─ area.py                   # 지역 탐색 관련 기능 분리 파일
├─ area_merge.py             # 지역 탐색 탭에서 사용하는 통합 로직
├─ build_infra_dataset.py    # 카카오맵 기반 인프라 데이터 수집 및 CSV 생성
├─ kakao_api.py              # 카카오맵 API 연동
├─ public_api.py             # 공공데이터포털 API 호출
├─ region_pipeline.py        # 임대 데이터 전처리 및 지역 단위 가공
├─ scoring.py                # 인프라 기본 점수 계산
├─ scraper.py                # 네이버 부동산 매물 정보 수집
├─ search_area.py            # 공공데이터 보조 수집/스크래핑
├─ team_explore.py           # area_merge.py 병합/수정 테스트 버전
├─ utils.py                  # 공통 유틸 함수 모음
├─ map_view.py               # 지도 시각화 보조 파일
├─ poi_schools.py            # 학교 POI 관련 데이터 처리
├─ subway_data.py            # 지하철 데이터 처리
├─ read_txt.py               # 텍스트 파일 로드 보조 파일
├─ region_code.txt           # 행정구역 코드 원본 파일
├─ station_code.csv          # 지하철역 코드 데이터
├─ requirements.txt          # 파이썬 패키지 목록
├─ PR.md                     # 프로젝트 메모/기록 문서
├─ README.md                 # 프로젝트 설명 문서
├─ infradev.md               # 인프라 개발 관련 문서
├─ infravis.md               # 인프라 시각화 관련 문서
├─ map.ipynb                 # 지도 기능 테스트용 노트북
├─ Visualization/            # 시각화 관련 보조 코드/실험 파일
└─ data/                     # CSV 및 가공 데이터 저장 폴더
```

# 디렉터리 구조 상세

## app.py

Streamlit에서 실행되는 메인 페이지입니다.
`streamlit run app.py` 명령으로 실행되며, 지역 탐색, 매물 검색, 시각화 UI가 연결되는 전체 서비스의 진입점입니다.

## area.py

지역 탐색 관련 기능을 분리해둔 파일입니다.
지역 단위 분석, 추천 로직, 화면 구성 요소를 정리할 때 사용됩니다.

## area_merge.py

지역 탐색 탭에서 사용하는 통합 로직 파일입니다.
지역별 점수 계산, 추천 지역 출력, 지도 연동 등 지역 탐색 핵심 기능이 모여 있습니다.

## build_infra_dataset.py

카카오맵 기반으로 생활 인프라 데이터를 수집하고 CSV 파일로 저장하는 전처리 스크립트입니다.
학교, 지하철, 병원, 카페, 편의점, 백화점, 문화생활 등의 데이터를 지역 단위로 집계합니다.

## kakao_api.py

카카오맵 API 연동 파일입니다.
장소 검색, 인프라 개수 집계, 지역별 생활 편의시설 조회 등에 사용됩니다.

## public_api.py

공공데이터포털 API를 호출하는 파일입니다.
시군구 코드, 지역 식별 정보 등 공공데이터 기반 기초 데이터를 가져오는 데 사용됩니다.

## region_pipeline.py

전세, 월세, 임대 관련 데이터를 전처리하고 지역 단위로 가공하는 파일입니다.
컬럼 정리, 파생 변수 생성, 데이터 병합 등 임대 데이터 처리 흐름을 담당합니다.

## scoring.py

수집된 인프라 데이터를 기반으로 지역별 기본 점수를 계산하는 파일입니다.
인프라 총점 산출과 1차 점수화 로직이 포함되어 있습니다.

## scraper.py

네이버 부동산 기반 매물 정보를 수집하는 파일입니다.
매물 정보, 좌표, 사진, 기본 상세 정보 등을 가져오는 핵심 크롤링 모듈입니다.

## search_area.py

공공데이터 관련 보조 수집 또는 스크래핑에 사용하는 파일입니다.
API 외 추가 데이터 수집 또는 지역 정보 보완에 사용됩니다.

## team_explore.py

코드 병합 과정에서 `area_merge.py`를 수정하거나 테스트하기 위해 만든 파일입니다.
통합 전 실험용 또는 협업 조정용 버전으로 사용됩니다.

## utils.py

매물 탐색에서 공통으로 사용하는 유틸 함수 모음입니다.
주요 기능은 다음과 같습니다.

* DataFrame 변환
* 가격 파싱
* 거리 계산
* 엑셀 저장
* 가격 구간 분류

## map_view.py

지도 시각화 보조 파일입니다.
매물 위치나 지역 위치를 지도에 출력하는 기능을 테스트하거나 분리할 때 사용됩니다.

## poi_schools.py

학교 관련 POI(Point of Interest) 데이터를 처리하는 파일입니다.
근거리 학교 정보나 교육 인프라 분석에 활용됩니다.

## subway_data.py

지하철 관련 데이터를 처리하는 파일입니다.
역세권 분석, 역 정보 정리, 거리 계산 등에 사용됩니다.


## requirements.txt

프로젝트 실행에 필요한 파이썬 패키지 목록입니다.


## Visualization/

시각화 관련 보조 코드 또는 실험용 파일을 모아둔 디렉터리입니다.

## data/

프로젝트에서 사용하는 CSV 및 가공 데이터를 저장하는 디렉터리입니다.
인프라 데이터, 임대 요약 데이터, 병합 결과 데이터 등이 포함됩니다.

# 실행방법

## 1. 패키지 설치

아래 명령으로 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

## 2. .env 파일 생성

프로젝트 루트 경로에 `.env` 파일을 생성합니다.

필요한 값 예시:

* 국토교통부 API Key
* 카카오맵 API Key
* 네이버 부동산 관련 값


예시 형태:

```env
PUBLIC_DATA_API_KEY=your_public_data_key
MOLIT_API_KEY=your_molit_key
KAKAO_API_KEY=your_kakao_key
NAVER_REAL_ESTATE_KEY=your_naver_value
```

실제 키 이름은 현재 코드에서 사용 중인 환경변수명에 맞게 맞춰주면 됩니다.

## 3. 서버 실행

아래 명령으로 Streamlit 서버를 실행합니다.

```bash
streamlit run app.py
```

