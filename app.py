import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="전국 기초자치단체 인프라 대시보드", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("전국_기초자치_인프라_점수.csv")
    # 광역자치단체(시/도) 컬럼 생성 (앞 5글자 혹은 첫 단어 추출)
    df['sido'] = df['region_name'].apply(lambda x: x.split()[0])
    return df

df = load_data()

st.title("📊 전국 기초자치단체 8대 인프라 분석 대시보드")
st.markdown("전국 시/군/구별 인프라 점수를 비교하고 상세 항목을 분석합니다.")

# --- 사이드바: 필터 설정 ---
st.sidebar.header("🔍 필터 설정")
selected_sido = st.sidebar.multiselect(
    "광역자치단체(시/도) 선택", 
    options=df['sido'].unique(), 
    default=df['sido'].unique()[:3]
)

# 데이터 필터링
filtered_df = df[df['sido'].isin(selected_sido)]

# --- 메인 화면 1: 전국/지역 TOP 20 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 인프라 종합 점수 TOP 20")
    top_20 = filtered_df.sort_values(by='total_score', ascending=False).head(20)
    fig_bar = px.bar(
        top_20, x='total_score', y='region_name', orientation='h',
        color='total_score', color_continuous_scale='Viridis',
        labels={'total_score': '종합 점수', 'region_name': '지역명'}
    )
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    st.subheader("📉 인프라 항목 간 상관관계")
    infra_cols = ["school", "subway", "hospital", "cafe", "academy", "department", "convenience", "park"]
    corr = filtered_df[infra_cols].corr()
    fig_heat = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r')
    st.plotly_chart(fig_heat, use_container_width=True)

# --- 메인 화면 2: 상세 비교 (레이더 차트) ---
st.divider()
st.subheader("🎯 지역별 인프라 DNA 비교 (레이더 차트)")

target_regions = st.multiselect("비교할 지역을 선택하세요 (최대 3개)", options=filtered_df['region_name'].unique(), default=filtered_df['region_name'].unique()[:2])

if target_regions:
    fig_radar = go.Figure()
    for region in target_regions:
        region_data = df[df['region_name'] == region].iloc[0]
        fig_radar.add_trace(go.Scatterpolar(
            r=[region_data[c] for c in infra_cols],
            theta=infra_cols,
            fill='toself',
            name=region
        ))
    
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, filtered_df[infra_cols].max().max()])),
        showlegend=True
    )
    st.plotly_chart(fig_radar, use_container_width=True)

# --- 메인 화면 3: 데이터 테이블 ---
st.subheader("📋 상세 데이터 확인")
st.dataframe(filtered_df.sort_values(by='total_score', ascending=False), use_container_width=True)