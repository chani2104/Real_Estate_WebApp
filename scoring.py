from kakao_api import get_kakao_count

def calculate_score(region_name, lat, lng):
    # 8가지 카테고리 코드로 인프라 개수 조회
    school      = get_kakao_count("SC4", lat, lng)  # 학교
    subway      = get_kakao_count("SW8", lat, lng)  # 지하철역
    hospital    = get_kakao_count("HP8", lat, lng)  # 병원
    cafe        = get_kakao_count("CE7", lat, lng)  # 카페
    academy     = get_kakao_count("AC5", lat, lng)  # 학원
    department  = get_kakao_count("MT1", lat, lng)  # 대형마트(백화점 대용)
    convenience = get_kakao_count("CS2", lat, lng)  # 편의점
    culture     = get_kakao_count("CT1", lat, lng)  # 문화시설 (공원 대용)

    total_score = (school + subway + hospital + cafe + academy + department + convenience + culture)

    return {
        "school": school, "subway": subway, "hospital": hospital,
        "cafe": cafe, "academy": academy, "department": department,
        "convenience": convenience, "culture": culture,
        "total_score": total_score
    }