import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="전국 기초자치단체 인프라·임대 분석 대시보드",
    layout="wide"
)

INFRA_COLS = [
    "school", "subway", "hospital", "cafe",
    "academy", "department", "convenience", "park"
]

INFRA_LABELS = {
    "school": "학교",
    "subway": "지하철",
    "hospital": "병원",
    "cafe": "카페",
    "academy": "학원",
    "department": "백화점",
    "convenience": "편의점",
    "park": "공원"
}


@st.cache_data
def load_data():
    df = pd.read_csv("data/region_rent_infra_final.csv", encoding="utf-8-sig")
    df["sido"] = df["region_name"].astype(str).apply(lambda x: x.split()[0] if x else "")

    # 숫자형 보정
    numeric_candidates = INFRA_COLS + [
        "total_score",
        "전세_평균보증금", "전세_평균면적", "전세_거래건수",
        "월세_평균보증금", "월세_평균월세", "월세_평균면적", "월세_거래건수",
        "전체_거래건수"
    ]
    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 테마 점수
    df["edu_score"] = df["school"] + df["academy"]
    df["transport_comm_score"] = df["subway"] + df["department"]
    df["life_medical_score"] = df["hospital"] + df["convenience"] + df["cafe"]

    # 면적당 보증금 (전세 가성비)
    if "전세_평균보증금" in df.columns and "전세_평균면적" in df.columns:
        value_df = df.copy()
        value_df["면적당_보증금"] = 0.0
        valid_mask = (value_df["전세_평균면적"] > 0) & (value_df["전세_거래건수"] > 0)
        value_df.loc[valid_mask, "면적당_보증금"] = (
            value_df.loc[valid_mask, "전세_평균보증금"] / value_df.loc[valid_mask, "전세_평균면적"]
        )
        df["면적당_보증금"] = value_df["면적당_보증금"]
    else:
        df["면적당_보증금"] = 0.0

    return df


def render_top20_total_score(current_df, title_text):
    top20 = current_df.sort_values(by="total_score", ascending=False).head(20)

    fig = px.bar(
        top20,
        x="total_score",
        y="region_name",
        color="sido",
        orientation="h",
        title=title_text,
        labels={"total_score": "통합 인프라 점수", "region_name": "지역명", "sido": "시도"},
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=700
    )
    st.plotly_chart(fig, use_container_width=True)


def render_sido_top20(current_df):
    sido_list = sorted(current_df["sido"].dropna().unique().tolist())
    if not sido_list:
        return

    selected_sido_for_top20 = st.selectbox(
        "광역자치단체별 Top 20 보기",
        options=sido_list,
        index=0
    )

    sido_df = current_df[current_df["sido"] == selected_sido_for_top20] \
        .sort_values(by="total_score", ascending=False) \
        .head(20)

    fig = px.bar(
        sido_df,
        x="total_score",
        y="region_name",
        orientation="h",
        color="total_score",
        title=f"{selected_sido_for_top20} 지역 인프라 Top 20",
        labels={"total_score": "통합 인프라 점수", "region_name": "지역명"}
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=650
    )
    st.plotly_chart(fig, use_container_width=True)


def render_theme_analysis(current_df):
    st.subheader("🏷️ 변수별 상세 테마 분석 Top 20")

    col1, col2, col3 = st.columns(3)

    with col1:
        top_edu = current_df.sort_values(by="edu_score", ascending=False).head(20)
        fig_edu = px.bar(
            top_edu,
            x="edu_score",
            y="region_name",
            orientation="h",
            title="🎓 교육 특화 Top 20",
            labels={"edu_score": "학교 + 학원", "region_name": "지역명"}
        )
        fig_edu.update_layout(yaxis={"categoryorder": "total ascending"}, height=650)
        st.plotly_chart(fig_edu, use_container_width=True)

    with col2:
        top_trans = current_df.sort_values(by="transport_comm_score", ascending=False).head(20)
        fig_trans = px.bar(
            top_trans,
            x="transport_comm_score",
            y="region_name",
            orientation="h",
            title="🚇 교통 및 프리미엄 상권 Top 20",
            labels={"transport_comm_score": "지하철 + 백화점", "region_name": "지역명"}
        )
        fig_trans.update_layout(yaxis={"categoryorder": "total ascending"}, height=650)
        st.plotly_chart(fig_trans, use_container_width=True)

    with col3:
        top_life = current_df.sort_values(by="life_medical_score", ascending=False).head(20)
        fig_life = px.bar(
            top_life,
            x="life_medical_score",
            y="region_name",
            orientation="h",
            title="🏥 의료 및 생활 밀착 Top 20",
            labels={"life_medical_score": "병원 + 편의점 + 카페", "region_name": "지역명"}
        )
        fig_life.update_layout(yaxis={"categoryorder": "total ascending"}, height=650)
        st.plotly_chart(fig_life, use_container_width=True)


