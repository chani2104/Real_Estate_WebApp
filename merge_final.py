import pandas as pd

# 1️⃣ 불러오기
infra_df = pd.read_csv("전국_기초자치_인프라_점수.csv", encoding="utf-8-sig")
rent_df = pd.read_csv("region_rent_summary_v2.csv", encoding="utf-8-sig")

# 2️⃣ 병합 (🔥 인프라 기준)
merged_df = pd.merge(
    infra_df,
    rent_df,
    on="region_name",
    how="left"
)

# 3️⃣ NaN 처리
merged_df.fillna(0, inplace=True)

# 4️⃣ 저장
merged_df.to_csv("region_rent_infra_final.csv",
                 index=False,
                 encoding="utf-8-sig")

print("✅ 최종 통합 완료")
print(f"총 지역 수: {len(merged_df)}")