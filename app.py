# app.py
import re
from urllib.parse import quote, urlparse, parse_qs

import requests
import pandas as pd
import plotly.express as px
import streamlit as st

import scraper
from utils import items_to_dataframe, parse_price_to_manwon, sqm_to_pyeong, price_bucket


# =========================================================
# 0) 페이지 설정 + 스타일(노랑톤 + 부드러운 폰트 + 상단 흰바 숨김)
# =========================================================
st.set_page_config(page_title="부동산 웹앱", layout="wide", initial_sidebar_state="expanded")

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
# 3) DF 생성 + 필터
# =========================================================
def build_df(items: list[dict]) -> pd.DataFrame:
    """
    items -> DF + 파생 컬럼
    - 가격(만원), 면적(평), 가격구간
    """
    df = items_to_dataframe(items)

    df["가격(만원)"] = df["가격"].apply(parse_price_to_manwon)
    df["면적(㎡)"] = pd.to_numeric(df["면적(㎡)"], errors="coerce")
    df["면적(평)"] = df["면적(㎡)"].apply(sqm_to_pyeong)
    df["가격구간"] = df["가격(만원)"].apply(price_bucket)

    df = df.sort_values(by="가격(만원)", ascending=False, na_position="last").reset_index(drop=True)
    return df


def apply_filters(
    df: pd.DataFrame,
    trad_selected: list[str],
    rlet_selected: list[str],
    pyeong_min: float,
    pyeong_max: float,
    budget_limit_manwon: int,
) -> pd.DataFrame:
    """
    필터:
    1) 거래유형
    2) 매물유형
    3) 면적(평)
    4) 예산(만원)
    """
    f = df.copy()

    if trad_selected:
        f = f[f["거래유형"].isin(trad_selected)]

    if rlet_selected:
        f = f[f["매물유형"].isin(rlet_selected)]

    f = f[(f["면적(평)"].isna()) | ((f["면적(평)"] >= pyeong_min) & (f["면적(평)"] <= pyeong_max))]

    if budget_limit_manwon > 0:
        f = f[(f["가격(만원)"].isna()) | (f["가격(만원)"] <= budget_limit_manwon)]

    return f.reset_index(drop=True)


