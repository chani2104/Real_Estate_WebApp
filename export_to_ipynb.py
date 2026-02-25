"""
콘솔에서 실행해 네이버 부동산 매물을 Jupyter Notebook(.ipynb)으로 저장하는 스크립트
"""

import sys
from pathlib import Path

# 패키지 루트 추가 (main.py와 동일 패턴)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from Real_Estate_WebApp.scraper import scrape_all_articles
from Real_Estate_WebApp.utils import (
    REGION_CONFIG,
    default_filename,
    save_items_to_ipynb,
)


def main():
    print("=== 네이버 부동산 매물 수집 → ipynb 저장 ===")

    # 등록된 지역 목록 간단 표시
    print("\n등록된 지역 예시:")
    for i, (cortar_no, (_, _, name)) in enumerate(REGION_CONFIG.items()):
        print(f"  - {name} ({cortar_no})")
        if i >= 9:
            print("  ...")
            break

    cortar_no = input(
        "\n법정동 코드(예: 5119000000)를 입력하세요 (위 목록 중 하나): "
    ).strip()

    if cortar_no not in REGION_CONFIG:
        print("⚠ REGION_CONFIG에 등록되지 않은 코드입니다. region_config.json을 확인하세요.")
        return

    lat, lon, region_name = REGION_CONFIG[cortar_no]

    print(f"\n[{region_name}] 매물 수집을 시작합니다...")
    items = scrape_all_articles(cortar_no, lat, lon)

    if not items:
        print("해당 지역에 매물이 없습니다. 종료합니다.")
        return

    print(f"총 {len(items)}건의 매물을 수집했습니다.")

    default_ipynb = default_filename(region_name).replace(".xlsx", ".ipynb")
    user_path = input(
        f"\n저장할 ipynb 파일명을 입력하세요 (기본값: {default_ipynb}): "
    ).strip()

    filepath = user_path or default_ipynb
    if not filepath.endswith(".ipynb"):
        filepath += ".ipynb"

    try:
        saved_path = save_items_to_ipynb(items, filepath, region_name=region_name)
    except Exception as e:
        print(f"\n❌ ipynb 저장 중 오류가 발생했습니다:\n{e}")
        return

    print(f"\n✅ 저장 완료: {saved_path}")
    print("Jupyter에서 노트북을 열면 `df` 변수에 매물 DataFrame이 준비되어 있습니다.")


if __name__ == "__main__":
    main()