def render_rent_analysis(current_df):
    st.subheader("🏠 임대 데이터 분석")

    col1, col2 = st.columns(2)

    with col1:
        jeonse_df = current_df[current_df["전세_거래건수"] > 0] \
            .sort_values("전세_평균보증금", ascending=True) \
            .head(15)

        if not jeonse_df.empty:
            fig_jeonse = px.bar(
                jeonse_df,
                x="전세_평균보증금",
                y="region_name",
                orientation="h",
                title="평균 전세 보증금이 가장 저렴한 지역 TOP 15",
                labels={"전세_평균보증금": "보증금(만원)", "region_name": "지역명"}
            )
            fig_jeonse.update_layout(yaxis={"categoryorder": "total descending"}, height=600)
            st.plotly_chart(fig_jeonse, use_container_width=True)
        else:
            st.info("전세 거래 데이터가 없습니다.")

    with col2:
        value_df = current_df[
            (current_df["전세_거래건수"] > 0) &
            (current_df["전세_평균면적"] > 0) &
            (current_df["면적당_보증금"] > 0)
        ].copy()

        top15_val = value_df.sort_values("면적당_보증금", ascending=True).head(15)

        if not top15_val.empty:
            fig_value = px.bar(
                top15_val,
                x="면적당_보증금",
                y="region_name",
                orientation="h",
                title="전세 가성비(면적당 보증금)가 좋은 지역 TOP 15",
                labels={"면적당_보증금": "면적당 보증금", "region_name": "지역명"}
            )
            fig_value.update_layout(yaxis={"categoryorder": "total descending"}, height=600)
            st.plotly_chart(fig_value, use_container_width=True)
        else:
            st.info("가성비 분석에 필요한 전세 데이터가 없습니다.")


def render_radar_chart(current_df):
    st.subheader("🎯 지역별 인프라 DNA 비교")

    region_options = current_df["region_name"].dropna().unique().tolist()
    default_regions = region_options[:2] if len(region_options) >= 2 else region_options

    target_regions = st.multiselect(
        "비교할 지역을 선택하세요 (최대 3개)",
        options=region_options,
        default=default_regions
    )

    if len(target_regions) > 3:
        st.warning("최대 3개 지역까지만 선택할 수 있습니다.")
        target_regions = target_regions[:3]

    if not target_regions:
        return

    max_range = current_df[INFRA_COLS].max().max()
    theta_labels = [INFRA_LABELS[col] for col in INFRA_COLS]

    fig_radar = go.Figure()

    for region in target_regions:
        region_data = current_df[current_df["region_name"] == region].iloc[0]
        fig_radar.add_trace(
            go.Scatterpolar(
                r=[region_data[col] for col in INFRA_COLS],
                theta=theta_labels,
                fill="toself",
                name=region
            )
        )

    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_range]
            )
        ),
        showlegend=True,
        height=700
    )

    st.plotly_chart(fig_radar, use_container_width=True)


# -------------------------
# 메인
# -------------------------
df = load_data()

st.title("📊 전국 기초자치단체 인프라·임대 분석 대시보드")
st.markdown(
    """
    - **기본값(필터 미선택):** 전국 단위 통합 분석  
    - **필터 선택 시:** 선택한 시/도 기준 특성 분석
    """
)

st.sidebar.header("🔍 지역 필터")
sido_options = sorted(df["sido"].dropna().unique().tolist())

selected_sido = st.sidebar.multiselect(
    "광역자치단체(시/도) 선택 (선택 안 하면 전국 분석)",
    options=sido_options,
    default=[]
)

# 기본값: 필터 없으면 전국 전체
if selected_sido:
    current_df = df[df["sido"].isin(selected_sido)].copy()
    analysis_scope_text = f"선택 지역 기준 분석 ({', '.join(selected_sido)})"
else:
    current_df = df.copy()
    analysis_scope_text = "전국 단위 분석"

if current_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

st.subheader(f"📌 {analysis_scope_text}")

# 1. 전국/선택지역 인프라 통합 Top 20
if selected_sido:
    render_top20_total_score(current_df, "선택 지역 인프라 통합 Top 20")
else:
    render_top20_total_score(current_df, "전국 인프라 통합 Top 20 지역")

st.divider()

# 2. 광역자치단체별 Top 20
st.subheader("🗺️ 광역자치단체별 인프라 상위 지역")
render_sido_top20(current_df)

st.divider()

# 3. 변수별 상세 테마 분석
render_theme_analysis(current_df)

st.divider()

# 4. 임대 분석
render_rent_analysis(current_df)

st.divider()

# 5. 지역별 인프라 DNA 비교
render_radar_chart(current_df)

st.divider()

# 6. 상세 테이블
st.subheader("📋 상세 데이터 확인")
st.dataframe(
    current_df.sort_values(by="total_score", ascending=False),
    use_container_width=True
)