# =========================================================
# 4) 추가 정보 카드형 출력
# =========================================================
def kv_grid(data: dict, cols: int = 3):
    """dict를 카드형 key-value 그리드로 예쁘게 출력"""
    keys = list(data.keys())
    rows = (len(keys) + cols - 1) // cols

    for r in range(rows):
        cs = st.columns(cols)
        for c in range(cols):
            i = r * cols + c
            if i >= len(keys):
                continue

            k = keys[i]
            v = data.get(k, "")
            v = "-" if (v is None or str(v).strip() == "") else str(v)

            cs[c].markdown(
                f"""
                <div style="
                    background: rgba(255,255,255,0.92);
                    border: 1px solid #F0D36A;
                    border-radius: 14px;
                    padding: 12px 12px;
                    box-shadow: 0 4px 14px rgba(0,0,0,0.03);
                    ">
                  <div style="color:#6b5b00; font-size:0.85rem; margin-bottom:4px;">{k}</div>
                  <div style="font-weight:700; font-size:1.02rem; color:#2f2500;">{v}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =========================================================
# 5) ✅ 사이드바 UI (전체 체크가 아래까지 동기화, 옵션은 항상 노출)
# =========================================================
def sidebar_controls():
    with st.sidebar:
        st.markdown("## 🔎 검색")

        default_kw = st.session_state.region_meta[0] if st.session_state.region_meta else ""
        keyword = st.text_input("지역", value=default_kw, placeholder="예) 서울 종로구 / 잠실동 / 판교", key="kw")

        limit = st.slider("가져올 개수", 10, 50, 50, 10, key="limit")

        st.markdown("---")
        st.markdown("## 🧰 필터")

        # ---------- 거래유형 ----------
        trad_opts = ["매매", "전세", "월세"]
        st.session_state.setdefault("trad_all", True)
        for t in trad_opts:
            st.session_state.setdefault(f"trad_{t}", True)

        def sync_trad_from_all():
            v = st.session_state["trad_all"]
            for t in trad_opts:
                st.session_state[f"trad_{t}"] = v

        def sync_trad_all_from_items():
            st.session_state["trad_all"] = all(st.session_state[f"trad_{t}"] for t in trad_opts)

        st.markdown("**거래유형**")
        st.checkbox("전체", key="trad_all", on_change=sync_trad_from_all)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("매매", key="trad_매매", on_change=sync_trad_all_from_items)
        with c2:
            st.checkbox("전세", key="trad_전세", on_change=sync_trad_all_from_items)
        with c3:
            st.checkbox("월세", key="trad_월세", on_change=sync_trad_all_from_items)

        trad_selected = [t for t in trad_opts if st.session_state[f"trad_{t}"]]

        st.markdown("---")

        # ---------- 매물유형 ----------
        rlet_opts = ["아파트", "오피스텔", "상가주택", "단독/다가구", "빌라", "다세대"]
        st.session_state.setdefault("rlet_all", True)
        for r in rlet_opts:
            st.session_state.setdefault(f"rlet_{r}", True)

        def sync_rlet_from_all():
            v = st.session_state["rlet_all"]
            for r in rlet_opts:
                st.session_state[f"rlet_{r}"] = v

        def sync_rlet_all_from_items():
            st.session_state["rlet_all"] = all(st.session_state[f"rlet_{r}"] for r in rlet_opts)

        st.markdown("**매물유형**")
        st.checkbox("전체", key="rlet_all", on_change=sync_rlet_from_all)

        colL, colR = st.columns(2)
        for i, r in enumerate(rlet_opts):
            target = colL if i % 2 == 0 else colR
            with target:
                st.checkbox(r, key=f"rlet_{r}", on_change=sync_rlet_all_from_items)

        rlet_selected = [r for r in rlet_opts if st.session_state[f"rlet_{r}"]]

        st.markdown("---")

        # ---------- 면적/예산 ----------
        st.markdown("**면적(평)**")
        pyeong_min = st.number_input("최소", min_value=0.0, value=0.0, step=1.0, key="py_min")
        pyeong_max = st.number_input("최대", min_value=0.0, value=200.0, step=1.0, key="py_max")

        st.markdown("---")
        st.markdown("**예산(상한)**")
        budget_eok = st.number_input("억", min_value=0, value=0, step=1, key="budget_eok")
        budget_man = st.number_input("만원", min_value=0, value=0, step=100, key="budget_man")
        budget_limit = budget_eok * 10000 + budget_man
        st.caption("예산을 0으로 두면 예산 필터를 적용하지 않습니다.")

        st.markdown("---")
        run = st.button("검색 실행", type="primary", use_container_width=True)

    return {
        "keyword": keyword,
        "limit": int(limit),
        "trad_selected": trad_selected,
        "rlet_selected": rlet_selected,
        "pyeong_min": float(pyeong_min),
        "pyeong_max": float(pyeong_max),
        "budget_limit": int(budget_limit),
        "run": run,
    }


# =========================================================
# 6) 페이지: 로비 / 탐색 / 검색
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
        st.markdown("<div class='muted'>지역을 확인하고 마음에 드는 곳을 고른 뒤, 매물 검색으로 넘어가는 흐름 테스트.</div>", unsafe_allow_html=True)
        if st.button("지역 탐색으로 이동", use_container_width=True):
            st.session_state.page = "explore"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>🔎 매물 검색</div>", unsafe_allow_html=True)
        st.markdown("<div class='muted'>필터 적용 + 목록 클릭 시 상세보기.</div>", unsafe_allow_html=True)
        if st.button("매물 검색으로 이동", use_container_width=True):
            st.session_state.page = "search"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_explore():
    top = st.columns([1, 1, 1, 1])
    with top[0]:
        if st.button("← 로비", use_container_width=True):
            st.session_state.page = "lobby"
            st.rerun()

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 🧭 지역 탐색(간단)")
    st.markdown("<div class='muted'>지도 구역/특징은 다음 단계에서 확장하고, 지금은 좌표 추출 + 선택 흐름만 테스트합니다.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    colL, colR = st.columns([0.55, 0.45], gap="large")

    with colL:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>지역 입력</div>", unsafe_allow_html=True)
        kw = st.text_input("예) 서울 종로구, 잠실동, 판교", key="explore_kw")
        if st.button("좌표 찾기", use_container_width=True):
            try:
                cortar_no, lat, lon = resolve_region(kw)
                st.session_state.region_meta = (kw, cortar_no, lat, lon)
                st.success("지역 정보를 찾았어요!")
            except Exception as e:
                st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    with colR:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>결과</div>", unsafe_allow_html=True)

        meta = st.session_state.region_meta
        if not meta:
            st.info("왼쪽에서 지역을 입력해보세요.")
        else:
            kw, cortar_no, lat, lon = meta
            st.markdown(f"<span class='badge'>지역</span> {kw}", unsafe_allow_html=True)
            st.markdown(f"<span class='badge'>cortarNo</span> {cortar_no}", unsafe_allow_html=True)
            st.markdown(f"<span class='badge'>lat/lon</span> {lat}, {lon}", unsafe_allow_html=True)

            st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))

            if st.button("이 지역으로 매물 검색 →", use_container_width=True):
                st.session_state.page = "search"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


def render_search():
    top = st.columns([1, 1, 1, 1])
    with top[0]:
        if st.button("← 로비", use_container_width=True):
            st.session_state.page = "lobby"
            st.rerun()

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 🔎 매물 검색")
    st.markdown("<div class='muted'>왼쪽 필터로 조건을 고르고, 목록에서 클릭하면 상세정보가 표시됩니다.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    ctl = sidebar_controls()

    # 검색 실행
    if ctl["run"]:
        st.session_state.selected_id = None
        try:
            cortar_no, lat, lon = resolve_region(ctl["keyword"])
            st.session_state.region_meta = (ctl["keyword"], cortar_no, lat, lon)

            prog = st.progress(0, text="매물 수집 준비...")
            def progress_cb(cur, total, msg):
                ratio = 0 if total == 0 else min(cur / total, 1.0)
                prog.progress(ratio, text=msg)

            items = scraper.scrape_articles(
                cortar_no=cortar_no,
                lat=lat,
                lon=lon,
                limit=ctl["limit"],
                progress_callback=progress_cb,
            )
            prog.empty()

            if not items:
                st.session_state.df = pd.DataFrame()
            else:
                df = build_df(items)

                # 선택값이 실제 데이터에 없으면 0건 될 수 있어서 교집합으로 보정
                real_trad = sorted({v for v in df["거래유형"].dropna().unique().tolist() if str(v).strip()})
                real_rlet = sorted({v for v in df["매물유형"].dropna().unique().tolist() if str(v).strip()})
                trad_eff = [t for t in ctl["trad_selected"] if t in real_trad] or real_trad
                rlet_eff = [r for r in ctl["rlet_selected"] if r in real_rlet] or real_rlet

                fdf = apply_filters(
                    df,
                    trad_eff,
                    rlet_eff,
                    ctl["pyeong_min"],
                    ctl["pyeong_max"],
                    ctl["budget_limit"],
                )
                st.session_state.df = fdf

        except Exception as e:
            st.error(str(e))

    df = st.session_state.df
    if df is None:
        st.info("왼쪽에서 지역을 입력하고 **검색 실행**을 눌러주세요.")
        return

    # 색상 맵(요구: 5,000만 미만=빨강 / 5,000만~5억=초록 / 5억 초과=파랑)
    color_map = {
        "5,000만 미만": "red",
        "5,000만 ~ 5억": "green",
        "5억 초과": "blue",
        "가격정보없음": "gray",
    }

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    valid_prices = df["가격(만원)"].dropna() if len(df) else pd.Series([], dtype=float)
    c1.metric("결과", f"{len(df):,}건")
    c2.metric("가격 있는 매물", f"{len(valid_prices):,}건")
    c3.metric("중앙값(만원)", f"{int(valid_prices.median()):,}" if len(valid_prices) else "-")
    c4.metric("평균(만원)", f"{int(valid_prices.mean()):,}" if len(valid_prices) else "-")
    st.markdown("</div>", unsafe_allow_html=True)

    if len(df) == 0:
        st.warning("조건에 맞는 매물이 없어요. 필터를 완화해보세요.")
        return

    left, right = st.columns([0.42, 0.58], gap="large")

    # ==========================
    # 좌측: 목록 (상단 흰바 → "목록 검색바"로 의미 있게)
    # ==========================
    with left:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>📋 목록</div>", unsafe_allow_html=True)
        st.markdown("<div class='muted'>건물명을 클릭하면 오른쪽 상세가 바뀝니다.</div>", unsafe_allow_html=True)

        # ✅ 걸리적거리던 흰색 바를 "목록 검색"으로 대체
        list_query = st.text_input(
            "목록에서 건물명 검색",
            placeholder="예) 중문, 푸르지오, 힐스테이트 ...",
            label_visibility="collapsed",
            key="list_query",
        )

        # 건물명 필터링
        list_df = df
        if list_query.strip():
            q = list_query.strip()
            list_df = df[df["단지/건물명"].astype(str).str.contains(q, case=False, na=False)].copy()

        st.markdown("<hr class='sep'/>", unsafe_allow_html=True)

        for _, r in list_df.head(50).iterrows():
            atcl_id = str(r.get("매물ID", ""))
            name = r.get("단지/건물명", "") or "(이름없음)"
            price = r.get("가격", "")
            pyeong = r.get("면적(평)", None)
            trad = r.get("거래유형", "")
            rlet = r.get("매물유형", "")
            bucket = r.get("가격구간", "가격정보없음")

            area_txt = f"{pyeong:.1f}평" if pd.notna(pyeong) else "-"
            summary = f"{price} · {area_txt} · {trad}/{rlet}"

            if st.button(name, key=f"pick_{atcl_id}", use_container_width=True):
                st.session_state.selected_id = atcl_id
                st.rerun()

            st.markdown(
                f"<div class='muted'>• {summary} | 구간: <b style='color:{color_map.get(bucket,'gray')}'>{bucket}</b></div>",
                unsafe_allow_html=True,
            )
            st.markdown("<hr class='sep'/>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # ==========================
    # 우측: 상세 (상단 흰바 제거, 추가정보 카드화)
    # ==========================
    with right:
        sel = st.session_state.selected_id
        if not sel:
            sel = str(df.iloc[0]["매물ID"])

        row = df[df["매물ID"] == sel]
        r = row.iloc[0].to_dict() if len(row) else df.iloc[0].to_dict()

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>📌 상세</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='muted'>선택된 매물ID: <b>{sel}</b></div>", unsafe_allow_html=True)

        st.markdown(f"### {r.get('단지/건물명','(이름없음)')}")

        st.markdown(
            f"""
            <span class="badge">거래 {r.get('거래유형','')}</span>
            <span class="badge">유형 {r.get('매물유형','')}</span>
            <span class="badge">구간 {r.get('가격구간','')}</span>
            """,
            unsafe_allow_html=True,
        )

        k1, k2, k3 = st.columns(3)
        k1.metric("가격", r.get("가격", ""))
        py = r.get("면적(평)", None)
        k2.metric("면적(평)", f"{py:.2f}" if pd.notna(py) else "-")
        k3.metric("층", r.get("층", ""))

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("### 추가 정보")

        info = {
            "동/호": r.get("동/호", ""),
            "방향": r.get("방향", ""),
            "중개사": r.get("중개사", ""),
            "직거래": r.get("직거래", ""),
            "확인일": r.get("확인일", ""),
        }
        kv_grid(info, cols=3)

        fetr = r.get("특징", "")
        if fetr:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown("### 특징")
            st.markdown(
                f"""
                <div style="
                    background: rgba(255,255,255,0.92);
                    border: 1px solid #F0D36A;
                    border-radius: 14px;
                    padding: 12px 12px;
                    line-height: 1.55;
                    ">
                  {str(fetr).replace("\\n", "<br/>")}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

        # 대시보드(가격 구간 분포) — 깔끔하게 아래 카드로
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>📊 가격 구간 분포</div>", unsafe_allow_html=True)

        bucket_order = ["5,000만 미만", "5,000만 ~ 5억", "5억 초과", "가격정보없음"]
        bc = df["가격구간"].value_counts().reindex(bucket_order).fillna(0).astype(int).reset_index()
        bc.columns = ["가격구간", "건수"]

        fig = px.bar(
            bc,
            x="가격구간",
            y="건수",
            color="가격구간",
            color_discrete_map=color_map,
            text="건수",
        )
        fig.update_layout(height=320, xaxis_title="", yaxis_title="매물 수", legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 7) 라우팅
# =========================================================
if st.session_state.page == "lobby":
    render_lobby()
elif st.session_state.page == "explore":
    render_explore()
else:
    render_search()