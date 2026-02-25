# app.py
import re
from urllib.parse import quote, urlparse, parse_qs

import requests
import pandas as pd
import plotly.express as px
import streamlit as st

import scraper
from utils import items_to_dataframe, parse_price_to_manwon, sqm_to_pyeong

# ----------------------------
# 0) 스타일: 노랑빛 UI
# ----------------------------
st.set_page_config(page_title="부동산 매물 검색 대시보드", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #FFF8D6; }
      [data-testid="stSidebar"] { background: #FFF2B3; }
      h1, h2, h3 { color: #3b2f00; }
      .block-container { padding-top: 1.3rem; }
      div[data-testid="stMetric"] {
        background: #fff;
        border-radius: 14px;
        padding: 10px;
        border: 1px solid #f0d46b;
      }
      .card {
        background: #ffffff;
        border: 1px solid #f0d46b;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 10px;
      }
      .small { color:#6b5b00; font-size: 0.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏠 네이버 부동산 매물 검색 (필터 + 상세보기)")
st.caption("지역을 검색하고, 거래유형/매물유형/면적(평)/예산으로 필터링한 뒤 목록에서 클릭해 상세를 볼 수 있어요.")


# ----------------------------
# 1) 지역명 입력 → (cortarNo, lat, lon) 추출
# ----------------------------
def _mobile_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": "https://m.land.naver.com/",
        "Accept": "text/html,application/json",
    }


def resolve_region(keyword: str):
    """
    m.land 검색 결과로 이동한 뒤,
    최종 URL/HTML에서 cortarNo, lat, lon을 최대한 자동으로 뽑는다.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        raise ValueError("지역명을 입력하세요. 예) 서울 종로구 / 잠실동 / 판교")

    url = f"https://m.land.naver.com/search/result/{quote(keyword)}"
    resp = requests.get(url, headers=_mobile_headers(), timeout=15, allow_redirects=True)
    resp.raise_for_status()

    final_url = resp.url
    parsed = urlparse(final_url)
    q = parse_qs(parsed.query)

    def pick(name):
        v = q.get(name)
        return v[0] if v else None

    cortar_no = pick("cortarNo")
    lat = pick("lat")
    lon = pick("lon")

    if cortar_no and lat and lon:
        return str(cortar_no), float(lat), float(lon), final_url

    html = resp.text
    m_c = re.search(r'cortarNo["\']?\s*[:=]\s*["\']?(\d+)', html)
    m_lat = re.search(r'lat["\']?\s*[:=]\s*["\']?([0-9.]+)', html)
    m_lon = re.search(r'lon["\']?\s*[:=]\s*["\']?([0-9.]+)', html)
    if m_c and m_lat and m_lon:
        return m_c.group(1), float(m_lat.group(1)), float(m_lon.group(1)), final_url

    raise RuntimeError("지역 좌표/코드를 자동으로 찾지 못했어요. 더 구체적으로 입력해보세요.")


# ----------------------------
# 2) 필터 옵션 후보(응답 데이터 기반으로 동적 생성)
# ----------------------------
def unique_non_empty(series: pd.Series):
    vals = sorted({str(v).strip() for v in series.dropna().tolist() if str(v).strip()})
    return vals


# ----------------------------
# 3) 페이지 상태(목록/상세 전환)
# ----------------------------
if "selected_atclNo" not in st.session_state:
    st.session_state["selected_atclNo"] = None  # 상세보기 대상 매물ID
if "latest_df" not in st.session_state:
    st.session_state["latest_df"] = None


# ----------------------------
# 4) 사이드바: 검색 + 필터
# ----------------------------
with st.sidebar:
    st.subheader("지역 검색")
    keyword = st.text_input("지역 입력", placeholder="예) 서울 종로구 / 잠실동 / 판교")
    limit = st.slider("가져올 개수", 10, 50, 50, 10)

    st.divider()
    st.subheader("필터")

    # 거래유형 필터 (요구사항: 전세/월세/매매)
    trad_selected = st.multiselect(
        "거래유형",
        options=["매매", "전세", "월세"],
        default=["매매", "전세", "월세"],
        help="네이버 응답의 '거래유형(tradTpNm)'를 기준으로 필터링합니다.",
    )

    # 매물유형 필터 (요구사항: 아파트/오피스텔/상가주택/단독/다가구/빌라/다세대 등)
    # 실제로 어떤 값이 오는지는 지역마다 달라서, 기본 후보를 주고, 수집 후 실제 값으로 자동 보정도 함
    rlet_default_options = ["아파트", "오피스텔", "상가주택", "단독/다가구", "빌라", "다세대"]
    rlet_selected = st.multiselect(
        "매물유형",
        options=rlet_default_options,
        default=rlet_default_options,
        help="네이버 응답의 '매물유형(rletTpNm)'을 기준으로 필터링합니다.",
    )

    # 면적(평) 필터: 수집 후 df 범위를 보고 자동으로 슬라이더 범위를 맞추는 게 베스트라
    # 일단 기본값으로 잡아두고, 아래에서 df 있으면 재계산
    min_py = st.number_input("최소 면적(평)", min_value=0.0, value=0.0, step=1.0)
    max_py = st.number_input("최대 면적(평)", min_value=0.0, value=200.0, step=1.0)

    # 예산 입력(만원 단위): 사용자가 5억이면 50000 입력하는 방식은 불편하니까,
    # UI에서는 '원 단위 느낌'으로 억/만을 받아서 내부에서 만원으로 변환
    st.markdown("**예산(상한)**")
    budget_eok = st.number_input("억(예: 5억이면 5)", min_value=0, value=0, step=1)
    budget_man = st.number_input("만원(예: 5억 3,000이면 3000)", min_value=0, value=0, step=100)
    budget_limit_manwon = budget_eok * 10000 + budget_man  # ✅ 만원 단위로 환산

    st.caption("예산을 0으로 두면 예산 필터를 적용하지 않습니다.")

    st.divider()
    run = st.button("검색 실행", type="primary", use_container_width=True)


# ----------------------------
# 5) 검색 실행: 수집 → DF 생성 → 파생컬럼 생성 → 필터 적용 → 저장
# ----------------------------
if run:
    st.session_state["selected_atclNo"] = None  # 새 검색이면 상세 선택 초기화

    try:
        with st.spinner("지역 코드/좌표 찾는 중..."):
            cortar_no, lat, lon, debug_url = resolve_region(keyword)

        prog = st.progress(0, text="매물 수집 준비...")
        def progress_cb(cur, total, msg):
            ratio = 0 if total == 0 else min(cur / total, 1.0)
            prog.progress(ratio, text=msg)

        with st.spinner("네이버에서 매물 수집 중..."):
            items = scraper.scrape_articles(
                cortar_no=cortar_no,
                lat=lat,
                lon=lon,
                limit=int(limit),
                progress_callback=progress_cb,
            )
        prog.empty()

        if not items:
            st.warning("해당 지역에서 매물이 0건으로 나왔어요.")
            st.stop()

        # ✅ items(list[dict]) -> DF (TABLE_COLUMNS 기반 정제)
        df = items_to_dataframe(items)

        # ✅ 파생컬럼 생성
        # - 가격(만원): 그래프/예산필터용
        # - 면적(평): 요구사항
        df["가격(만원)"] = df["가격"].apply(parse_price_to_manwon)
        df["면적(㎡)"] = pd.to_numeric(df["면적(㎡)"], errors="coerce")
        df["면적(평)"] = df["면적(㎡)"].apply(sqm_to_pyeong)

        # ✅ 가격구간(요구사항: 5,000만 미만 / 5,000만~5억 / 5억 초과)
        def price_bucket(x):
            if pd.isna(x):
                return "가격정보없음"
            if x < 5000:
                return "5,000만 미만"
            if x <= 50000:
                return "5,000만 ~ 5억"
            return "5억 초과"

        df["가격구간"] = df["가격(만원)"].apply(price_bucket)

        # ✅ “실제 응답에 존재하는 매물유형/거래유형”을 수집 후 알 수 있으므로
        #    필요하면 사용자 선택값과 실제 값을 교집합으로 적용
        # (ex: 응답에 '다세대'가 없으면 자동으로 무시)
        real_trad = set(unique_non_empty(df["거래유형"]))
        real_rlet = set(unique_non_empty(df["매물유형"]))

        trad_selected_eff = [t for t in trad_selected if t in real_trad] or list(real_trad)
        rlet_selected_eff = [r for r in rlet_selected if r in real_rlet] or list(real_rlet)

        # ✅ 필터 적용
        fdf = df.copy()

        # 1) 거래유형
        fdf = fdf[fdf["거래유형"].isin(trad_selected_eff)]

        # 2) 매물유형
        fdf = fdf[fdf["매물유형"].isin(rlet_selected_eff)]

        # 3) 면적(평) 범위
        fdf = fdf[(fdf["면적(평)"].isna()) | ((fdf["면적(평)"] >= min_py) & (fdf["면적(평)"] <= max_py))]

        # 4) 예산(상한) 필터 (0이면 적용 안 함)
        if budget_limit_manwon > 0:
            fdf = fdf[(fdf["가격(만원)"].isna()) | (fdf["가격(만원)"] <= budget_limit_manwon)]

        # ✅ 정렬: 기본은 가격(만원) 오름/내림은 “가격이 숫자인 것”이 더 앞으로 오게
        fdf = fdf.sort_values(by="가격(만원)", ascending=False, na_position="last").reset_index(drop=True)

        # ✅ 세션에 저장 (요구사항: DataFrame으로 저장)
        st.session_state["latest_df"] = fdf

        st.success(f"검색 완료: {len(fdf)}건 (필터 적용 후)")

        with st.expander("디버그(지역 자동추출 정보)", expanded=False):
            st.write(f"- cortarNo: `{cortar_no}`")
            st.write(f"- lat/lon: `{lat}`, `{lon}`")
            st.write(f"- 검색 URL: {debug_url}")

    except Exception as e:
        st.error(f"에러: {e}")
        st.stop()


# ----------------------------
# 6) 화면 렌더: 목록(건물명) → 클릭 → 상세
# ----------------------------
df = st.session_state.get("latest_df")

if df is None or len(df) == 0:
    st.info("왼쪽에서 지역을 입력하고 검색을 눌러주세요.")
    st.stop()

# 색상 요구사항: 5,000만 미만=빨강 / 5,000만~5억=초록 / 5억 초과=파랑
color_map = {
    "5,000만 미만": "red",
    "5,000만 ~ 5억": "green",
    "5억 초과": "blue",
    "가격정보없음": "gray",
}

# ----------------------------
# A) 상세 페이지
# ----------------------------
if st.session_state["selected_atclNo"]:
    atcl_no = st.session_state["selected_atclNo"]
    row = df[df["매물ID"] == str(atcl_no)]
    if row.empty:
        st.warning("선택한 매물을 찾지 못했어요. (필터 변경으로 제외되었을 수 있어요)")
        st.session_state["selected_atclNo"] = None
        st.stop()

    r = row.iloc[0].to_dict()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader(f"📌 상세 보기: {r.get('단지/건물명','')}")
    st.markdown(f"<div class='small'>매물ID: {r.get('매물ID','')}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("거래유형", r.get("거래유형", ""))
    c2.metric("매물유형", r.get("매물유형", ""))
    c3.metric("가격", r.get("가격", ""))

    c4, c5, c6 = st.columns(3)
    c4.metric("면적(평)", f"{r.get('면적(평)', None):.2f}" if pd.notna(r.get("면적(평)", None)) else "-")
    c5.metric("층", r.get("층", ""))
    c6.metric("방향", r.get("방향", ""))

    st.markdown("### 추가 정보")
    st.write({
        "동/호": r.get("동/호", ""),
        "중개사": r.get("중개사", ""),
        "직거래": r.get("직거래", ""),
        "확인일": r.get("확인일", ""),
        "특징": r.get("특징", ""),
        "가격(만원)": r.get("가격(만원)", None),
        "가격구간": r.get("가격구간", ""),
    })

    st.button("← 목록으로", on_click=lambda: st.session_state.update({"selected_atclNo": None}))
    st.stop()


# ----------------------------
# B) 목록 페이지 (요구사항: 건물 이름만 주루룩 → 클릭 → 상세)
# ----------------------------
st.subheader("🏢 매물 목록 (건물 이름)")
st.caption("건물 이름을 클릭하면 상세보기로 이동합니다.")

# “건물 이름만” 목록처럼 보이게 카드형 리스트 + 버튼으로 클릭 구현
for _, r in df.iterrows():
    name = r.get("단지/건물명", "")
    atcl_no = r.get("매물ID", "")
    price = r.get("가격", "")
    bucket = r.get("가격구간", "가격정보없음")
    pyeong = r.get("면적(평)", None)

    # 간단 요약 라인 (이름 + 가격 + 면적 + 구간)
    summary = f"{price} / {pyeong:.1f}평" if pd.notna(pyeong) else f"{price}"

    st.markdown('<div class="card">', unsafe_allow_html=True)
    cols = st.columns([4, 2, 2])
    with cols[0]:
        # 버튼 텍스트를 “건물명”으로
        if st.button(f"{name}", key=f"btn_{atcl_no}"):
            st.session_state["selected_atclNo"] = str(atcl_no)
            st.rerun()

        st.markdown(f"<div class='small'>{summary}</div>", unsafe_allow_html=True)

    with cols[1]:
        st.markdown(f"<div class='small'>거래: {r.get('거래유형','')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small'>유형: {r.get('매물유형','')}</div>", unsafe_allow_html=True)

    with cols[2]:
        # 가격구간 색은 차트에서 주로 쓰고, 목록에서는 텍스트로만 표기(가독성)
        st.markdown(f"<div class='small'>구간: <b>{bucket}</b></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# C) 대시보드 (가격 구간 분포)
# ----------------------------
st.subheader("📊 대시보드: 가격 구간 분포")

bucket_order = ["5,000만 미만", "5,000만 ~ 5억", "5억 초과", "가격정보없음"]
bucket_counts = (
    df["가격구간"]
    .value_counts()
    .reindex(bucket_order)
    .fillna(0)
    .astype(int)
    .reset_index()
)
bucket_counts.columns = ["가격구간", "건수"]

fig_bar = px.bar(
    bucket_counts,
    x="가격구간",
    y="건수",
    color="가격구간",
    color_discrete_map=color_map,
    text="건수",
)
fig_bar.update_layout(height=360, xaxis_title="", yaxis_title="매물 수", legend_title_text="")
st.plotly_chart(fig_bar, use_container_width=True)

# 다운로드: 필터된 DataFrame 저장 활용
st.download_button(
    "CSV 다운로드(필터 적용 결과)",
    data=df.to_csv(index=False, encoding="utf-8-sig"),
    file_name="filtered_listings.csv",
    mime="text/csv",
    use_container_width=True,
)