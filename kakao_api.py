import requests
import time
import threading
import os
from dotenv import load_dotenv

load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
lock = threading.Lock()
MIN_INTERVAL = 0.2 
last_call_time = 0

def rate_limited():
    global last_call_time
    with lock:
        now = time.time()
        elapsed = now - last_call_time
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        last_call_time = time.time()

def get_coords_by_address(region_name):
    """지역명을 입력받아 카카오 API로 위도, 경도를 반환합니다."""
    if not KAKAO_REST_API_KEY: return None, None
    
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": region_name}
    
    try:
        rate_limited()
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            documents = res.json().get("documents")
            if documents:
                return documents[0]["y"], documents[0]["x"] # lat, lng 반환
        return None, None
    except:
        return None, None

def get_kakao_count(category_code, lat, lng):
    if not KAKAO_REST_API_KEY:
        return 0
        
    rate_limited()
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    
    params = {
        "category_group_code": category_code,
        "x": lng,          
        "y": lat,          
        "radius": 2000,    # 반경 2km 제한
        "size": 1          
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("meta", {}).get("total_count", 0)
        return 0
    except:
        return 0