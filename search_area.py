import os
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import time

# 1. 환경 변수 설정 로드
load_dotenv()

DATA_API_KEY = os.getenv("DATA_API_KEY")
API_ENDPOINT_ROOM = os.getenv("API_ENDPOINT_room")
API_ENDPOINT_OFFI = os.getenv("API_ENDPOINT_offi")

# 2. 지역 코드 파일 읽기
try:
    df_code = pd.read_csv('region_code.txt', sep='\t', names=['법정동코드', '법정동명', '상태'], encoding='utf-8', engine='python', header=None)
except:
    df_code = pd.read_csv('region_code.txt', sep='\t', names=['법정동코드', '법정동명', '상태'], encoding='cp949', engine='python', header=None)

# '존재'하는 지역의 5자리 시군구 코드 리스트 생성
sigungu_list = df_code[df_code['상태'] == '존재']['법정동코드'].astype(str).str[:5].unique().tolist()

# 3. 데이터 수집 설정
all_data = []
target_month = "202401" # 원하는 수집 월
endpoints = {'단독다가구': API_ENDPOINT_ROOM, '오피스텔': API_ENDPOINT_OFFI}

print(f"🚀 [전국 수집 시작] 총 {len(sigungu_list)}개 지역 수집을 시작합니다. (대상: {target_month})")
print("⚠️ 지역이 많아 약 10분 정도 소요될 수 있습니다. 잠시만 기다려주세요.")

# 4. 전국 루프 실행
try:
    for i, code in enumerate(sigungu_list):
        # 10개 지역마다 진행 상황 보고
        if (i + 1) % 10 == 0 or (i + 1) == len(sigungu_list):
            print(f"🔄 진행 중: [{i+1}/{len(sigungu_list)}] 지역 수집 완료...")

        for category, url in endpoints.items():
            if not url: continue
            
            params = {
                'serviceKey': requests.utils.unquote(DATA_API_KEY),
                'LAWD_CD': code,
                'DEAL_YMD': target_month
            }
            
            try:
                # 주소 끝 공백 제거 후 요청
                response = requests.get(url.strip(), params=params, timeout=15)
                
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    items = root.findall('.//item')
                    for item in items:
                        item_dict = {child.tag: child.text.strip() if child.text else "" for child in item}
                        
                        # 전처리를 위해 쉼표(,) 제거 (보증금, 월세 등 숫자 데이터)
                        for key in ['보증금', '월세']:
                            if key in item_dict:
                                item_dict[key] = item_dict[key].replace(',', '')
                                
                        item_dict['매물유형'] = category
                        all_data.append(item_dict)
            except Exception as e:
                print(f"\n❌ {code} 지역 {category} 수집 중 오류 발생: {e}")
                continue
                
        # API 차단 방지용 미세 대기
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n\n🛑 사용자에 의해 중단되었습니다. 현재까지 수집된 데이터를 저장합니다...")

# 5. 최종 결과 저장
if all_data:
    output_filename = f"national_rent_data_{target_month}.csv"
    final_df = pd.DataFrame(all_data)
    
    # 엑셀 깨짐 방지를 위해 utf-8-sig로 저장
    final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print("\n" + "="*50)
    print(f"✨ 수집 완료!")
    print(f"📊 총 수집 데이터 건수: {len(final_df)}건")
    print(f"📁 파일 저장 완료: {output_filename}")
    print("="*50)
    
    # 상위 5개 미리보기
    print("\n[수집 데이터 샘플]")
    print(final_df.head())
else:
    print("\n❌ 수집된 데이터가 없습니다.")