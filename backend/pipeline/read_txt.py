import pandas as pd
import os

def process_region_codes(input_path='region_code.txt', output_dir='../../data'):
    # 경로 보정
    base_dir = os.path.dirname(__file__)
    input_file = os.path.abspath(os.path.join(base_dir, input_path))
    
    if not os.path.exists(input_file):
        print(f"❌ {input_file} 파일이 없습니다.")
        return

    # 법정동코드 데이터 읽기
    try:
        df_code = pd.read_csv(input_file, sep='	', encoding='cp949') 
    except:
        df_code = pd.read_csv(input_file, sep='	', encoding='utf-8')

    # 앞 5자리(시군구 코드) 추출
    df_code['region_5digit'] = df_code['법정동코드'].astype(str).str[:5]
    
    output_path = os.path.abspath(os.path.join(base_dir, output_dir, 'processed_region_codes.csv'))
    df_code.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 지역 코드 전처리 완료: {output_path}")

if __name__ == "__main__":
    process_region_codes()
