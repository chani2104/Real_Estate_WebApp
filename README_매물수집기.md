# 네이버 부동산 매물 수집기

지역을 선택하면 해당 지역의 부동산 매물을 수집하고, GUI로 조회·엑셀 저장할 수 있는 프로그램입니다.

## 설치

```bash
pip install PySide6 requests pandas openpyxl
```

## 실행

```bash
python main.py
```

## 사용 방법

1. **지역 선택**: 드롭다운에서 지역을 선택하거나, 법정동코드(예: 5119000000)를 직접 입력
2. **수집 시작**: "수집 시작" 버튼 클릭
3. **결과 확인**: 테이블에 매물 목록 표시 (컬럼 헤더 클릭으로 정렬 가능)
4. **엑셀 저장**: "엑셀로 저장" 버튼으로 .xlsx 파일 저장

## 지역 추가

`region_config.json` 파일을 편집하여 지역을 추가할 수 있습니다.

```json
{
  "법정동코드": [위도, 경도, "표시명"],
  "5119000000": [37.164232, 128.985713, "강원도 태백시"]
}
```

법정동코드와 좌표는 [네이버 부동산](https://m.land.naver.com) 지도에서 해당 지역을 검색한 URL에서 확인할 수 있습니다.

## 파일 구성

| 파일 | 설명 |
|------|------|
| main.py | 진입점 |
| main_window.py | PySide6 GUI |
| scraper.py | 네이버 부동산 API 호출 |
| worker.py | QThread 비동기 수집 |
| utils.py | 엑셀 저장, 지역 설정 |
| region_config.json | 지역 목록 (편집 가능) |
| requirements.txt | 패키지 의존성 |

## 참조

- ApiRef.md: API 분석 결과
- PRD.md: 제품 요구사항 문서
