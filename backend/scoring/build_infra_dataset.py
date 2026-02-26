import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import sys
import os
import tqdm 

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pipeline.public_api import get_all_dongs
from scoring import calculate_score

def process_region(row):
    try:
        region_name = row["region_name"]
        score_data = calculate_score(region_name)
        return {
            "dong_code": row["dong_code"],
            "region_name": region_name,
            **score_data
        }
    except Exception as e:
        print(f"Error processing {row.get('region_name')}: {e}")
        return None

def main():
    df_regions = get_all_dongs()
    
    if df_regions.empty:
        print("❌ 불러온 지역 데이터가 없습니다. 프로그램을 종료합니다.")
        return

    print(f"🚀 총 {len(df_regions)}개 지역 분석 시작...")

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        list_records = df_regions.to_dict("records")
        for result in tqdm.tqdm(executor.map(process_region, list_records), total=len(list_records)):
            if result:
                results.append(result)

    final_df = pd.DataFrame(results)
    # 데이터 경로를 중앙 data 폴더로 설정
    output_path = os.path.join(os.path.dirname(__file__), '../../data/전국_기초자치_인프라_점수.csv')
    final_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"✅ 분석 완료! 저장된 행 개수: {len(final_df)}")

if __name__ == "__main__":
    main()
