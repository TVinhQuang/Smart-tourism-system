from flask import Flask, request, jsonify
from flask_cors import CORS
from app import app
import requests
import json
from typing import List
from serpapi.google_search import GoogleSearch
import re
from translator import translate_text
from dataclasses import dataclass
from typing import List
import math
import folium
from deep_translator import GoogleTranslator
API_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

# ==================== TỪ ĐIỂN DỊCH THUẬT (Backend) ====================
TRANS = {
    "vi": {
        "start": "Bắt đầu từ",
        "start_default": "điểm xuất phát",
        "arrive": "Đến điểm đến",
        "right": "bên phải",
        "left": "bên trái",
        "turn": "rẽ",
        "go": "Đi",
        "onto": "vào đường",
        "continue": "Đi tiếp",
        "roundabout": "Vào vòng xuyến",
        "exit": "lối ra thứ",
        "merge": "Nhập làn/ra khỏi làn",
        
        "walk_short": "Quãng đường rất ngắn, đi bộ là hợp lý nhất.",
        "walk_med": "Không quá xa, đi bộ hoặc xe đạp đều ổn.",
        "bike_med": "Quãng đường trung bình, phù hợp đi xe máy/xe đạp.",
        "drive_long": "Khá xa, nên đi ô tô hoặc xe máy.",
        "fly_long": "Rất xa! Cân nhắc đi máy bay/xe khách.",
        
        "easy": "Dễ đi",
        "medium": "Trung bình",
        "hard": "Phức tạp",
        "easy_desc": "Đường đi đơn giản, ít ngã rẽ.",
        "med_desc": "Lộ trình có chút thử thách về khoảng cách.",
        "hard_desc": "Lộ trình dài hoặc nhiều ngã rẽ phức tạp.",
        "dist_warn": "Quãng đường rất dài, cần nghỉ ngơi.",
        "turn_warn": "Nhiều ngã rẽ, chú ý quan sát.",
        "speed_warn": "Tốc độ di chuyển dự kiến chậm."
    },
    "en": {
        "start": "Start from",
        "start_default": "starting point",
        "arrive": "Arrive at destination",
        "right": "on the right",
        "left": "on the left",
        "turn": "turn",
        "go": "Go",
        "onto": "onto",
        "continue": "Continue",
        "roundabout": "Enter roundabout",
        "exit": "exit",
        "merge": "Merge/Take ramp",
        
        "walk_short": "Very short distance, walking is best.",
        "walk_med": "Not too far, walking or cycling is fine.",
        "bike_med": "Medium distance, suitable for motorbike/bicycle.",
        "drive_long": "Quite far, prefer car or motorbike.",
        "fly_long": "Very far! Consider flying or taking a bus.",
        
        "easy": "Easy",
        "medium": "Medium",
        "hard": "Complex",
        "easy_desc": "Simple route, few turns.",
        "med_desc": "Route is a bit challenging in distance.",
        "hard_desc": "Long route or complex turns.",
        "dist_warn": "Very long distance, take breaks.",
        "turn_warn": "Many turns, pay attention.",
        "speed_warn": "Expected speed is slow."
    }
}

# ==================== CÁC HÀM XỬ LÝ LOGIC ====================

def _get_text(lang, key):
    return TRANS.get(lang, TRANS["vi"]).get(key, "")

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

