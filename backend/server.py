from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import List, Optional
from serpapi.google_search import GoogleSearch
import math
import requests
import json
import time
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

# ==============================================================================
# 0. CẤU HÌNH & KHỞI TẠO
# ==============================================================================

app = Flask(__name__)
# Cho phép mọi nguồn (Frontend/Mobile) gọi vào
CORS(app, resources={r"/*": {"origins": "*"}})

# API Key SerpApi (Dành cho việc tìm khách sạn/địa điểm)
SERPAPI_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

# --- CẤU HÌNH OSRM LOCAL ---
# Chạy Docker: docker run -t -i -p 5000:5000 -v ... osrm/osrm-backend ...
OSRM_BASE_URL = "http://127.0.0.1:5000"

# ==============================================================================
# 1. CẤU TRÚC DỮ LIỆU
# ==============================================================================

@dataclass
class Accommodation:
    id: str
    name: str
    city: str
    type: str
    price: float
    stars: float
    rating: float
    capacity: int
    amenities: List[str]
    address: str
    lon: float
    lat: float
    distance_km: float
    thumbnail: str

@dataclass
class SearchQuery:
    city: str
    price_min: float
    price_max: float
    types: List[str]
    rating_min: float
    amenities_preferred: List[str]
    radius_km: float
    priority: str = "balanced"

# ==============================================================================
# 2. HÀM TIỆN ÍCH (LOGIC ĐỒNG BỘ VỚI APP.PY)
# ==============================================================================

def haversine_km(lon1, lat1, lon2, lat2):
    """Tính khoảng cách đường chim bay"""
    try:
        R = 6371.0 
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = phi2 - phi1
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))
    except Exception:
        return 0.0

def _format_distance(meters: float) -> str:
    """Chuyển mét sang km hoặc m"""
    if meters < 1000:
        return f"{int(round(meters))} m"
    km = meters / 1000.0
    return f"{km:.1f} km"

def describe_osrm_step(step: dict) -> str:
    """
    Phiên bản nâng cấp: Dịch hướng dẫn đường đi OSRM sang tiếng Việt tự nhiên hơn.
    """
    maneuver = step.get("maneuver", {})
    step_type = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    # Nếu không có tên đường, thử dùng ref (số hiệu đường, vd: QL1A)
    if not name:
        name = (step.get("ref") or "").strip()

    distance = step.get("distance", 0.0)
    dist_str = _format_distance(distance)

    # Từ điển hướng
    dir_map = {
        "right": "rẽ phải", "slight right": "chếch sang phải", "sharp right": "quẹo gắt sang phải",
        "left": "rẽ trái", "slight left": "chếch sang trái", "sharp left": "quẹo gắt sang trái",
        "straight": "đi thẳng", "uturn": "quay đầu xe",
    }
    action = dir_map.get(modifier, "rẽ")

    # 1. Khởi hành
    if step_type == "depart":
        return f"🚀 Bắt đầu di chuyển từ {name if name else 'điểm xuất phát'}."
    
    # 2. Đến nơi
    if step_type == "arrive":
        side = maneuver.get("modifier", "")
        side_text = "ở bên phải" if side == "right" else ("ở bên trái" if side == "left" else "")
        return f"🏁 Đã đến điểm đến {side_text}."

    # 3. Vòng xuyến
    if step_type == "roundabout":
        exit_nr = maneuver.get("exit")
        return f"🔄 Vào vòng xuyến, đi theo lối ra thứ {exit_nr}."

    # 4. Các hành động rẽ / đi tiếp
    if step_type in ("turn", "end of road", "fork", "merge", "new name", "continue"):
        if modifier == "straight":
            if name: return f"⬆️ Đi thẳng {dist_str} trên {name}."
            return f"⬆️ Đi thẳng {dist_str}."
        else:
            if name: return f"{action.capitalize()} vào {name}, đi tiếp {dist_str}."
            return f"{action.capitalize()}, sau đó đi {dist_str}."

    # Mặc định
    if name:
        return f"Đi tiếp {dist_str} trên {name}."
    return f"Đi tiếp {dist_str}."

