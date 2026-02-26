import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="부동산 가이드 v4")

# --- 상수 및 헬퍼 함수 ---
INFRA_COLS = ["school", "subway", "hospital", "cafe", "academy", "department", "convenience", "park"]
INFRA_LABELS = {
    "school": "학교", "subway": "지하철", "hospital": "병원", "cafe": "카페",
    "academy": "학원", "department": "백화점", "convenience": "편의점", "park": "공원"
}

def format_price(val):
    if pd.isna(val) or val == 0: return "정보 없음"
    val = int(val)
    if val >= 10000:
        억 = val // 10000
        천 = (val % 10000)
        return f"{억}억 {천:,}만원" if 천 > 0 else f"{억}억원"
    return f"{val:,}만원"

def get_data_path(filename):
    if os.path.exists(f"data/{filename}"): return f"data/{filename}"
    return filename

# --- 세션 상태 초기화 ---
if 'map_center' not in st.session_state: st.session_state.map_center = [36.5, 127.5]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 7

# --- 데이터 로드 및 전처리 ---
@st.cache_data
def load_data():
    try:
        main_df = pd.read_csv(get_data_path('region_rent_infra_final.csv'))
        coord_df = pd.read_csv(get_data_path('korea_sigungu_coordinates.csv'))
    except FileNotFoundError as e:
        st.error(f"필수 파일({e.filename})을 찾을 수 없습니다.")
        st.stop()

    main_df['sidoNm'] = main_df['region_name'].apply(lambda x: str(x).split()[0])
    main_df['sidoNm'] = main_df['sidoNm'].replace({'전라북도': '전북특별자치도', '강원도': '강원특별자치도'})
    main_df['sggCd_key'] = main_df['sigungu_code'].astype(str).str.zfill(5).str[:5]
    coord_df['sggCd_key'] = coord_df['시군구코드'].astype(str).str.zfill(5).str[:5]
    #  위경도 좌표 병합
    df = pd.merge(main_df, coord_df[['sggCd_key', '위도', '경도']], on='sggCd_key', how='left')
    df['full_region'] = df['region_name']
    df.dropna(subset=['full_region', '위도', '경도'], inplace=True)
        # 인프라 점수 정규화 (0~1)
    for col in INFRA_COLS:
        if col in df.columns:
            min_v, max_v = df[col].min(), df[col].max()
            df[f'norm_{col}'] = (df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0
    #  테마 점수 계산 (인프라 분석용)
    df["edu_score"] = df.get("school", 0) + df.get("academy", 0)
    df["transport_comm_score"] = df.get("subway", 0) + df.get("department", 0)
    df["life_medical_score"] = df.get("hospital", 0) + df.get("convenience", 0) + df.get("cafe", 0)
        #  임대 가성비 계산 (면적당 전세가)
    df["면적당_보증금"] = 0.0
    mask = (df["전세_평균면적"] > 0) & (df["전세_평균보증금"] > 0)
    df.loc[mask, "면적당_보증금"] = df.loc[mask, "전세_평균보증금"] / df.loc[mask, "전세_평균면적"]
    
    return df

df = load_data()

# ==========================================================
# 사이드바 설정
# ==========================================================
with st.sidebar:
    st.header("🗺️ 지역 및 조건 선택")
    all_sido = ["전국"] + sorted(df['sidoNm'].unique().tolist())
    selected_sido = st.selectbox("분석할 시도를 선택하세요", all_sido, key="sido_select")
    
    st.divider()
    
    # --- [추가] 분석 기준 선택 섹션 ---
    st.header("🔎 분석 기준 설정")
    score_type = st.radio(
        "순위 산정 기준 선택", 
        ["나만의 맞춤 점수", "기본 인프라 점수"], 
        horizontal=False, # 사이드바에서는 세로 배치가 더 깔끔합니다
        help="사용자가 설정한 가중치를 반영할지(Custom), 지역의 객관적 총점(Total)을 기반으로 할지 결정합니다.",
        key="score_type_select"
    )
    # 변수 설정
    score_col = 'custom_score' if score_type.startswith("나만의") else 'total_score'
    score_label = "나만의 맞춤 점수" if score_col == 'custom_score' else "기본 인프라 점수"
    
    st.divider()
    
    # 가중치 설정 (나만의 맞춤 점수 선택 시에만 강조되도록 구성)
    st.header("⚖️ 나만의 인프라 가중치")
    if score_col == 'total_score':
        st.caption("⚠️ 현재 '기본 인프라 점수' 기준입니다. 가중치를 반영하려면 위에서 '나만의 맞춤 점수'를 선택하세요.")
    
    w_subway = st.slider("🚇 역세권", 0, 10, 5)
    w_school = st.slider("🎓 교육", 0, 10, 4)
    w_hospital = st.slider("🏥 의료", 0, 10, 3)
    w_park = st.slider("🌳 공원", 0, 10, 2)
    w_mall = st.slider("🛍️ 쇼핑", 0, 10, 1)

# --- 필터링 및 점수 계산 (기존과 동일하지만 score_col에 따라 메인 화면이 반응함) ---
view_df = df.copy()
if selected_sido != "전국":
    view_df = view_df[view_df['sidoNm'] == selected_sido]

weights_sum = w_subway + w_school + w_hospital + w_park + w_mall
if weights_sum > 0:
    edu_norm_score = (view_df.get('norm_school', 0) + view_df.get('norm_academy', 0)) / 2
    infra_score = (
        (view_df.get('norm_subway', 0) * w_subway) +
        (edu_norm_score * w_school) +
        (view_df.get('norm_hospital', 0) * w_hospital) +
        (view_df.get('norm_park', 0) * w_park) +
        (view_df.get('norm_department', 0) * w_mall)
    )
    view_df['custom_score'] = (infra_score / weights_sum * 100).round(1)
else:
    view_df['custom_score'] = 0.0

# ==========================================================
# 상단: 이사 지역 가이드
# ==========================================================
st.title(f"🏘️ {selected_sido} 맞춤형 이사 지역 가이드")

col1, col2 = st.columns([0.6, 0.4], gap="large")
highlight_codes = set()

with col2:
    # 1. 제목 및 테마 선택 UI (전국/지역 공통)
    header_title = "📊 전국 추천 테마 TOP 5" if selected_sido == "전국" else f"🏆 {selected_sido} 항목별 TOP 5"
    st.subheader(header_title)
    
    theme = st.radio("관심 테마", ["월세", "전세", "인프라"], horizontal=True, key="theme_radio_combined")
    
    # 2. 데이터 필터링 및 정렬 로직 (공통)
    if theme == "월세":
        target_df = view_df[view_df['월세_평균월세'] > 0].sort_values('월세_평균월세', ascending=True).head(5)
        metric_col, theme_title = "월세_평균월세", "💰 월세가 저렴한 지역"
    elif theme == "전세":
        target_df = view_df[view_df['전세_평균보증금'] > 0].sort_values('전세_평균보증금', ascending=True).head(5)
        metric_col, theme_title = "전세_평균보증금", "🏠 전세가 저렴한 지역"
    else: # 인프라
        target_df = view_df.sort_values('custom_score', ascending=False).head(5)
        metric_col, theme_title = "custom_score", "✨ 인프라 만족도 상위"

    st.write(f"#### {theme_title}")
    highlight_codes = set(target_df['sggCd_key'])

    # 3. 리스트 출력 로직
    if target_df.empty:
        st.info("해당 조건의 데이터가 없습니다.")
    else:
       for i, (idx, data) in enumerate(target_df.iterrows()):
            r_col1, r_col2 = st.columns([0.8, 0.2])
            
            # 특정 지역(시도)을 선택했을 때는 상세 정보(expander)를 포함하여 출력
            if selected_sido != "전국":
                with r_col1:
                    # 제목에서 점수를 빼고 지역명만 노출
                    with st.expander(f"**{i+1}위: {data['full_region']}**"):
                        st.markdown(f"🏠 **평균 전세**: {format_price(data['전세_평균보증금'])}")
                        st.markdown(f"💰 **평균 월세**: {format_price(data['월세_평균월세'])}")
                        # 요청하신 인프라 점수 항목 추가
                        st.markdown(f"✨ **인프라 점수**: {data['custom_score']:.1f}점")
            
            # 전국 모드일 때 보여줄 기본 텍스트 라인
            else:
                val = f"{data[metric_col]:.1f}점" if metric_col == "custom_score" else format_price(data[metric_col])
                r_col1.markdown(f"**{i+1}위. {data['full_region']}** : {val}")

            # 🔍 지도 이동 버튼 (공통)
            if r_col2.button("🔍", key=f"btn_map_nav_{data['sggCd_key']}", use_container_width=True):
                st.session_state.map_center = [data['위도'], data['경도']]
                st.session_state.map_zoom = 13 if selected_sido != "전국" else 12
                st.rerun()

with col1:
    st.subheader("📍 인터랙티브 지도")
    if st.button("지도 초기화", use_container_width=True):
        if not view_df.empty:
            st.session_state.map_center = [view_df['위도'].mean(), view_df['경도'].mean()]
            st.session_state.map_zoom = 7 if selected_sido == "전국" else 10
        st.rerun()

    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, tiles="cartodbpositron")
    for _, row in view_df.iterrows():
        popup_html = f"<b>{row['full_region']}</b><br>점수: {row['custom_score']:.1f}"
        folium.CircleMarker(
            location=[row['위도'], row['경도']],
            radius=8 if row['sggCd_key'] in highlight_codes else 4,
            popup=folium.Popup(popup_html, max_width=300),
            color='crimson' if row['sggCd_key'] in highlight_codes else '#3186cc',
            fill=True, fill_color='crimson' if row['sggCd_key'] in highlight_codes else '#3186cc',
            fill_opacity=0.8 if row['sggCd_key'] in highlight_codes else 0.5,
            weight=3 if row['sggCd_key'] in highlight_codes else 1
        ).add_to(m)
    st_folium(m, width="100%", height=500, key="main_map")


