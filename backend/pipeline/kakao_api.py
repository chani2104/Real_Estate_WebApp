import requests
import time
import threading
import os
from dotenv import load_dotenv

load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
lock = threading.Lock()
MIN_INTERVAL = 0.2 # 카카오 API 가이드에 맞춘 간격 조절
last_call_time = 0

def rate_limited():
    global last_call_time
    with lock:
        now = time.time()
        elapsed = now - last_call_time
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        last_call_time = time.time()

def get_kakao_count(query, region):
    if not KAKAO_REST_API_KEY:
        return 0
        
    rate_limited()
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": f"{region} {query}", "size": 1} # 개수만 파악하므로 size는 최소화

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            # meta의 total_count를 쓰면 정확한 전체 개수를 알 수 있음
            return res.json().get("meta", {}).get("total_count", 0)
        else:
            return 0
    except:
        return 0