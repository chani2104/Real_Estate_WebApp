# team_explore.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os

INFRA_COLS = [
    "school",
    "subway",
    "hospital",
    "cafe",
    "academy",
    "department",
    "convenience",
    "culture",
]
INFRA_LABELS = {
    "school": "학교",
    "subway": "지하철",
    "hospital": "병원",
    "cafe": "카페",
    "academy": "학원",
    "department": "백화점",
    "convenience": "편의점",
    "culture": "문화생활",
}


def format_price(val):
    if pd.isna(val) or val == 0:
        return "정보 없음"
    val = int(val)
    if val >= 10000:
        억 = val // 10000
        천 = val % 10000
        return f"{억}억 {천:,}만원" if 천 > 0 else f"{억}억원"
    return f"{val:,}만원"


def get_data_path(filename):
    if os.path.exists(f"data/{filename}"):
        return f"data/{filename}"
    return filename


@st.cache_data
def load_data():
    main_df = pd.read_csv(get_data_path("region_rent_infra_final.csv"))
    coord_df = pd.read_csv(get_data_path("korea_sigungu_coordinates.csv"))

    main_df["sidoNm"] = main_df["region_name"].apply(lambda x: str(x).split()[0])
    main_df["sidoNm"] = main_df["sidoNm"].replace(
        {"전라북도": "전북특별자치도", "강원도": "강원특별자치도"}
    )
    main_df["sggCd_key"] = main_df["sigungu_code"].astype(str).str.zfill(5).str[:5]
    coord_df["sggCd_key"] = coord_df["시군구코드"].astype(str).str.zfill(5).str[:5]

    df = pd.merge(
        main_df, coord_df[["sggCd_key", "위도", "경도"]], on="sggCd_key", how="left"
    )
    df["full_region"] = df["region_name"]
    df.dropna(subset=["full_region", "위도", "경도"], inplace=True)

    for col in INFRA_COLS:
        if col in df.columns:
            min_v, max_v = df[col].min(), df[col].max()
            df[f"norm_{col}"] = (
                (df[col] - min_v) / (max_v - min_v) if max_v != min_v else 0
            )

    df["edu_score"] = df.get("school", 0) + df.get("academy", 0)
    df["transport_comm_score"] = df.get("subway", 0) + df.get("department", 0)
    df["life_medical_score"] = (
        df.get("hospital", 0) + df.get("convenience", 0) + df.get("cafe", 0)
    )

    df["면적당_보증금"] = 0.0
    mask = (df["전세_평균면적"] > 0) & (df["전세_평균보증금"] > 0)
    df.loc[mask, "면적당_보증금"] = (
        df.loc[mask, "전세_평균보증금"] / df.loc[mask, "전세_평균면적"]
    )
    return df


def calculate_custom_scores(
    target_df, current_theme, w_subway, w_school, w_hospital, w_culture, w_mall
):
    res_df = target_df.copy()
    weights_sum = w_subway + w_school + w_hospital + w_culture + w_mall

    if current_theme == "인프라":
        if weights_sum > 0:
            edu_norm_score = (
                res_df.get("norm_school", 0) + res_df.get("norm_academy", 0)
            ) / 2
            infra_score = (
                (res_df.get("norm_subway", 0) * w_subway)
                + (edu_norm_score * w_school)
                + (res_df.get("norm_hospital", 0) * w_hospital)
                + (res_df.get("norm_culture", 0) * w_culture)
                + (res_df.get("norm_department", 0) * w_mall)
            )
            res_df["custom_score"] = (infra_score / weights_sum * 100).round(1)
        else:
            res_df["custom_score"] = 0.0
    elif current_theme == "전세":
        valid_df = res_df[res_df["전세_평균보증금"] > 0]
        if not valid_df.empty:
            max_deposit = valid_df["전세_평균보증금"].max()
            res_df["custom_score"] = res_df["전세_평균보증금"].apply(
                lambda x: round((1 - (x / max_deposit)) * 100, 1) if x > 0 else -1.0
            )
        else:
            res_df["custom_score"] = -1.0
    else:  # 월세
        valid_df = res_df[res_df["월세_평균월세"] > 0]
        if not valid_df.empty:
            max_monthly = valid_df["월세_평균월세"].max()
            res_df["custom_score"] = res_df["월세_평균월세"].apply(
                lambda x: round((1 - (x / max_monthly)) * 100, 1) if x > 0 else -1.0
            )
        else:
            res_df["custom_score"] = -1.0

    return res_df


