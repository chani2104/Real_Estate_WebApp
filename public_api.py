import requests
import pandas as pd
import os
import time
from dotenv import load_dotenv

load_dotenv()

PUBLIC_DATA_API_KEY = os.getenv("SERVICE_KEY")

def get_all_dongs():
    print("📡 전국 기초자치단체(시/군/구) 데이터 수집 시작...")
    all_items = []
    page = 1
    
    # 기초자치단체는 전국에 약 226~250개 사이이므로 보통 1페이지로 충분하지만,
    # 안전하게 루프를 사용합니다.
    while True:
        url = "http://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
        params = {
            "serviceKey": PUBLIC_DATA_API_KEY,
            "pageNo": page,
            "numOfRows": 1000,
            "type": "json"
        }

        try:
            res = requests.get(url, params=params, timeout=15)
            if res.status_code != 200:
                print(f"❌ API 연결 실패: {res.status_code}")
                break
                
            data = res.json()
            
            if "StanReginCd" in data and len(data["StanReginCd"]) > 1:
                items = data["StanReginCd"][1].get("row", [])
                if not items: 
                    break
                all_items.extend(items)
                page += 1
            else:
                break
        except Exception as e:
            print(f"⚠️ 수집 알림: {e}")
            break

    if not all_items:
        return pd.DataFrame()

    df = pd.DataFrame(all_items)

    # 1. 활성 지역 필터링
    if "flag" in df.columns:
        df = df[df["flag"] == "Y"].copy()
    
    df["region_cd"] = df["region_cd"].astype(str)

    # 2. 기초자치단체(시/군/구) 추출 로직
    # 법정동 코드 체계상:
    # - 앞 2자리만 있고 나머지가 0이면 '광역자치단체'(시/도)
    # - 앞 5자리까지 있고 나머지가 0이면 '기초자치단체'(시/군/구)
    
    # 광역자치단체(끝 8자리가 00000000)를 제외하고,
    # 기초자치단체(끝 5자리가 00000)인 데이터만 필터링합니다.
    
    df_basic = df[
        (df["region_cd"].str.endswith("00000")) & 
        (~df["region_cd"].str.endswith("00000000"))
    ].copy()

    # 3. 데이터 정리
    df_basic = df_basic.rename(columns={
        "region_cd": "dong_code",
        "locatadd_nm": "region_name"
    })

    print(f"✅ 필터링 완료: 전국 총 {len(df_basic)}개 기초자치단체(시/군/구) 수집됨")
    return df_basic[["dong_code", "region_name"]]