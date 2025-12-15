from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import List, Optional
from serpapi.google_search import GoogleSearch
import re
import math
import requests
import json
import time
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

# --- THƯ VIỆN MỚI ---
import firebase_admin
from firebase_admin import credentials, firestore, auth as admin_auth

# Xử lý import optional cho ollama
try:
    import ollama
except ImportError:
    ollama = None

# ==============================================================================
# 0. INIT & CONFIG
# ==============================================================================

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 1. Cấu hình SerpApi
SERPAPI_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

# 2. Cấu hình Ollama
OLLAMA_MODEL = "llama3.2:latest" 

# 3. Cấu hình Firebase
try:
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("DEBUG: ✅ Firebase Connected")
    else:
        print("DEBUG: ⚠️ serviceAccountKey.json not found. Firebase disabled.")
        db = None
except Exception as e:
    print(f"DEBUG: ⚠️ Firebase Warning: {e}")
    db = None

LAST_OSRM_CALL = 0
OSRM_INTERVAL = 0.5 

# Fallback translator
try:
    from translator import translate_text
except ImportError:
    def translate_text(text, target_lang):
        return text 

# TỪ ĐIỂN DỊCH THUẬT ROUTING
TRANS = {
    "vi": {
        "start": "Bắt đầu từ", "start_default": "điểm xuất phát", "arrive": "Đến điểm đến",
        "right": "bên phải", "left": "bên trái", "turn": "rẽ", "go": "Đi", "onto": "vào đường",
        "continue": "Đi tiếp", "roundabout": "Vào vòng xuyến", "exit": "lối ra thứ", "merge": "Nhập làn/ra khỏi làn",
        "walk_short": "Quãng đường rất ngắn, đi bộ là hợp lý nhất.",
        "walk_med": "Không quá xa, đi bộ hoặc xe đạp đều ổn.",
        "bike_med": "Quãng đường trung bình, phù hợp đi xe máy/xe đạp.",
        "drive_long": "Khá xa, nên đi ô tô hoặc xe máy.",
        "fly_long": "Rất xa! Cân nhắc đi máy bay/xe khách.",
        "easy": "Dễ đi", "medium": "Trung bình", "hard": "Phức tạp",
        "easy_desc": "Đường đi đơn giản, ít ngã rẽ.", "med_desc": "Lộ trình có chút thử thách về khoảng cách.",
        "hard_desc": "Lộ trình dài hoặc nhiều ngã rẽ phức tạp.",
        "dist_warn": "Quãng đường rất dài, cần nghỉ ngơi.", "turn_warn": "Nhiều ngã rẽ, chú ý quan sát.",
        "speed_warn": "Tốc độ di chuyển dự kiến chậm."
    },
    "en": {
        "start": "Start from", "start_default": "starting point", "arrive": "Arrive at destination",
        "right": "on the right", "left": "on the left", "turn": "turn", "go": "Go", "onto": "onto",
        "continue": "Continue", "roundabout": "Enter roundabout", "exit": "exit", "merge": "Merge/Take ramp",
        "walk_short": "Very short distance, walking is best.",
        "walk_med": "Not too far, walking or cycling is fine.",
        "bike_med": "Medium distance, suitable for motorbike/bicycle.",
        "drive_long": "Quite far, prefer car or motorbike.",
        "fly_long": "Very far! Consider flying or taking a bus.",
        "easy": "Easy", "medium": "Medium", "hard": "Complex",
        "easy_desc": "Simple route, few turns.", "med_desc": "Route is a bit challenging in distance.",
        "hard_desc": "Long route or complex turns.", "dist_warn": "Very long distance, take breaks.",
        "turn_warn": "Many turns, pay attention.", "speed_warn": "Expected speed is slow."
    }
}

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

@dataclass
class SearchQuery:
    city: str
    group_size: int
    price_min: float
    price_max: float
    types: List[str]
    rating_min: float
    amenities_required: List[str]
    amenities_preferred: List[str]
    radius_km: float
    priority: str = "balanced"

# ==============================================================================
# UTILS
# ==============================================================================

def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

def clamp01(x: float) -> float: return max(0.0, min(1.0, x))
def _get_text(lang, key): return TRANS.get(lang, TRANS["vi"]).get(key, "")
def _format_distance(meters: float) -> str: return f"{int(round(meters))} m" if meters < 1000 else f"{meters/1000.0:.1f} km"

def serpapi_geocode(q: str):
    # (Giữ nguyên logic cũ)
    print(f"DEBUG: Đang Geocode '{q}'...")
    params = {"engine": "google_maps", "q": q, "type": "search", "api_key": SERPAPI_KEY, "hl": "vi"}
    try:
        results = GoogleSearch(params).get_dict()
        if "error" in results: return None
        if "local_results" in results and results["local_results"]:
            place = results["local_results"][0]
            return {"name": place.get("title"), "lat": place["gps_coordinates"]["latitude"], "lon": place["gps_coordinates"]["longitude"], "address": place.get("address", "")}
        if "place_results" in results:
            place = results["place_results"]
            return {"name": place.get("title"), "lat": place["gps_coordinates"]["latitude"], "lon": place["gps_coordinates"]["longitude"], "address": place.get("address", "")}
        return None
    except Exception as e:
        print(f"DEBUG: Error geocode: {e}")
        return None

