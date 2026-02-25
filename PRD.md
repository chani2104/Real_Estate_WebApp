# 네이버 부동산 매물 수집기 PRD (Product Requirements Document)

## 1. 문서 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | 네이버 부동산 매물 수집기 (Naver Real Estate Scraper) |
| 버전 | 1.1 |
| 작성일 | 2026-02-24 |
| 갱신 | 2026-02-25 — Streamlit 앱 중심으로 변경, PySide6 GUI 제외 |
| 참조 문서 | ApiRef.md |

---

## 2. 프로젝트 목적

사용자가 **지역을 선택**하면 해당 지역의 부동산 매물을 **네이버 부동산 API**로 **실시간 수집**하고, **웹 UI(Streamlit)**에서 조회·필터·정제 후 CSV/엑셀로 내보낼 수 있도록 한다. 데이터 가공은 **Python 스크립트(.py)**로만 수행하며, Jupyter Notebook(.ipynb)은 데이터 파이프라인에서 제외한다.

---

## 3. 핵심 요구사항 요약

- **입력:** 사용자가 지역(region_config 기반 드롭다운) 선택
- **처리:** clusterList → articleList API로 매물 수집, pandas DataFrame으로 정제
- **출력:** Streamlit 테이블 표시, 필터/정렬, CSV·엑셀 다운로드
- **UI:** Streamlit (PySide6 데스크톱 GUI는 **제외**)

---

## 4. 기능 요구사항

### 4.1 지역 검색 및 매물 수집

| ID | 요구사항 | 상세 |
|----|----------|------|
| F-01 | 지역 선택 | region_config.json 기반 드롭다운으로 지역 선택 (예: 서울 강남구, 강원 태백시) |
| F-02 | 지역 → 좌표/법정동코드 | cortarNo, lat, lon은 설정 파일(region_config.json) 매핑으로 확보 |
| F-03 | 매물 수집 실행 | "매물 실시간 수집" 버튼 클릭 시 clusterList → articleList 순차 호출 |
| F-04 | 페이지네이션 | articleList의 more: true일 때 page 증가하여 전부 수집 |
| F-05 | 수집 진행 표시 | 수집 중 스피너/메시지, 완료 시 건수 표시 |

### 4.2 매물 데이터 표시 및 정제 (Streamlit)

| ID | 요구사항 | 상세 |
|----|----------|------|
| F-06 | 테이블 뷰 | st.dataframe으로 수집 결과 표시 |
| F-07 | 표시 컬럼 | 매물ID, 단지/건물명, 매물유형, 거래유형, 가격, 면적(㎡), 층, 방향, 중개사, 직거래, 확인일, 특징 등 |
| F-08 | 필터·정렬 | 거래유형/매물유형 필터, 검색어 필터, 정렬(가격·면적·확인일 등) |
| F-09 | 빈 결과 처리 | 매물 0건 시 안내 메시지 |

### 4.3 내보내기

| ID | 요구사항 | 상세 |
|----|----------|------|
| F-10 | CSV 다운로드 | 필터/정제된 뷰 기준으로 CSV 다운로드 (utf-8-sig) |
| F-11 | 엑셀 다운로드 | openpyxl/pandas로 .xlsx 다운로드 (기본 파일명: 매물목록_지역명_날짜.xlsx) |

### 4.4 기타

| ID | 요구사항 | 상세 |
|----|----------|------|
| F-12 | 매물 유형 필터 | (선택) 거래유형·매물유형 드롭다운 필터 |
| F-13 | 데이터 파이프라인 | 가공·저장은 Python(.py)만 사용, .ipynb는 파이프라인에서 미사용 |

---

## 5. 비기능 요구사항

| ID | 요구사항 | 상세 |
|----|----------|------|
| NF-01 | UI 반응성 | 수집 시 st.spinner 등으로 대기 표시 |
| NF-02 | 에러 처리 | API/네트워크 오류 시 st.error 등으로 메시지 표시 |
| NF-03 | 요청 간격 | API 호출 딜레이(예: 0.8초) 적용 |
| NF-04 | User-Agent/Referer | ApiRef 권장(모바일 UA, Referer) 준수 |
| NF-05 | 실행 환경 | 프로젝트 루트에서 `streamlit run Real_Estate_WebApp/app_streamlit.py`로 실행 가능 |

---

## 6. Streamlit 앱 설계

### 6.1 화면 구성