def describe_osrm_step(step: dict, lang="vi") -> str:
    t = lambda k: _get_text(lang, k)
    maneuver = step.get("maneuver", {})
    type = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    dist_str = _format_distance(step.get("distance", 0.0))

    dir_map = {
        "right": "right", "slight right": "right", "sharp right": "right",
        "left": "left", "slight left": "left", "sharp left": "left",
        "straight": "straight", "uturn": "uturn"
    }
    
    # Mapping direction words
    action_en = dir_map.get(modifier, "turn")
    action_vi = "rẽ phải" if "right" in action_en else ("rẽ trái" if "left" in action_en else "đi thẳng")
    if lang == 'en': action_text = action_en
    else: action_text = action_vi

    if type == "depart":
        return f"{t('start')} {name if name else t('start_default')}."
    if type == "arrive":
        return t("arrive") + "."
    
    if type in ("turn", "end of road", "fork"):
        if name: return f"{t('go')} {dist_str}, {action_text} {t('onto')} {name}."
        return f"{t('go')} {dist_str}, {action_text}."

    if type == "roundabout":
        exit_nr = maneuver.get("exit")
        return f"{t('roundabout')}, {t('exit')} {exit_nr}." if exit_nr else t('roundabout') + "."

    if name: return f"{t('continue')} {dist_str} ({name})."
    return f"{t('continue')} {dist_str}."

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

def recommend_transport_mode(dist_km, lang="vi"):
    t = lambda k: _get_text(lang, k)
    if dist_km <= 1.5: return "walking", t("walk_short")
    elif dist_km <= 7: return "walking", t("walk_med")
    elif dist_km <= 25: return "cycling", t("bike_med")
    elif dist_km <= 300: return "driving", t("drive_long")
    else: return "driving", t("fly_long")

def analyze_route_complexity(route, profile, lang="vi"):
    t = lambda k: _get_text(lang, k)
    dist_km = route["distance_km"]
    steps = len(route["steps_raw"])
    
    score = 0
    reasons = []

    if dist_km > 50: score += 3; reasons.append(f"{t('dist_warn')} ({dist_km:.1f} km).")
    elif dist_km > 20: score += 2
    
    if steps > 25: score += 2; reasons.append(f"{t('turn_warn')} ({steps}).")
    elif steps > 15: score += 1

    if score <= 1: return "low", t("easy"), t("easy_desc"), reasons
    elif score <= 3: return "medium", t("medium"), t("med_desc"), reasons
    return "high", t("hard"), t("hard_desc"), reasons
# ==============================================================================
#3. API ENDPOINT (Kết nối với Frontend)
# ==============================================================================

@app.route('/api/route', methods=['POST'])
def api_get_route():
    data = request.json
    src = data.get("src")
    dst = data.get("dst")
    profile = data.get("profile", "driving")
    lang = data.get("lang", "vi") # Nhận ngôn ngữ từ Frontend

    if not src or not dst:
        return jsonify({"status": "error"}), 400

    # 1. Gọi OSRM
    osrm_mode = 'foot' if profile in ['foot', 'walking'] else 'driving'
    url = f"https://router.project-osrm.org/route/v1/{osrm_mode}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}?overview=full&geometries=geojson&steps=true"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return jsonify({"status": "error", "message": "OSRM Error"})
        res = r.json()
        if not res.get("routes"): return jsonify({"status": "error", "message": "No route found"})
        
        route = res["routes"][0]
        dist_km = route["distance"] / 1000.0
        dur_min = route["duration"] / 60.0
        
        # 2. Xử lý đa ngôn ngữ
        steps_raw = route["legs"][0]["steps"]
        instructions = [describe_osrm_step(s, lang) for s in steps_raw]
        
        rec_mode, rec_msg = recommend_transport_mode(dist_km, lang)
        lvl, lbl, summ, reasons = analyze_route_complexity({"distance_km": dist_km, "steps_raw": steps_raw}, profile, lang)

        return jsonify({
            "status": "success",
            "path": [[lat, lon] for lon, lat in route["geometry"]["coordinates"]],
            "info": {
                "distance_text": f"{dist_km:.2f} km",
                "duration_text": f"{int(dur_min)} min" if lang == 'en' else f"{int(dur_min)} phút",
                "complexity_level": lvl,
                "complexity_label": lbl,
                "complexity_summary": summ,
                "recommendation_msg": rec_msg,
                "analysis_details": reasons
            },
            "instructions": instructions
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)})

