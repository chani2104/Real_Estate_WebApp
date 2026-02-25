import pandas as pd

# 1. 데이터 불러오기
df = pd.read_csv('national_rent_data_202401.csv', encoding='utf-8-sig')

# 2. '계약유형' 컬럼 추가
df['contractType'] = df['monthlyRent'].apply(lambda x: '전세' if x == 0 else '월세')

# 3. 수치 전처리
for col in ['deposit', 'monthlyRent', 'excluUseAr']: 
    if df[col].dtype == 'object':
        df[col] = df[col].str.replace(',', '').astype(float)
    else:
        df[col] = df[col].astype(float)


# 4. 지역별 요약 (Pivot Table)
# 전세 데이터
jeonse_df = df[df['contractType'] == '전세']
jeonse_summary = jeonse_df.groupby('sggNm').agg(
    전세_평균보증금=('deposit', 'mean'),
    전세_평균전용면적=('excluUseAr', 'mean'),
    전세_거래건수=('contractType', 'count')
).reset_index()

# 월세 데이터
wolse_df = df[df['contractType'] == '월세']
wolse_summary = wolse_df.groupby('sggNm').agg(
    월세_평균보증금=('deposit', 'mean'),
    월세_평균월세액=('monthlyRent', 'mean'),
    월세_평균전용면적=('excluUseAr', 'mean'),
    월세_거래건수=('contractType', 'count')
).reset_index()

# 데이터 병합
summary_df = pd.merge(jeonse_summary, wolse_summary, on='sggNm', how='outer').fillna(0)

# 5. '월세비중(%)' 계산
summary_df['전체_거래건수'] = summary_df['전세_거래건수'] + summary_df['월세_거래건수']
summary_df['월세비중(%)'] = (summary_df['월세_거래건수'] / summary_df['전체_거래건수']) * 100

# 6. 결과 저장
summary_df.to_csv('region_rent_summary.csv', index=False, encoding='utf-8-sig')

# 7. 월세 및 전세가 가장 저렴한 지역 TOP 5 출력
# 월세가 0인 지역(전세만 있는 지역)을 제외하고 계산
wolse_top5 = summary_df[summary_df['월세_평균월세액'] > 0].sort_values('월세_평균월세액').head(5)
# 전세가 0인 지역(월세만 있는 지역)을 제외하고 계산
jeonse_top5 = summary_df[summary_df['전세_평균보증금'] > 0].sort_values('전세_평균보증금').head(5)


print("--- 월세가 가장 저렴한 지역 TOP 5 ---")
print(wolse_top5[['sggNm', '월세_평균월세액']])

print("\n--- 전세가 가장 저렴한 지역 TOP 5 ---")
print(jeonse_top5[['sggNm', '전세_평균보증금']])