# ==============================================================================
# LOGIC & RANKING
# ==============================================================================

def describe_osrm_step(step: dict, lang="vi") -> str:
    t = lambda k: _get_text(lang, k)
    maneuver = step.get("maneuver", {})
    type_ = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    dist_str = _format_distance(step.get("distance", 0.0))
    dir_map = {"right": "right", "slight right": "right", "sharp right": "right", "left": "left", "slight left": "left", "sharp left": "left", "straight": "straight", "uturn": "uturn"}
    action_en = dir_map.get(modifier, "turn")
    action_vi = "rẽ phải" if "right" in action_en else ("rẽ trái" if "left" in action_en else "đi thẳng")
    action_text = action_en if lang == 'en' else action_vi

    if type_ == "depart": return f"{t('start')} {name if name else t('start_default')}."
    if type_ == "arrive": return t("arrive") + "."
    if type_ in ("turn", "end of road", "fork"):
        return f"{t('go')} {dist_str}, {action_text} {t('onto')} {name}." if name else f"{t('go')} {dist_str}, {action_text}."
    if type_ == "roundabout":
        exit_nr = maneuver.get("exit")
        return f"{t('roundabout')}, {t('exit')} {exit_nr}." if exit_nr else t('roundabout') + "."
    return f"{t('continue')} {dist_str} ({name})." if name else f"{t('continue')} {dist_str}."

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
    score = 0; reasons = []
    if dist_km > 50: score += 3; reasons.append(f"{t('dist_warn')} ({dist_km:.1f} km).")
    elif dist_km > 20: score += 2
    if steps > 25: score += 2; reasons.append(f"{t('turn_warn')} ({steps}).")
    elif steps > 15: score += 1
    
    if score <= 1: return "low", t("easy"), t("easy_desc"), reasons
    elif score <= 3: return "medium", t("medium"), t("med_desc"), reasons
    return "high", t("hard"), t("hard_desc"), reasons

def detect_acc_type(item) -> str:
    # (Giữ nguyên logic cũ)
    title = item.get("title", "")
    type_str = item.get("type", "")
    types_list = " ".join(item.get("types", [])) if item.get("types") else ""
    text = f"{title} {type_str} {types_list}".lower()
    
    if any(kw in text for kw in ["homestay", "guest house", "nhà nghỉ", "nhà dân"]): return "Homestay"
    if "resort" in text: return "Resort"
    if "hostel" in text: return "Hostel"
    if any(kw in text for kw in ["apartment", "căn hộ", "chung cư"]): return "Apartment"
    if "villa" in text: return "Villa"
    return "Hotel"

def fetch_google_hotels(city_name: str, radius_km: float = 5.0, wanted_types: List[str] = None):
    if wanted_types is None: wanted_types = []
    
    city_geo = serpapi_geocode(city_name + ", Vietnam")
    if not city_geo: return [], None
    city_lat, city_lon = city_geo["lat"], city_geo["lon"]
    
    # TỰ ĐỘNG TẠO NGÀY: Ngày mai -> Ngày kia (Để lấy giá từ Google)
    tomorrow = datetime.now() + timedelta(days=1)
    next_day = tomorrow + timedelta(days=1)
    
    q_str = f"hotel homestay in {city_name}"
    params = {
        "engine": "google_maps", 
        "type": "search", 
        "google_domain": "google.com.vn", 
        "q": q_str, 
        "ll": f"@{city_lat},{city_lon},14z", 
        "check_in_date": tomorrow.strftime("%Y-%m-%d"),
        "check_out_date": next_day.strftime("%Y-%m-%d"),
        "api_key": SERPAPI_KEY, 
        "hl": "vi"
    }
    
    accommodations = [] 

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        local_results = results.get("local_results", [])
    except Exception as e:
        print(f"DEBUG: SerpApi error: {e}")
        return [], (city_lon, city_lat)

    for item in local_results:
        try:
            gps = item.get("gps_coordinates")
            if not gps: continue

            raw_name = item.get("title", "Unknown")
            
            price_val = 700000.0 # Giá mặc định nếu Google không trả về
            price_raw = item.get("price")
            if price_raw:
                clean_price = "".join(filter(str.isdigit, str(price_raw)))
                if clean_price:
                    price_val = float(clean_price)

            acc = Accommodation(
                id=str(item.get("data_id") or hash(raw_name)),
                name=raw_name,
                city=city_name,
                type=detect_acc_type(item),
                price=price_val,
                stars=float(item.get("rating", 0.0)),
                rating=float(item.get("rating", 0.0)),
                capacity=4, # Mặc định capacity vì đã bỏ input
                amenities=item.get("amenities", []),
                address=item.get("address", "Đang cập nhật địa chỉ"),
                lon=float(gps["longitude"]),
                lat=float(gps["latitude"]),
                distance_km=haversine_km(city_lon, city_lat, float(gps["longitude"]), float(gps["latitude"]))
            )
            accommodations.append(acc)
        except Exception as e:
            continue

    return accommodations, (city_lon, city_lat)

