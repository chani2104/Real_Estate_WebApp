import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os

# ==========================================================
# 1. 설정 및 상수
# ==========================================================
st.set_page_config(layout="wide", page_title="부동산 가이드 v4")

THEME_CONFIG = {
    "월세": {"color": "green", "metric": "월세_평균월세", "label": "💰 월세가 저렴한 지역 TOP 5", "asc": True},
    "전세": {"color": "blue", "metric": "전세_평균보증금", "label": "🏠 전세가 저렴한 지역 TOP 5", "asc": True},
    "인프라": {"color": "crimson", "metric": "custom_score", "label": "✨ 인프라 만족도 상위 TOP 5", "asc": False}
}

INFRA_LABELS = {
    "school": "학교", "subway": "지하철", "hospital": "병원", "cafe": "카페",
    "academy": "학원", "department": "백화점", "convenience": "편의점", "culture": "문화생활"
}
INFRA_COLS = list(INFRA_LABELS.keys())

# ==========================================================
# 2. 헬퍼 함수 및 데이터 로드
# ==========================================================
def format_price(val):
    if pd.isna(val) or val <= 0: return "정보 없음"
    val = int(val)
    if val >= 10000:
        억, 천 = val // 10000, val % 10000
        return f"{억}억 {천:,}만원" if 천 > 0 else f"{억}억원"
    return f"{val:,}만원"

@st.cache_data
def load_data():
    def get_path(f): return f"data/{f}" if os.path.exists(f"data/{f}") else f
    try:
        main_df = pd.read_csv(get_path('region_rent_infra_final.csv'))
        coord_df = pd.read_csv(get_path('korea_sigungu_coordinates.csv'))
    except Exception as e:
        st.error(f"데이터 파일 로드 실패: {e}")
        st.stop()

    main_df['sidoNm'] = main_df['region_name'].str.split().str[0].replace({'전라북도': '전북특별자치도', '강원도': '강원특별자치도'})
    main_df['sggCd_key'] = main_df['sigungu_code'].astype(str).str.zfill(5).str[:5]
    coord_df['sggCd_key'] = coord_df['시군구코드'].astype(str).str.zfill(5).str[:5]
    
    df = pd.merge(main_df, coord_df[['sggCd_key', '위도', '경도']], on='sggCd_key', how='left')
    df.dropna(subset=['region_name', '위도', '경도'], inplace=True)
    
    for col in INFRA_COLS:
        if col in df.columns:
            min_v, max_v = df[col].min(), df[col].max()
            df[f'norm_{col}'] = (df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0
            
    df["edu_score"] = df.get("school", 0) + df.get("academy", 0)
    df["transport_comm_score"] = df.get("subway", 0) + df.get("department", 0)
    df["life_medical_score"] = df.get("hospital", 0) + df.get("convenience", 0) + df.get("cafe", 0)
    return df

df = load_data()

# ==========================================================
# 3. 사이드바 및 필터링
# ==========================================================
with st.sidebar:
    st.header("🗺️ 조건 선택")
    selected_sido = st.selectbox("분석 시도", ["전국"] + sorted(df['sidoNm'].unique().tolist()))
    st.divider()
    score_type = st.radio("순위 산정 기준", ["나만의 맞춤 점수", "기본 인프라 점수"])
    score_col = 'custom_score' if score_type.startswith("나만의") else 'total_score'
    score_label = "나만의 맞춤 점수" if score_col == 'custom_score' else "기본 인프라 점수"
    
    st.header("⚖️ 인프라 가중치")
    w_params = {
        'subway': st.slider("🚇 역세권", 0, 10, 5), 'school': st.slider("🎓 교육", 0, 10, 4),
        'hospital': st.slider("🏥 의료", 0, 10, 3), 'culture': st.slider("🎭 문화생활", 0, 10, 2),
        'mall': st.slider("🛍️ 쇼핑", 0, 10, 1)
    }

view_df = df[df['sidoNm'] == selected_sido].copy() if selected_sido != "전국" else df.copy()

def calculate_custom_scores(target_df, current_theme, weights):
    res_df = target_df.copy()
    w_sum = sum(weights.values())
    
    if current_theme == "인프라":
        if w_sum > 0:
            edu = (res_df.get('norm_school', 0) + res_df.get('norm_academy', 0)) / 2
            infra = (res_df.get('norm_subway', 0)*weights['subway'] + edu*weights['school'] + 
                     res_df.get('norm_hospital', 0)*weights['hospital'] + res_df.get('norm_culture', 0)*weights['culture'] + 
                     res_df.get('norm_department', 0)*weights['mall'])
            res_df['custom_score'] = (infra / w_sum * 100).round(1)
        else: res_df['custom_score'] = 0.0
    else:
        m_col = "전세_평균보증금" if current_theme == "전세" else "월세_평균월세"
        valid_df = res_df[res_df[m_col] > 0]
        if not valid_df.empty:
            max_v = valid_df[m_col].max()
            res_df['custom_score'] = res_df[m_col].apply(lambda x: round((1 - (x / max_v)) * 100, 1) if x > 0 else -1.0)
        else: res_df['custom_score'] = -1.0
    return res_df

# ==========================================================
# 4. 메인 화면 상단 (지도 & TOP 5)
# ==========================================================
st.title(f"🏘️ {selected_sido} 맞춤형 이사 가이드")
col1, col2 = st.columns([0.6, 0.4], gap="large")

if 'map_center' not in st.session_state: st.session_state.map_center = [36.5, 127.5]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 7

with col2:
    theme = st.radio("관심 테마", list(THEME_CONFIG.keys()), horizontal=True)
    view_df = calculate_custom_scores(view_df, theme, w_params)
    conf = THEME_CONFIG[theme]
    target_df = view_df[view_df[conf['metric']] > 0].sort_values(conf['metric'], ascending=conf['asc']).head(5)
    
    st.subheader(conf['label'])
    for i, (idx, row) in enumerate(target_df.iterrows()):
        c1, c2 = st.columns([0.8, 0.2])
        with c1:
            with st.expander(f"**{i+1}위: {row['region_name']}**"):
                st.write(f"🏠 전세: {format_price(row['전세_평균보증금'])} | 💰 월세: {format_price(row['월세_평균월세'])}")
                st.write(f"✨ 점수: {row['custom_score']}점")
        if c2.button("🔍", key=f"nav_{row['sggCd_key']}"):
            st.session_state.map_center, st.session_state.map_zoom = [row['위도'], row['경도']], 13
            st.rerun()

with col1:
    # 기본 지도 생성
    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
    
    for _, row in view_df.iterrows():
        # TOP 5 지역인지 확인 (하이라이트 여부)
        is_h = row['sggCd_key'] in set(target_df['sggCd_key'])
        
        # 팝업에 표시될 정보 구성 (HTML 형식)
        popup_html = f"""
        <div style="width:200px; font-family: 'Noto Sans KR', sans-serif;">
            <h4 style="margin-bottom:5px;">{row['region_name']}</h4>
            <hr style="margin:5px 0;">
            <b>💰 맞춤 점수:</b> {row['custom_score']}점<br>
            <b>🏠 전세:</b> {format_price(row['전세_평균보증금'])}<br>
            <b>💵 월세:</b> {format_price(row['월세_평균월세'])}
        </div>
        """
        
        folium.CircleMarker(
            location=[row['위도'], row['경도']],
            radius=12 if is_h else 6,  # TOP 5는 더 크게
            color=conf['color'] if is_h else "#3186cc",
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=250), # 클릭 시 팝업 설정
            tooltip=row['region_name'] # 마우스 올렸을 때 이름 표시
        ).add_to(m)
    
    # 지도 출력
    st_folium(m, width="100%", height=500, key="main_map")
    
