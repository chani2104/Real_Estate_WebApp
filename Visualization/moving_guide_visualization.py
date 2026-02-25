import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# 1. 공통 설정: 한글 폰트 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 부호 깨짐 방지

# 데이터 불러오기
summary_df = pd.read_csv('region_rent_summary.csv')
original_df = pd.read_csv('national_rent_data_202401.csv', encoding='utf-8-sig')


# --- 차트 1: [가격 비교] 전세 가장 저렴한 TOP 15 ---
jeonse_df = summary_df[summary_df['전세_거래건수'] > 0].sort_values('전세_평균보증금').head(15)

plt.figure(figsize=(12, 8))
sns.barplot(x='전세_평균보증금', y='sggNm', data=jeonse_df)
plt.title('전세 보증금이 가장 저렴한 상위 15개 지역 (시도명 포함)')
plt.xlabel('평균 전세 보증금')
plt.ylabel('시군구')
plt.tight_layout()
plt.savefig('moving_chart1_cheapest_jeonse.png')
plt.close()
print("[이사 팁 1] 초기 자금 부담이 적은 전세 지역을 찾고 있다면 다음 지역들을 고려해보세요.")


# --- 차트 2: [거래 핫플레이스] 거래량 히트맵 ---
top20_transactions = summary_df.sort_values('전체_거래건수', ascending=False).head(20)
plt.figure(figsize=(10, 10))
sns.heatmap(top20_transactions[['전체_거래건수']], yticklabels=top20_transactions['sggNm'], annot=True, cmap='viridis', fmt='.0f')
plt.title('전체 거래 건수가 가장 많은 상위 20개 지역 (거래 핫플레이스, 시도명 포함)')
plt.ylabel('시군구')
plt.tight_layout()
plt.savefig('moving_chart2_transaction_hotspot.png')
plt.close()
print("[이사 팁 2] 시도명을 포함하여 확인하니, 어느 도시의 거래가 가장 활발한지 한눈에 알 수 있습니다.")

# --- 차트 3: [가성비 분석] 면적당 보증금 낮은 순 (전세) ---
# 0으로 나누는 것을 방지
value_df = summary_df[(summary_df['전세_거래건수'] > 0) & (summary_df['전세_평균전용면적'] > 0)].copy()
value_df['면적당_보증금'] = value_df['전세_평균보증금'] / value_df['전세_평균전용면적']
top15_value = value_df.sort_values('면적당_보증금').head(15)

plt.figure(figsize=(12, 8))
sns.barplot(x='면적당_보증금', y='sggNm', data=top15_value)
plt.title('전세 가성비(면적당 보증금)가 좋은 상위 15개 지역 (시도명 포함)')
plt.xlabel('1㎡당 평균 전세 보증금')
plt.ylabel('시군구')
plt.tight_layout()
plt.savefig('moving_chart3_value_for_money.png')
plt.close()
print("[이사 팁 3] 같은 가격이라도 더 넓은 집을 원한다면 '면적당 보증금'이 낮은 지역을 눈여겨보세요.")


# --- 차트 4: [신축/구축 분포] 건축년도 vs 가격 ---
# 원본 데이터 전처리
if original_df['deposit'].dtype == 'object':
    original_df['deposit'] = original_df['deposit'].str.replace(',', '').astype(float)
original_df['buildYear'] = pd.to_numeric(original_df['buildYear'], errors='coerce')

# 원본 데이터에서 지역별 평균 건축년도 및 평균 보증금 계산 (전세만)
original_jeonse = original_df[original_df['monthlyRent'] == 0]
build_year_price = original_jeonse.groupby('sggNm').agg(
    평균_건축년도=('buildYear', 'mean'),
    평균_보증금=('deposit', 'mean')
).reset_index()

# 거래가 5건 이상인 지역만 필터링하여 신뢰도 높이기
sgg_counts = original_jeonse['sggNm'].value_counts().reset_index()
sgg_counts.columns = ['sggNm', 'count']
reliable_sgg = sgg_counts[sgg_counts['count'] >= 5]['sggNm']
build_year_price_reliable = build_year_price[build_year_price['sggNm'].isin(reliable_sgg)]


plt.figure(figsize=(15, 10))
sns.scatterplot(x='평균_건축년도', y='평균_보증금', data=build_year_price_reliable, s=100, alpha=0.7)
for i, row in build_year_price_reliable.iterrows():
    plt.text(row['평균_건축년도'] + 0.1, row['평균_보증금'], row['sggNm'], size=9)

plt.title('지역별 평균 건축년도 vs 평균 전세 보증금 (거래 5건 이상 지역, 시도명 포함)')
plt.xlabel('평균 건축년도 (높을수록 신축)')
plt.ylabel('평균 전세 보증금')
plt.grid(True)
plt.tight_layout()
plt.savefig('moving_chart4_buildyear_vs_price.png')
plt.close()
print("[이사 팁 4] 저렴하면서도 비교적 신축인 집을 원한다면 차트의 좌측 하단에 위치한 지역들을 살펴보세요.")


# --- 차트 5: [임대 성격] 월세 비중별 지역 분포 ---
wolse_focus_df = summary_df.sort_values('월세비중(%)', ascending=False).head(20)

fig, ax1 = plt.subplots(figsize=(12, 10))

# 월세 비중 barplot
sns.barplot(x='월세비중(%)', y='sggNm', data=wolse_focus_df, ax=ax1, color='lightgray', label='월세 비중')
ax1.set_xlabel('월세 비중 (%)')
ax1.set_ylabel('시군구')
ax1.legend(loc='lower right')


# 월세액 line plot
ax2 = ax1.twiny()
sns.lineplot(x='월세_평균월세액', y='sggNm', data=wolse_focus_df, ax=ax2, color='r', marker='o', label='평균 월세액')
ax2.set_xlabel('평균 월세액')
ax2.legend(loc='upper right')

plt.title('월세 비중이 높은 지역의 평균 월세액 분포 (시도명 포함)')
plt.tight_layout()
plt.savefig('moving_chart5_rental_personality.png')
plt.close()
print("[이사 팁 5] 월세 중심 지역이라도 월세액은 다양합니다. 월세 비중과 함께 실제 월세 가격을 비교하여 합리적인 선택을 하세요.")
