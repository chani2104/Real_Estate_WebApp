"""
네이버 부동산 매물 수집 + 데이터 정제 — Streamlit 앱
- 지역 선택 후 실시간 수집
- 테이블 표시, 필터/정렬, CSV·엑셀 내보내기
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가 (실행 위치와 무관하게 동작)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import streamlit as st

from Real_Estate_WebApp.scraper import scrape_all_articles
from Real_Estate_WebApp.utils import (
    REGION_CONFIG,
    items_to_dataframe,
    save_to_excel,
    default_filename,
    TABLE_COLUMNS,
)


def main():
    st.set_page_config(
        page_title="네이버 부동산 매물 수집",
        page_icon="🏠",
        layout="wide",
    )
    st.title("🏠 네이버 부동산 매물 수집·정제")

    # 세션에 DataFrame 저장
    if "df" not in st.session_state:
        st.session_state.df = None
    if "region_name" not in st.session_state:
        st.session_state.region_name = ""

    # ---- 지역 선택 및 실시간 수집 ----
    st.subheader("1. 지역 선택 및 매물 수집")
    region_options = [
        f"{name} ({cortar_no})" for cortar_no, (_, _, name) in REGION_CONFIG.items()
    ]
    region_display = st.selectbox(
        "지역 선택",
        options=region_options,
        index=0,
        help="등록된 지역 중 선택하면 해당 지역 매물을 수집합니다.",
    )
    cortar_no = region_display.split("(")[-1].rstrip(")")
    if cortar_no not in REGION_CONFIG:
        st.warning("선택한 지역 코드를 찾을 수 없습니다. region_config.json을 확인하세요.")
        return
    lat, lon, region_name = REGION_CONFIG[cortar_no]

    if st.button("매물 실시간 수집", type="primary"):
        with st.spinner(f"[{region_name}] 매물을 불러오는 중..."):
            try:
                items = scrape_all_articles(cortar_no, lat, lon)
                if not items:
                    st.info("해당 지역에 매물이 없습니다.")
                    st.session_state.df = None
                else:
                    st.session_state.df = items_to_dataframe(items)
                    st.session_state.region_name = region_name
                    st.success(f"총 {len(items)}건 수집 완료.")
            except Exception as e:
                st.error(f"수집 중 오류: {e}")
                st.session_state.df = None

    if st.session_state.df is None or st.session_state.df.empty:
        st.info("위에서 지역을 선택한 뒤 **매물 실시간 수집**을 눌러 주세요.")
        return

    df = st.session_state.df
    region_label = st.session_state.region_name or "지역"

    st.subheader("2. 매물 목록")
    st.caption(f"총 {len(df)}건 · 지역: {region_label}")

    # ---- 데이터 정제: 필터 ----
    with st.expander("필터 및 정제", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            if "거래유형" in df.columns:
                trad_opts = ["전체"] + sorted(df["거래유형"].dropna().unique().tolist())
                trad_filter = st.selectbox("거래유형", trad_opts)
            else:
                trad_filter = "전체"
        with col2:
            if "매물유형" in df.columns:
                rlet_opts = ["전체"] + sorted(df["매물유형"].dropna().unique().tolist())
                rlet_filter = st.selectbox("매물유형", rlet_opts)
            else:
                rlet_filter = "전체"
        with col3:
            sort_col = st.selectbox(
                "정렬 기준",
                ["선택 안 함"] + [c for c in df.columns if c in ("가격", "면적(㎡)", "확인일", "매물ID")],
            )
            sort_asc = st.checkbox("오름차순", value=False) if sort_col != "선택 안 함" else True

        # 가격/면적 범위 (문자열이라 간단 필터만)
        st.caption("가격·면적은 텍스트 필드라 검색으로만 필터됩니다.")
        search_text = st.text_input("검색 (단지명·가격·특징 등)", "")

    # 필터 적용
    df_view = df.copy()
    if "거래유형" in df_view.columns and trad_filter != "전체":
        df_view = df_view[df_view["거래유형"] == trad_filter]
    if "매물유형" in df_view.columns and rlet_filter != "전체":
        df_view = df_view[df_view["매물유형"] == rlet_filter]
    if search_text:
        mask = df_view.astype(str).apply(
            lambda row: search_text.lower() in row.str.cat().lower(), axis=1
        )
        df_view = df_view[mask]
    if sort_col and sort_col != "선택 안 함" and sort_col in df_view.columns:
        # 숫자 컬럼이면 변환 시도
        if sort_col == "가격":
            s = pd.to_numeric(df_view[sort_col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce")
            df_view = df_view.loc[s.sort_values(ascending=sort_asc).index]
        elif sort_col == "면적(㎡)":
            s = pd.to_numeric(df_view[sort_col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce")
            df_view = df_view.loc[s.sort_values(ascending=sort_asc).index]
        else:
            df_view = df_view.sort_values(sort_col, ascending=sort_asc)

    st.dataframe(df_view, use_container_width=True, height=400)

    # ---- 내보내기 ----
    st.subheader("3. 내보내기")
    c1, c2 = st.columns(2)
    with c1:
        csv_name = default_filename(region_label).replace(".xlsx", ".csv")
        st.download_button(
            "CSV 다운로드",
            data=df_view.to_csv(index=False).encode("utf-8-sig"),
            file_name=csv_name,
            mime="text/csv",
        )
    with c2:
        xlsx_name = default_filename(region_label)
        # 메모리 버퍼로 엑셀 생성 후 다운로드
        try:
            from io import BytesIO
            buf = BytesIO()
            df_view.to_excel(buf, index=False, engine="openpyxl")
            buf.seek(0)
            st.download_button(
                "엑셀 다운로드",
                data=buf.getvalue(),
                file_name=xlsx_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.caption(f"엑셀 다운로드에는 openpyxl이 필요합니다. {e}")


if __name__ == "__main__":
    main()