# ==========================================================
# 5. 심층 분석 리포트 (추가된 Top 20 차트 포함)
# ==========================================================
st.divider()
st.title("📊 인프라 및 점수 심층 분석")

# 요청하신 Top 20 바 차트
top20_df = view_df.sort_values(by=score_col, ascending=False).head(20)
fig_top20 = px.bar(
    top20_df, x=score_col, y="region_name", color=score_col,
    color_continuous_scale="Viridis", orientation="h",
    title=f"'{selected_sido}' {score_label} Top 20 지역",
    labels={score_col: f"{score_label} (점)", "region_name": "지역명"},
    template="plotly_white"
)
fig_top20.update_layout(yaxis={"categoryorder": "total ascending"}, height=550)
st.plotly_chart(fig_top20, use_container_width=True)

# 분야별 상세 순위 차트
st.write("---")
st.subheader("분야별 상세 순위")
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(px.bar(view_df.sort_values("edu_score").tail(15), x="edu_score", y="region_name", orientation="h", title="🎓 교육 우수"), use_container_width=True)
    st.plotly_chart(px.bar(view_df.sort_values("life_medical_score").tail(15), x="life_medical_score", y="region_name", orientation="h", title="🏥 생활/의료 우수"), use_container_width=True)
with col_b:
    st.plotly_chart(px.bar(view_df.sort_values("transport_comm_score").tail(15), x="transport_comm_score", y="region_name", orientation="h", title="🚇 교통/상권 우수"), use_container_width=True)
    # 가성비 차트 (저렴할수록 상단)
    eff_df = view_df[view_df["전세_평균보증금"] > 0].sort_values("전세_평균보증금", ascending=True).head(15)
    st.plotly_chart(px.bar(eff_df, x="전세_평균보증금", y="region_name", orientation="h", title="💰 전세가 저렴한 지역"), use_container_width=True)

# 인프라 DNA 비교
st.write("---")
st.subheader("🎯 지역별 인프라 DNA 비교")
target_regions = st.multiselect("비교 지역 선택", options=view_df["region_name"].unique(), default=view_df.sort_values(score_col, ascending=False)['region_name'].head(3).tolist())
if target_regions:
    fig_radar = go.Figure()
    for reg in target_regions[:4]:
        r_data = view_df[view_df["region_name"] == reg].iloc[0]
        fig_radar.add_trace(go.Scatterpolar(r=[r_data.get(f'norm_{c}', 0) for c in INFRA_COLS], theta=[INFRA_LABELS[c] for c in INFRA_COLS], fill="toself", name=reg))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), height=500)
    st.plotly_chart(fig_radar, use_container_width=True)

# ==========================================================
# 6. 상세 데이터 테이블 (유지)
# ==========================================================
st.divider()
st.header("📋 상세 데이터 테이블")
disp_df = view_df[['region_name', '전세_평균보증금', '월세_평균월세', 'custom_score', 'total_score']].copy()
disp_df = disp_df.sort_values(score_col, ascending=False).reset_index(drop=True)
disp_df.index += 1
disp_df['전세_평균보증금'] = disp_df['전세_평균보증금'].apply(format_price)
disp_df['월세_평균월세'] = disp_df['월세_평균월세'].apply(format_price)
disp_df.rename(columns={'region_name': '지역명', '전세_평균보증금': '평균 전세가', '월세_평균월세': '평균 월세액', 'custom_score': '나만의 점수', 'total_score': '기본 점수'}, inplace=True)
st.dataframe(disp_df, use_container_width=True, height=500)