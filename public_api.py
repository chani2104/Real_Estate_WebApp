import requests
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

# 발급받은 'Decoding' 키를 사용하거나, requests가 자동 인코딩하도록 처리해야 합니다.
PUBLIC_DATA_API_KEY = os.getenv("SERVICE_KEY")

def get_all_dongs():
    print("📡 전국 법정동 목록 조회 중...")
    
    # 행정안전부_지역주소코드 조회 서비스 엔드포인트 확인 필요
    url = "http://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"

    params = {
        "serviceKey": PUBLIC_DATA_API_KEY,
        "pageNo": 1,
        "numOfRows": 1000, # 한 번에 가져올 양 조절
        "type": "json"
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        
        # 500 에러 발생 시 본문 내용을 확인하기 위한 디버깅
        if res.status_code != 200:
            print(f"❌ API 오류 발생 (Status: {res.status_code})")
            print(f"응답 내용: {res.text}")
            return pd.DataFrame()

        data = res.json()
        
        # 응답 구조에 따른 데이터 추출 (API마다 계층 구조가 다를 수 있음)
        if "StanReginCd" in data:
            items = data["StanReginCd"][1]["row"]
        else:
            print("❌ 예상치 못한 JSON 구조:", data)
            return pd.DataFrame()

        df = pd.DataFrame(items)
        
        # 법정동 코드 필터링 및 정리
        df["region_cd"] = df["region_cd"].astype(str)
        # 하위 행정동/법정동만 추출 (시/군/구 제외 - 끝자리가 00000이 아닌 경우 등)
        df = df[~df["region_cd"].str.endswith("0000")] 

        df = df.rename(columns={
            "region_cd": "dong_code",
            "locatadd_nm": "region_name"
        })

        return df[["dong_code", "region_name"]]

    except Exception as e:
        print(f"❌ 네트워크 또는 파싱 오류: {e}")
        return pd.DataFrame()