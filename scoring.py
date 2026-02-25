from kakao_api import get_kakao_count

def calculate_score(region_name):
    # 각 카테고리별 검색 결과 개수 조회
    school = get_kakao_count("초등학교", region_name)
    subway = get_kakao_count("지하철역", region_name)
    hospital = get_kakao_count("병원", region_name)
    cafe = get_kakao_count("카페", region_name)

    # 가중치 적용 합산
    total_score = (school * 2) + (subway * 3) + (hospital * 2) + (cafe * 1)

    return {
        "school": school,
        "subway": subway,
        "hospital": hospital,
        "cafe": cafe,
        "total_score": total_score
    }