# ==========================================================
# 중단: 인프라 심층 분석
# ==========================================================
st.divider()
st.title("📊 인프라 심층 분석")

# 인프라 점수 계산 설명
with st.expander("💡 인프라 만족도 점수는 어떻게 계산되나요?"):
    st.write("8대 핵심 인프라 수치를 0~1로 정규화한 뒤, 사용자가 설정한 가중치를 반영하여 100점 만점으로 환산한 결과입니다.")
    st.write("**[포함된 인프라 항목]**")
    st.write("🎓 학교, 🚇 지하철, 🏥 병원, ☕ 카페, ✍️ 학원, 🛍️ 백화점, 🏪 편의점, 🌳 공원")

st.info(f"📍 현재 사이드바 설정에 따라 **'{score_label}'** 기준으로 분석 중입니다.")

# 메인 바 차트 (사이드바에서 선택한 score_col에 따라 자동 정렬)
top20_df = view_df.sort_values(by=score_col, ascending=False).head(20)
fig_top20 = px.bar(
    top20_df, 
    x=score_col, 
    y="full_region", 
    color=score_col, 
    color_continuous_scale="Viridis",
    orientation="h",
    title=f"'{selected_sido}' {score_label} Top 20 지역",
    labels={score_col: f"{score_label} (점)", "full_region": "지역명"}, 
    template="plotly_white"
)
fig_top20.update_layout(yaxis={"categoryorder": "total ascending"}, height=550)
st.plotly_chart(fig_top20, use_container_width=True)

