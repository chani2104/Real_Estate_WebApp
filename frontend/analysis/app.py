import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="전국 이사 가이드 및 인프라 분석 대시보드")

# --- 공통 상수 및 설정 ---
INFRA_COLS = ["school", "subway", "hospital", "cafe", "academy", "department", "convenience", "park"]
INFRA_LABELS = {
    "school": "학교", "subway": "지하철", "hospital": "병원", "cafe": "카페",
    "academy": "학원", "department": "백화점", "convenience": "편의점", "park": "공원"
}

def get_data_path(filename):
    # data 폴더 위치를 상대 경로로 찾음
    base_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(base_dir, "../../data", filename))

# --- 데이터 로드 함수 (통합) ---
@st.cache_data
def load_combined_data():
    summary_df = pd.read_csv(get_data_path('region_rent_summary.csv'))
    original_df = pd.read_csv(get_data_path('national_rent_data_202401.csv'), encoding='utf-8-sig')
    infra_df = pd.read_csv(get_data_path('전국_기초자치_인프라_점수.csv'))
    coord_df = pd.read_csv(get_data_path('korea_sigungu_coordinates.csv'))

    if 'sggNm' not in original_df.columns and 'region_name' in original_df.columns:
        original_df['sggNm'] = original_df['region_name']

    code_map = original_df[['sggNm', 'sggCd']].drop_duplicates()
    
    if 'sggNm' not in summary_df.columns:
         summary_df.rename(columns={'region_name': 'sggNm'}, inplace=True)
         
    summary_df = pd.merge(summary_df, code_map, on='sggNm', how='left')

    infra_df['sggCd_key'] = infra_df['dong_code'].astype(str).str[:5]
    summary_df['sggCd_key'] = summary_df['sggCd'].astype(str).str.split('.').str[0].str.zfill(5).str[:5]
    coord_df['sggCd_key'] = coord_df['시군구코드'].astype(str).str.zfill(5).str[:5]

    df = pd.merge(summary_df, infra_df, on='sggCd_key', how='inner')
    df = pd.merge(df, coord_df[['sggCd_key', '위도', '경도', '시도']], on='sggCd_key', how='left')

    df['sidoNm'] = df['시도'].replace({'전라북도': '전북특별자치도', '강원도': '강원특별자치도'})
    df['full_region'] = df['sidoNm'] + " " + df['sggNm']

    for col in INFRA_COLS:
        if col in df.columns:
            min_v, max_v = df[col].min(), df[col].max()
            df[f'norm_{col}'] = (df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0

    df["edu_score"] = df.get("school", 0) + df.get("academy", 0)
    df["transport_comm_score"] = df.get("subway", 0) + df.get("department", 0)
    df["life_medical_score"] = df.get("hospital", 0) + df.get("convenience", 0) + df.get("cafe", 0)
    
    df["면적당_보증금"] = 0.0
    if "전세_평균보증금" in df.columns and "전세_평균면적" in df.columns:
        mask = (df["전세_평균면적"] > 0)
        df.loc[mask, "면적당_보증금"] = df.loc[mask, "전세_평균보증금"] / df.loc[mask, "전세_평균면적"]

    df.dropna(subset=['full_region', '위도', '경도'], inplace=True)
    return df

def format_price(val):
    if pd.isna(val) or val == 0: return "정보 없음"
    val = int(val)
    if val >= 10000:
        억, 천 = val // 10000, (val % 10000) // 1000 * 1000
        return f"{억}억 {천:,}만원" if 천 > 0 else f"{억}억원"
    return f"{val:,}만원"

try:
    df = load_combined_data()
except Exception as e:
    st.error(f"데이터 로드 오류: {e}"); st.stop()

# --- 사이드바 ---
with st.sidebar:
    st.header("🔍 메인 검색 필터")
    all_sido = ["전국"] + sorted(df['sidoNm'].dropna().unique().tolist())
    selected_sido = st.selectbox("분석 지역 선택", all_sido, key="main_sido_select")
    rent_type = st.radio("거래 유형 선택", ["전세", "월세"], key="main_rent_radio")

    st.divider()
    st.header("🎯 내 맞춤 가중치")
    st.caption("나에게 중요한 항목의 점수를 높여주세요.")
    w_subway = st.slider("🚇 역세권", 0, 5, 3, key="w_sub")
    w_school = st.slider("🎓 교육", 0, 5, 2, key="w_sch")
    w_hospital = st.slider("🏥 의료", 0, 5, 2, key="w_hos")
    w_park = st.slider("🌳 숲세권", 0, 5, 2, key="w_par")
    w_mall = st.slider("🛍️ 쇼핑", 0, 5, 1, key="w_mal")

view_df = df.copy()
if selected_sido != "전국":
    view_df = view_df[view_df['sidoNm'] == selected_sido]

w_sum = w_subway + w_school + w_hospital + w_park + w_mall
if w_sum > 0:
    infra_score = ((view_df['norm_subway'] * w_subway) + ((view_df['norm_school'] + view_df['norm_academy']) / 2 * w_school) +
                   (view_df['norm_hospital'] * w_hospital) + (view_df['norm_park'] * w_park) + (view_df['norm_department'] * w_mall))
    view_df['custom_score'] = (infra_score / w_sum * 100).round(1)
else:
    view_df['custom_score'] = 0.0

st.title(f"🏘️ {selected_sido} 이사 지역 선정 시뮬레이터")
col1, col2 = st.columns([6, 4])
selected_top5_codes = []

with col2:
    if selected_sido == "전국":
        st.subheader("📊 전국 분야별 TOP 5")
        theme = st.radio("추천 테마", ["💰 저렴한 월세", "🏠 저렴한 전세", "✨ 우수한 인프라"], horizontal=True, key="theme_radio")
        
        if theme == "💰 저렴한 월세":
            target_df = view_df[view_df['월세_평균월세액'] > 0].sort_values('월세_평균월세액').head(5)
            c_name = "월세_평균월세액"
        elif theme == "🏠 저렴한 전세":
            target_df = view_df[view_df['전세_평균보증금'] > 0].sort_values('전세_평균보증금').head(5)
            c_name = "전세_평균보증금"
        else:
            target_df = view_df.sort_values('custom_score', ascending=False).head(5)
            c_name = "custom_score"

        selected_top5_codes = target_df['sggCd_key'].tolist()
        for i, (_, row) in enumerate(target_df.iterrows()):
            r_col1, r_col2 = st.columns([8, 2])
            val = format_price(row[c_name]) if c_name != "custom_score" else f"{row[c_name]}점"
            r_col1.write(f"**{i+1}위. {row['full_region']}** : {val}")
            if r_col2.button("🔍", key=f"btn_{row['sggCd_key']}"):
                st.session_state.map_center, st.session_state.map_zoom = [row['위도'], row['경도']], 12
                st.rerun()
    else:
        st.subheader(f"🏆 {selected_sido} 맞춤 추천 TOP 5")
        top5 = view_df.sort_values('custom_score', ascending=False).head(5)
        selected_top5_codes = top5['sggCd_key'].tolist()
        for i, (_, row) in enumerate(top5.iterrows()):
            ec1, ec2 = st.columns([8, 2])
            with ec1:
                with st.expander(f"{i+1}위: {row['full_region']}"):
                    p = row['전세_평균보증금'] if rent_type == "전세" else row['월세_평균월세액']
                    st.write(f"💰 **평균 {rent_type}:** {format_price(p)} | ⭐ **점수:** {row['custom_score']}점")
                    st.progress(float(row['norm_subway']), text="지하철")
                    st.progress(float(row['norm_hospital']), text="의료")
            if ec2.button("🔍", key=f"det_{row['sggCd_key']}"):
                st.session_state.map_center, st.session_state.map_zoom = [row['위도'], row['경도']], 13
                st.rerun()

with col1:
    st.subheader("📍 지역별 추천 지도")
    if st.button("지도 초기화 🔄"):
        st.session_state.map_center = [view_df['위도'].mean(), view_df['경도'].mean()]
        st.session_state.map_zoom = 7 if selected_sido == "전국" else 11
        st.rerun()

    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
    for _, row in view_df.iterrows():
        is_t5 = row['sggCd_key'] in selected_top5_codes
        color = 'red' if is_t5 else ('blue' if rent_type == "전세" else 'orange')
        folium.CircleMarker(
            location=[row['위도'], row['경도']],
            radius=(row['custom_score'] / 10) + 4 if is_t5 else (row['custom_score'] / 10) + 2,
            popup=f"{row['full_region']}<br>점수: {row['custom_score']}",
            color=color, fill=True, fill_opacity=0.7, weight=5 if is_t5 else 1
        ).add_to(m)
    st_folium(m, width="100%", height=600, key="main_map")

st.divider()
st.title("📊 인프라 데이터 심층 시각화")
top20_df = view_df.sort_values(by="custom_score", ascending=False).head(20)
fig_top20 = px.bar(top20_df, x="custom_score", y="full_region", color="sidoNm", orientation="h",
                   title=f"{selected_sido} 인프라 만족도 Top 20 지역")
st.plotly_chart(fig_top20, use_container_width=True)
