"""
folium + streamlit-folium 기반 지도 시각화 모듈
- 검색한 지역(위도/경도)을 중심으로 인터랙티브 지도를 렌더링한다.
- 추후 매물 마커/클러스터 추가를 위해 listings_df 인자를 옵션으로 남겨둔다.
"""

from typing import Any, Dict, Optional
import streamlit as st

# 런타임 환경에 따라 라이브러리가 없을 경우를 대비한 예외 처리 (방어적 프로그래밍)
try:
    import folium
    # Figure는 스트림릿 렌더링 시 불필요하므로 제거했습니다.
except ImportError:  
    folium = None  

try:
    from streamlit_folium import st_folium
except ImportError:  
    st_folium = None  

from poi_schools import fetch_nearby_schools_osm

DEFAULT_ZOOM = 10

def _can_render_map() -> bool:
    """folium 및 streamlit-folium 패키지 설치 여부를 확인하는 함수입니다."""
    if folium is None:
        st.warning("folium 패키지가 설치되어 있지 않아 지도를 표시할 수 없습니다. `pip install folium` 후 다시 실행해주세요.")
        return False
    if st_folium is None:
        st.warning("streamlit-folium 패키지가 설치되어 있지 않아 지도를 표시할 수 없습니다. `pip install streamlit-folium` 후 다시 실행해주세요.")
        return False
    return True

def create_region_map(
    lat: float,
    lon: float,
    zoom: int = DEFAULT_ZOOM,
    *,
    width: int = 800,
    height: int = 500,
    listings_df: Optional[Any] = None,
    school_overlay: Optional[Dict[str, object]] = None,
) -> "folium.Map":
    """
    주어진 위도/경도를 중심으로 folium 지도 객체를 생성합니다.
    데이터프레임(listings_df)이 주어지면 마커도 함께 표시합니다.
    """
    assert folium is not None

    # 기본 타일 중복을 막기 위해 tiles=None 옵션을 추가했습니다.
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        control_scale=True,
        tiles=None 
    )

    # 3가지 종류의 지도 타일(배경)을 추가하여 사용자가 레이어 컨트롤에서 선택할 수 있게 합니다.
    # 1. 기본 지도 (show=False를 적지 않아 기본으로 표시됨)
    folium.TileLayer("OpenStreetMap", name="기본 지도", control=True).add_to(m)

    # 2. 구글 위성 지도 추가 (옵션)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="위성 지도",
        control=True,
        show=False  # 처음에 숨김
    ).add_to(m)

    # 3. 밝은 배경
    folium.TileLayer(
        tiles="CartoDB positron",
        name="밝은 배경",
        control=True,
        show=False  # 처음에 숨김
    ).add_to(m)

    # 4. 어두운 배경
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="어두운 배경",
        control=True,
        show=False  # 처음에 숨김
    ).add_to(m)

    # 데이터프레임이 전달되었고, 순회 가능한 형태인지 확인합니다.
    if listings_df is not None and hasattr(listings_df, "iterrows"):
        cols = getattr(listings_df, "columns", [])
        
        # '위도'와 '경도' 컬럼이 모두 존재하는지 확인합니다.
        if "위도" in cols and "경도" in cols:
            # 브라우저 성능 저하를 막기 위해 렌더링할 최대 마커 개수를 200개로 제한합니다.
            max_markers = 200 
            try:
                # 결측치가 있는 행을 제거하고 상위 200개만 추출합니다.
                sub = listings_df.dropna(subset=["위도", "경도"]).head(max_markers)
            except Exception:
                sub = None
                
            if sub is not None:
                # 추출된 데이터를 한 줄씩 순회하며 지도에 마커를 추가합니다.
                for _, row in sub.iterrows():
                    try:
                        # 위도/경도를 실수형(float)으로 변환합니다. 에러 발생 시 해당 마커는 건너뜁니다.
                        r_lat = float(row["위도"])
                        r_lon = float(row["경도"])
                    except Exception:
                        continue
                        
                    # 툴팁(마우스 오버 시)과 팝업(클릭 시)에 표시할 텍스트를 구성합니다.
                    name = str(row.get("단지/건물명", "") or "")
                    price = str(row.get("가격", "") or "")
                    tooltip = name if name else None
                    popup_html = f"{name}<br>{price}" if name or price else None
                    
                    # 원형 마커(CircleMarker)를 생성하여 지도 객체(m)에 추가합니다.
                    folium.CircleMarker(
                        location=[r_lat, r_lon],
                        radius=5,
                        color="#2b8cbe",
                        fill=True,
                        fill_color="#2b8cbe",
                        fill_opacity=0.8,
                        tooltip=tooltip,
                        popup=popup_html,
                    ).add_to(m)

    # 주변 학교 오버레이(선택 기능)
    if school_overlay and school_overlay.get("enabled"):
        try:
            radius_m = int(school_overlay.get("radius_m", 2000))
            levels = school_overlay.get("levels") or ["초", "중", "고"]
            limit = int(school_overlay.get("limit", 200))
            if not isinstance(levels, list):
                levels = ["초", "중", "고"]

            schools = fetch_nearby_schools_osm(lat, lon, radius_m, limit=limit)

            # 색상 매핑: 초/중/고/기타
            color_map = {"초": "#2ca25f", "중": "#ff7f00", "고": "#de2d26", "기타": "#6a51a3"}

            shown = 0
            for s in schools:
                level = str(s.get("level", "기타"))
                if level not in levels:
                    continue
                try:
                    s_lat = float(s["lat"])
                    s_lon = float(s["lon"])
                except Exception:
                    continue
                name = str(s.get("name", "") or "")
                color = color_map.get(level, "#6a51a3")

                folium.CircleMarker(
                    location=[s_lat, s_lon],
                    radius=6,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.9,
                    tooltip=f"[{level}] {name}" if name else f"[{level}] 학교",
                ).add_to(m)
                shown += 1

            # 간단 안내(지도 위 캡션은 app.py에서 보여주고, 여기서는 지도만)
            _ = shown
        except Exception:
            # 학교 조회 실패 시에도 지도/매물은 정상 표시되어야 함
            pass

    # 우측 상단에 타일(배경)을 변경할 수 있는 레이어 컨트롤(LayerControl)을 추가합니다.
    folium.LayerControl(collapsed=False).add_to(m)

    return m

