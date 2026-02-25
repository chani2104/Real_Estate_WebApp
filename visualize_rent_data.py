import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# 1. 한글 폰트 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False # 마이너스 부호 깨짐 방지

# 데이터 불러오기
df = pd.read_csv('region_rent_summary.csv')

# 2. 차트 1 (시장 성격): '월세비중(%)'이 가장 높은 상위 15개 지역
plt.figure(figsize=(12, 8))
top15_wolse_ratio = df.sort_values('월세비중(%)', ascending=False).head(15)
sns.barplot(x='월세비중(%)', y='sggNm', data=top15_wolse_ratio)
plt.title('월세 비중이 가장 높은 상위 15개 지역')
plt.xlabel('월세 비중 (%)')
plt.ylabel('시군구')
plt.tight_layout()
plt.savefig('chart1_wolse_ratio.png')
plt.close()

# 3. 차트 2 (전세 가성비): x축은 '전세_평균전용면적', y축은 '전세_평균보증금'
# 전세 거래가 있는 지역만
jeonse_df = df[df['전세_거래건수'] > 0]
plt.figure(figsize=(12, 8))
sns.scatterplot(x='전세_평균전용면적', y='전세_평균보증금', data=jeonse_df)
for i, row in jeonse_df.iterrows():
    plt.text(row['전세_평균전용면적'], row['전세_평균보증금'], row['sggNm'], size=8)
plt.title('전세 평균 전용면적 vs 평균 보증금')
plt.xlabel('평균 전용면적 (㎡)')
plt.ylabel('평균 보증금')
plt.grid(True)
plt.tight_layout()
plt.savefig('chart2_jeonse_value.png')
plt.close()

# 4. 차트 3 (월세 시장): '월세_거래건수'가 많은 상위 10개 지역의 '월세_평균월세액'
plt.figure(figsize=(12, 8))
top10_wolse_count = df.sort_values('월세_거래건수', ascending=False).head(10)
sns.barplot(x='월세_평균월세액', y='sggNm', data=top10_wolse_count)
plt.title('월세 거래가 많은 상위 10개 지역의 평균 월세액')
plt.xlabel('평균 월세액')
plt.ylabel('시군구')
plt.tight_layout()
plt.savefig('chart3_wolse_market.png')
plt.close()

# 5. 상관관계: heatmap
plt.figure(figsize=(10, 8))
corr_df = df[['전세_평균보증금', '전세_평균전용면적', '전세_거래건수', '월세_평균보증금', '월세_평균월세액', '월세_거래건수']].corr()
sns.heatmap(corr_df, annot=True, cmap='coolwarm', fmt=".2f")
plt.title('주요 수치 간 상관관계')
plt.tight_layout()
plt.savefig('chart4_correlation_heatmap.png')
plt.close()

print("시각화 분석이 완료되었으며, 다음 파일들이 생성되었습니다:")
print("- chart1_wolse_ratio.png: 월세 비중 상위 15개 지역")
print("- chart2_jeonse_value.png: 전세 가성비 지역")
print("- chart3_wolse_market.png: 월세 시장 분석")
print("- chart4_correlation_heatmap.png: 주요 수치 상관관계 히트맵")