```
┌─────────────────────────────────────────────────────────────────┐
│  🏠 네이버 부동산 매물 수집·정제                                 │
├─────────────────────────────────────────────────────────────────┤
│  1. 지역 선택 및 매물 수집                                       │
│  [지역 선택 ▼]  [매물 실시간 수집]                               │
│                                                                  │
│  2. 매물 목록 (총 N건 · 지역: OOO)                               │
│  ▼ 필터 및 정제                                                  │
│     거래유형 ▼  매물유형 ▼  정렬 ▼  [검색어____________]          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 매물ID │ 단지/건물명 │ 매물유형 │ 거래유형 │ 가격 │ ...   │  │
│  ├───────┼─────────────┼──────────┼──────────┼──────┼──────┤  │
│  │ ...   │ ...         │ ...      │ ...      │ ...  │ ...  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  3. 내보내기                                                     │
│  [CSV 다운로드]  [엑셀 다운로드]                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 실행 방법

- **실행 위치:** 프로젝트 루트(`2016_presidential_election`)
- **명령:**
  ```bash
  streamlit run Real_Estate_WebApp/app_streamlit.py
  ```
- **의존성:** requests, pandas, openpyxl, streamlit (requirements.txt 참고)

---

## 7. 기술 스택

| 구분 | 기술 |
|------|------|
| UI | **Streamlit** |
| HTTP 요청 | requests |
| 데이터 처리 | pandas (DataFrame 변환, 필터/정렬, CSV·엑셀) |
| 엑셀 | openpyxl / pandas.to_excel |

※ PySide6(Qt) 데스크톱 GUI는 본 프로젝트 범위에서 **제외**한다.

### 7.1 의존성 (requirements.txt 예시)

```
requests>=2.28.0
pandas>=2.0.0
openpyxl>=3.1.0
streamlit>=1.28.0
```

---

## 8. 데이터 흐름

```
[사용자: 지역 선택]
        ↓
[region_config.json → cortarNo, lat, lon]
        ↓
[매물 실시간 수집 클릭]
        ↓
[clusterList API] → totCnt
        ↓
[articleList API] (page=1,2,... more:false까지)
        ↓
[JSON → 매물 리스트] → items_to_dataframe() → DataFrame
        ↓
[Streamlit: st.dataframe 표시]
        ↓
[필터/정렬 적용된 뷰] → CSV·엑셀 다운로드
```

---

## 9. 지역 검색 구현 방안

| 방안 | 설명 | 현재 |
|------|------|------|
| C | cortarNo·좌표를 region_config.json에 등록 후 드롭다운 선택 | **채택** |
| B | 법정동코드 매핑 확장 후 지역명 검색 | 추후 확장 |
| A | 네이버 지도/검색 API 연동 | 추후 검토 |

---

## 10. 에러 시나리오 및 처리

| 시나리오 | 처리 |
|----------|------|
| 네트워크 실패 | st.error 메시지, 재시도 안내 |
| API 403/429 | "일시적으로 접근이 제한되었습니다" 안내 |
| 잘못된 cortarNo | "지역 코드를 찾을 수 없습니다" + region_config 안내 |
| 매물 0건 | "해당 지역에 매물이 없습니다" |
| 엑셀 미지원 환경 | openpyxl 없을 시 CSV만 안내 |

---

## 11. 산출물 목록

| 산출물 | 설명 |
|--------|------|
| **app_streamlit.py** | Streamlit 진입점 — 지역 선택, 실시간 수집, 테이블·필터·내보내기 |
| scraper.py | 네이버 부동산 API 호출 (clusterList, articleList) |
| utils.py | region_config 로드, items_to_dataframe, 엑셀/CSV 저장, TABLE_COLUMNS |
| region_config.json | 지역별 cortarNo, lat, lon, 지역명 매핑 |
| requirements.txt | 패키지 의존성 |
| PRD.md | 본 문서 |
| ApiRef.md | API 참조 |

※ PySide6 관련(main.py, main_window.py, worker.py)은 **범위 제외**이며, 유지할 경우 레거시/참고용으로만 둔다.

---

## 12. 제약사항 및 유의사항

- 네이버 부동산은 비공식 활용이므로 API 구조 변경 시 scraper 수정 필요
- 과도한 요청 시 IP 차단 가능 → 요청 간격·재시도 적용
- 이용약관, robots.txt 준수
- 수집 데이터 상업적 이용 시 법적 검토 필요
- **데이터 가공·저장은 Python(.py)만 사용** — Streamlit과 호환되도록 .ipynb는 파이프라인에서 사용하지 않음
