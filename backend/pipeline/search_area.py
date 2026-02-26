import os
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import time

load_dotenv()

DATA_API_KEY = os.getenv("DATA_API_KEY")
API_ENDPOINT_ROOM = os.getenv("API_ENDPOINT_room")
API_ENDPOINT_OFFI = os.getenv("API_ENDPOINT_offi")

def fetch_rent_data(target_month="202401"):
    base_dir = os.path.dirname(__file__)
    code_file = os.path.abspath(os.path.join(base_dir, "../../region_code.txt"))
    
    try:
        df_code = pd.read_csv(code_file, sep='	', names=['법정동코드', '법정동명', '상태'], encoding='cp949', engine='python', header=None)
    except:
        df_code = pd.read_csv(code_file, sep='	', names=['법정동코드', '법정동명', '상태'], encoding='utf-8', engine='python', header=None)

    sigungu_list = df_code[df_code['상태'] == '존재']['법정동코드'].astype(str).str[:5].unique().tolist()

    all_data = []
    endpoints = {'단독다가구': API_ENDPOINT_ROOM, '오피스텔': API_ENDPOINT_OFFI}

    print(f"🚀 [데이터 수집] {len(sigungu_list)}개 지역 수집 시작 (대상: {target_month})")

    for i, code in enumerate(sigungu_list):
        if (i + 1) % 50 == 0: print(f"🔄 진행 중: [{i+1}/{len(sigungu_list)}]")

        for category, url in endpoints.items():
            if not url: continue
            params = {'serviceKey': requests.utils.unquote(DATA_API_KEY), 'LAWD_CD': code, 'DEAL_YMD': target_month}
            try:
                response = requests.get(url.strip(), params=params, timeout=15)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    for item in root.findall('.//item'):
                        item_dict = {child.tag: child.text.strip() if child.text else "" for child in item}
                        for key in ['보증금', '월세']:
                            if key in item_dict: item_dict[key] = item_dict[key].replace(',', '')
                        item_dict['매물유형'] = category
                        all_data.append(item_dict)
            except: continue
        time.sleep(0.05)

    if all_data:
        final_df = pd.DataFrame(all_data)
        output_path = os.path.abspath(os.path.join(base_dir, f"../../data/national_rent_data_{target_month}.csv"))
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✨ 수집 완료 및 저장: {output_path}")

if __name__ == "__main__":
    fetch_rent_data()
