# 네이버 부동산(m.land.naver.com) API 분석 결과

## 분석 개요

**분석 대상 URL:** `https://m.land.naver.com/map/37.1636848:128.9853697:12:5119000000/OR:APT:JGC:OPST:ABYG:OBYG:VL:JWJT:SGJT:DDDGG/B1:B2:B3#mapList`

**분석 일시:** 2026-02-24

**결론:** 특정 지역의 모든 부동산 매물 정보를 스크래핑하는 데 사용할 수 있는 **데이터 API 2개**가 확인되었습니다.

---

## 1. clusterList API (지도 클러스터 데이터)

### 엔드포인트
```
GET https://m.land.naver.com/cluster/clusterList
```

### 요청 파라미터

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| view | 뷰 타입 | atcl |
| cortarNo | 법정동 코드 (지역 식별) | 5119000000 (강원도 태백시) |
| rletTpCd | 매물 유형 코드 | OR:APT:JGC:OPST:ABYG:OBYG:VL:YR:DSD:JWJT:SGJT:DDDGG |
| tradTpCd | 거래 유형 코드 | B1:B2:B3 (전세:월세:단기임대) |
| z | 줌 레벨 | 12 |
| lat | 중심 위도 | 37.164232 |
| lon | 중심 경도 | 128.985713 |
| btm | 지도 하단 위도 | 37.0747131 |
| lft | 지도 좌측 경도 | 128.8078718 |
| top | 지도 상단 위도 | 37.253645 |
| rgt | 지도 우측 경도 | 129.1635542 |
| pCortarNo | 상위 법정동 코드 (선택) | (비어있음) |

### 응답 구조
```json
{
  "code": "success",
  "data": {
    "ARTICLE": [
      {
        "lgeo": "30200313",
        "count": 11,
        "z": 12,
        "lat": 37.165625,
        "lon": 128.99238281,
        "psr": 0.6,
        "tourExist": false
      },
      {
        "lgeo": "30201202",
        "count": 1,
        "itemId": "2609722371",
        "tradTpCd": "B2",
        "rletNm": "빌라",
        "tradNm": "월세",
        "priceTtl": "300/30",
        ...
      }
    ],
    "cpolygon": { "crdnData": "...", "z": 12 },
    "cortar": {
      "detail": {
        "cortarNo": "5119010100",
        "cortarNm": "황지동",
        "regionName": "강원도 태백시 황지동",
        ...
      }
    }
  }
}
```

### 용도
- 지도 뷰에서 매물 클러스터(그룹) 정보 조회
- 단일 매물 또는 클러스터 단위 위치/개수 정보 제공

---

## 2. articleList API (매물 상세 목록) ⭐ **스크래핑 핵심**

### 엔드포인트
```
GET https://m.land.naver.com/cluster/ajax/articleList
```

### 요청 파라미터

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| rletTpCd | 매물 유형 코드 | OR:APT:JGC:OPST:ABYG:OBYG:VL:YR:DSD:JWJT:SGJT:DDDGG |
| tradTpCd | 거래 유형 코드 | B1:B2:B3 |
| z | 줌 레벨 | 12 |
| lat | 중심 위도 | 37.164232 |
| lon | 중심 경도 | 128.985713 |
| btm | 지도 하단 위도 | 37.0747131 |
| lft | 지도 좌측 경도 | 128.8078718 |
| top | 지도 상단 위도 | 37.253645 |
| rgt | 지도 우측 경도 | 129.1635542 |
| showR0 | (선택) | (비어있음) |
| totCnt | 총 매물 수 (clusterList에서 획득) | 17 |
| cortarNo | 법정동 코드 | 5119000000 |