def analyze_route_complexity(distance_km, duration_min, steps_count, profile):
    """
    Phân tích độ phức tạp lộ trình (Phiên bản tối ưu cho giao thông Việt Nam).
    Dựa trên: Thời gian di chuyển thực tế, Số lượng khúc cua, và Quãng đường.
    """
    difficulty_score = 0
    reasons = []

    # 1. Đánh giá theo THỜI GIAN (Quan trọng nhất ở VN)
    # Đi xe máy/ô tô mà trên 45 phút là bắt đầu mệt
    if duration_min > 90:
        difficulty_score += 3
        reasons.append(f"Thời gian di chuyển rất lâu (~{int(duration_min // 60)}h{int(duration_min % 60)}p), dễ gây mệt mỏi.")
    elif duration_min > 45:
        difficulty_score += 2
        reasons.append(f"Thời gian di chuyển khá lâu (~{int(duration_min)} phút).")
    elif duration_min > 25:
        difficulty_score += 1

    # 2. Đánh giá theo QUÃNG ĐƯỜNG
    # Ở nội thành, >15km là xa. Ngoại thành >30km là xa.
    if distance_km > 30:
        difficulty_score += 2
        reasons.append(f"Quãng đường xa ({distance_km:.1f} km).")
    elif distance_km > 15:
        difficulty_score += 1
        reasons.append("Quãng đường tương đối dài so với di chuyển nội thành.")

    # 3. Đánh giá theo ĐỘ RẮC RỐI (Số lượng ngã rẽ)
    # Quá nhiều ngã rẽ (trên 20) dễ bị lạc hoặc nhầm đường
    if steps_count > 30:
        difficulty_score += 2
        reasons.append(f"Đường đi rất rắc rối, có tới {steps_count} lần chuyển hướng.")
    elif steps_count > 18:
        difficulty_score += 1
        reasons.append("Lộ trình có nhiều ngã rẽ, cần chú ý quan sát bản đồ.")

    # 4. Đánh giá TỐC ĐỘ TRUNG BÌNH (Phát hiện kẹt xe nặng)
    # Nếu đi xe máy mà tốc độ < 15km/h => Kẹt xe hoặc đường rất xấu
    if duration_min > 0:
        avg_speed = distance_km / (duration_min / 60.0)
        if profile == "driving" and avg_speed < 15:
            difficulty_score += 2
            reasons.append("Cảnh báo: Tốc độ di chuyển dự kiến rất chậm (khu vực đông đúc/kẹt xe).")

    # --- KẾT LUẬN ---
    if difficulty_score <= 1:
        level = "low"
        label_vi = "Dễ đi"
        summary = "Lộ trình ngắn, đơn giản, phù hợp để đi ngay."
    elif difficulty_score <= 3:
        level = "medium"
        label_vi = "Trung bình"
        summary = "Lộ trình tốn chút thời gian hoặc cần chú ý các ngã rẽ."
    else:
        level = "high"
        label_vi = "Phức tạp"
        summary = "Lộ trình khó (xa, lâu hoặc tắc đường). Nên cân nhắc nghỉ ngơi hoặc chọn giờ thấp điểm."

    return {
        "level": level,
        "label": label_vi,
        "summary": summary,
        "reasons": reasons
    }

def recommend_transport_mode(distance_km: float, duration_min: float):
    """
    Gợi ý phương tiện di chuyển dựa trên quãng đường & thời gian ước tính.

    Trả về:
      - best_profile: "walking" / "cycling" / "driving"
      - explanation: chuỗi tiếng Việt giải thích ngắn gọn
    """
    if distance_km <= 2.0:
        return "walking", "Quãng đường ngắn, đi bộ hoặc xe đạp là lựa chọn tốt cho sức khỏe, tiết kiệm chi phí và thoải mái ngắm cảnh xung quanh."
    elif distance_km <= 5:
        return "cycling", "Quãng đường khá ngắn, đi xe đạp hoặc xe máy sẽ nhanh và tiện lợi hơn. Nếu không mang hành lí và thời gian thoải mái thì có thể đi bộ."
    elif distance_km <= 30:
        return "cycling", "Quãng đường trung bình, phù hợp đi xe máy. Nếu mang nhiều hành lý hoặc muốn thoải mái có thể gọi ô tô."
    elif distance_km <= 100:
        return "driving", "Quãng đường khá xa, nên đi ô tô hoặc xe máy để đảm bảo thời gian và sự thoải mái."
    else:
        return "driving", "Quãng đường rất xa, đi ô tô hoặc máy bay là lựa chọn duy nhất để đảm bảo an toàn và tiết kiệm thời gian."

# ==============================================================================
# 3. HÀM TÌMKIẾM GOOGLE MAPS (GIỮ NGUYÊN)
# ==============================================================================

