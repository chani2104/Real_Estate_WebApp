# app.py  (Naver Land-ish UI/UX version)
import re
from urllib.parse import quote, urlparse, parse_qs

import math
import requests
import team_explore
import pandas as pd
import plotly.express as px
import streamlit as st
import folium
from streamlit_folium import st_folium

import scraper
from utils import (
    items_to_dataframe,
    parse_price_to_manwon,
    sqm_to_pyeong,
    haversine_distance,
    estimate_walking_minutes,
)
from subway_data import SUBWAY_LINES
from poi_schools import fetch_nearby_schools_osm


# =========================================================
# 0) Page + Naver-ish style
# =========================================================
st.set_page_config(page_title="부동산 웹앱", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');

html, body, [class*="css"]  {
  font-family: "Nunito", "Noto Sans KR", system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
}

/* ===== 기본 UI 크롬 숨김(사이드바 토글 포함) ===== */
header { visibility: hidden; height: 0px; }
footer { visibility: hidden; height: 0px; }
[data-testid="stToolbar"] { display: none !important; }
/* ✅ 사이드바는 항상 보이게 강제 */
[data-testid="stSidebar"]{
  display: block !important;
  visibility: visible !important;
  transform: none !important;
}

/* ✅ 사이드바 '접기' 버튼만 숨김 (접기 기능 사실상 봉인) */
/* 사이드바 접기/펼치기 컨트롤(버전별로 이름이 다를 수 있음) */
div[data-testid="stSidebarCollapseButton"] { 
  display: none !important; 
}

div[data-testid="collapsedControl"] { 
  display: none !important; 
}

/* aria-label 기반(문구가 달라질 수 있으니 contains로도 시도) */
button[aria-label="Collapse sidebar"],
button[aria-label*="Collapse"][aria-label*="sidebar"] {
  display: none !important;
}

/* ===== 배경 / 레이아웃 ===== */
.stApp { background: #F6F7FB; } /* 네이버 느낌: 회색-화이트 */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E6E8EF; }
.block-container { padding-top: 0.8rem; padding-bottom: 1.5rem; }

/* ===== 상단 바(가짜 네이버 느낌) ===== */
.topbar {
  background: #FFFFFF;
  border: 1px solid #E6E8EF;
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: 0 6px 18px rgba(16,24,40,0.06);
  margin-bottom: 12px;
}
.brand {
  font-weight: 900;
  font-size: 1.1rem;
  color: #111827;
}
.brand-dot { color: #03C75A; } /* 네이버 그린 느낌 */
.topbar-sub { color: #6B7280; font-size: 0.92rem; margin-top: 2px; }

/* ✅ 사이드바 강제 표시 (접힘 상태까지 풀기) */
section[data-testid="stSidebar"]{
  display: block !important;
  visibility: visible !important;
  transform: none !important;
  margin-left: 0 !important;
  width: 21rem !important;      /* 핵심: 접히면 width=0 되는 케이스 방지 */
  min-width: 21rem !important;
}

/* sidebar 내부 컨텐츠도 폭 보장 */
section[data-testid="stSidebar"] > div{
  width: 21rem !important;
}

/* ===== 공용 카드 ===== */
.card {
  background: #FFFFFF;
  border: 1px solid #E6E8EF;
  border-radius: 16px;
  padding: 14px 14px;
  box-shadow: 0 6px 18px rgba(16,24,40,0.05);
  margin-bottom: 12px;
}
.section-title { font-weight: 900; font-size: 1.05rem; color: #111827; margin: 0 0 10px 0;}
.muted { color: #6B7280; font-size: 0.92rem; }

/* ===== 사이드바 필터 카드 ===== */
.filter-card{
  background: #F9FAFB;
  border: 1px solid #EEF0F6;
  border-radius: 14px;
  padding: 12px;
  margin: 10px 0;
}
.filter-title{ font-weight: 900; color:#111827; font-size: 0.98rem; margin: 0 0 8px 0; }
.filter-sub{ color:#6B7280; font-size:0.88rem; margin-bottom:8px; }

/* ===== 입력/버튼 ===== */
.stButton>button { border-radius: 12px; }
input, textarea { border-radius: 12px !important; }
div.stButton>button[kind="primary"] { background: #03C75A; border: 1px solid #03C75A; }
div.stButton>button[kind="primary"]:hover { filter: brightness(0.96); }

/* ===== 리스트(네이버처럼: 좌측 목록 스크롤 분리) ===== */
.list-wrap{
  max-height: 72vh;   /* ✅ 최대 높이만 */
  height: auto;       /* ✅ 내용만큼 늘어남 */
  overflow: auto;
  padding-right: 6px;
}
.list-item{
  border: 1px solid #E6E8EF;
  border-radius: 14px;
  background: #FFFFFF;
  margin: 10px 0;
  overflow: hidden;
  box-shadow: 0 6px 14px rgba(16,24,40,0.05);
}
.list-row{
  display:flex;
  align-items:flex-start;
  gap:10px;
  padding: 12px 12px;
}
.swatch{ width:12px; height:38px; border-radius:10px; flex:0 0 12px; margin-top:2px; }
.li-title{ font-weight:900; color:#111827; line-height:1.15; font-size: 1.0rem; }
.li-sub{ color:#6B7280; font-size:0.88rem; margin-top:6px; }
.li-meta{ color:#6B7280; font-size:0.86rem; margin-top:4px; }
.li-cta { padding: 0 12px 12px 12px; }

/* ===== 선택 강조 ===== */
.list-item.selected { border-color: #03C75A; box-shadow: 0 8px 20px rgba(3,199,90,0.14); }

/* ===== 오른쪽 지도/상세 sticky ===== */
.sticky-pane{
  position: sticky;
  top: 12px;
  z-index: 5;
}

/* ===== 메인 타이틀 ===== */
.main-title{
  font-size: 2.2rem;
  font-weight: 900;
  color:#111827;
  margin-bottom: 4px;
}
.main-sub{
  color:#6B7280;
  font-size:1rem;
  margin-bottom: 18px;
}

/* ===== 로비 카드 ===== */
/* ===== 로비 카드: 내용 삐져나옴 해결 + hover 하이라이트 ===== */
.lobby-card{
  position: relative;
  border-radius: 22px;
  padding: 26px 26px 22px 26px;
  border: 1px solid #E6E8EF;
  background: linear-gradient(135deg,#f8fafc,#eef2f7);
  box-shadow: 0 10px 30px rgba(0,0,0,0.06);
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
  min-height: 210px;          /* ✅ 고정 height 대신 최소 높이 */
  overflow: hidden;           /* ✅ 삐져나오는 텍스트/요소 숨김 */
}

.lobby-card:hover{
  transform: translateY(-4px);
  border-color: #03C75A;
  box-shadow: 0 18px 40px rgba(3,199,90,0.14);
}

.lobby-title{
  font-size:1.6rem;
  font-weight:900;
  color:#111827;
}

.lobby-desc{
  margin-top:10px;
  color:#4B5563;
  font-size:0.95rem;
  line-height:1.5;
}

/* 체크리스트 줄간격 */
.lobby-desc br{ line-height: 1.7; }

/* ===== 카드 전체 클릭용: 투명 버튼을 덮기 ===== */
.card-overlay-btn .stButton>button{
  position:absolute;
  inset:0;                  /* top/right/bottom/left = 0 */
  width:100%;
  height:100%;
  opacity:0;                /* ✅ 완전 투명 */
  border:none;
  background:transparent;
  cursor:pointer;
  z-index:10;
}

/* 버튼 포커스 테두리 제거(보이면 거슬림) */
.card-overlay-btn .stButton>button:focus{
  outline:none !important;
  box-shadow:none !important;
}

/* ===== 로비 영역: 화면 중앙쯤으로 올리기 ===== */
.lobby-wrap{
  flex: 1;                         /* 남는 공간 차지 */
  display:flex;
  flex-direction:column;
  justify-content:center;          /* ✅ 세로 중앙에 가깝게 */
  padding-top: 30px;               /* 너무 딱 중앙이면 위로 살짝 */
}

/* 카드+버튼을 같은 박스에 겹치기 위한 래퍼 */
.lobby-clickable{
  position: relative;
}

/* 카드 눌림(클릭) 효과 */
.lobby-clickable:active .lobby-card{
  transform: translateY(-2px) scale(0.995);
  box-shadow: 0 14px 32px rgba(3,199,90,0.12);
}

/* ===== 카드 전체 클릭(버튼 오버레이) ===== */
.lobby-clickable .stButton{
  position: absolute;
  inset: 0;
  margin: 0;
  z-index: 20;
}
.lobby-clickable .stButton>button{
  width:100%;
  height:100%;
  opacity:0;
  border:none;
  background:transparent;
  cursor:pointer;
}

/* ===== 로비 카드 전체 클릭(찐) : Streamlit 버튼 흔적 제거 버전 ===== */
.lobby-clickable{
  position: relative;
}

/* 버튼 컨테이너 자체를 카드 위로 띄워버려서 레이아웃 공간을 안 차지하게 */
.lobby-clickable .stButton{
  position: absolute !important;
  inset: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  z-index: 50 !important;
}

/* 버튼은 투명 + 전체 영역 */
.lobby-clickable .stButton > button{
  width: 100% !important;
  height: 100% !important;
  opacity: 0 !important;
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
  cursor: pointer !important;
}

/* 포커스/아웃라인 제거 */
.lobby-clickable .stButton > button:focus,
.lobby-clickable .stButton > button:active{
  outline: none !important;
  box-shadow: none !important;
}

/* 혹시 남는 “작은 네모/원” 같은 잔상 제거(버튼 wrapper 최소높이 방지) */
.lobby-clickable [data-testid="stButton"]{
  min-height: 0 !important;
}

/* secondary 버튼 높이 0으로 죽이는 거는 lobby 화면까지 같이 죽일 수 있어요.
   아래처럼 "lobby-clickable 내부에서만" 숨기도록 제한 */
.lobby-clickable button[kind="secondary"]{
  height:100% !important;
  padding:0 !important;
  border:none !important;
  background:transparent !important;
}

/* 페이지 전체를 세로 flex 구조로 */
.main .block-container{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* footer를 맨 아래로 밀기 */
.lobby-footer{
  margin-top: auto;   /* ⭐ 핵심 */
  padding-top: 300px;
  padding-bottom: 20px;
  text-align:center;
  color:#9CA3AF;
  font-size:0.9rem;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# 1) Session State
# =========================================================
if "page" not in st.session_state:
    st.session_state.page = "lobby"  # lobby | explore | search
if "df" not in st.session_state:
    st.session_state.df = None
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None
if "region_meta" not in st.session_state:
    st.session_state.region_meta = None  # (keyword, cortarNo, lat, lon)


# =========================================================
# 2) Region resolving
# =========================================================
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
        return str(cortar_no), float(lat), float(lon)

    html = resp.text
    m_c = re.search(r'cortarNo["\']?\s*[:=]\s*["\']?(\d+)', html)
    m_lat = re.search(r'lat["\']?\s*[:=]\s*["\']?([0-9.]+)', html)
    m_lon = re.search(r'lon["\']?\s*[:=]\s*["\']?([0-9.]+)', html)

    if m_c and m_lat and m_lon:
        return m_c.group(1), float(m_lat.group(1)), float(m_lon.group(1))

    raise RuntimeError("지역 좌표/코드를 찾지 못했어요. 더 구체적으로 입력해보세요.")


# =========================================================
# 2-1) Price bucket (list colors)
# =========================================================
def price_bucket_v2(price_manwon):
    if price_manwon is None or pd.isna(price_manwon):
        return "가격정보없음"
    try:
        p = float(price_manwon)
    except:
        return "가격정보없음"

    if p < 10000:
        return "1억 미만"
    elif p < 50000:
        return "1억 ~ 5억"
    elif p < 100000:
        return "5억 ~ 10억"
    else:
        return "10억 초과"


BUCKET_COLOR = {
    "1억 미만": "#D8C9A8",   # 베이지
    "1억 ~ 5억": "#2E8B57",  # 초(그린)
    "5억 ~ 10억": "#2F6DF6", # 파(블루)
    "10억 초과": "#E74C3C",  # 빨(레드)
    "가격정보없음": "#9AA0A6",
}


# =========================================================
# 3) Map rendering
# =========================================================
def display_map(
    df,
    center_lat=None,
    center_lon=None,
    zoom=13,
    stations=None,
    walking_limit=10,
    school_overlay=None,
    selected_id=None,
):
    if df is None or df.empty:
        if center_lat is None or center_lon is None:
            return

    if center_lat is None or center_lon is None:
        center_lat = pd.to_numeric(df["위도"], errors="coerce").mean()
        center_lon = pd.to_numeric(df["경도"], errors="coerce").mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles=None)

    folium.TileLayer("OpenStreetMap", name="기본 지도", control=True).add_to(m)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="위성 지도",
        control=True,
        show=False,
    ).add_to(m)
    folium.TileLayer(tiles="CartoDB positron", name="밝은 배경", control=True, show=False).add_to(m)
    folium.LayerControl().add_to(m)

    # 학교 오버레이
    if school_overlay and school_overlay.get("enabled"):
        try:
            radius_m = int(school_overlay.get("radius_m", 2000))
            levels = school_overlay.get("levels") or ["초", "중", "고"]
            schools = fetch_nearby_schools_osm(center_lat, center_lon, radius_m)
            sch_color_map = {"초": "green", "중": "orange", "고": "red", "기타": "purple"}

            for s in schools:
                if s.get("level") not in levels:
                    continue
                folium.Marker(
                    location=[float(s["lat"]), float(s["lon"])],
                    tooltip=f"[{s['level']}] {s['name']}",
                    icon=folium.Icon(
                        color=sch_color_map.get(s["level"], "purple"),
                        icon="graduation-cap",
                        prefix="fa",
                    ),
                ).add_to(m)
        except:
            pass

    # 지하철
    if stations:
        radius_meters = walking_limit * 80
        for s_name, (s_lat, s_lon) in stations.items():
            folium.Marker(
                [s_lat, s_lon],
                tooltip=f"🚉 {s_name}",
                icon=folium.Icon(color="black", icon="subway", prefix="fa"),
            ).add_to(m)
            folium.Circle(
                location=[s_lat, s_lon],
                radius=radius_meters,
                color="blue",
                fill=True,
                fill_opacity=0.1,
                weight=1,
                interactive=False,
            ).add_to(m)

    # 매물 마커
    if df is not None and not df.empty:
        # folium.Icon은 팔레트 제한 => 대표 색 이름으로만
        color_map = {
            "1억 미만": "lightgray",
            "1억 ~ 5억": "green",
            "5억 ~ 10억": "blue",
            "10억 초과": "red",
            "가격정보없음": "gray",
        }

        for _, row in df.iterrows():
            lat, lon = pd.to_numeric(row["위도"]), pd.to_numeric(row["경도"])
            if pd.isna(lat) or pd.isna(lon):
                continue

            is_selected = selected_id is not None and str(row["매물ID"]) == str(selected_id)
            icon_name = "star" if is_selected else ("building" if "아파트" in str(row["매물유형"]) else "home")

            folium.Marker(
                [lat, lon],
                tooltip=f"[{row['매물유형']}] {row['단지/건물명']}",
                popup=f"<b>{row['단지/건물명']}</b><br>가격: {row['가격']}<br>{row['매물유형']} / {row['거래유형']}",
                icon=folium.Icon(
                    color=color_map.get(row.get("가격구간"), "gray"),
                    icon=icon_name,
                    prefix="fa",
                ),
            ).add_to(m)

    st_folium(m, use_container_width=True, height=560, returned_objects=[])


# =========================================================
# 4) UI helpers
# =========================================================
def kv_grid(data: dict, cols: int = 3):
    keys = list(data.keys())
    rows = (len(keys) + cols - 1) // cols
    for r in range(rows):
        cs = st.columns(cols)
        for c in range(cols):
            i = r * cols + c
            if i >= len(keys):
                continue
            k, v = keys[i], data.get(keys[i], "")
            v = "-" if (v is None or str(v).strip() == "") else str(v)
            cs[c].markdown(
                f"""
                <div style="background:#FFFFFF; border:1px solid #E6E8EF; border-radius:14px; padding:12px; box-shadow:0 6px 14px rgba(16,24,40,0.05);">
                  <div style="color:#6B7280; font-size:0.84rem; margin-bottom:4px;">{k}</div>
                  <div style="font-weight:900; font-size:1.02rem; color:#111827;">{v}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def topbar(title="부동산 매물 검색", subtitle=None):
    sub_html = f"<div class='topbar-sub'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"""
        <div class="topbar">
          <div class="brand">{title}<span class="brand-dot">.</span></div>
          {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls():
    with st.sidebar:
        st.markdown("### 🔎 검색")

        default_kw = (
            st.session_state.region_meta[0] if st.session_state.region_meta else ""
        )

        # ✅ kw가 비어있을 때만 기본값 채우기 (다른 페이지에서 미리 넣은 값 유지)
        if "kw" not in st.session_state or not str(st.session_state["kw"]).strip():
            st.session_state["kw"] = default_kw

        keyword = st.text_input(
            "지역",
            key="kw",
            placeholder="예) 잠실동 / 판교 / 서울 종로구",
        )

        limit = st.slider("가져올 개수", 10, 50, 50, 10, key="limit")

        st.markdown("---")
        st.markdown("### 🧰 필터")

        # 거래유형
        st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
        st.markdown("<div class='filter-title'>거래유형</div>", unsafe_allow_html=True)
        st.markdown("<div class='filter-sub'>원하는 거래 형태만 선택</div>", unsafe_allow_html=True)

        trad_opts = ["매매", "전세", "월세"]
        st.session_state.setdefault("trad_all", True)
        for t in trad_opts:
            st.session_state.setdefault(f"trad_{t}", True)

        def sync_t():
            for t in trad_opts:
                st.session_state[f"trad_{t}"] = st.session_state["trad_all"]

        st.checkbox("전체", key="trad_all", on_change=sync_t)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("매매", key="trad_매매")
        with c2:
            st.checkbox("전세", key="trad_전세")
        with c3:
            st.checkbox("월세", key="trad_월세")
        trad_selected = [t for t in trad_opts if st.session_state[f"trad_{t}"]]
        st.markdown("</div>", unsafe_allow_html=True)

        # 매물유형
        st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
        st.markdown("<div class='filter-title'>매물유형</div>", unsafe_allow_html=True)
        st.markdown("<div class='filter-sub'>보고 싶은 타입만 선택</div>", unsafe_allow_html=True)

        rlet_opts = ["아파트", "오피스텔", "상가주택", "단독/다가구", "빌라", "다세대"]
        st.session_state.setdefault("rlet_all", True)
        for r in rlet_opts:
            st.session_state.setdefault(f"rlet_{r}", True)

        def sync_r():
            for r in rlet_opts:
                st.session_state[f"rlet_{r}"] = st.session_state["rlet_all"]

        st.checkbox("전체", key="rlet_all", on_change=sync_r)
        colL, colR = st.columns(2)
        for i, r in enumerate(rlet_opts):
            target = colL if i % 2 == 0 else colR
            target.checkbox(r, key=f"rlet_{r}")
        rlet_selected = [r for r in rlet_opts if st.session_state[f"rlet_{r}"]]
        st.markdown("</div>", unsafe_allow_html=True)

        # 면적/예산
        st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
        st.markdown("<div class='filter-title'>면적/예산</div>", unsafe_allow_html=True)
        st.markdown("<div class='filter-sub'>조건을 좁혀서 정확히 찾기</div>", unsafe_allow_html=True)

        st.markdown("**면적(평)**")
        py_min = st.number_input("최소", min_value=0.0, value=0.0, key="py_min")
        py_max = st.number_input("최대", min_value=0.0, value=200.0, key="py_max")

        st.markdown("**예산(상한)**")
        b_eok = st.number_input("억", min_value=0, value=0, key="b_eok")
        b_man = st.number_input("만원", min_value=0, value=0, step=100, key="b_man")
        budget_limit = b_eok * 10000 + b_man
        st.markdown("</div>", unsafe_allow_html=True)

        # 지하철
        st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
        st.markdown("<div class='filter-title'>지하철</div>", unsafe_allow_html=True)
        st.markdown("<div class='filter-sub'>선택한 노선 기준 도보 제한</div>", unsafe_allow_html=True)

        subway_line = st.selectbox("노선 선택", options=["선택 안 함"] + list(SUBWAY_LINES.keys()), key="subway_line")
        w_time = 10
        if subway_line != "선택 안 함":
            w_time = st.slider("최대 도보 시간 (분)", 5, 30, 10, 5, key="w_time")
        st.markdown("</div>", unsafe_allow_html=True)

        run = st.button("검색 실행", type="primary", use_container_width=True)

    return {
        "keyword": keyword,
        "limit": int(limit),
        "trad_selected": trad_selected,
        "rlet_selected": rlet_selected,
        "py_min": py_min,
        "py_max": py_max,
        "budget_limit": budget_limit,
        "subway_line": subway_line,
        "w_time": w_time,
        "run": run,
    }


# =========================================================
# 5) Pages
# =========================================================
def render_lobby():
    st.markdown("<div class='lobby-wrap'>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="main-title">🏠 Real Estate WebApp</div>
        <div class="main-sub">지역 기반 부동산 매물 탐색 · 지도 시각화 · 가격 분석</div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("<div class='lobby-clickable'>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="lobby-card">
              <div class="lobby-title">🧭 지역 탐색</div>
              <div class="lobby-desc">
                원하는 지역의 월세 / 전세 / 인프라를 분석하고<br>
                지도 기반으로 주변 환경을 표시합니다.<br><br>
                ✓ 전국 맞춤형 이사 지역 가이드<br>
                ✓ 지도 미리보기<br>
                ✓ 개인별 인프라 가중치 설정<br>
                ✓ 분야별 인프라 순위 그래프<br>
                ✓ 상세 데이터 테이블
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ✅ 이 버튼은 화면에 "흔적"이 남지 않고 카드 전체 클릭이 됨
        if st.button("지역 탐색", key="go_explore_card", use_container_width=True):
            st.session_state.page = "explore"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='lobby-clickable'>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="lobby-card">
              <div class="lobby-title">🔎 매물 검색</div>
              <div class="lobby-desc">
                지역 · 가격 · 면적 · 지하철 조건을 설정하고<br>
                실제 매물을 지도와 함께 확인합니다.<br><br>
                ✓ 개인별 필터링에 따른 매물 검색<br>
                ✓ 지도 + 상세정보 실시간 연동<br>
                ✓ 근처 학교 유무 표시<br>
                ✓ 매물 사진 미리보기<br>
                ✓ 가격 구간 분석 시각화 제공
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("매물 검색", key="go_search_card", use_container_width=True):
            st.session_state.page = "search"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='lobby-footer'>Real Estate WebApp · 지도 기반 부동산 탐색 프로젝트</div>",
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def render_explore():
    topbar("지역 탐색", "전국/시도별 이사 가이드")

    if st.button(" ← 메인으로"):
        st.session_state.page = "lobby"
        st.rerun()

    # ✅ 팀 화면을 여기서 그대로 렌더
    team_explore.render_team_explore()


def render_search():
    topbar("부동산 매물 검색", "희망 지역내 매물 검색")

    # back
    if st.button(" ← 메인으로"):
        st.session_state.page = "lobby"
        st.rerun()

    ctl = sidebar_controls()

    # run search
    if ctl["run"]:
        st.session_state.selected_id = None
        try:
            c, lat, lon = resolve_region(ctl["keyword"])
            st.session_state.region_meta = (ctl["keyword"], c, lat, lon)

            with st.spinner("매물 수집 중..."):
                items = scraper.scrape_articles(cortar_no=c, lat=lat, lon=lon, limit=ctl["limit"])
            if not items:
                st.warning("매물이 없습니다.")
                st.stop()

            df = items_to_dataframe(items)
            df["가격(만원)"] = df["가격"].apply(parse_price_to_manwon)
            df["면적(평)"] = pd.to_numeric(df["면적(㎡)"], errors="coerce").apply(sqm_to_pyeong)
            df["가격구간"] = df["가격(만원)"].apply(price_bucket_v2)
            df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
            df["경도"] = pd.to_numeric(df["경도"], errors="coerce")

            # subway filter
            if ctl["subway_line"] != "선택 안 함":
                stns = SUBWAY_LINES[ctl["subway_line"]]

                def get_w(row):
                    if pd.isna(row["위도"]) or pd.isna(row["경도"]):
                        return 999
                    m_t = 999
                    for _, (slat, slon) in stns.items():
                        d = haversine_distance(row["위도"], row["경도"], slat, slon)
                        t = estimate_walking_minutes(d)
                        if t < m_t:
                            m_t = t
                    return m_t

                df["도보시간(분)"] = df.apply(get_w, axis=1)
                df = df[df["도보시간(분)"] <= ctl["w_time"]]

            # other filters
            if ctl["trad_selected"]:
                df = df[df["거래유형"].isin(ctl["trad_selected"])]
            if ctl["rlet_selected"]:
                df = df[df["매물유형"].isin(ctl["rlet_selected"])]

            df = df[
                (df["면적(평)"].isna())
                | ((df["면적(평)"] >= ctl["py_min"]) & (df["면적(평)"] <= ctl["py_max"]))
            ]

            if ctl["budget_limit"] > 0:
                df = df[(df["가격(만원)"].isna()) | (df["가격(만원)"] <= ctl["budget_limit"])]

            st.session_state.df = df.sort_values("가격(만원)", ascending=False).reset_index(drop=True)

        except Exception as e:
            st.error(str(e))

    df = st.session_state.df
    if df is None:
        st.info("좌측에서 지역/조건 설정 후 ‘검색 실행’을 눌러주세요.")
        return

    # overlay options
    with st.expander("🏫 지도 오버레이 (주변 학교)", expanded=False):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        se = c1.checkbox("초등학교", key="se")
        sm = c2.checkbox("중학교", key="sm")
        sh = c3.checkbox("고등학교", key="sh")
        r_m = c4.slider("반경(m)", 500, 5000, 2000, 500, key="r_m")
        levels = []
        if se:
            levels.append("초")
        if sm:
            levels.append("중")
        if sh:
            levels.append("고")
        school_overlay = {"enabled": bool(levels), "levels": levels, "radius_m": r_m}

    # search summary
    region_txt = st.session_state.region_meta[0] if st.session_state.region_meta else "-"
    st.markdown(
        f"<div class='card'><div class='section-title'>검색 결과</div>"
        f"<div class='muted'>지역: <b>{region_txt}</b> · 결과: <b>{len(df)}</b>건</div></div>",
        unsafe_allow_html=True,
    )

    # main 2-pane: list + map/detail (naver-ish)
    L, R = st.columns([0.44, 0.56], gap="large")

    # LEFT: list (scroll inside)
    with L:
        st.markdown("---")
        st.markdown("<div class='section-title'>📋 목록</div>", unsafe_allow_html=True)
        q = st.text_input("목록 내 검색", placeholder="건물명 검색...", label_visibility="collapsed")
        ldf = df[df["단지/건물명"].str.contains(q, case=False, na=False)] if q else df

        st.markdown("<div class='list-wrap'>", unsafe_allow_html=True)

        # default selection if none
        if st.session_state.selected_id is None and not df.empty:
            st.session_state.selected_id = str(df.iloc[0]["매물ID"])

        for _, r in ldf.head(80).iterrows():  # ✅ 네이버처럼 더 길게 보여도 목록만 스크롤
            b = r.get("가격구간", "가격정보없음")
            sw = BUCKET_COLOR.get(b, "#9AA0A6")
            sel = (str(r["매물ID"]) == str(st.session_state.selected_id))
            cls = "list-item selected" if sel else "list-item"

            price = r.get("가격", "-")
            rlet = r.get("매물유형", "-")
            trad = r.get("거래유형", "-")
            py = r.get("면적(평)")
            py_txt = f"{py:.1f}평" if pd.notna(py) else "-"
            floor = r.get("층", "-")

            st.markdown(f"<div class='{cls}'>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class='list-row'>
                  <div class='swatch' style='background:{sw}'></div>
                  <div style='flex:1; min-width:0;'>
                    <div class='li-title'>{r['단지/건물명']}</div>
                    <div class='li-sub'><b>{price}</b> · {b}</div>
                    <div class='li-meta'>{rlet} / {trad} · {py_txt} · {floor}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div class='li-cta'>", unsafe_allow_html=True)
            if st.button("지도/상세 보기", key=f"btn_{r['매물ID']}", use_container_width=True):
                st.session_state.selected_id = str(r["매물ID"])
                st.rerun()
            st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)  # list-wrap
        st.markdown("</div>", unsafe_allow_html=True)  # card

    # RIGHT: map + detail sticky
    with R:
        st.markdown("<div class='sticky-pane'>", unsafe_allow_html=True)

        sel = st.session_state.selected_id or (str(df.iloc[0]["매물ID"]) if not df.empty else None)
        if sel:
            row = df[df["매물ID"] == sel].iloc[0]

            st.markdown("---")
            st.markdown("<div class='section-title'>🗺️ 지도</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='muted'><b>{row['단지/건물명']}</b> 중심으로 표시</div>", unsafe_allow_html=True)

            curr_stns = SUBWAY_LINES.get(ctl["subway_line"]) if ctl.get("subway_line") != "선택 안 함" else None
            display_map(
                df,
                center_lat=row["위도"],
                center_lon=row["경도"],
                zoom=16,
                stations=curr_stns,
                walking_limit=ctl.get("w_time", 10),
                school_overlay=school_overlay,
                selected_id=sel,
            )
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>📌 상세</div>", unsafe_allow_html=True)
            kv_grid(
                {
                    "가격": row.get("가격"),
                    "유형": f"{row.get('매물유형','-')}/{row.get('거래유형','-')}",
                    "면적": f"{row['면적(평)']:.1f}평" if pd.notna(row.get("면적(평)")) else "-",
                    "층": row.get("층"),
                    "방향": row.get("방향"),
                    "확인일": row.get("확인일"),
                }
            )
            if row.get("특징"):
                st.markdown(
                    f"<div style='margin-top:10px; padding:12px; border:1px solid #E6E8EF; border-radius:14px; background:#FFFFFF;'>"
                    f"<b style='color:#111827;'>특징</b><div class='muted' style='margin-top:6px;'>{row['특징']}</div></div>",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

            # 📷 매물 사진 (목록 썸네일 + 상세 갤러리 병합)
            thumb_url = None
            raw_rep = row.get("대표이미지")
            if isinstance(raw_rep, str) and raw_rep.strip():
                u = raw_rep.strip()
                # 사용자가 준 코드와 동일한 규칙으로 도메인 보정
                if u.startswith("//"):
                    u = "https:" + u
                elif u.startswith("/"):
                    u = "https://landthumb-phinf.pstatic.net" + u
                thumb_url = u

            atcl_no = str(row["매물ID"])
            gallery_urls: List[str] = []
            try:
                # 네이버 프론트 API/HTML에서 방 사진(갤러리) 시도
                gallery_urls = scraper.get_article_image_urls(atcl_no) or []
            except Exception:
                gallery_urls = []

            # 썸네일 + 갤러리 URL을 하나의 리스트로 합치고 중복 제거
            merged: List[str] = []
            if thumb_url:
                merged.append(thumb_url)
            merged.extend(gallery_urls)
            # 순서 유지하면서 중복 제거
            seen = set()
            final_urls: List[str] = []
            for u in merged:
                if not isinstance(u, str):
                    continue
                uu = u.strip()
                if not uu or uu in seen:
                    continue
                seen.add(uu)
                final_urls.append(uu)

            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>📷 매물 사진</div>", unsafe_allow_html=True)
            if final_urls:
                # 너무 많은 이미지는 부담이 될 수 있어 상위 12장만 노출
                st.image(final_urls[:12])
            else:
                st.markdown(
                    "<div class='muted'>해당 매물에 대해 불러올 수 있는 사진이 없거나, 네이버 측 응답이 없어 이미지를 표시하지 못했습니다.</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # dashboard (like naver's mini stats)
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📊 가격 구간 분포</div>", unsafe_allow_html=True)
    order = ["1억 미만", "1억 ~ 5억", "5억 ~ 10억", "10억 초과"]
    bc = df["가격구간"].value_counts().reindex(order).fillna(0).reset_index()
    bc.columns = ["가격구간", "건수"]
    fig = px.bar(
        bc,
        x="가격구간",
        y="건수",
        color="가격구간",
        color_discrete_map=BUCKET_COLOR,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 6) Routing
# =========================================================
if st.session_state.page == "lobby":
    render_lobby()
elif st.session_state.page == "explore":
    render_explore()
else:
    render_search()
