# app.py
import re
from urllib.parse import quote, urlparse, parse_qs

import requests
import pandas as pd
import plotly.express as px
import streamlit as st
import folium
from streamlit_folium import st_folium
import sys
import os

# 현재 디렉토리와 모듈 디렉토리를 path에 추가하여 로컬 모듈 로드 보장
current_dir = os.path.dirname(os.path.abspath(__file__))
module_dir = os.path.join(os.path.dirname(current_dir), "frontend", "map_service")

if module_dir not in sys.path:
    sys.path.append(module_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)

import scraper
from utils import items_to_dataframe, parse_price_to_manwon, sqm_to_pyeong, haversine_distance, estimate_walking_minutes, price_bucket
from subway_data import SUBWAY_LINES
from poi_schools import fetch_nearby_schools_osm

# =========================================================
# 0) 페이지 설정 + 스타일(노랑톤 + 부드러운 폰트 + 상단 흰바 숨김)
# =========================================================
st.set_page_config(page_title="부동산 웹앱", layout="wide", initial_sidebar_state="expanded")

if st.button("🏠 홈으로 이동"):
    st.switch_page("app.py")

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');

      html, body, [class*="css"]  {
        font-family: "Nunito", "Noto Sans KR", system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      }

      /* Streamlit 기본 헤더/푸터/상단 툴바 숨기기 */
      header { visibility: hidden; height: 0px; }
      footer { visibility: hidden; height: 0px; }
      [data-testid="stToolbar"] { display: none; }

      /* 전체 배경/사이드바 */
      .stApp { background: #FFF7D1; }
      [data-testid="stSidebar"] { background: #FFF0A8; }

      /* 기본 여백 */
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

      /* 카드 */
      .card {
        background: rgba(255,255,255,0.92);
        border: 1px solid #F0D36A;
        border-radius: 18px;
        padding: 16px 16px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.04);
        margin-bottom: 10px;
      }
      .muted { color: #6b5b00; font-size: 0.95rem; }

      /* 배지 */
      .badge {
        display:inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid #F0D36A;
        background: #FFF6C8;
        font-size: 0.85rem;
        margin-right: 6px;
        margin-bottom: 6px;
      }

      /* 섹션 타이틀 */
      .section-title { font-weight: 800; font-size: 1.25rem; color: #3b2f00; margin: 0 0 10px 0;}

      /* 버튼/입력 라운드 */
      .stButton>button { border-radius: 14px; }
      input, textarea { border-radius: 12px !important; }

      /* 구분선 */
      .sep { border:none; border-top:1px solid #f5e4a3; margin:12px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 1) 세션 상태
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
# 2) 지역명 -> (cortarNo, lat, lon) 자동 추출
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
    """
    m.land 검색 페이지를 열고 URL/HTML에서 cortarNo, lat, lon 추출
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
        return str(cortar_no), float(lat), float(lon)

    html = resp.text
    m_c = re.search(r'cortarNo["\']?\s*[:=]\s*["\']?(\d+)', html)
    m_lat = re.search(r'lat["\']?\s*[:=]\s*["\']?([0-9.]+)', html)
    m_lon = re.search(r'lon["\']?\s*[:=]\s*["\']?([0-9.]+)', html)

    if m_c and m_lat and m_lon:
        return m_c.group(1), float(m_lat.group(1)), float(m_lon.group(1))

    raise RuntimeError("지역 좌표/코드를 찾지 못했어요. 더 구체적으로 입력해보세요.")


# =========================================================
# 3) 지도 렌더링 함수 (Folium)
# =========================================================
def display_map(df, center_lat=None, center_lon=None, zoom=13, stations=None, walking_limit=10, school_overlay=None, selected_id=None):
    if df is None or df.empty:
        # 매물이 없더라도 중심점이 있으면 지도 표시
        if center_lat is None or center_lon is None:
            return
    
    if center_lat is None or center_lon is None:
        center_lat = pd.to_numeric(df["위도"], errors="coerce").mean()
        center_lon = pd.to_numeric(df["경도"], errors="coerce").mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles=None)

    # 타일 설정
    folium.TileLayer("OpenStreetMap", name="기본 지도", control=True).add_to(m)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="위성 지도",
        control=True,
        show=False
    ).add_to(m)
    folium.TileLayer(tiles="CartoDB positron", name="밝은 배경", control=True, show=False).add_to(m)
    folium.LayerControl().add_to(m)

    # 학교 오버레이
    if school_overlay and school_overlay.get("enabled"):
        try:
            radius_m = int(school_overlay.get("radius_m", 2000))
            levels = school_overlay.get("levels") or ["초", "중", "고"]
            schools = fetch_nearby_schools_osm(center_lat, center_lon, radius_m)
            # folium.Icon의 color는 정해진 색상 이름만 지원하므로 맵핑 변경
            sch_color_map = {"초": "green", "중": "orange", "고": "red", "기타": "purple"}

            for s in schools:
                if s.get("level") not in levels: continue
                folium.Marker(
                    location=[float(s["lat"]), float(s["lon"])],
                    tooltip=f"[{s['level']}] {s['name']}",
                    icon=folium.Icon(color=sch_color_map.get(s["level"], "purple"), icon="graduation-cap", prefix="fa")
                ).add_to(m)
        except: pass

    # 지하철
    if stations:
        radius_meters = walking_limit * 80
        for s_name, (s_lat, s_lon) in stations.items():
            folium.Marker([s_lat, s_lon], tooltip=f"🚉 {s_name}", icon=folium.Icon(color="black", icon="subway", prefix="fa")).add_to(m)
            folium.Circle(location=[s_lat, s_lon], radius=radius_meters, color="blue", fill=True, fill_opacity=0.1, weight=1, interactive=False).add_to(m)

    # 매물 마커
    if df is not None and not df.empty:
        # 색상 요구사항: 5,000만 미만=빨강 / 5,000만~5억=초록 / 5억 초과=파랑
        color_map = {"5,000만 미만": "red", "5,000만 ~ 5억": "green", "5억 초과": "blue", "가격정보없음": "gray"}
        for _, row in df.iterrows():
            lat, lon = pd.to_numeric(row["위도"]), pd.to_numeric(row["경도"])
            if pd.isna(lat) or pd.isna(lon): continue
            
            is_selected = (selected_id is not None and str(row["매물ID"]) == str(selected_id))
            icon_name = "star" if is_selected else ("building" if "아파트" in str(row["매물유형"]) else "home")
            
            folium.Marker(
                [lat, lon],
                tooltip=f"[{row['매물유형']}] {row['단지/건물명']}",
                popup=f"<b>{row['단지/건물명']}</b><br>가격: {row['가격']}<br>{row['매물유형']} / {row['거래유형']}",
                icon=folium.Icon(color=color_map.get(row["가격구간"], "gray"), icon=icon_name, prefix="fa")
            ).add_to(m)

    st_folium(m, use_container_width=True, height=500, returned_objects=[])


# =========================================================
# 4) UI 컴포넌트
# =========================================================
def kv_grid(data: dict, cols: int = 3):
    """dict를 카드형 key-value 그리드로 예쁘게 출력"""
    keys = list(data.keys())
    rows = (len(keys) + cols - 1) // cols
    for r in range(rows):
        cs = st.columns(cols)
        for c in range(cols):
            i = r * cols + c
            if i >= len(keys): continue
            k, v = keys[i], data.get(keys[i], "")
            v = "-" if (v is None or str(v).strip() == "") else str(v)
            cs[c].markdown(f"""
                <div style="background:rgba(255,255,255,0.92); border:1px solid #F0D36A; border-radius:14px; padding:12px; box-shadow:0 4px 14px rgba(0,0,0,0.03);">
                  <div style="color:#6b5b00; font-size:0.85rem; margin-bottom:4px;">{k}</div>
                  <div style="font-weight:700; font-size:1.02rem; color:#2f2500;">{v}</div>
                </div>
                """, unsafe_allow_html=True)


def sidebar_controls():
    with st.sidebar:
        st.markdown("## 🔎 검색")
        default_kw = st.session_state.region_meta[0] if st.session_state.region_meta else ""
        keyword = st.text_input("지역", value=default_kw, placeholder="예) 서울 종로구 / 잠실동 / 판교", key="kw")
        limit = st.slider("가져올 개수", 10, 50, 50, 10, key="limit")

        st.markdown("---")
        st.markdown("## 🧰 필터")

        # 거래유형
        trad_opts = ["매매", "전세", "월세"]
        st.session_state.setdefault("trad_all", True)
        for t in trad_opts: st.session_state.setdefault(f"trad_{t}", True)
        def sync_t():
            for t in trad_opts: st.session_state[f"trad_{t}"] = st.session_state["trad_all"]
        st.checkbox("거래유형 전체", key="trad_all", on_change=sync_t)
        c1, c2, c3 = st.columns(3)
        with c1: st.checkbox("매매", key="trad_매매")
        with c2: st.checkbox("전세", key="trad_전세")
        with c3: st.checkbox("월세", key="trad_월세")
        trad_selected = [t for t in trad_opts if st.session_state[f"trad_{t}"]]

        # 매물유형
        rlet_opts = ["아파트", "오피스텔", "상가주택", "단독/다가구", "빌라", "다세대"]
        st.session_state.setdefault("rlet_all", True)
        for r in rlet_opts: st.session_state.setdefault(f"rlet_{r}", True)
        def sync_r():
            for r in rlet_opts: st.session_state[f"rlet_{r}"] = st.session_state["rlet_all"]
        st.checkbox("매물유형 전체", key="rlet_all", on_change=sync_r)
        colL, colR = st.columns(2)
        for i, r in enumerate(rlet_opts):
            target = colL if i % 2 == 0 else colR
            target.checkbox(r, key=f"rlet_{r}")
        rlet_selected = [r for r in rlet_opts if st.session_state[f"rlet_{r}"]]

        st.markdown("---")
        st.markdown("**면적(평)**")
        py_min = st.number_input("최소", min_value=0.0, value=0.0, key="py_min")
        py_max = st.number_input("최대", min_value=0.0, value=200.0, key="py_max")

        st.markdown("**예산(상한)**")
        b_eok = st.number_input("억", min_value=0, value=0, key="b_eok")
        b_man = st.number_input("만원", min_value=0, value=0, step=100, key="b_man")
        budget_limit = b_eok * 10000 + b_man

        st.markdown("---")
        st.markdown("## 🚉 지하철 필터")
        subway_line = st.selectbox("노선 선택", options=["선택 안 함"] + list(SUBWAY_LINES.keys()), key="subway_line")
        w_time = 10
        if subway_line != "선택 안 함":
            w_time = st.slider("최대 도보 시간 (분)", 5, 30, 10, 5, key="w_time")

        st.markdown("---")
        run = st.button("검색 실행", type="primary", use_container_width=True)

    return {
        "keyword": keyword, "limit": int(limit), "trad_selected": trad_selected, 
        "rlet_selected": rlet_selected, "py_min": py_min, "py_max": py_max,
        "budget_limit": budget_limit, "subway_line": subway_line, "w_time": w_time, "run": run
    }


# =========================================================
# 5) 페이지 렌더링
# =========================================================
def render_lobby():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 🏠 로비")
    st.markdown("<div class='muted'>아래에서 할 일을 선택하세요.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>🧭 지역 탐색</div>", unsafe_allow_html=True)
        if st.button("지역 탐색으로 이동", use_container_width=True):
            st.session_state.page = "explore"; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>🔎 매물 검색</div>", unsafe_allow_html=True)
        if st.button("매물 검색으로 이동", use_container_width=True):
            st.session_state.page = "search"; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_explore():
    if st.button("← 로비"): st.session_state.page = "lobby"; st.rerun()
    st.markdown("<div class='card'><h2>🧭 지역 탐색</h2></div>", unsafe_allow_html=True)
    colL, colR = st.columns([0.4, 0.6], gap="large")
    with colL:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        kw = st.text_input("지역 입력", key="exp_kw")
        if st.button("좌표 찾기", use_container_width=True):
            try:
                c, lat, lon = resolve_region(kw)
                st.session_state.region_meta = (kw, c, lat, lon)
            except Exception as e: st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)
    with colR:
        meta = st.session_state.region_meta
        if meta:
            kw, c, lat, lon = meta
            st.markdown(f"<div class='card'><span class='badge'>지역</span> {kw}<br><span class='badge'>좌표</span> {lat}, {lon}</div>", unsafe_allow_html=True)
            display_map(None, center_lat=lat, center_lon=lon, zoom=14)
            if st.button("이 지역으로 매물 검색 →", use_container_width=True):
                st.session_state.page = "search"; st.rerun()
        else: st.info("지역을 입력해보세요.")


def render_search():
    if st.button("← 로비"): st.session_state.page = "lobby"; st.rerun()
    ctl = sidebar_controls()
    
    if ctl["run"]:
        st.session_state.selected_id = None
        try:
            c, lat, lon = resolve_region(ctl["keyword"])
            st.session_state.region_meta = (ctl["keyword"], c, lat, lon)
            with st.spinner("수집 중..."):
                items = scraper.scrape_articles(cortar_no=c, lat=lat, lon=lon, limit=ctl["limit"])
            if not items: st.warning("매물이 없습니다."); st.stop()
            
            df = items_to_dataframe(items)
            df["가격(만원)"] = df["가격"].apply(parse_price_to_manwon)
            df["면적(평)"] = pd.to_numeric(df["면적(㎡)"], errors="coerce").apply(sqm_to_pyeong)
            df["가격구간"] = df["가격(만원)"].apply(price_bucket)
            df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
            df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
            
            # 지하철 필터
            if ctl["subway_line"] != "선택 안 함":
                stns = SUBWAY_LINES[ctl["subway_line"]]
                def get_w(row):
                    if pd.isna(row["위도"]) or pd.isna(row["경도"]): return 999
                    m_t = 999
                    for sn, (slat, slon) in stns.items():
                        d = haversine_distance(row["위도"], row["경도"], slat, slon)
                        t = estimate_walking_minutes(d)
                        if t < m_t: m_t = t
                    return m_t
                df["도보시간(분)"] = df.apply(get_w, axis=1)
                df = df[df["도보시간(분)"] <= ctl["w_time"]]
            
            # 기타 필터
            if ctl["trad_selected"]: df = df[df["거래유형"].isin(ctl["trad_selected"])]
            if ctl["rlet_selected"]: df = df[df["매물유형"].isin(ctl["rlet_selected"])]
            df = df[(df["면적(평)"].isna()) | ((df["면적(평)"] >= ctl["py_min"]) & (df["면적(평)"] <= ctl["py_max"]))]
            if ctl["budget_limit"] > 0: df = df[(df["가격(만원)"].isna()) | (df["가격(만원)"] <= ctl["budget_limit"])]
            
            st.session_state.df = df.sort_values("가격(만원)", ascending=False).reset_index(drop=True)
        except Exception as e: st.error(str(e))

    df = st.session_state.df
    if df is None: st.info("지역을 입력하고 검색 실행을 눌러주세요."); return

    # 학교 오버레이 옵션
    with st.expander("🏫 지도 오버레이 (주변 학교 설정)", expanded=False):
        c1, c2, c3, c4 = st.columns([1,1,1,2])
        se = c1.checkbox("초등학교", key="se")
        sm = c2.checkbox("중학교", key="sm")
        sh = c3.checkbox("고등학교", key="sh")
        r_m = c4.slider("반경(m)", 500, 5000, 2000, 500, key="r_m")
        levels = []
        if se: levels.append("초")
        if sm: levels.append("중")
        if sh: levels.append("고")
        school_overlay = {"enabled": bool(levels), "levels": levels, "radius_m": r_m}

    # 레이아웃
    st.markdown(f"<div class='card'><h3>🔎 매물 검색 결과 ({len(df)}건)</h3></div>", unsafe_allow_html=True)
    
    L, R = st.columns([0.4, 0.6], gap="large")
    with L:
        st.markdown("<div class='card'><h4>📋 목록</h4>", unsafe_allow_html=True)
        q = st.text_input("목록 내 검색", placeholder="건물명...", label_visibility="collapsed")
        ldf = df[df["단지/건물명"].str.contains(q, case=False, na=False)] if q else df
        for _, r in ldf.head(30).iterrows():
            if st.button(f"{r['단지/건물명']} ({r['가격']})", key=f"btn_{r['매물ID']}", use_container_width=True):
                st.session_state.selected_id = str(r["매물ID"])
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    with R:
        sel = st.session_state.selected_id or (str(df.iloc[0]["매물ID"]) if not df.empty else None)
        if sel:
            row = df[df["매물ID"] == sel].iloc[0]
            st.markdown(f"<div class='card'><h4>📌 상세: {row['단지/건물명']}</h4>", unsafe_allow_html=True)
            
            curr_stns = SUBWAY_LINES.get(ctl["subway_line"]) if ctl.get("subway_line") != "선택 안 함" else None
            display_map(df, center_lat=row["위도"], center_lon=row["경도"], zoom=16, 
                        stations=curr_stns, walking_limit=ctl.get("w_time", 10), 
                        school_overlay=school_overlay, selected_id=sel)
            
            kv_grid({
                "가격": row["가격"], "유형": f"{row['매물유형']}/{row['거래유형']}", 
                "면적": f"{row['면적(평)']:.1f}평" if pd.notna(row['면적(평)']) else "-",
                "층": row["층"], "방향": row["방향"], "확인일": row["확인일"]
            })
            if row["특징"]: st.markdown(f"<div class='card'><b>특징:</b><br>{row['특징']}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # 대시보드
    st.markdown("<div class='card'><h4>📊 가격 구간 분포</h4>", unsafe_allow_html=True)
    order = ["5,000만 미만", "5,000만 ~ 5억", "5억 초과", "가격정보없음"]
    bc = df["가격구간"].value_counts().reindex(order).fillna(0).reset_index()
    bc.columns = ["가격구간", "건수"]
    fig = px.bar(bc, x="가격구간", y="건수", color="가격구간", color_discrete_map={"5,000만 미만":"red","5,000만 ~ 5억":"green","5억 초과":"blue","가격정보없음":"gray"})
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 6) 라우팅
# =========================================================
if st.session_state.page == "lobby": render_lobby()
elif st.session_state.page == "explore": render_explore()
else: render_search()