def serpapi_geocode(q: str):
    """Gọi Google Maps để lấy tọa độ thành phố thật"""
    print(f"DEBUG: Đang gọi Google Maps Geocode cho: '{q}'...")
    params = {"engine": "google_maps", "q": q, "type": "search", "api_key": SERPAPI_KEY, "hl": "vi"}
    try:
        results = GoogleSearch(params).get_dict()
        if "error" in results: return None
        
        # Thử tìm trong local_results trước
        if "local_results" in results and results["local_results"]:
            place = results["local_results"][0]
            return {
                "name": place.get("title"), 
                "lat": place["gps_coordinates"]["latitude"], 
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
        # Thử tìm trong place_results
        if "place_results" in results:
            place = results["place_results"]
            return {
                "name": place.get("title"), 
                "lat": place["gps_coordinates"]["latitude"], 
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
        return None
    except Exception as e:
        print(f"DEBUG: Lỗi Geocode: {e}")
        return None

def detect_acc_type(item) -> str:
    title = item.get("title", "")
    type_str = item.get("type", "")
    text = f"{title} {type_str}".lower()
    if any(kw in text for kw in ["homestay", "nhà nghỉ"]): return "Homestay"
    if "resort" in text: return "Resort"
    if "villa" in text: return "Villa"
    return "Hotel"

def fetch_google_hotels(city_name: str, radius_km: float = 5.0):
    # 1. Lấy tọa độ trung tâm
    city_geo = serpapi_geocode(city_name + ", Vietnam")
    if not city_geo: return [], None
    
    city_lat, city_lon = city_geo["lat"], city_geo["lon"]
    
    # 2. Tạo query tìm kiếm
    params = {
        "engine": "google_maps", 
        "type": "search", 
        "google_domain": "google.com.vn", 
        "q": f"hotel in {city_name}", 
        "ll": f"@{city_lat},{city_lon},14z", 
        "api_key": SERPAPI_KEY, 
        "hl": "vi"
    }
    
    accommodations = [] 
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        local_results = results.get("local_results", [])
    except Exception as e:
        print(f"DEBUG: Lỗi SerpApi: {e}")
        return [], (city_lon, city_lat)

    for item in local_results:
        try:
            gps = item.get("gps_coordinates")
            if not gps: continue

            price_val = 0.0
            raw_price = str(item.get("price", ""))
            
            if raw_price:
                clean = "".join(filter(str.isdigit, raw_price))
                if clean:
                    val = float(clean)
                    if val < 5000: 
                        temp_price = val * 25400 
                    else:
                        temp_price = val
                    price_val = round(temp_price / 500) * 500

            acc = Accommodation(
                id=str(item.get("data_id") or item.get("position")),
                name=item.get("title", "Unknown"),
                city=city_name,
                type=detect_acc_type(item),
                price=price_val,
                stars=float(item.get("rating", 0.0)),
                rating=float(item.get("rating", 0.0)),
                capacity=4,
                amenities=item.get("amenities", []),
                address=item.get("address", ""),
                lon=float(gps["longitude"]),
                lat=float(gps["latitude"]),
                distance_km=haversine_km(city_lon, city_lat, float(gps["longitude"]), float(gps["latitude"])),
                thumbnail=item.get("thumbnail", "https://via.placeholder.com/300")
            )
            accommodations.append(acc)
        except Exception as e:
            continue

    return accommodations, (city_lon, city_lat)

# ==============================================================================
# 4. API ENDPOINTS
# ==============================================================================

@app.route('/api/recommend-hotel', methods=['POST'])
def recommend_api():
    """API Tìm kiếm Khách sạn"""
    try:
        data = request.json
        print("DEBUG: Nhận request tìm kiếm:", data)

        query = SearchQuery(
            city=data.get("city", ""),
            price_min=float(data.get("price_min", 0)),
            price_max=float(data.get("price_max", 0)),
            types=data.get("types", []),
            rating_min=float(data.get("rating_min", 0)),
            amenities_preferred=data.get("amenities_preferred", []),
            radius_km=float(data.get("radius_km", 5)),
            priority=data.get("priority", "balanced")
        )

        accommodations, center = fetch_google_hotels(query.city, query.radius_km)
        
        results = []
        for acc in accommodations:
            if query.price_max > 0 and acc.price > query.price_max and acc.price > 0:
                continue 
            
            results.append({
                "id": acc.id,
                "name": acc.name, 
                "price": acc.price,
                "rating": acc.rating,
                "address": acc.address,
                "amenities": acc.amenities,
                "lat": acc.lat,
                "lon": acc.lon,
                "img": acc.thumbnail
            })

        return jsonify({
            "results": results[:5], 
            "relaxation_note": "Kết quả từ Google Maps (Real-time).",
            "center": {"lat": center[1], "lon": center[0]} if center else None
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/route', methods=['POST'])
def api_get_route():
    """API Tìm đường - Sử dụng OSRM LOCAL (Port 5000)"""
    try:
        data = request.json
        src = data.get("src")
        dst = data.get("dst")
        profile = data.get("profile", "driving") # driving, walking, cycling

        # --- LƯU Ý KHI DÙNG OSRM LOCAL ---
        # Nếu Docker của bạn chỉ chạy profile CAR, các request 'foot' hoặc 'bike'
        # có thể sẽ bị lỗi 400 Bad Request.
        # Nếu gặp lỗi này, hãy đổi dòng dưới thành: osrm_mode = 'driving'
        
        osrm_mode = 'foot' if profile in ['walking', 'foot'] else ('bike' if profile == 'cycling' else 'driving')
        
        # Endpoint OSRM Local
        osrm_url = (
            f"{OSRM_BASE_URL}/route/v1/{osrm_mode}/"
            f"{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}"
            f"?overview=full&geometries=geojson&steps=true"
        )
        
        print(f"DEBUG: Đang gọi OSRM Local: {osrm_url}")
        
        try:
            r = requests.get(osrm_url, timeout=5) # Timeout nhanh vì chạy local
        except requests.exceptions.ConnectionError:
            return jsonify({
                "status": "error", 
                "message": "Không kết nối được OSRM Local tại cổng 5000. Hãy kiểm tra Docker."
            }), 503

        if r.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"OSRM trả về lỗi: {r.status_code}. Có thể profile '{osrm_mode}' không được hỗ trợ trong Docker container."
            }), 500
            
        res = r.json()
        if "routes" not in res or not res["routes"]:
            return jsonify({"status": "error", "message": "Không tìm thấy đường đi"}), 404

        route = res["routes"][0]
        
        # 1. Xử lý Duration với Traffic Factor (Giống app.py)
        # Hệ số: 3.0 cho xe, 12 cho đi bộ (giả lập kẹt xe/thực tế VN)
        traffic_factor = 3.0 if profile in ["driving", "cycling"] else 12
        duration_min = (route["duration"] / 60.0) * traffic_factor
        distance_km = route["distance"] / 1000.0

        # 2. Xử lý Steps (Hướng dẫn chi tiết tiếng Việt)
        legs = route.get("legs", [])
        step_descriptions = []
        
        for leg in legs:
            for step in leg.get("steps", []):
                desc = describe_osrm_step(step)
                if desc: step_descriptions.append(desc)

        # 3. Phân tích độ phức tạp & Gợi ý phương tiện
        complexity = analyze_route_complexity(distance_km, duration_min, len(step_descriptions), profile)
        rec_mode, rec_msg = recommend_transport_mode(distance_km, duration_min)

        # 4. Trả về kết quả JSON đầy đủ
        return jsonify({
            "status": "success",
            # OSRM trả GeoJSON [lon, lat], frontend thường cần [lat, lon] nếu dùng Leaflet cũ,
            # nhưng nếu dùng pydeck/folium GeoJSON thì giữ nguyên.
            # Ở đây ta đảo lại [lat, lon] để an toàn cho map vẽ Polyline
            "path": [[lat, lon] for lon, lat in route["geometry"]["coordinates"]], 
            "info": {
                "distance_km": distance_km,
                "distance_text": f"{distance_km:.2f} km",
                "duration_min": duration_min,
                "duration_text": f"~{duration_min:.0f} phút",
                
                # Thông tin phân tích
                "complexity": complexity, # level, label, summary, reasons
                "recommendation": {
                    "mode": rec_mode,
                    "message": rec_msg
                }
            },
            "instructions": step_descriptions
        })

    except Exception as e:
        print("ERROR Route:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("✅ Server Python đang chạy trên Port 8000...")
    print(f"🌐 Kết nối OSRM Local tại: {OSRM_BASE_URL}")
    app.run(host='0.0.0.0', port=8000, debug=True)