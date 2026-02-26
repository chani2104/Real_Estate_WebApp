import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# 1. 한글 폰트 및 마이너스 깨짐 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False 

# 2. 데이터 로드
try:
    summary_df = pd.read_csv('../data/region_rent_summary.csv')
    original_df = pd.read_csv('../data/national_rent_data_202401.csv', encoding='utf-8-sig')
    print("✅ 데이터 로드 성공")
except Exception as e:
    print(f"❌ 로드 실패: {e}")
    exit()

# 3. [핵심] 시군구 코드(sggCd)를 활용해 시도명(sidoNm) 생성
# 법정동 코드 앞 2자리 매핑 테이블
sido_mapping = {
    '11': '서울', '21': '부산', '22': '대구', '23': '인천', 
    '24': '광주', '25': '대전', '26': '울산', '29': '세종', 
    '41': '경기', '42': '강원', '43': '충북', '44': '충남', 
    '45': '전북', '46': '전남', '47': '경북', '48': '경남', '50': '제주'
}

# original_df에서 sggCd를 기반으로 sidoNm 만들기
original_df['sggCd_prefix'] = original_df['sggCd'].astype(str).str[:2]
original_df['sidoNm'] = original_df['sggCd_prefix'].map(sido_mapping)

# 시도명과 시군구명 쌍 추출
region_map = original_df[['sidoNm', 'sggNm']].drop_duplicates()

# 4. 요약 데이터와 합쳐서 'full_region' 만들기
# 요약본에 시도명이 없다면 merge로 붙여줌
if 'sidoNm' not in summary_df.columns:
    summary_df = pd.merge(summary_df, region_map, on='sggNm', how='left')

# 최종 지역명 (예: 서울 종로구)
summary_df['full_region'] = summary_df['sidoNm'].fillna('기타') + " " + summary_df['sggNm']
print("🚀 지역명 통합 완료 (예: 서울 종로구)")

# --- 시각화 실행 (차트 1: 전세 저렴 TOP 15) ---
jeonse_df = summary_df[summary_df['전세_거래건수'] > 0].sort_values('전세_평균보증금').head(15)
plt.figure(figsize=(12, 8))
sns.barplot(x='전세_평균보증금', y='full_region', data=jeonse_df, palette='viridis')
plt.title('평균 전세 보증금이 가장 저렴한 지역 TOP 15')
plt.xlabel('보증금 (만원)')
plt.ylabel('지역')
plt.tight_layout()
plt.savefig('moving_chart1_cheapest_jeonse.png')
plt.close()

# --- 시각화 실행 (차트 2: 거래 핫플레이스 히트맵) ---
top20 = summary_df.sort_values('전체_거래건수', ascending=False).head(20)
plt.figure(figsize=(10, 10))
sns.heatmap(top20.set_index('full_region')[['전체_거래건수']], annot=True, cmap='YlGnBu', fmt='.0f')
plt.title('거래가 가장 활발한 지역 TOP 20')
plt.tight_layout()
plt.savefig('moving_chart2_transaction_hotspot.png')
plt.close()

# --- 시각화 실행 (차트 3: 가성비 분석) ---
value_df = summary_df[(summary_df['전세_거래건수'] > 0) & (summary_df['전세_평균전용면적'] > 0)].copy()
value_df['면적당_보증금'] = value_df['전세_평균보증금'] / value_df['전세_평균전용면적']
top15_val = value_df.sort_values('면적당_보증금').head(15)
plt.figure(figsize=(12, 8))
sns.barplot(x='면적당_보증금', y='full_region', data=top15_val, palette='magma')
plt.title('전세 가성비(면적당 보증금)가 좋은 지역 TOP 15')
plt.tight_layout()
plt.savefig('moving_chart3_value_for_money.png')
plt.close()

# --- 시각화 실행 (차트 4: 건축년도 vs 가격) ---
original_df['full_region'] = original_df['sidoNm'].fillna('') + " " + original_df['sggNm']
original_df['deposit_num'] = pd.to_numeric(original_df['deposit'].astype(str).str.replace(',', ''), errors='coerce')
original_jeonse = original_df[original_df['monthlyRent'] == 0]
build_price = original_jeonse.groupby('full_region').agg({'buildYear': 'mean', 'deposit_num': 'mean', 'sggNm': 'count'}).reset_index()
build_price = build_price[build_price['sggNm'] >= 5] # 5건 이상만

plt.figure(figsize=(15, 10))
sns.scatterplot(x='buildYear', y='deposit_num', data=build_price, s=100, alpha=0.7)
for i, row in build_price.iterrows():
    plt.text(row['buildYear']+0.1, row['deposit_num'], row['full_region'], size=8)
plt.title('평균 건축년도 vs 전세 보증금 상관관계')
plt.grid(True)
plt.savefig('moving_chart4_buildyear_vs_price.png')
plt.close()

# --- 시각화 실행 (차트 5: 월세 비중) ---
wolse_top = summary_df.sort_values('월세비중(%)', ascending=False).head(20)
fig, ax1 = plt.subplots(figsize=(12, 10))
sns.barplot(x='월세비중(%)', y='full_region', data=wolse_top, ax=ax1, color='lightgray')
ax2 = ax1.twiny()
sns.lineplot(x='월세_평균월세액', y='full_region', data=wolse_top, ax=ax2, color='red', marker='o')
plt.title('월세 비중이 높은 지역 및 평균 월세액')
plt.savefig('moving_chart5_rental_personality.png')
plt.close()

print("✨ 모든 시각화 차트가 '시도명 포함' 버전으로 생성되었습니다!")