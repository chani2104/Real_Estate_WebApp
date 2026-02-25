import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from public_api import get_all_dongs
from scoring import calculate_score
import tqdm # 진행 상황 확인용 (pip install tqdm 필요)

def process_region(row):
    try:
        region_name = row["region_name"]
        score_data = calculate_score(region_name)
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
    
    if df_regions.empty:
        print("❌ 불러온 지역 데이터가 없습니다. 프로그램을 종료합니다.")
        return

    print(f"🚀 총 {len(df_regions)}개 지역 분석 시작...")

    results = []
    # ThreadPoolExecutor를 사용하여 병렬 처리 속도 향상
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 진행 바 표시 (선택 사항)
        list_records = df_regions.to_dict("records")
        for result in tqdm.tqdm(executor.map(process_region, list_records), total=len(list_records)):
            if result:
                results.append(result)

    final_df = pd.DataFrame(results)
    final_df.to_csv("전국_기초자치_인프라_점수.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 분석 완료! 저장된 행 개수: {len(final_df)}")

if __name__ == "__main__":
    main()