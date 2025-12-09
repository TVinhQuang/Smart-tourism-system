from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from typing import List
from serpapi import GoogleSearch
import re
from flask import Flask, request, jsonify
from translator import translate_text
from dataclasses import dataclass
from typing import List
import math
import folium
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)
API_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

def serpapi_geocode(q: str):
    # 1. GÁN CỨNG KEY (Để đảm bảo hàm này luôn có key đúng)
    # Bạn thay key của bạn vào đây:
    HARDCODED_KEY = API_KEY
    
    print(f"DEBUG: Đang Geocode '{q}' với SerpApi...")

    params = {
        "engine": "google_maps",
        "q": q,
        "type": "search",
        "api_key": HARDCODED_KEY, # Dùng key cứng tại đây
        "hl": "vi"
    }
    
    try:
        # Gọi API
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # 2. KIỂM TRA LỖI TỪ API
        if "error" in results:
            print(f"DEBUG: ❌ SerpApi Error: {results['error']}")
            return None
            
        # 3. XỬ LÝ KẾT QUẢ (Thử nhiều trường hợp)
        # Trường hợp 1: local_results (Kết quả địa điểm cụ thể)
        if "local_results" in results and len(results["local_results"]) > 0:
            place = results["local_results"][0]
            print(f"DEBUG: ✅ Tìm thấy (local_results): {place.get('title')}")
            return {
                "name": place.get("title"),
                "lat": place["gps_coordinates"]["latitude"],
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
            
        # Trường hợp 2: place_results (Kết quả chính xác duy nhất)
        if "place_results" in results:
            place = results["place_results"]
            print(f"DEBUG: ✅ Tìm thấy (place_results): {place.get('title')}")
            return {
                "name": place.get("title"),
                "lat": place["gps_coordinates"]["latitude"],
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
            
        # Nếu không tìm thấy gì
        print("DEBUG: ⚠️ Không tìm thấy toạ độ nào trong phản hồi của Google Maps.")
        # In thử các keys để debug xem Google trả về cái gì
        print(f"DEBUG: Keys nhận được: {list(results.keys())}") 
        return None

    except Exception as e:
        print(f"DEBUG: ❌ Lỗi ngoại lệ trong serpapi_geocode: {e}")
        return None


def osrm_route(src, dst, profile="driving"):
    """
    Tính lộ trình bằng OSRM public:
      - src, dst: dict có keys 'lat', 'lon', 'name'
      - profile: 'driving' / 'walking' / 'cycling'

    Trả về:
      {
        distance_km: float,
        duration_min: float,
        geometry: list[(lat, lon)],
        steps: list[str],
        distance_text: str,
        duration_text: str
      }
    """
    url = (
        f"https://router.project-osrm.org/route/v1/"
        f"{profile}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}"
    )
    params = {
        "overview": "full",       # lấy full đường đi
        "geometries": "geojson",  # geometry dạng GeoJSON
        "steps": "true",          # lấy chi tiết từng bước
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            print("⚠️ OSRM trả về code:", data.get("code"))
            return None

        route = data["routes"][0]

        distance_km = route["distance"] / 1000.0
        duration_min = route["duration"] / 60.0

        # ---- 1) Chuyển geometry GeoJSON -> list[(lat, lon)] cho draw_map ----
        coords = route["geometry"]["coordinates"]    # [[lon, lat], ...]
        geometry = [(lat, lon) for lon, lat in coords]

        # ---- 2) Tạo list hướng dẫn từng bước ----
        legs = route.get("legs", [])
        step_descriptions = []
        for leg in legs:
            for step in leg.get("steps", []):
                desc = describe_osrm_step(step)      # đã có sẵn phía trên
                if desc:
                    step_descriptions.append(desc)

        return {
            "distance_km": distance_km,
            "duration_min": duration_min,
            "geometry": geometry,
            "steps": step_descriptions,
            "distance_text": f"~{distance_km:.2f} km",
            "duration_text": f"~{duration_min:.1f} phút",
        }

    except Exception as e:
        print("❌ Lỗi khi gọi OSRM:", e)
        return None
    
def haversine_km(lon1, lat1, lon2, lat2):
    """
    Tính khoảng cách đường tròn lớn giữa 2 điểm (lat, lon) trên Trái đất, đơn vị km.
    Dùng công thức Haversine.
    """
    R = 6371.0  # bán kính Trái đất (km)

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c

def _format_distance(meters: float) -> str:
    """
    Chuyển khoảng cách từ mét -> chuỗi dễ đọc:
      - < 1000m: 'xxx m'
      - >= 1000m: 'x.y km'
    """
    if meters < 1000:
        return f"{int(round(meters))} m"
    km = meters / 1000.0
    return f"{km:.1f} km"

def describe_osrm_step(step: dict) -> str:
    """
    Nhận 1 step từ OSRM và trả về 1 câu mô tả ngắn gọn bằng tiếng Việt.

    Ví dụ:
      - 'Đi thẳng 500 m trên đường Nguyễn Văn Cừ.'
      - 'Rẽ phải vào đường Lê Lợi.'
      - 'Đến điểm đến ở bên phải.'
    """
    maneuver = step.get("maneuver", {})
    step_type = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    distance = step.get("distance", 0.0)  # mét
    dist_str = _format_distance(distance)

    # Mapping hướng rẽ
    dir_map = {
        "right": "rẽ phải",
        "slight right": "chếch phải",
        "sharp right": "quẹo gắt phải",
        "left": "rẽ trái",
        "slight left": "chếch trái",
        "sharp left": "quẹo gắt trái",
        "straight": "đi thẳng",
        "uturn": "quay đầu",
    }

    # ---- Các trường hợp chính ----
    if step_type == "depart":
        if name:
            return f"Bắt đầu từ {name}."
        return "Bắt đầu từ điểm xuất phát."

    if step_type == "arrive":
        side = maneuver.get("modifier", "").lower()
        if side in ("right", "left"):
            side_vi = "bên phải" if side == "right" else "bên trái"
            return f"Đến điểm đến ở {side_vi}."
        return "Đến điểm đến."

    if step_type in ("turn", "end of road", "fork"):
        action = dir_map.get(modifier, "rẽ")
        if name:
            return f"Đi {dist_str} rồi {action} vào đường {name}."
        else:
            return f"Đi {dist_str} rồi {action}."

    if step_type == "roundabout":
        exit_nr = maneuver.get("exit")
        if exit_nr:
            return f"Vào vòng xuyến, đi hết lối ra thứ {exit_nr}."
        else:
            return "Vào vòng xuyến và tiếp tục theo hướng chính."

    if step_type in ("merge", "on ramp", "off ramp"):
        if name:
            return f"Nhập làn/ra khỏi làn và tiếp tục trên {name} khoảng {dist_str}."
        return f"Nhập làn/ra khỏi làn và tiếp tục khoảng {dist_str}."

    # Fallback: mô tả chung chung
    if name:
        return f"Đi tiếp {dist_str} trên đường {name}."
    return f"Đi tiếp {dist_str}."

def draw_map(src, dst, route):
    """
    Vẽ bản đồ Folium với Polyline từ Google Maps.
    """
    # Khởi tạo map
    m = folium.Map(
        location=[src["lat"], src["lon"]],
        zoom_start=12,
        tiles="OpenStreetMap", # Hoặc dùng tiles mặc định
    )

    # Marker điểm xuất phát
    folium.Marker(
        [src["lat"], src["lon"]],
        tooltip="Xuất phát",
        popup=src["name"],
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # Marker điểm đến
    folium.Marker(
        [dst["lat"], dst["lon"]],
        tooltip="Đích đến",
        popup=dst["name"],
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    # Vẽ đường đi (Polyline)
    if route and route.get("geometry"):
        # route["geometry"] bây giờ là list [(lat, lon), ...] từ hàm polyline.decode
        path_coords = route["geometry"]
        
        folium.PolyLine(
            locations=path_coords,
            color="blue",
            weight=5,
            opacity=0.7,
            tooltip=f"{route.get('distance_text')} - {route.get('duration_text')}"
        ).add_to(m)

        # Fit bản đồ bao trọn lộ trình
        m.fit_bounds(path_coords)
    else:
        # Fallback nếu không có đường
        m.fit_bounds([[src["lat"], src["lon"]], [dst["lat"], dst["lon"]]])

    return m

def recommend_transport_mode(distance_km: float, duration_min: float):
    """
    Gợi ý phương tiện di chuyển dựa trên quãng đường & thời gian ước tính.

    Trả về:
      - best_profile: "walking" / "cycling" / "driving"
      - explanation: chuỗi tiếng Việt giải thích ngắn gọn
    """
    if distance_km <= 1.5:
        return "walking", (
            "Quãng đường rất ngắn, bạn có thể đi bộ để tiết kiệm chi phí "
            "và thoải mái ngắm cảnh xung quanh."
        )
    elif distance_km <= 7:
        return "walking", (
            "Quãng đường không quá xa, đi bộ hoặc xe đạp đều phù hợp. "
            "Nếu mang nhiều hành lý có thể gọi xe máy/ô tô."
        )
    elif distance_km <= 25:
        return "cycling", (
            "Quãng đường trung bình, phù hợp đi xe máy hoặc xe đạp nếu bạn quen di chuyển xa."
        )
    elif distance_km <= 300:
        return "driving", (
            "Quãng đường khá xa, nên đi ô tô/xe máy, taxi hoặc xe công nghệ "
            "để đảm bảo thời gian và sự thoải mái."
        )
    else:
        return "driving", (
            "Đây là quãng đường rất xa. Thực tế nên cân nhắc đi máy bay, tàu hoặc xe khách "
            "rồi bắt taxi/xe buýt đến nơi ở."
        )

def analyze_route_complexity(route: dict, profile: str):
    """
    Phân tích độ phức tạp dựa trên dữ liệu từ Google Maps.
    """
    distance_km = route.get("distance_km", 0.0)
    # Google tính duration rất chuẩn (đã bao gồm tắc đường nếu có dữ liệu), tin tưởng nó hơn tính toán thủ công
    duration_min = route.get("duration_min", 0.0)
    steps_list = route.get("steps", [])
    steps_count = len(steps_list)

    difficulty_score = 0
    reasons = []

    # 1. Phân tích quãng đường
    if distance_km > 50:
        difficulty_score += 3
        reasons.append(f"Quãng đường rất dài ({distance_km:.1f} km), cần nghỉ ngơi giữa chừng.")
    elif distance_km > 20:
        difficulty_score += 2
        reasons.append("Quãng đường khá dài, hãy chuẩn bị sức khỏe.")
    
    # 2. Phân tích độ phức tạp của đường đi (số lượng ngã rẽ)
    # Google thường gộp các hướng dẫn "đi thẳng" nên nếu steps nhiều nghĩa là phải rẽ nhiều
    if steps_count > 25:
        difficulty_score += 2
        reasons.append(f"Lộ trình rất phức tạp với {steps_count} chỉ dẫn chuyển hướng.")
    elif steps_count > 15:
        difficulty_score += 1
        reasons.append(f"Lộ trình có khá nhiều ngã rẽ ({steps_count} bước).")

    # 3. Phân tích tốc độ trung bình (để phát hiện tắc đường/đường xấu)
    if duration_min > 0 and distance_km > 0:
        avg_speed = distance_km / (duration_min / 60.0) # km/h
        
        if profile == "driving":
            if avg_speed < 20: # Ô tô/xe máy mà < 20km/h là rất chậm
                difficulty_score += 2
                reasons.append("Tốc độ di chuyển dự kiến rất chậm (đường đông hoặc xấu).")
        elif profile == "cycling":
            if avg_speed < 8:
                difficulty_score += 1
                reasons.append("Tốc độ đạp xe dự kiến chậm hơn bình thường.")

    # 4. Kết luận
    if difficulty_score <= 1:
        level = "low"
        label_vi = "Dễ đi"
        summary = "Lộ trình đơn giản, đường thông thoáng."
    elif difficulty_score <= 3:
        level = "medium"
        label_vi = "Trung bình"
        summary = "Lộ trình có chút thử thách về khoảng cách hoặc các ngã rẽ."
    else:
        level = "high"
        label_vi = "Phức tạp"
        summary = "Lộ trình khó, tốn nhiều thời gian hoặc đường đi phức tạp."

    return level, label_vi, summary, reasons

# ==============================================================================
#3. API ENDPOINT (Kết nối với Frontend)
# ==============================================================================

@app.route('/api/route', methods=['POST'])
def api_get_route():
    data = request.json
    src = data.get("src") # {lat: ..., lon: ...}
    dst = data.get("dst") # {lat: ..., lon: ...}
    profile = data.get("profile", "driving")

    if not src or not dst:
        return jsonify({"status": "error", "message": "Thiếu tọa độ src hoặc dst"}), 400

    # 1. Gọi OSRM để lấy đường đi và thông tin cơ bản
    route_data = osrm_route(src, dst, profile)
    
    if not route_data:
        return jsonify({"status": "error", "message": "Không tìm thấy đường đi"}), 404

    # 2. Gọi hàm nhận xét/đánh giá của BẠN
    # Gợi ý phương tiện
    rec_mode, rec_msg = recommend_transport_mode(
        route_data["distance_km"], 
        route_data["duration_min"]
    )
    
    # Phân tích độ khó
    level, label_vi, summary, reasons = analyze_route_complexity(route_data, profile)

    # 3. Trả về JSON cho Frontend hiển thị
    return jsonify({
        "status": "success",
        "path": route_data["geometry"],  # Để Leaflet vẽ đường xanh
        "info": {
            "distance_text": route_data["distance_text"],
            "duration_text": route_data["duration_text"],
            
            # Dữ liệu phân tích của bạn
            "complexity_level": level,         # low/medium/high
            "complexity_label": label_vi,      # "Dễ đi", "Phức tạp"...
            "complexity_summary": summary,     # "Lộ trình đơn giản..."
            "recommendation_mode": rec_mode,
            "recommendation_msg": rec_msg,
            "analysis_details": reasons        # List lý do
        },
        "instructions": route_data["steps"]    # List hướng dẫn từng bước
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)