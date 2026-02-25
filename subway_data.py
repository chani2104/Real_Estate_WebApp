# subway_data.py
import csv
import os

def load_subway_data():
    """
    station_code.csv 파일을 읽어 호선별 역 좌표 데이터를 딕셔너리로 반환합니다.
    구조: { "1호선": { "서울": (37.55, 126.97), ... }, "2호선": { ... } }
    """
    subway_lines = {}
    # 현재 파일 위치 기준으로 csv 경로 설정
    csv_path = os.path.join(os.path.dirname(__file__), 'station_code.csv')
    
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} 파일을 찾을 수 없습니다.")
        return {}

    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            # 첫 번째 줄(헤더)을 건너뛰거나 DictReader를 사용하여 컬럼명으로 접근
            reader = csv.DictReader(f)
            for row in reader:
                line_id = row['호선']
                # 숫자로만 되어 있으면 '호선'을 붙여줌 (예: 1 -> 1호선)
                line_name = f"{line_id}호선" if line_id.isdigit() else line_id
                
                station_name = row['역명']
                try:
                    lat = float(row['위도'])
                    lon = float(row['경도'])
                except (ValueError, TypeError):
                    continue

                if line_name not in subway_lines:
                    subway_lines[line_name] = {}
                
                # 동일 노선 내 중복 역명은 마지막 데이터로 덮어씌워짐
                subway_lines[line_name][station_name] = (lat, lon)
                
    except Exception as e:
        print(f"Error loading subway data: {e}")
        return {}
            
    # 노선 이름을 기준으로 정렬하여 반환 (1호선, 2호선... 순서)
    sorted_lines = dict(sorted(subway_lines.items(), key=lambda x: x[0]))
    return sorted_lines

# 앱 실행 시점에 데이터를 한 번 로드하여 캐싱
SUBWAY_LINES = load_subway_data()