# --- 이하 차트 및 테이블 로직 동일 ---
st.write("---")
st.subheader("분야별 상세 순위")
col_a, col_b = st.columns(2)
with col_a:
    fig_edu = px.bar(view_df.sort_values("edu_score", ascending=True).tail(15), x="edu_score", y="full_region", orientation="h", title="🎓 교육 우수 Top 15")
    st.plotly_chart(fig_edu, use_container_width=True)
    fig_life = px.bar(view_df.sort_values("life_medical_score", ascending=True).tail(15), x="life_medical_score", y="full_region", orientation="h", title="🏥 생활/의료 우수 Top 15")
    st.plotly_chart(fig_life, use_container_width=True)
with col_b:
    fig_trans = px.bar(view_df.sort_values("transport_comm_score", ascending=True).tail(15), x="transport_comm_score", y="full_region", orientation="h", title="🚇 교통/상권 우수 Top 15")
    st.plotly_chart(fig_trans, use_container_width=True)
    rent_eff_df = view_df[view_df["면적당_보증금"] > 0]
    fig_eff = px.bar(rent_eff_df.sort_values("면적당_보증금", ascending=False).tail(15), x="면적당_보증금", y="full_region", orientation="h", title="💰 전세 가성비 우수 Top 15")
    st.plotly_chart(fig_eff, use_container_width=True)

st.write("---")
st.subheader("🎯 지역별 인프라 DNA 비교")
target_regions = st.multiselect("비교할 지역 선택 (최대 4개)", options=view_df["full_region"].unique(), default=view_df.sort_values(score_col, ascending=False)['full_region'].head(3).tolist())
if target_regions:
    fig_radar = go.Figure()
    for reg in target_regions[:4]:
        r_data = view_df[view_df["full_region"] == reg].iloc[0]
        radar_values = [r_data.get(f'norm_{c}', 0) for c in INFRA_COLS]
        fig_radar.add_trace(go.Scatterpolar(r=radar_values, theta=[INFRA_LABELS[c] for c in INFRA_COLS], fill="toself", name=reg))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), height=500, title="인프라 구조 비교 (정규화 점수)")
    st.plotly_chart(fig_radar, use_container_width=True)

# 하단 테이블
st.divider()
st.header("📋 상세 데이터 테이블")
disp_df = view_df[['full_region', '전세_평균보증금', '월세_평균월세', 'custom_score', 'total_score']].copy()
disp_df = disp_df.sort_values(score_col, ascending=False).reset_index(drop=True)
disp_df.index += 1
disp_df['전세_평균보증금'] = disp_df['전세_평균보증금'].apply(format_price)
disp_df['월세_평균월세'] = disp_df['월세_평균월세'].apply(format_price)
disp_df.rename(columns={'full_region': '지역명', '전세_평균보증금': '평균 전세가', '월세_평균월세': '평균 월세액', 'custom_score': '나만의 점수', 'total_score': '기본 점수'}, inplace=True)
st.dataframe(disp_df, use_container_width=True, height=500)