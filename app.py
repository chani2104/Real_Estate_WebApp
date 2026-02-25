import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

# 페이지 설정
st.set_page_config(layout="wide", page_title="이사 지역 가이드: 맞춤형 동네 찾기")

@st.cache_data
def load_data():
    # 1. 파일 읽기
    # 모든 파일이 app.py와 같은 위치에 있다고 가정합니다.
    summary_df = pd.read_csv('region_rent_summary.csv')
    original_df = pd.read_csv('national_rent_data_202401.csv', encoding='utf-8-sig')
    infra_df = pd.read_csv('전국_기초자치_인프라_점수.csv')
    coord_df = pd.read_csv('korea_sigungu_coordinates.csv')

    # 2. 부동산 요약 데이터에 시군구코드(sggCd) 매핑
    # 요약본에 코드가 없으므로 원본 데이터에서 이름-코드 쌍을 가져와 합칩니다.
    code_map = original_df[['sggNm', 'sggCd']].drop_duplicates()
    summary_df = pd.merge(summary_df, code_map, on='sggNm', how='left')

    # 3. 데이터 코드 형식 통일 (5자리 문자열)
    # 인프라 데이터는 10자리일 수 있으므로 앞 5자리만 추출
    infra_df['sggCd_key'] = infra_df['sigungu_code'].astype(str).str[:5]
    summary_df['sggCd_key'] = summary_df['sggCd'].astype(str).str.split('.').str[0].str[:5]
    coord_df['sggCd_key'] = coord_df['시군구코드'].astype(str).str[:5]

    # 4. 데이터 통합 (코드를 키로 사용: 가장 정확함)
    # 부동산 + 인프라 결합
    merged_df = pd.merge(summary_df, infra_df, left_on='sggCd_key', right_on='sggCd_key', how='inner')
    # + 좌표 데이터 결합
    merged_df = pd.merge(merged_df, coord_df[['sggCd_key', '위도', '경도', '시도']], on='sggCd_key', how='left')

    # 5. 시도명 및 풀네임 정리
    # 좌표 파일의 '시도' 컬럼을 사용하거나 매핑을 사용
    merged_df['sidoNm'] = merged_df['시도']
    merged_df['full_region'] = merged_df['sidoNm'] + " " + merged_df['sggNm']

    # 6. 인프라 점수 정규화 (0~1점 스케일링)
    infra_cols = ['school', 'subway', 'hospital', 'cafe', 'academy', 'department', 'convenience', 'park']
    for col in infra_cols:
        if col in merged_df.columns:
            min_v = merged_df[col].min()
            max_v = merged_df[col].max()
            merged_df[f'norm_{col}'] = (merged_df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0

    return merged_df

# 데이터 로드
try:
    df = load_data()
except Exception as e:
    st.error(f"데이터 로드 중 오류 발생: {e}")
    st.stop()

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("🔍 검색 필터")
    all_sido = ["전국"] + sorted(df['sidoNm'].dropna().unique().tolist())
    selected_sido = st.selectbox("지역 선택", all_sido)
    
    rent_type = st.radio("거래 유형", ["전세", "월세"])
    
    st.divider()
    st.header("🎯 인프라 가중치")
    st.caption("나에게 중요한 항목의 점수를 높여주세요.")
    w_subway = st.slider("🚇 역세권", 0, 5, 3)
    w_school = st.slider("🎓 교육(학교/학원)", 0, 5, 2)
    w_hospital = st.slider("🏥 의료(병원)", 0, 5, 2)
    w_park = st.slider("🌳 숲세권(공원)", 0, 5, 2)
    w_mall = st.slider("🛍️ 쇼핑(백화점/마트)", 0, 5, 1)

# --- 필터링 및 점수 계산 ---
view_df = df.copy()
if selected_sido != "전국":
    view_df = view_df[view_df['sidoNm'] == selected_sido]

# 맞춤 점수 합산
view_df['custom_score'] = (
    (view_df['norm_subway'] * w_subway) +
    ((view_df['norm_school'] + view_df['norm_academy'])/2 * w_school) +
    (view_df['norm_hospital'] * w_hospital) +
    (view_df['norm_park'] * w_park) +
    (view_df['norm_department'] * w_mall)
)

# --- 메인 화면 ---
st.title(f"🏘️ {selected_sido} 이사 지역 선정 시뮬레이터")
st.markdown(f"**{rent_type}** 데이터와 인프라 점수를 결합한 분석 결과입니다.")

col1, col2 = st.columns([6, 4])

# --- 지도 생성 부분 수정 ---
with col1:
    st.subheader("📍 지역별 추천 지도")
    
    # 1. 좌표가 비어있는(NaN) 행은 제거하고 그릴 준비를 합니다.
    map_df = view_df.dropna(subset=['위도', '경도'])
    
    # 2. 만약 필터링 후 데이터가 하나도 없다면 안내 메시지 출력
    if map_df.empty:
        st.warning("선택한 지역에 표시할 좌표 데이터가 없습니다.")
    else:
        # 지도 중심점 설정 (좌표가 있는 데이터의 평균값)
        m_lat = map_df['위도'].mean()
        m_lng = map_df['경도'].mean()
        
        m = folium.Map(location=[m_lat, m_lng], zoom_start=7 if selected_sido == "전국" else 11)
        
        for _, row in map_df.iterrows():
            # 가격 데이터 설정
            price = row['전세_평균보증금'] if rent_type == "전세" else row['월세_평균월세액']
            
            # 3. 개별 좌표값 검사 (한 번 더 안전하게)
            if pd.notna(row['위도']) and pd.notna(row['경도']):
                folium.CircleMarker(
                    location=[row['위도'], row['경도']],
                    radius=row['custom_score'] * 3 + 5,
                    popup=f"<b>{row['full_region']}</b><br>평균 {rent_type}: {int(price)}만원<br>만족도: {row['custom_score']:.2f}",
                    color='blue' if rent_type == "전세" else 'orange',
                    fill=True,
                    fill_opacity=0.7
                ).add_to(m)
        
        st_folium(m, width="100%", height=600)

with col2:
    st.subheader("🏆 당신을 위한 추천 TOP 5")
    top5 = view_df.sort_values('custom_score', ascending=False).head(5)
    
    for i, row in top5.iterrows():
        with st.expander(f"{i+1}위: {row['full_region']}"):
            st.write(f"💰 **평균 {rent_type}:** {int(row['전세_평균보증금'] if rent_type == '전세' else row['월세_평균월세액'])}만원")
            st.write(f"⭐ **인프라 만족도 점수:** {row['custom_score']:.2f}")
            # 주요 지표 프로그레스 바
            st.write("지하철 접근성")
            st.progress(float(row['norm_subway']))
            st.write("의료 인프라")
            st.progress(float(row['norm_hospital']))

st.divider()
st.subheader("📂 전체 지역 상세 비교")
st.dataframe(view_df[['full_region', '전세_평균보증금', '월세_평균월세액', 'custom_score']].sort_values('custom_score', ascending=False), use_container_width=True)