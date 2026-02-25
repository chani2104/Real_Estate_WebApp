import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# 1. 한글 폰트 및 환경 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False 

# 데이터 불러오기
df = pd.read_csv('region_rent_summary.csv')

# --- 데이터 전처리 및 파생변수 생성 ---
# 6번 가성비 지표: 전세 데이터가 있는 경우만 계산 (분모가 0인 경우 방지)
df['전세_면적당보증금'] = df.apply(lambda x: x['전세_평균보증금'] / x['전세_평균전용면적'] if x['전세_평균전용면적'] > 0 else 0, axis=1)

# 7번 월세 효율 지표: 월세 데이터가 있는 경우만 계산
df['월세_면적당월세액'] = df.apply(lambda x: x['월세_평균월세액'] / x['월세_평균전용면적'] if x['월세_평균전용면적'] > 0 else 0, axis=1)

# 시각화 가독성을 위해 상위 지역 추출 시 사용할 데이터 정렬
df_top20_total = df.nlargest(10, '전체_거래건수')
df_top20_rent = df.sort_values('월세_평균월세액', ascending=False).head(20)

# --- 시각화 시작 ---

# ① 거래량 상위 30개 지역별 월세 비중(%) 선 그래프
plt.figure(figsize=(15, 6))
df_top30 = df.sort_values('전체_거래건수', ascending=False).head(30)
sns.lineplot(data=df_top30, x='sggNm', y='월세비중(%)', marker='o', color='royalblue', linewidth=2)

# 수치 표시
for i, val in enumerate(df_top30['월세비중(%)']):
    plt.text(i, val + 2, f'{val:.1f}%', ha='center', fontsize=9)

plt.title('① 거래량 상위 30개 지역별 월세 비중 (%)')
plt.xticks(rotation=45)
plt.grid(True, axis='y', linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig('01_monthly_rent_ratio_line.png')
plt.close()

# ② 전세/월세 거래 건수 비교 바 차트 (전체 거래 상위 20개 지역)
top20_vol = df.nlargest(20, '전체_거래건수')
top20_vol.plot(x='sggNm', y=['전세_거래건수', '월세_거래건수'], kind='bar', stacked=True, figsize=(12, 6), color=['skyblue', 'orange'])
plt.title('② 지역별 전세/월세 거래 건수 비교 (상위 20개 지역)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('02_transaction_volume_comparison.png')
plt.close()

# ③ 전세 보증금 vs 월세 보증금 산점도
plt.figure(figsize=(10, 8))
sns.scatterplot(data=df[df['전세_평균보증금'] > 0], x='전세_평균보증금', y='월세_평균보증금', size='전체_거래건수', hue='전체_거래건수', sizes=(20, 500), alpha=0.6)
plt.title('③ 전세 보증금 vs 월세 보증금 분포')
plt.grid(True, linestyle='--', alpha=0.5)
plt.savefig('03_deposit_scatterplot.png')
plt.close()

# ④ 지역별 평균 월세액 순위 (상위 20개 지역)
plt.figure(figsize=(12, 6))
sns.barplot(data=df_top20_rent, x='sggNm', y='월세_평균월세액', palette='Reds_r')
plt.title('④ 지역별 평균 월세액 순위 (Top 20)')
plt.xticks(rotation=45)
plt.savefig('04_avg_monthly_rent_rank.png')
plt.close()

# ⑤ 전체 거래 건수 상위 20개 지역
plt.figure(figsize=(10, 6))
sns.barplot(data=df_top20_total, x='전체_거래건수', y='sggNm', palette='viridis')
plt.title('⑤ 전체 거래 활성도 상위 20개 지역')
plt.savefig('05_top20_transaction_areas.png')
plt.close()

# ⑥ 면적당 전세가(가성비) 지표 (전세 데이터 있는 곳 중 하위 15개 - 저렴한 순)
plt.figure(figsize=(12, 6))
df_jeonse_eff = df[df['전세_면적당보증금'] > 0].nsmallest(15, '전세_면적당보증금')
sns.barplot(data=df_jeonse_eff, x='sggNm', y='전세_면적당보증금', palette='GnBu')
plt.title('⑥ 면적당 전세가 낮은 지역 (가성비 Top 15)')
plt.ylabel('보증금 / 전용면적')
plt.savefig('06_jeonse_efficiency.png')
plt.close()

# ⑦ 면적당 월세 효율 지표 (상위 15개 - 면적 대비 월세 비싼 순)
plt.figure(figsize=(12, 6))
df_rent_eff = df[df['월세_면적당월세액'] > 0].nlargest(15, '월세_면적당월세액')
sns.barplot(data=df_rent_eff, x='sggNm', y='월세_면적당월세액', palette='OrRd')
plt.title('⑦ 면적당 월세액 높은 지역 (단위 면적당 주거비 부담 Top 15)')
plt.ylabel('월세액 / 전용면적')
plt.savefig('07_rent_efficiency.png')
plt.close()

# ⑧ 지역별 평균 전용면적 비교 (전체 거래 상위 15개 지역)
plt.figure(figsize=(12, 6))
df_area = df.nlargest(15, '전체_거래건수')
df_area.plot(x='sggNm', y=['전세_평균전용면적', '월세_평균전용면적'], kind='bar', figsize=(12, 6))
plt.title('⑧ 주요 지역 전세 vs 월세 평균 전용면적')
plt.xticks(rotation=45)
plt.savefig('08_area_comparison.png')
plt.close()

# ⑨ 월세액과 전용면적의 상관관계 (Regplot)
plt.figure(figsize=(10, 6))
sns.regplot(data=df[df['월세_평균월세액'] > 0], x='월세_평균전용면적', y='월세_평균월세액', scatter_kws={'alpha':0.5}, line_kws={'color':'red'})
plt.title('⑨ 월세액과 전용면적의 상관관계')
plt.grid(True)
plt.savefig('09_rent_area_correlation.png')
plt.close()

print("모든 시각화 파일이 png 형태로 저장되었습니다.")