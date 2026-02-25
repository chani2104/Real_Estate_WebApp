from __future__ import annotations

from typing import Dict, List, Optional

import requests
import streamlit as st


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _classify_school_level(name: str) -> str:
    n = (name or "").strip()
    if "초등학교" in n:
        return "초"
    if "중학교" in n:
        return "중"
    if "고등학교" in n:
        return "고"
    return "기타"


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_nearby_schools_osm(
    lat: float,
    lon: float,
    radius_m: int = 2000,
    *,
    limit: int = 200,
) -> List[Dict[str, object]]:
    """
    OpenStreetMap Overpass API로 주변 학교(amenity=school) 좌표를 가져온다.
    - 초/중/고 분류는 OSM 태그가 일관되지 않아, 우선 '학교명' 문자열에 포함된
      '초등학교/중학교/고등학교'로 휴리스틱 분류한다.
    반환 예시:
      [{ "name": "...", "lat": 37..., "lon": 126..., "level": "초" }, ...]
    """
    radius_m = int(max(100, min(radius_m, 20000)))
    limit = int(max(1, min(limit, 1000)))

    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="school"](around:{radius_m},{lat},{lon});
      way["amenity"="school"](around:{radius_m},{lat},{lon});
      relation["amenity"="school"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """

    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    out: List[Dict[str, object]] = []
    elements = data.get("elements", []) if isinstance(data, dict) else []

    for el in elements:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags", {}) if isinstance(el.get("tags"), dict) else {}
        name = tags.get("name") or tags.get("name:ko") or ""
        name = str(name).strip()
        if not name:
            continue

        el_lat: Optional[float] = None
        el_lon: Optional[float] = None

        if "lat" in el and "lon" in el:
            try:
                el_lat = float(el["lat"])
                el_lon = float(el["lon"])
            except Exception:
                el_lat = None
                el_lon = None
        elif isinstance(el.get("center"), dict):
            c = el["center"]
            try:
                el_lat = float(c.get("lat"))
                el_lon = float(c.get("lon"))
            except Exception:
                el_lat = None
                el_lon = None

        if el_lat is None or el_lon is None:
            continue

        level = _classify_school_level(name)
        out.append({"name": name, "lat": el_lat, "lon": el_lon, "level": level})

        if len(out) >= limit:
            break

    return out

