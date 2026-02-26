import pandas as pd

# 1. 파일 로드
infra_df = pd.read_csv('전국_기초자치_인프라_점수.csv')
rent_df = pd.read_csv('region_rent_summary_v2.csv')

# 2. 컬럼명 공백 제거 (KeyError 방지)
infra_df.columns = infra_df.columns.str.strip()
rent_df.columns = rent_df.columns.str.strip()

# 3. 데이터 통합 (Left Join)
# how='left'를 사용하면 infra_df의 모든 지역(속초시 등)이 유지됩니다.
merged_df = pd.merge(infra_df, rent_df, on='region_name', how='left')

# 4. 결측치 처리
# 일치하는 값이 없는 경우(부동산 정보가 없는 경우) NaN을 0.0으로 채웁니다.
merged_df = merged_df.fillna(0.0)

# 5. 결과 저장
merged_df.to_csv('region_rent_infra_final.csv', index=False, encoding='utf-8-sig')

print(f"✅ 통합 완료! 총 {len(merged_df)}개의 지역 데이터가 보존되었습니다.")
print("--- 병합 결과 예시 (속초시 등 포함) ---")
print(merged_df[merged_df['region_name'].str.contains('속초시', na=False)])