def render_team_explore():
    # 세션 초기화 (키 충돌 방지용 prefix team_)
    if "team_map_center" not in st.session_state:
        st.session_state.team_map_center = [36.5, 127.5]
    if "team_map_zoom" not in st.session_state:
        st.session_state.team_map_zoom = 7

    df = load_data()

    with st.sidebar:
        st.header("🗺️ 지역 및 조건 선택")
        all_sido = ["전국"] + sorted(df["sidoNm"].unique().tolist())
        selected_sido = st.selectbox(
            "분석할 시도를 선택하세요", all_sido, key="team_sido_select"
        )

        st.divider()
        st.header("🔎 분석 기준 설정")
        score_type = st.radio(
            "순위 산정 기준 선택",
            ["나만의 맞춤 점수", "기본 인프라 점수"],
            horizontal=False,
            key="team_score_type_select",
        )
        score_col = "custom_score" if score_type.startswith("나만의") else "total_score"
        score_label = (
            "나만의 맞춤 점수" if score_col == "custom_score" else "기본 인프라 점수"
        )

        st.divider()
        st.header("⚖️ 나만의 인프라 가중치")
        if score_col == "total_score":
            st.caption(
                "⚠️ 현재 '기본 인프라 점수' 기준입니다. 가중치를 반영하려면 위에서 '나만의 맞춤 점수'를 선택하세요."
            )

        w_subway = st.slider("🚇 역세권", 0, 10, 5, key="team_w_subway")
        w_school = st.slider("🎓 교육", 0, 10, 4, key="team_w_school")
        w_hospital = st.slider("🏥 의료", 0, 10, 3, key="team_w_hospital")
        w_culture = st.slider("🎭 문화생활", 0, 10, 2, key="team_w_culture")
        w_mall = st.slider("🛍️ 쇼핑", 0, 10, 1, key="team_w_mall")

    view_df = df.copy()
    if selected_sido != "전국":
        view_df = view_df[view_df["sidoNm"] == selected_sido]

    st.title(f"🏘️ {selected_sido} 맞춤형 이사 지역 가이드")

    col1, col2 = st.columns([0.6, 0.4], gap="large")

    with col2:
        header_title = (
            "📊 전국 추천 테마 TOP 5"
            if selected_sido == "전국"
            else f"🏆 {selected_sido} 항목별 TOP 5"
        )
        st.subheader(header_title)

        theme = st.radio(
            "관심 테마",
            ["월세", "전세", "인프라"],
            horizontal=True,
            key="team_theme_radio",
        )
        view_df = calculate_custom_scores(
            view_df, theme, w_subway, w_school, w_hospital, w_culture, w_mall
        )

        marker_color = "#3186cc"
        if theme == "월세":
            target_df = (
                view_df[view_df["월세_평균월세"] > 0]
                .sort_values("월세_평균월세", ascending=True)
                .head(5)
            )
            theme_title, marker_color, metric_col = (
                "💰 월세가 저렴한 지역 TOP 5",
                "green",
                "월세_평균월세",
            )
        elif theme == "전세":
            target_df = (
                view_df[view_df["전세_평균보증금"] > 0]
                .sort_values("전세_평균보증금", ascending=True)
                .head(5)
            )
            theme_title, marker_color, metric_col = (
                "🏠 전세가 저렴한 지역 TOP 5",
                "blue",
                "전세_평균보증금",
            )
        else:
            target_df = view_df.sort_values("custom_score", ascending=False).head(5)
            theme_title, marker_color, metric_col = (
                "✨ 인프라 만족도 상위 TOP 5",
                "crimson",
                "custom_score",
            )

        st.write(f"#### {theme_title}")
        highlight_codes = set(target_df["sggCd_key"])

        if target_df.empty:
            st.info("조건에 맞는 데이터가 없습니다.")
        else:
            for i, (_, data) in enumerate(target_df.iterrows()):
                r_col1, r_col2 = st.columns([0.8, 0.2])
                with r_col1:
                    if selected_sido != "전국":
                        with st.expander(f"**{i+1}위: {data['full_region']}**"):
                            st.markdown(
                                f"🏠 **평균 전세**: {format_price(data['전세_평균보증금'])}"
                            )
                            st.markdown(
                                f"💰 **평균 월세**: {format_price(data['월세_평균월세'])}"
                            )
                            st.markdown(f"✨ **점수**: {data['custom_score']:.1f}점")
                    else:
                        val = (
                            f"{data[metric_col]:.1f}점"
                            if metric_col == "custom_score"
                            else format_price(data[metric_col])
                        )
                        st.markdown(f"**{i+1}위. {data['full_region']}** : {val}")

                if r_col2.button(
                    "🔍",
                    key=f"team_btn_nav_{data['sggCd_key']}",
                    use_container_width=True,
                ):
                    st.session_state.team_map_center = [data["위도"], data["경도"]]
                    st.session_state.team_map_zoom = (
                        13 if selected_sido != "전국" else 11
                    )
                    st.rerun()

    with col1:
        st.subheader("📍 지역별 만족도 지도", "마커를 클릭하여 매물 검색")
        m = folium.Map(
            location=st.session_state.team_map_center,
            zoom_start=st.session_state.team_map_zoom,
        )

        for _, row in view_df.iterrows():
            is_highlight = row["sggCd_key"] in highlight_codes
            popup_html = f"<b>{row['full_region']}</b><br>테마 점수: {row['custom_score']:.1f}"

            folium.CircleMarker(
                location=[row["위도"], row["경도"]],
                radius=10 if is_highlight else 5,
                popup=folium.Popup(popup_html, max_width=300),
                color=marker_color if is_highlight else "#3186cc",
                fill=True,
                fill_opacity=0.7 if is_highlight else 0.4,
                weight=2 if is_highlight else 1,
            ).add_to(m)

        # ✅ 클릭 정보 받기
        out = st_folium(m, width="100%", height=500, key="team_main_map")

        # ✅ 마커(원) 클릭 감지: 클릭 좌표 기준으로 가장 가까운 지역 찾기
        if out and out.get("last_object_clicked"):
            lat = out["last_object_clicked"]["lat"]
            lon = out["last_object_clicked"]["lng"]

            # 가장 가까운 행 찾기 (유클리드 근사, 충분히 잘 맞음)
            tmp = view_df.copy()
            tmp["__d"] = (tmp["위도"] - lat) ** 2 + (tmp["경도"] - lon) ** 2
            picked = tmp.sort_values("__d").iloc[0]

            st.session_state["team_picked_region"] = str(picked["full_region"])

        # ✅ 선택된 지역이 있으면 “매물 검색” 버튼 노출
        picked_region = st.session_state.get("team_picked_region")

        if picked_region:
            st.markdown(
                f"""
                <div style="
                    background:#FFFFFF;
                    border:1px solid #E6E8EF;
                    border-radius:16px;
                    padding:14px 14px;
                    box-shadow:0 10px 24px rgba(16,24,40,0.08);
                    margin-top:10px;
                ">
                <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                    <div style="min-width:0;">
                    <div style="color:#6B7280; font-size:0.92rem; font-weight:800; margin-bottom:6px;">
                        📍 현재 선택한 지역
                    </div>
                    <div style="
                        font-size:1.25rem;
                        font-weight:900;
                        color:#111827;
                        line-height:1.25;
                        white-space:nowrap;
                        overflow:hidden;
                        text-overflow:ellipsis;
                    ">
                        {picked_region}
                    </div>
                    </div>
                    <div style="
                        background:rgba(3,199,90,0.12);
                        color:#03C75A;
                        font-weight:900;
                        font-size:0.9rem;
                        padding:6px 10px;
                        border-radius:999px;
                        flex:0 0 auto;
                    ">
                    선택됨
                    </div>
                </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 버튼은 아래에서 "넓고 크게"
            go_search = st.button(
                "🔎 이 지역 매물 검색하기",
                key="go_search_from_map",
                type="primary",
                use_container_width=True,
            )

            if go_search:
                st.session_state.page = "search"
                st.session_state["kw"] = picked_region
                st.session_state.region_meta = (picked_region, None, None, None)
                st.session_state.df = None
                st.session_state.selected_id = None
                st.rerun()
        else:
            st.info(
                "지도에서 원(마커)을 클릭하면 선택 지역이 표시되고, 바로 매물 검색으로 이동할 수 있어요."
            )

    # (이하 인프라 심층 분석 파트도 그대로 이어붙이면 됨)
    st.divider()
    st.title("📊 인프라 심층 분석")
    st.info(f"📍 현재 사이드바 설정에 따라 **'{score_label}'** 기준으로 분석 중입니다.")

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
        template="plotly_white",
    )
    fig_top20.update_layout(yaxis={"categoryorder": "total ascending"}, height=550)
    st.plotly_chart(fig_top20, use_container_width=True)

    # --- 이하 차트 및 테이블 로직 동일 ---
    st.write("---")
    st.subheader("분야별 상세 순위")
    col_a, col_b = st.columns(2)
    with col_a:
        fig_edu = px.bar(
            view_df.sort_values("edu_score", ascending=True).tail(15),
            x="edu_score",
            y="full_region",
            orientation="h",
            title="🎓 교육 우수 Top 15",
        )
        st.plotly_chart(fig_edu, use_container_width=True)
        fig_life = px.bar(
            view_df.sort_values("life_medical_score", ascending=True).tail(15),
            x="life_medical_score",
            y="full_region",
            orientation="h",
            title="🏥 생활/의료 우수 Top 15",
        )
        st.plotly_chart(fig_life, use_container_width=True)
    with col_b:
        fig_trans = px.bar(
            view_df.sort_values("transport_comm_score", ascending=True).tail(15),
            x="transport_comm_score",
            y="full_region",
            orientation="h",
            title="🚇 교통/상권 우수 Top 15",
        )
        st.plotly_chart(fig_trans, use_container_width=True)
        rent_eff_df = view_df[view_df["면적당_보증금"] > 0]
        fig_eff = px.bar(
            rent_eff_df.sort_values("면적당_보증금", ascending=False).tail(15),
            x="면적당_보증금",
            y="full_region",
            orientation="h",
            title="💰 전세 가성비 우수 Top 15",
        )
        st.plotly_chart(fig_eff, use_container_width=True)

    st.write("---")
    st.subheader("🎯 지역별 인프라 DNA 비교")
    target_regions = st.multiselect(
        "비교할 지역 선택 (최대 4개)",
        options=view_df["full_region"].unique(),
        default=view_df.sort_values(score_col, ascending=False)["full_region"]
        .head(3)
        .tolist(),
    )
    if target_regions:
        fig_radar = go.Figure()
        for reg in target_regions[:4]:
            r_data = view_df[view_df["full_region"] == reg].iloc[0]
            radar_values = [r_data.get(f"norm_{c}", 0) for c in INFRA_COLS]
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=radar_values,
                    theta=[INFRA_LABELS[c] for c in INFRA_COLS],
                    fill="toself",
                    name=reg,
                )
            )
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            height=500,
            title="인프라 구조 비교 (정규화 점수)",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # 하단 테이블
    st.divider()
    st.header("📋 상세 데이터 테이블")
    disp_df = view_df[
        ["full_region", "전세_평균보증금", "월세_평균월세", "custom_score", "total_score"]
    ].copy()
    disp_df = disp_df.sort_values(score_col, ascending=False).reset_index(drop=True)
    disp_df.index += 1
    disp_df["전세_평균보증금"] = disp_df["전세_평균보증금"].apply(format_price)
    disp_df["월세_평균월세"] = disp_df["월세_평균월세"].apply(format_price)
    disp_df.rename(
        columns={
            "full_region": "지역명",
            "전세_평균보증금": "평균 전세가",
            "월세_평균월세": "평균 월세액",
            "custom_score": "나만의 점수",
            "total_score": "기본 점수",
        },
        inplace=True,
    )
    st.dataframe(disp_df, use_container_width=True, height=500)