def render_region_map(
    region_info: Dict[str, Any],
    *,
    title: Optional[str] = "🗺️ 검색 지역 지도",
    height: int = 500,
    listings_df: Optional[Any] = None,
    school_overlay: Optional[Dict[str, object]] = None,
) -> None:
    """
    Streamlit 화면에 완성된 지도를 렌더링하는 래퍼(Wrapper) 함수입니다.
    """
    # 라이브러리가 제대로 설치되어 있는지 먼저 점검합니다.
    if not _can_render_map():
        return

    # region_info 딕셔너리에서 중심 좌표, 줌 레벨, 키워드를 안전하게 가져옵니다.
    lat = region_info.get("lat")
    lon = region_info.get("lon")
    zoom = int(region_info.get("zoom", DEFAULT_ZOOM))
    keyword = region_info.get("keyword") or ""

    # 위도나 경도 값이 없으면 안내 메시지만 띄우고 렌더링을 중단합니다.
    if lat is None or lon is None:
        st.info("지도를 표시할 좌표 정보가 없습니다. 왼쪽에서 지역을 검색한 뒤 다시 시도해주세요.")
        return

    # Streamlit UI 상단에 제목과 캡션(안내 문구)을 출력합니다.
    if title:
        st.subheader(title)

    if keyword:
        st.caption(f"현재 검색 지역: **{keyword}** 기준 지도입니다.")
    else:
        st.caption("검색한 지역 전역을 한눈에 볼 수 있는 지도입니다.")

    # 위에서 정의한 create_region_map 함수를 호출하여 folium 지도 객체를 생성합니다.
    m = create_region_map(
        lat,
        lon,
        zoom=zoom,
        height=height,
        listings_df=listings_df,
        school_overlay=school_overlay,
    )

    # st_folium을 사용하여 완성된 folium 객체를 스트림릿 화면에 출력합니다. 
    # use_container_width=True 옵션으로 브라우저 너비에 맞게 지도를 꽉 채웁니다.
    st_folium(m, use_container_width=True, height=height)