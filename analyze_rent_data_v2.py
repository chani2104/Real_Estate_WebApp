import pandas as pd

# 1️⃣ 데이터 불러오기
df = pd.read_csv('national_rent_data_202401.csv', encoding='utf-8-sig')

# 🔹 컬럼명 한글로 변경 (영문 → 한글)
df = df.rename(columns={
    'deposit': '보증금',
    'monthlyRent': '월세',
    'excluUseAr': '전용면적',
    'sggCd': '시군구코드',
    'sggNm': '시군구명'
})

# 2️⃣ 숫자 컬럼 정리
numeric_cols = ['보증금', '월세', '전용면적']

for col in numeric_cols:
    if col in df.columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(',', '', regex=False)
            .str.strip()
        )
        df[col] = pd.to_numeric(df[col], errors='coerce')

# 3️⃣ 계약 유형 구분
df['계약유형'] = df['월세'].apply(lambda x: '전세' if x == 0 else '월세')

# 4️⃣ 시도 코드 매핑
sido_map = {
    '11': '서울특별시',
    '26': '부산광역시',
    '27': '대구광역시',
    '28': '인천광역시',
    '29': '광주광역시',
    '30': '대전광역시',
    '31': '울산광역시',
    '36': '세종특별자치시',
    '41': '경기도',
    '42': '강원특별자치도',
    '43': '충청북도',
    '44': '충청남도',
    '45': '전라북도',
    '46': '전라남도',
    '47': '경상북도',
    '48': '경상남도',
    '50': '제주특별자치도'
}

df['시도코드'] = df['시군구코드'].astype(str).str[:2]
df['시도명'] = df['시도코드'].map(sido_map)

# 🔥 최종 기준 키 생성 (인프라와 동일 구조)
df['region_name'] = df['시도명'] + " " + df['시군구명']

# 5️⃣ 결측 제거
df = df.dropna(subset=numeric_cols)

# 6️⃣ 전세 요약
전세_df = df[df['계약유형'] == '전세']
전세_요약 = 전세_df.groupby('region_name', as_index=False).agg(
    전세_평균보증금=('보증금', 'mean'),
    전세_평균면적=('전용면적', 'mean'),
    전세_거래건수=('보증금', 'count')
)

# 7️⃣ 월세 요약
월세_df = df[df['계약유형'] == '월세']
월세_요약 = 월세_df.groupby('region_name', as_index=False).agg(
    월세_평균보증금=('보증금', 'mean'),
    월세_평균월세=('월세', 'mean'),
    월세_평균면적=('전용면적', 'mean'),
    월세_거래건수=('보증금', 'count')
)

# 8️⃣ 병합
임대요약 = pd.merge(
    전세_요약,
    월세_요약,
    on='region_name',
    how='outer'
).fillna(0)

임대요약['전체_거래건수'] = (
    임대요약['전세_거래건수'] +
    임대요약['월세_거래건수']
)

# 9️⃣ 저장
임대요약.to_csv(
    "region_rent_summary_v2.csv",
    index=False,
    encoding='utf-8-sig'
)

print("✅ 한국어 컬럼 기반 임대 요약 완료")
print(f"총 지역 수: {len(임대요약)}")