import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np

# --- 세션 상태 초기화 (최상단) ---
if "map_center" not in st.session_state:
    st.session_state.map_center = [36.5, 127.5] # 대한민국 중심 근처 디폴트
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 7
if "prev_sido" not in st.session_state:
    st.session_state.prev_sido = "전국"

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="전국 이사 가이드 및 인프라 분석 대시보드")

if st.button("🏠 홈으로 이동"):
    st.switch_page("app.py")

# --- 공통 상수 및 설정 ---
INFRA_COLS = ["school", "subway", "hospital", "cafe", "academy", "department", "convenience", "park", "culture"]
INFRA_LABELS = {
    "school": "학교", "subway": "지하철", "hospital": "병원", "cafe": "카페",
    "academy": "학원", "department": "백화점", "convenience": "편의점", "park": "공원", "culture": "문화"
}

def get_data_path(filename):
    # 루트 폴더의 data 폴더 참조
    return os.path.join("data", filename)

# --- 데이터 로드 함수 (통합) ---
@st.cache_data
def load_combined_data():
    summary_df = pd.read_csv(get_data_path('region_rent_summary.csv'))
    infra_df = pd.read_csv(get_data_path('전국_기초자치_인프라_점수.csv'))
    coord_df = pd.read_csv(get_data_path('korea_sigungu_coordinates.csv'))

    # 1. 공백 제거 및 문자열 타입 강제
    summary_df['region_name'] = summary_df['region_name'].astype(str).str.strip()
    infra_df['region_name'] = infra_df['region_name'].astype(str).str.strip()
    
    # sggNm 추출 (디스플레이용)
    summary_df['sggNm'] = summary_df['region_name'].apply(lambda x: x.split()[-1])

    # 2. 좌표 데이터 정리 (region_name 생성)
    if '시도' in coord_df.columns and '시군구명' in coord_df.columns:
        coord_df['region_name'] = coord_df['시도'].astype(str).str.strip() + " " + coord_df['시군구명'].astype(str).str.strip()
    elif '시도' in coord_df.columns and '시군구' in coord_df.columns:
        coord_df['region_name'] = coord_df['시도'].astype(str).str.strip() + " " + coord_df['시군구'].astype(str).str.strip()
    
    if 'region_name' in coord_df.columns:
        coord_df['region_name'] = coord_df['region_name'].str.strip()

    # 3. 병합 (left join으로 데이터 손실 방지)
    # 임대 요약 기준으로 인프라와 좌표를 붙임
    df = pd.merge(summary_df, infra_df, on='region_name', how='left')
    df = pd.merge(df, coord_df[['region_name', '위도', '경도', '시도']], on='region_name', how='left')

    # 4. 시도명 및 풀네임 정리
    if '시도' in df.columns and df['시도'].notna().any():
        df['sidoNm'] = df['시도'].fillna(df['region_name'].apply(lambda x: x.split()[0]))
    else:
        df['sidoNm'] = df['region_name'].apply(lambda x: x.split()[0])
    
    df['sidoNm'] = df['sidoNm'].replace({'전라북도': '전북특별자치도', '강원도': '강원특별자치도'})
    df['full_region'] = df['region_name']

    # 5. 인프라 점수 정규화 및 결측치 처리
    for col in INFRA_COLS:
        if col in df.columns:
            df[col] = df[col].fillna(0)
            min_v, max_v = df[col].min(), df[col].max()
            df[f'norm_{col}'] = (df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0
        else:
            df[f'norm_{col}'] = 0.0

    # 6. 테마별 점수 계산 (결측치 0 처리)
    df["total_score"] = df.get("total_score", 0).fillna(0)
    df["edu_score"] = (df.get("school", 0).fillna(0) + df.get("academy", 0).fillna(0))
    df["transport_comm_score"] = (df.get("subway", 0).fillna(0) + df.get("department", 0).fillna(0))
    df["life_medical_score"] = (df.get("hospital", 0).fillna(0) + df.get("convenience", 0).fillna(0) + df.get("cafe", 0).fillna(0))
    
    df["면적당_보증금"] = 0.0
    if "전세_평균보증금" in df.columns and "전세_평균면적" in df.columns:
        mask = (df["전세_평균면적"] > 0)
        df.loc[mask, "면적당_보증금"] = df.loc[mask, "전세_평균보증금"] / df.loc[mask, "전세_평균면적"]

    # 7. sggCd_key 더미 생성 (지도 마커 클릭 등 호환용)
    df['sggCd_key'] = [str(i) for i in range(len(df))]

    # 8. 필수 좌표 데이터가 있는 것만 유지
    df.dropna(subset=['위도', '경도'], inplace=True)
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
    st.header("🔎 분석 기준 설정")
    score_type = st.radio(
        "순위 산정 기준 선택", 
        ["나만의 맞춤 점수", "기본 인프라 점수"], 
        index=0,
        help="사용자가 설정한 가중치를 반영할지(Custom), 지역의 객관적 총점(Total)을 기반으로 할지 결정합니다.",
        key="score_type_select"
    )
    score_col = 'custom_score' if score_type.startswith("나만의") else 'total_score'

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
    # 데이터셋에 park가 없을 경우 culture가 있다면 대신 사용하도록 유연하게 대응
    park_val = view_df['norm_park'] if 'norm_park' in view_df.columns and view_df['norm_park'].sum() > 0 else view_df.get('norm_culture', 0)
    
    infra_score = ((view_df['norm_subway'] * w_subway) + 
                   ((view_df['norm_school'] + view_df['norm_academy']) / 2 * w_school) +
                   (view_df['norm_hospital'] * w_hospital) + 
                   (park_val * w_park) + 
                   (view_df['norm_department'] * w_mall))
    view_df['custom_score'] = (infra_score / w_sum * 100).round(1)
else:
    view_df['custom_score'] = 0.0

# --- 지역 변경 시 지도 좌표 업데이트 (안전한 계산) ---
if st.session_state.prev_sido != selected_sido:
    if not view_df.empty:
        new_lat = view_df['위도'].mean()
        new_lon = view_df['경도'].mean()
        # NaN 체크
        if pd.notna(new_lat) and pd.notna(new_lon):
            st.session_state.map_center = [new_lat, new_lon]
            st.session_state.map_zoom = 7 if selected_sido == "전국" else 11
    st.session_state.prev_sido = selected_sido

st.title(f"🏘️ {selected_sido} 이사 지역 선정 시뮬레이터")
col1, col2 = st.columns([6, 4])
selected_top5_codes = []

with col2:
    if selected_sido == "전국":
        st.subheader("📊 전국 분야별 TOP 5")
        theme = st.radio("추천 테마", ["💰 저렴한 월세", "🏠 저렴한 전세", "✨ 우수한 인프라"], horizontal=True, key="theme_radio")
        
        if theme == "💰 저렴한 월세":
            target_df = view_df[view_df['월세_평균월세'] > 0].sort_values('월세_평균월세').head(5)
            c_name = "월세_평균월세"
        elif theme == "🏠 저렴한 전세":
            target_df = view_df[view_df['전세_평균보증금'] > 0].sort_values('전세_평균보증금').head(5)
            c_name = "전세_평균보증금"
        else:
            target_df = view_df.sort_values(score_col, ascending=False).head(5)
            c_name = score_col

        selected_top5_codes = target_df['sggCd_key'].tolist()
        for i, (_, row) in enumerate(target_df.iterrows()):
            r_col1, r_col2 = st.columns([8, 2])
            val = format_price(row[c_name]) if c_name not in ['custom_score', 'total_score'] else f"{row[c_name]}점"
            r_col1.write(f"**{i+1}위. {row['full_region']}** : {val}")
            if r_col2.button("🔍", key=f"btn_{row['sggCd_key']}"):
                st.session_state.map_center, st.session_state.map_zoom = [row['위도'], row['경도']], 12
                st.rerun()
    else:
        st.subheader(f"🏆 {selected_sido} 맞춤 추천 TOP 5")
        top5 = view_df.sort_values(score_col, ascending=False).head(5)
        selected_top5_codes = top5['sggCd_key'].tolist()
        for i, (_, row) in enumerate(top5.iterrows()):
            ec1, ec2 = st.columns([8, 2])
            with ec1:
                with st.expander(f"{i+1}위: {row['full_region']}"):
                    p = row['전세_평균보증금'] if rent_type == "전세" else row['월세_평균월세']
                    st.write(f"💰 **평균 {rent_type}:** {format_price(p)} | ⭐ **점수:** {row[score_col]}점")
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
st.title("📊 인프라 데이터 심층 분석")

# 인프라 점수 계산 설명
with st.expander("💡 인프라 만족도 점수는 어떻게 계산되나요?"):
    st.write("핵심 인프라 수치를 0~1로 정규화한 뒤, 선택하신 기준(맞춤/기본)에 따라 100점 만점으로 환산한 결과입니다.")
    st.write("**[분석 지표]**")
    st.write("🎓 학교, 🚇 지하철, 🏥 병원, ☕ 카페, ✍️ 학원, 🛍️ 백화점, 🏪 편의점, 🌳 공원(또는 문화생활)")

st.info(f"📍 현재 **'{score_type}'** 기준으로 분석 중입니다.")

# 메인 바 차트
top20_df = view_df.sort_values(by=score_col, ascending=False).head(20)
fig_top20 = px.bar(
    top20_df, 
    x=score_col, 
    y="full_region", 
    color=score_col, 
    color_continuous_scale="Viridis",
    orientation="h",
    title=f"{selected_sido} {score_type} Top 20 지역",
    labels={score_col: "점수", "full_region": "지역명"}, 
    template="plotly_white"
)
fig_top20.update_layout(yaxis={"categoryorder": "total ascending"}, height=550)
st.plotly_chart(fig_top20, use_container_width=True)

# --- 분야별 상세 순위 (2x2) ---
st.write("---")
st.subheader("🚩 주요 분야별 상세 순위")
col_a, col_b = st.columns(2)
with col_a:
    fig_edu = px.bar(view_df.sort_values("edu_score", ascending=True).tail(15), x="edu_score", y="full_region", orientation="h", title="🎓 교육 환경 우수 Top 15")
    st.plotly_chart(fig_edu, use_container_width=True)
    fig_life = px.bar(view_df.sort_values("life_medical_score", ascending=True).tail(15), x="life_medical_score", y="full_region", orientation="h", title="🏥 생활/의료 인프라 Top 15")
    st.plotly_chart(fig_life, use_container_width=True)
with col_b:
    fig_trans = px.bar(view_df.sort_values("transport_comm_score", ascending=True).tail(15), x="transport_comm_score", y="full_region", orientation="h", title="🚇 교통/상권 중심지 Top 15")
    st.plotly_chart(fig_trans, use_container_width=True)
    
    # 가성비 (면적당 보증금 낮을수록 우수)
    rent_eff_df = view_df[view_df["면적당_보증금"] > 0]
    if not rent_eff_df.empty:
        fig_eff = px.bar(rent_eff_df.sort_values("면적당_보증금", ascending=False).tail(15), x="면적당_보증금", y="full_region", orientation="h", title="💰 임대 가성비(면적당 보증금 저렴) Top 15")
        st.plotly_chart(fig_eff, use_container_width=True)

# --- 지역별 인프라 DNA 비교 (레이더) ---
st.write("---")
st.subheader("🎯 지역별 인프라 DNA 비교")
target_regions = st.multiselect(
    "비교할 지역을 선택하세요 (최대 4개)", 
    options=view_df["full_region"].unique(), 
    default=view_df.sort_values(score_col, ascending=False)['full_region'].head(3).tolist()
)

if target_regions:
    fig_radar_cmp = go.Figure()
    for reg in target_regions[:4]:
        r_data = view_df[view_df["full_region"] == reg].iloc[0]
        radar_values = [r_data.get(f'norm_{c}', 0) * 100 for c in INFRA_COLS]
        fig_radar_cmp.add_trace(go.Scatterpolar(
            r=radar_values, 
            theta=[INFRA_LABELS.get(c, c) for c in INFRA_COLS], 
            fill="toself", 
            name=reg
        ))
    fig_radar_cmp.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])), 
        height=600, 
        title="지역별 인프라 구조 비교 (100점 만점 환산)"
    )
    st.plotly_chart(fig_radar_cmp, use_container_width=True)

# --- 상세 데이터 테이블 ---
st.divider()
st.subheader("📋 전체 지역 상세 데이터")
disp_df = view_df[['full_region', '전세_평균보증금', '월세_평균월세', 'custom_score', 'total_score']].copy()
disp_df = disp_df.sort_values(score_col, ascending=False).reset_index(drop=True)
disp_df.index += 1

disp_df['전세_평균보증금'] = disp_df['전세_평균보증금'].apply(format_price)
disp_df['월세_평균월세'] = disp_df['월세_평균월세'].apply(format_price)

disp_df.rename(columns={
    'full_region': '지역명', 
    '전세_평균보증금': '평균 전세가', 
    '월세_평균월세': '평균 월세액', 
    'custom_score': '나만의 점수', 
    'total_score': '기본 점수'
}, inplace=True)

st.dataframe(disp_df, use_container_width=True, height=500)
