from kakao_api import get_kakao_count

def calculate_score(region_name):
    # 각 카테고리별 검색 결과 개수 조회 (총 8개 항목)
    school = get_kakao_count("초등학교", region_name)
    subway = get_kakao_count("지하철역", region_name)
    hospital = get_kakao_count("병원", region_name)
    cafe = get_kakao_count("카페", region_name)
    academy = get_kakao_count("학원", region_name)
    department = get_kakao_count("백화점", region_name)
    convenience = get_kakao_count("편의점", region_name)
    park = get_kakao_count("공원", region_name)

    # 가중치 설정 (사용자 편의에 따라 조정 가능)
    total_score = (
        (school * 1) +       # 교육 중요도 상향
        (subway * 1) +       # 역세권
        (hospital * 1) +     # 병세권
        (academy * 1) +      # 학세권
        (department * 1) +   # 몰세권
        (cafe * 1) +         # 편의시설
        (convenience * 1) +  # 생활밀착
        (park * 1)           # 숲세권
    )

    return {
        "school": school,
        "subway": subway,
        "hospital": hospital,
        "cafe": cafe,
        "academy": academy,
        "department": department,
        "convenience": convenience,
        "park": park,
        "total_score": total_score
    }