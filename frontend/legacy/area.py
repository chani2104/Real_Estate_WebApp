import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

# 페이지 설정
st.set_page_config(layout="wide", page_title="이사 지역 가이드: 맞춤형 동네 찾기")

# --- 세션 상태 초기화 (지도 이동 및 테마 관리를 위함) ---
if 'map_center' not in st.session_state:
    st.session_state.map_center = [36.5, 127.5] # 초기 중앙값
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 7

@st.cache_data
def load_data():
    # 파일 읽기
    summary_df = pd.read_csv('region_rent_summary.csv')
    original_df = pd.read_csv('national_rent_data_202401.csv', encoding='utf-8-sig')
    infra_df = pd.read_csv('전국_기초자치_인프라_점수.csv')
    coord_df = pd.read_csv('korea_sigungu_coordinates.csv')
    # 2. 부동산 요약 데이터에 시군구코드(sggCd) 매핑
    code_map = original_df[['sggNm', 'sggCd']].drop_duplicates()
    summary_df = pd.merge(summary_df, code_map, on='sggNm', how='left')
    # 3. 데이터 코드 형식 통일 (5자리 문자열)
    infra_df['sggCd_key'] = infra_df['sigungu_code'].astype(str).str[:5]
    summary_df['sggCd_key'] = summary_df['sggCd'].astype(str).str.split('.').str[0].str[:5] 
    coord_df['sggCd_key'] = coord_df['시군구코드'].astype(str).str[:5]
    # 4. 데이터 통합
    merged_df = pd.merge(summary_df, infra_df, on='sggCd_key', how='inner')
    merged_df = pd.merge(merged_df, coord_df[['sggCd_key', '위도', '경도', '시도']], on='sggCd_key', how='left')
    # 5. 시도명 및 풀네임 정리
    merged_df['sidoNm'] = merged_df['시도']
    merged_df['full_region'] = merged_df['sidoNm'] + " " + merged_df['sggNm']
    # 6. 인프라 점수 정규화
    infra_cols = ['school', 'subway', 'hospital', 'cafe', 'academy', 'department', 'convenience', 'park']
    for col in infra_cols:
        if col in merged_df.columns:
            min_v, max_v = merged_df[col].min(), merged_df[col].max()
            merged_df[f'norm_{col}'] = (merged_df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0
    # 7. 데이터 클렌징: 명칭이나 좌표가 없는 데이터 제외
    merged_df.dropna(subset=['full_region', '위도', '경도'], inplace=True)
    return merged_df

def format_price(val):
    if pd.isna(val) or val == 0: return "정보 없음"
    val = int(val)
    if val >= 10000:
        억, 천 = val // 10000, (val % 10000) // 1000 * 1000
        return f"{억}억 {천:,}만원" if 천 > 0 else f"{억}억원"
    return f"{val:,}만원"

try:
    df = load_data()
except Exception as e:
    st.error(f"데이터 로드 중 오류 발생: {e}"); st.stop()

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("🔍 검색 필터")
    all_sido = ["전국"] + sorted(df['sidoNm'].dropna().unique().tolist())
    selected_sido = st.selectbox("지역 선택", all_sido)
    rent_type = st.radio("거래 유형", ["전세", "월세"])

    st.divider()
    st.header("🎯 인프라 가중치")
    w_subway = st.slider("🚇 역세권", 0, 5, 3)
    w_school = st.slider("🎓 교육", 0, 5, 2)
    w_hospital = st.slider("🏥 의료", 0, 5, 2)
    w_park = st.slider("🌳 숲세권", 0, 5, 2)
    w_mall = st.slider("🛍️ 쇼핑", 0, 5, 1)

# --- 필터링 및 점수 계산 ---
view_df = df.copy()
if selected_sido != "전국":
    view_df = view_df[view_df['sidoNm'] == selected_sido]

weights_sum = w_subway + w_school + w_hospital + w_park + w_mall
if weights_sum > 0:
    infra_score = ((view_df['norm_subway'] * w_subway) + ((view_df['norm_school'] + view_df['norm_academy']) / 2 * w_school) +
                   (view_df['norm_hospital'] * w_hospital) + (view_df['norm_park'] * w_park) + (view_df['norm_department'] * w_mall))
    view_df['custom_score'] = (infra_score / weights_sum * 100).round(1)
else:
    view_df['custom_score'] = 0.0

# --- 메인 화면 ---
st.title(f"🏘️ {selected_sido} 이사 지역 선정 시뮬레이터")
col1, col2 = st.columns([6, 4])

# 강조할 지역 코드 리스트 초기화
selected_top5_codes = []

# --- col2 콘텐츠 (추천 리스트 및 테마 선택) ---
with col2:
    if selected_sido == "전국":
        st.subheader("📊 전국 분야별 TOP 5")
        # 탭 대신 라디오 버튼을 사용하여 테마 선택 감지
        theme = st.radio("추천 테마 선택", ["💰 저렴한 월세", "🏠 저렴한 전세", "✨ 우수한 인프라"], horizontal=True)
        
        if theme == "💰 저렴한 월세":
            target_df = view_df[view_df['월세_평균월세액'] > 0].sort_values('월세_평균월세액').head(5)
            label, col_name = "평균 월세", "월세_평균월세액"
        elif theme == "🏠 저렴한 전세":
            target_df = view_df[view_df['전세_평균보증금'] > 0].sort_values('전세_평균보증금').head(5)
            label, col_name = "평균 전세", "전세_평균보증금"
        else:
            target_df = view_df.sort_values('custom_score', ascending=False).head(5)
            label, col_name = "인프라 점수", "custom_score"

        selected_top5_codes = target_df['sggCd_key'].tolist()

        for i, (_, row) in enumerate(target_df.iterrows()):
            c1, c2 = st.columns([8, 2])
            val = format_price(row[col_name]) if col_name != "custom_score" else f"{row[col_name]}점"
            c1.write(f"**{i+1}위. {row['full_region']}** : {val}")
            if c2.button("🔍", key=f"btn_{row['sggCd_key']}"):
                st.session_state.map_center = [row['위도'], row['경도']]
                st.session_state.map_zoom = 12
                st.rerun()
    
    else:
        # 특정 지역 선택 시 기존의 상세 expander 출력 유지
        st.subheader(f"🏆 {selected_sido} 맞춤 추천 TOP 5")
        top5 = view_df.sort_values('custom_score', ascending=False).head(5)
        selected_top5_codes = top5['sggCd_key'].tolist()

        if top5.empty:
            st.write("데이터가 없습니다.")
        else:
            for i, (_, row) in enumerate(top5.iterrows()):
                exp_col1, exp_col2 = st.columns([8, 2])
                with exp_col1:
                    with st.expander(f"{i+1}위: {row['full_region']}"):
                        price = row['전세_평균보증금'] if rent_type == "전세" else row['월세_평균월세액']
                        st.write(f"💰 **평균 {rent_type}:** {format_price(price)}")
                        st.write(f"⭐ **인프라 만족도:** {row['custom_score']}점")
                        st.progress(float(row['norm_subway']), text="지하철 접근성")
                        st.progress(float(row['norm_hospital']), text="의료 인프라")
                with exp_col2:
                    # 상세 모드에서도 돋보기 버튼 추가
                    if st.button("🔍", key=f"detail_btn_{row['sggCd_key']}"):
                        st.session_state.map_center = [row['위도'], row['경도']]
                        st.session_state.map_zoom = 13
                        st.rerun()

# --- col1 지도 생성 ---
with col1:
    st.subheader("📍 지역별 추천 지도")
    # 지도 중심점 자동 초기화 (전국 클릭 시 다시 중심으로)
    if st.button("지도 초기화 🔄"):
        st.session_state.map_center = [view_df['위도'].mean(), view_df['경도'].mean()]
        st.session_state.map_zoom = 7 if selected_sido == "전국" else 11
        st.rerun()

    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
    
    for _, row in view_df.iterrows():
        is_top5 = row['sggCd_key'] in selected_top5_codes
        color = 'red' if is_top5 else ('blue' if rent_type == "전세" else 'orange')
        
        folium.CircleMarker(
            location=[row['위도'], row['경도']],
            radius=(row['custom_score'] / 10) + 4 if is_top5 else (row['custom_score'] / 10) + 2,
            popup=f"<b>{row['full_region']}</b><br>점수: {row['custom_score']}점",
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8 if is_top5 else 0.5,
            weight=5 if is_top5 else 1
        ).add_to(m)
    st_folium(m, width="100%", height=600, key="main_map")

st.divider()
st.subheader("📂 전체 지역 상세 비교")

# 1. 안내 문구 추가
st.caption("※ 위 표는 사용자가 설정한 '인프라 만족도(점수)'를 기준으로 내림차순 정렬되어 있습니다.")

# 2. 데이터 가공 및 숫자 기준 정렬
display_df = view_df[['full_region', '전세_평균보증금', '월세_평균월세액', 'custom_score']].copy()
display_df = display_df.sort_values('custom_score', ascending=False)

# 3. 인덱스 1부터 새로 부여 (순위 표시)
display_df = display_df.reset_index(drop=True)
display_df.index = display_df.index + 1

# 4. 가격 포맷팅 적용
display_df['전세_평균보증금'] = display_df['전세_평균보증금'].apply(format_price)
display_df['월세_평균월세액'] = display_df['월세_평균월세액'].apply(format_price)

# 5. 칼럼명 한글로 변경
display_df.columns = ['지역명', '평균 전세가', '평균 월세액', '인프라 만족도']

# 6. 최종 출력
st.dataframe(
    display_df, 
    use_container_width=True
)