def rank_accommodations(accommodations, q, top_k=5):
    # Hàm xếp hạng đơn giản hóa
    ranked = []
    for acc in accommodations:
        # Logic chấm điểm đơn giản
        score = 0.5
        if acc.rating >= 4.0: score += 0.2
        if acc.price <= q.price_max: score += 0.2
        ranked.append({"score": score, "accommodation": acc})
    
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k], "Đã lọc theo tiêu chí tốt nhất."

# ==============================================================================
# 5. API ENDPOINTS
# ==============================================================================

@app.route('/api/recommend-hotel', methods=['POST'])
def recommend_api():
    try:
        data = request.json
        lang = data.get("lang", "vi")

        # CẬP NHẬT: Không lấy group_size từ request nữa
        query = SearchQuery(
            city=data.get("city"),
            # group_size=int(data.get("group_size", 1)), --> ĐÃ XÓA
            price_min=float(data.get("price_min", 0)),
            price_max=float(data.get("price_max", 0)),
            types=data.get("types", []),
            rating_min=float(data.get("rating_min", 0)),
            amenities_required=data.get("amenities_required", []),
            amenities_preferred=data.get("amenities_preferred", []),
            radius_km=float(data.get("radius_km", 5)),
            priority=data.get("priority", "balanced")
        )

        accommodations, center = fetch_google_hotels(query.city, query.radius_km, query.types)
        
        if not accommodations:
             return jsonify({
                "results": [],
                "relaxation_note": "Không tìm thấy khách sạn nào.",
                "center": {"lat": center[1], "lon": center[0]} if center else None
            })

        ranked_results, note = rank_accommodations(accommodations, query, top_k=5)

        results = []
        for item in ranked_results:
            acc = item["accommodation"]
            results.append({
                "id": acc.id,
                "name": acc.name, 
                "type": acc.type,
                "price": acc.price,
                "rating": acc.rating,
                "stars": acc.stars,
                "address": acc.address,
                "amenities": acc.amenities,
                "distance_km": acc.distance_km,
                "score": item["score"],
                "lat": acc.lat,
                "lon": acc.lon
            })

        return jsonify({
            "results": results,
            "relaxation_note": note,
            "center": {"lat": center[1], "lon": center[0]} if center else None
        })
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/route', methods=['POST'])
def api_get_route():
    data = request.json
    src = data.get("src")
    dst = data.get("dst")
    profile = data.get("profile", "driving")
    lang = data.get("lang", "vi")

    if not src or not dst: return jsonify({"status": "error"}), 400

    global LAST_OSRM_CALL
    now = time.time()
    if now - LAST_OSRM_CALL < OSRM_INTERVAL:
        return jsonify({"status": "error", "message": "Too many requests"})
    LAST_OSRM_CALL = now

    osrm_mode = 'foot' if profile in ['foot', 'walking'] else 'driving'
    
    # [GIỮ NGUYÊN] URL Local OSRM
    url = f"http://127.0.0.1:5000/route/v1/{osrm_mode}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}?overview=full&geometries=geojson&steps=true"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return jsonify({"status": "error", "message": "OSRM Error"})
        res = r.json()
        if not res.get("routes"): return jsonify({"status": "error", "message": "No route found"})
        
        route = res["routes"][0]
        dist_km = route["distance"] / 1000.0
        dur_min = route["duration"] / 60.0
        steps_raw = route["legs"][0]["steps"]
        instructions = [describe_osrm_step(s, lang) for s in steps_raw]
        rec_mode, rec_msg = recommend_transport_mode(dist_km, lang)
        lvl, lbl, summ, reasons = analyze_route_complexity({"distance_km": dist_km, "steps_raw": steps_raw}, profile, lang)

        return jsonify({
            "status": "success",
            "path": [[lat, lon] for lon, lat in route["geometry"]["coordinates"]],
            "info": {
                "distance_text": f"{dist_km:.2f} km",
                "duration_text": f"{int(dur_min)} min",
                "complexity_level": lvl, "complexity_label": lbl,
                "complexity_summary": summ, "recommendation_msg": rec_msg,
                "analysis_details": reasons
            },
            "instructions": instructions
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        data = request.json
        user_message = data.get("message", "")
        # Nếu có Ollama local, uncomment đoạn này:
        # if ollama:
        #    res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': user_message}])
        #    return jsonify({"reply": res['message']['content']})
        
        return jsonify({"reply": f"Server nhận được: {user_message}. (Ollama chưa kích hoạt)"})
    except Exception as e:
        return jsonify({"reply": "Lỗi server."}), 500

@app.route('/api/generate_itinerary', methods=['POST'])
def generate_itinerary_api():
    return jsonify({"result": "Chức năng đang bảo trì."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Server running on port {port}")
    app.run(host='0.0.0.0', port=port)