### 응답 구조
```json
{
  "code": "success",
  "hasPaidPreSale": false,
  "more": true,
  "page": 1,
  "body": [
    {
      "atclNo": "2609077416",
      "cortarNo": "5119010100",
      "atclNm": "태백황지청솔",
      "rletTpCd": "A01",
      "rletTpNm": "아파트",
      "tradTpCd": "B2",
      "tradTpNm": "월세",
      "flrInfo": "12/15",
      "prc": 500,
      "rentPrc": 50,
      "hanPrc": "500",
      "spc1": "50",
      "spc2": "38.36",
      "direction": "남향",
      "atclCfmYmd": "26.02.19.",
      "lat": 37.164497,
      "lng": 128.982375,
      "tagList": ["25년이내", "대단지", "화장실한개", "소형평수"],
      "bildNm": "110동",
      "cpid": "SERVE",
      "cpNm": "부동산써브",
      "rltrNm": "태백OK공인중개사무소",
      "directTradYn": "N",
      "repImgUrl": "/20260223_103/...",
      "atclFetrDesc": "시청,하나로마트,...",
      ...
    }
  ]
}
```

### body 배열 주요 필드

| 필드 | 설명 |
|------|------|
| atclNo | 매물 고유 ID |
| cortarNo | 법정동 코드 |
| atclNm | 단지/건물명 |
| rletTpNm | 매물 유형 (아파트, 빌라, 상가주택 등) |
| tradTpNm | 거래 유형 (전세, 월세) |
| flrInfo | 층 정보 (예: 12/15) |
| prc | 가격 (만원) |
| rentPrc | 월세 (만원) |
| hanPrc | 가격 표시 문자열 |
| spc1, spc2 | 전용면적(평), 전용면적(㎡) |
| direction | 방향 |
| lat, lng | 위도, 경도 |
| tagList | 매물 태그 배열 |
| bildNm | 동/호수 |
| rltrNm | 중개사명 |
| directTradYn | 직거래 여부 (Y/N) |
| repImgUrl | 대표 이미지 URL |
| atclFetrDesc | 매물 특징 설명 |

### 페이지네이션
- `more`: true이면 추가 페이지 존재
- `page`: 현재 페이지 번호
- 추가 페이지 요청 시 `page` 파라미터 증가

---

## URL 구조 해석

### 지도 페이지 URL 패턴
```
https://m.land.naver.com/map/{lat}:{lon}:{z}:{cortarNo}/{rletTpCd}/{tradTpCd}#mapList
```

### 코드 의미
- **cortarNo (법정동 코드):** 5119000000 = 강원도 태백시
- **rletTpCd (매물 유형):** OR(전체), APT(아파트), JGC(재건축), OPST(오피스텔), ABYG(아파트분양권), OBYG(오피스텔분양권), VL(빌라), JWJT(전원주택), SGJT(상가주택), DDDGG(단독/다가구)
- **tradTpCd (거래 유형):** B1(전세), B2(월세), B3(단기임대)

---

## 스크래핑 구현 가이드

### 권장 워크플로우
1. **clusterList** 호출 → `totCnt` 및 지역 정보 획득
2. **articleList** 호출 → `totCnt`, `cortarNo` 포함하여 전체 매물 목록 조회
3. `more: true`인 경우 `page` 증가하여 반복 요청
4. 각 매물의 `atclNo`로 상세 페이지 `/article/info/{atclNo}` 접근 가능

### 주의사항
- **User-Agent**: 모바일 브라우저 UA 권장 (m.land 도메인)
- **Referer**: `https://m.land.naver.com/` 설정 권장
- **요청 빈도**: 과도한 요청 시 차단 가능성 있음
- **법적 준수**: 네이버 이용약관 및 robots.txt 확인 필요

---

## 기타 확인된 요청

| URL | 용도 |
|-----|------|
| https://m.land.naver.com/api/check/private-ip | IP 체크 |
| https://nam.veta.naver.com/nac/1 | 네이버 분석 |
| https://kr-col-ext.nelo.navercorp.com/_store | 로깅 |
| https://nam.veta.naver.com/gfp/v1 | 광고 관련 |
| https://tivan.naver.com/g/... | 추적/분석 |

※ 부동산 매물 데이터 스크래핑에는 **clusterList**, **articleList** 두 API만 사용하면 됩니다.
