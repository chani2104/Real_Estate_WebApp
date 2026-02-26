import pandas as pd
import os

def build_rent_summary(
    rent_csv_path="../../data/national_rent_data_202401.csv",
    output_summary_path="../../data/region_rent_summary.csv"
):
    # 경로 보정
    base_dir = os.path.dirname(__file__)
    rent_csv_path = os.path.abspath(os.path.join(base_dir, rent_csv_path))
    output_summary_path = os.path.abspath(os.path.join(base_dir, output_summary_path))

    if not os.path.exists(rent_csv_path):
        print(f"❌ 파일을 찾을 수 없습니다: {rent_csv_path}")
        return

    df = pd.read_csv(rent_csv_path, encoding="utf-8-sig")

    df = df.rename(columns={
        "deposit": "보증금",
        "monthlyRent": "월세",
        "excluUseAr": "전용면적",
        "sggCd": "시군구코드",
        "sggNm": "시군구명"
    })

    numeric_cols = ["보증금", "월세", "전용면적"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["계약유형"] = df["월세"].apply(lambda x: "전세" if x == 0 else "월세")

    sido_map = {
        "11": "서울특별시", "26": "부산광역시", "27": "대구광역시", "28": "인천광역시",
        "29": "광주광역시", "30": "대전광역시", "31": "울산광역시", "36": "세종특별자치시",
        "41": "경기도", "42": "강원특별자치도", "43": "충청북도", "44": "충청남도",
        "45": "전라북도", "46": "전라남도", "47": "경상북도", "48": "경상남도", "50": "제주특별자치도"
    }

    df["시도코드"] = df["시군구코드"].astype(str).str[:2]
    df["시도명"] = df["시도코드"].map(sido_map)
    df["region_name"] = (df["시도명"] + " " + df["시군구명"]).str.strip()

    df = df.dropna(subset=numeric_cols)

    jeonse_df = df[df["계약유형"] == "전세"]
    monthly_df = df[df["계약유형"] == "월세"]

    jeonse_summary = jeonse_df.groupby("region_name", as_index=False).agg(
        전세_평균보증금=("보증금", "mean"),
        전세_평균면적=("전용면적", "mean"),
        전세_거래건수=("보증금", "count")
    )

    monthly_summary = monthly_df.groupby("region_name", as_index=False).agg(
        월세_평균보증금=("보증금", "mean"),
        월세_평균월세=("월세", "mean"),
        월세_평균면적=("전용면적", "mean"),
        월세_거래건수=("보증금", "count")
    )

    rent_summary = pd.merge(
        jeonse_summary,
        monthly_summary,
        on="region_name",
        how="outer"
    ).fillna(0)

    rent_summary["전체_거래건수"] = (
        rent_summary["전세_거래건수"] + rent_summary["월세_거래건수"]
    )

    rent_summary.to_csv(output_summary_path, index=False, encoding="utf-8-sig")
    print("✅ 임대 요약 완료")
    return rent_summary


def merge_infra_and_rent(
    infra_csv_path="../../data/전국_기초자치_인프라_점수.csv",
    rent_summary_path="../../data/region_rent_summary.csv",
    output_path="../../data/region_rent_infra_final.csv"
):
    base_dir = os.path.dirname(__file__)
    infra_csv_path = os.path.abspath(os.path.join(base_dir, infra_csv_path))
    rent_summary_path = os.path.abspath(os.path.join(base_dir, rent_summary_path))
    output_path = os.path.abspath(os.path.join(base_dir, output_path))

    if not os.path.exists(infra_csv_path) or not os.path.exists(rent_summary_path):
        print("❌ 필수 데이터 파일이 없습니다.")
        return

    infra_df = pd.read_csv(infra_csv_path, encoding="utf-8-sig")
    rent_df = pd.read_csv(rent_summary_path, encoding="utf-8-sig")

    merged_df = pd.merge(
        infra_df,
        rent_df,
        on="region_name",
        how="left"
    ).fillna(0)

    merged_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print("✅ 최종 통합 완료")
    return merged_df


def run_region_pipeline():
    build_rent_summary()
    merge_infra_and_rent()


if __name__ == "__main__":
    run_region_pipeline()
