import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from public_api import get_all_dongs
from scoring import calculate_score
from kakao_api import get_coords_by_address # 추가
import tqdm 

def process_region(row):
    try:
        region_name = row["region_name"]
        
        # 1. 지역명으로 좌표 추출
        lat, lng = get_coords_by_address(region_name)
        
        if lat is None or lng is None:
            return None

        # 2. 좌표를 포함하여 점수 계산
        score_data = calculate_score(region_name, lat, lng)
        
        return {
            "sigungu_code": row["sigungu_code"],
            "region_name": region_name,
            **score_data
        }
    except Exception as e:
        print(f"Error processing {row.get('region_name')}: {e}")
        return None

def main():
    df_regions = get_all_dongs()
    if df_regions.empty: return

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        list_records = df_regions.to_dict("records")
        for result in tqdm.tqdm(executor.map(process_region, list_records), total=len(list_records)):
            if result:
                results.append(result)

    final_df = pd.DataFrame(results)
    final_df.to_csv("전국_기초자치_인프라_점수.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 분석 완료! 저장된 행 개수: {len(final_df)}")

if __name__ == "__main__":
    main()