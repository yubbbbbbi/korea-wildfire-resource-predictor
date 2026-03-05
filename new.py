from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from utils import get_elevation_google

load_dotenv(dotenv_path=".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__)
CORS(app)

KAKAO_REST_API_KEY = "a9d8df87e3d54c86fad734a2532b0ff5"

@app.route('/')
def index():
    return send_file('weather.html')

def address_to_coord(address):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
    }
    params = {"query": address}
    res = requests.get(url, headers=headers, params=params)
    data = res.json()
    if 'documents' not in data or not data['documents']:
        raise ValueError("주소 변환 실패")
    lat = float(data['documents'][0]['y'])
    lon = float(data['documents'][0]['x'])
    return lat, lon

def dfs_xy_conv(lat, lon):
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136
    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn * math.cos(slat1)) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    x = int(ra * math.sin(theta) + XO + 0.5)
    y = int(ro - ra * math.cos(theta) + YO + 0.5)
    return x, y

def fetch_weather_data(lat, lon):
    service_key = "QR5BO3GIlFO4ITNfN%2F%2FLGttv5WnX7l9P%2FLQWPGtmLrAnbQP%2BSblhL9QOVGB1pcsamPoJQ9EmHeYTEVDNX87OFg%3D%3D"
    now = datetime.now()
    base_time = (now - timedelta(hours=1)).strftime('%H00')
    base_date = now.strftime('%Y%m%d')
    x, y = dfs_xy_conv(lat, lon)
    url = (
        f"http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
        f"?serviceKey={service_key}&numOfRows=1000&pageNo=1&"
        f"dataType=JSON&base_date={base_date}&base_time={base_time}&nx={x}&ny={y}"
    )
    res = requests.get(url)
    data = res.json()
    if 'response' not in data:
        raise ValueError("기상청 응답 오류")
    items = data['response']['body']['items']['item']
    result = {"온도": None, "습도": None, "시간당풍속": None, "풍향": None, "반대풍향": None}
    for item in items:
        cat = item['category']
        val = item['fcstValue']
        if cat == 'T1H': result["온도"] = float(val)
        elif cat == 'REH': result["습도"] = int(val)
        elif cat == 'WSD': result["시간당풍속"] = float(val)
        elif cat == 'VEC':
            풍향 = int(val)
            반대풍향 = (풍향 + 180) % 360
            result["풍향"] = 풍향
            result["반대풍향"] = 반대풍향
    return result

@app.route('/weather', methods=['POST'])
def weather():
    data = request.json
    address = data.get("address")
    if not address:
        return jsonify({"error": "주소를 입력해주세요"}), 400
    try:
        lat, lon = address_to_coord(address)
        elevation = get_elevation_google(lat, lon, GOOGLE_API_KEY)
        if elevation is not None:
            elevation = round(elevation, 2)
        weather_info = fetch_weather_data(lat, lon)
        print("[DEBUG] 날씨 정보:", weather_info)

        def search_place(keyword):
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            params = {
                "query": keyword,
                "x": lon,
                "y": lat,
                "radius": 10000,
                "sort": "distance"
            }
            r = requests.get(url, headers=headers, params=params)
            docs = r.json().get("documents", [])
            if docs:
                name = docs[0]['place_name']
                distance_km = round(float(docs[0]['distance']) / 1000, 2)
                return name, distance_km
            return "없음", None

        fire_name, fire_dist = search_place("소방서")
        center_name, center_dist = search_place("119안전센터")

        response = {
                "lat": lat,  # 추가!
                "lon": lon,
                "소방서": fire_name,
                "소방서거리_km": fire_dist,
                "안전센터": center_name,
                "안전센터거리_km": center_dist,
                "고도": elevation,
                "날씨": {
                    "풍속": weather_info["시간당풍속"],
                    "온도": weather_info["온도"],
                    "습도": weather_info["습도"],
                    "풍향": weather_info["풍향"],
                    "반대풍향": weather_info["반대풍향"],
                }
            }

        return jsonify(response)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)