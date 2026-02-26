import sys
import os
# 상대 경로 임포트를 위해 부모 디렉토리를 path에 추가하거나 absolute import 사용
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pipeline.kakao_api import get_kakao_count

def calculate_score(region_name):
    school = get_kakao_count("초등학교", region_name)
    subway = get_kakao_count("지하철역", region_name)
    hospital = get_kakao_count("병원", region_name)
    cafe = get_kakao_count("카페", region_name)
    academy = get_kakao_count("학원", region_name)
    department = get_kakao_count("백화점", region_name)
    convenience = get_kakao_count("편의점", region_name)
    park = get_kakao_count("공원", region_name)

    total_score = (
        (school * 1) +
        (subway * 1) +
        (hospital * 1) +
        (academy * 1) +
        (department * 1) +
        (cafe * 1) +
        (convenience * 1) +
        (park * 1)
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
