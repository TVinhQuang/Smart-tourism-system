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
import random
import ollama
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from deep_translator import GoogleTranslator
# ==============================================================================
# 0. CẤU HÌNH & KHỞI TẠO
# ==============================================================================

app = Flask(__name__)

# ✅ FIX CORS - Cho phép mọi origin
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Lấy API Key (Ưu tiên biến môi trường, fallback sang key cứng)
API_KEY = os.getenv("SERPAPI_KEY", "55a38717134583be0bd08237ab34117bc212f65e5b62c597804c8747855fe741")

OSRM_BASE_URL = "http://127.0.0.1:5000"

# --- CẤU HÌNH OLLAMA ---
OLLAMA_MODEL = "llama3.2:latest"
SYSTEM_PROMPT = """
Bạn là một trợ lý du lịch ảo thông minh, thân thiện và am hiểu về du lịch Việt Nam.
Nhiệm vụ của bạn là hỗ trợ người dùng tìm kiếm địa điểm, lên kế hoạch và giải đáp thắc mắc du lịch.
- Hãy trả lời ngắn gọn, súc tích, định dạng dễ đọc (dùng markdown).
- Luôn xưng hô là "mình" và gọi người dùng là "bạn".
"""
BOT_GREETING = "Chào bạn! Mình là trợ lý du lịch ảo. Mình có thể giúp gì cho chuyến đi của bạn?"

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
    reviews: int
    amenities: List[str]
    address: str
    lon: float
    lat: float
    distance_km: float
    # Thêm field để lưu điểm số tính toán
    match_score: float = 0.0 

@dataclass
class SearchQuery:
    city: str
    price_min: float
    price_max: float
    types: List[str]
    rating_min: float
    radius_km: float
    amenities_preferred: List[str] = None
    priority: str = "balanced" 

# ==============================================================================
# 2. RAM DATABASE (KHÔNG DÙNG FILE JSON)
# ==============================================================================
ram_db = {}

def normalize_city(city: str) -> str:
    if not city: return ""
    return city.strip().lower()

def acc_to_dict(a: Accommodation) -> dict:
    return {
        "id": a.id, "name": a.name, "city": normalize_city(a.city),
        "type": a.type, "price": a.price, "stars": a.stars,
        "rating": a.rating, "reviews": a.reviews,
        "amenities": list(a.amenities or []), "address": a.address,
        "lon": a.lon, "lat": a.lat, "distance_km": a.distance_km,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def dict_to_acc(d: dict) -> Accommodation:
    return Accommodation(
        id=d["id"], name=d["name"], city=normalize_city(d.get("city", "")),
        type=d.get("type", "hotel"), price=d.get("price", 0.0),
        stars=d.get("stars", 0.0), rating=d.get("rating", 0.0),
        reviews=int(d.get("reviews") or 0), amenities=d.get("amenities", []),
        address=d.get("address", ""), lon=d.get("lon", 0.0),
        lat=d.get("lat", 0.0), distance_km=d.get("distance_km", 0.0),
    )

def load_accommodation_db() -> dict: return ram_db
def save_accommodation_db(db: dict) -> None: 
    global ram_db
    ram_db = db

def is_fresh_record(cached: dict, days: int = 7) -> bool:
    ts = cached.get("updated_at")
    if not ts: return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) < timedelta(days=days)
    except: return False

# ==============================================================================
# 3. HÀM HELPER & PARSING
# ==============================================================================

# ✅ ĐÃ BỔ SUNG HÀM NÀY
def _format_distance(meters: float) -> str:
    """Chuyển mét sang km hoặc m"""
    if meters < 1000:
        return f"{int(round(meters))} m"
    km = meters / 1000.0
    return f"{km:.1f} km"

def haversine_km(lon1, lat1, lon2, lat2):
    try:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    except: return 0.0

def parse_review_count(x) -> int:
    if x is None: return 0
    if isinstance(x, dict):
        for k in ("count", "total", "value", "reviews"):
            if k in x: return parse_review_count(x[k])
        return 0
    s = str(x).strip().lower()
    m = re.search(r"([\d.,]+)\s*([km])\b", s)
    if m:
        try:
            return int(float(m.group(1).replace(",", ".")) * (1000 if m.group(2) == "k" else 1000000))
        except: return 0
    digits = re.sub(r"\D", "", s)
    return int(digits) if digits else 0

def smart_geocode(query: str):
    q_lower = query.lower()
    # Hardcode tọa độ lớn để tiết kiệm API và nhanh hơn
    if "hồ chí minh" in q_lower or "tphcm" in q_lower: return {"lat": 10.7769, "lon": 106.7009}
    if "hà nội" in q_lower: return {"lat": 21.0285, "lon": 105.8542}
    if "đà nẵng" in q_lower: return {"lat": 16.0544, "lon": 108.2022}
    if "đà lạt" in q_lower: return {"lat": 11.9404, "lon": 108.4583}
    if "vũng tàu" in q_lower: return {"lat": 10.34599, "lon": 107.08426}

    if not API_KEY: return None
    try:
        res = GoogleSearch({"engine": "google_maps", "type": "search", "q": query, "api_key": API_KEY, "hl": "vi"}).get_dict()
        if "local_results" in res and res["local_results"]:
            gps = res["local_results"][0].get("gps_coordinates", {})
            return {"lat": gps.get("latitude"), "lon": gps.get("longitude")}
        if "place_results" in res:
            gps = res["place_results"].get("gps_coordinates", {})
            return {"lat": gps.get("latitude"), "lon": gps.get("longitude")}
    except: pass
    return None

def extract_amenities_basic(item: dict) -> list[str]:
    mapping = {
        "Wifi": ["wifi", "wi-fi", "internet", "mạng"],
        "Bể bơi": ["pool", "bể bơi", "hồ bơi", "swimming"],
        "Đỗ xe": ["parking", "đỗ xe", "giữ xe", "bãi xe"],
        "Điều hòa": ["ac", "air conditioning", "điều hòa", "máy lạnh"],
        "Nhà hàng": ["restaurant", "nhà hàng", "ăn uống"],
        "Bữa sáng": ["breakfast", "bữa sáng", "ăn sáng"],
        "Bar": ["bar", "pub", "lounge"],
        "Gym": ["gym", "thể hình", "fitness"],
        "Spa": ["spa", "massage", "xông hơi"]
    }
    found = set()
    raw_list = item.get("amenities", [])
    full_text = (str(raw_list) + " " + str(item.get("description", "")) + " " + item.get("title", "")).lower()
    for std_name, keywords in mapping.items():
        if any(kw in full_text for kw in keywords): found.add(std_name)
    return sorted(list(found))

# ==============================================================================
# 4. CORE ALGORITHMS (NÂNG CẤP TỪ APP.PY)
# ==============================================================================

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def has_amenity(have_lower: List[str], code: str) -> bool:
    """Kiểm tra xem khách sạn có tiện ích 'code' hay không"""
    code = code.lower()
    # Mapping từ code frontend sang text tiếng Việt/Anh có thể gặp
    KEYWORDS = {
        "wifi": ["wifi", "wi-fi", "mạng"],
        "breakfast": ["breakfast", "bữa sáng", "ăn sáng"],
        "pool": ["pool", "bể bơi", "hồ bơi"],
        "parking": ["parking", "đỗ xe", "bãi xe", "giữ xe"],
        "gym": ["fitness", "gym", "thể dục"],
        "spa": ["spa", "massage"],
        "restaurant": ["restaurant", "nhà hàng"],
        "bar": ["bar", "quầy bar"],
        "airport_shuttle": ["airport", "sân bay", "đưa đón"],
        "air_conditioning": ["ac", "điều hòa", "máy lạnh"]
    }
    keywords = KEYWORDS.get(code, [code])
    
    # Duyệt qua danh sách tiện ích của khách sạn
    for text in have_lower:
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                return True
    return False

def score_accommodation(a: Accommodation, q: SearchQuery) -> float:
    """
    Tính điểm xếp hạng (Score) dựa trên app.py
    """
    # 1. Điểm GIÁ (S_price)
    Pmin, Pmax = q.price_min, q.price_max
    if Pmax > Pmin and a.price > 0:
        t = (a.price - Pmin) / (Pmax - Pmin)
        t = clamp01(t)
        
        if q.priority == "cheap": S_price = 1.0 - t # Càng rẻ càng tốt
        elif q.priority == "balanced": S_price = 1.0 - abs(t - 0.5) * 2.0 # Giá giữa là tốt nhất
        else: S_price = t # Ưu tiên giá cao (chất lượng) cho near_center/amenities
    else:
        S_price = 1.0

    # 2. Điểm ĐÁNH GIÁ (S_rating & S_stars)
    S_rating = clamp01((a.rating or 0.0) / 5.0)
    
    is_hotel_resort = a.type in ("hotel", "resort")
    if is_hotel_resort and (a.stars or 0.0) > 0:
        S_stars = clamp01(a.stars / 5.0)
        w_rating = 0.28
        w_stars = 0.05
    else:
        S_stars = 0.0
        w_rating = 0.33 # Dồn trọng số sang rating
        w_stars = 0.0

    # 3. Điểm TIỆN ÍCH (S_amen)
    pref = q.amenities_preferred
    if pref:
        have_lower = [x.lower() for x in a.amenities]
        matched = sum(1 for code in pref if has_amenity(have_lower, code))
        S_amen = matched / len(pref)
    else:
        S_amen = 1.0

    # 4. Điểm KHOẢNG CÁCH (S_dist)
    radius_limit = q.radius_km or 10.0 # Mặc định 10km nếu không set
    if a.distance_km > 0:
        S_dist = 1.0 - min(a.distance_km / radius_limit, 1.0)
    else:
        S_dist = 1.0

    # 5. TỔNG HỢP (Trọng số cố định từ app.py)
    w_price = 0.32
    w_amen = 0.15
    w_dist = 0.20
    
    # Điều chỉnh trọng số động theo Priority
    if q.priority == "near_center":
        w_dist = 0.40 # Tăng gấp đôi trọng số vị trí
        w_price = 0.12 # Giảm trọng số giá
    elif q.priority == "amenities":
        w_amen = 0.35 # Tăng trọng số tiện ích
        w_price = 0.12

    score = (w_price * S_price + w_stars * S_stars + w_rating * S_rating + w_amen * S_amen + w_dist * S_dist)
    return score

def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    """
    THUẬT TOÁN TÍCH LŨY (ACCUMULATION) + SCORING
    """
    
    def _do_filter(rating_min, amenity_mode="all", price_relax=1.0, radius_relax=1.0):
        # Nới lỏng Giá & Bán kính
        pmin, pmax = q.price_min, q.price_max
        if price_relax > 1.0 and pmax > 0:
            extra = (pmax - pmin) * (price_relax - 1.0)
            pmin = max(0, pmin - extra/2)
            pmax = pmax + extra/2
            
        dist_limit = (q.radius_km * radius_relax) if q.radius_km > 0 else None

        filtered = []
        for a in accommodations:
            # Lọc cơ bản
            if dist_limit and a.distance_km > dist_limit: continue
            if pmin > 0 and a.price < pmin: continue
            if pmax > 0 and a.price > pmax: continue
            if q.types and (a.type not in q.types): continue
            if a.rating < rating_min: continue
            
            # Lọc Tiện ích theo Mode
            if q.amenities_preferred and amenity_mode != "ignore":
                have_lower = [x.lower() for x in a.amenities]
                matched_count = sum(1 for code in q.amenities_preferred if has_amenity(have_lower, code))
                
                if amenity_mode == "all" and matched_count < len(q.amenities_preferred):
                    continue
                if amenity_mode == "any" and matched_count == 0:
                    continue
            
            filtered.append(a)
        return filtered

    # --- CÁC MỨC ĐỘ (LEVELS) TỪ APP.PY ---
    levels = [
        {"desc": "Thỏa mãn đầy đủ tiêu chí.", "rating_min": q.rating_min, "amenity_mode": "all", "price_relax": 1.0, "radius_relax": 1.0},
        {"desc": "Ưu tiên nơi có ít nhất một phần tiện ích.", "rating_min": q.rating_min, "amenity_mode": "any", "price_relax": 1.0, "radius_relax": 1.0},
        {"desc": "Nới lỏng đánh giá và tiện ích.", "rating_min": max(0.0, q.rating_min - 1.0), "amenity_mode": "ignore", "price_relax": 1.0, "radius_relax": 1.2},
        {"desc": "Mở rộng tối đa phạm vi tìm kiếm.", "rating_min": 0.0, "amenity_mode": "ignore", "price_relax": 1.3, "radius_relax": 2.0},
    ]

    final_list = []
    used_ids = set()
    final_note = ""

    # 1. GOM KẾT QUẢ (ACCUMULATION)
    for cfg in levels:
        candidates = _do_filter(cfg["rating_min"], cfg["amenity_mode"], cfg["price_relax"], cfg["radius_relax"])
        
        if candidates:
            if not final_note: final_note = cfg["desc"]
            for c in candidates:
                if c.id not in used_ids:
                    # Tính điểm Score ngay lúc này
                    c.match_score = score_accommodation(c, q)
                    final_list.append(c)
                    used_ids.add(c.id)
        
        # Nếu đã đủ số lượng thì dừng gom
        if len(final_list) >= top_k:
            break
            
    # 2. SẮP XẾP CUỐI CÙNG (DỰA TRÊN SCORE ĐÃ TÍNH)
    # Score cao nhất lên đầu
    final_list.sort(key=lambda x: x.match_score, reverse=True)

    return final_list[:top_k], final_note

def parse_maps_item_to_acc(item: dict, city_name: str, city_lat: float, city_lon: float) -> Optional[Accommodation]:
    raw_name = (item.get("title") or item.get("name") or "").strip()
    if not raw_name: return None
    
    data_id = item.get("data_id") or str(hash(raw_name + str(item.get("address", ""))))
    
    raw_price = item.get("price")
    price = 0.0
    if raw_price:
        s = str(raw_price)
        m = re.search(r"\d+(?:[.,]\d+)?", s)
        if m:
            val = float(m.group(0).replace(",", "."))
            if val < 5000 and "₫" not in s: price = val * 26000
            else: price = val

    rating = float(item.get("rating", 0.0)) if item.get("rating") else 0.0
    reviews = parse_review_count(item.get("reviews") or item.get("user_ratings_total"))
    
    # Detect Type đơn giản
    type_str = (item.get("type", "") + " " + raw_name).lower()
    if any(x in type_str for x in ["homestay", "nhà nghỉ"]): acc_type = "homestay"
    elif "resort" in type_str: acc_type = "resort"
    elif "hostel" in type_str: acc_type = "hostel"
    elif "apartment" in type_str: acc_type = "apartment"
    else: acc_type = "hotel"

    gps = item.get("gps_coordinates", {})
    if not gps.get("latitude") or not gps.get("longitude"): return None
    
    lat, lon = float(gps["latitude"]), float(gps["longitude"])
    dist = haversine_km(city_lon, city_lat, lon, lat)

    return Accommodation(
        id=str(data_id), name=raw_name, city=normalize_city(city_name),
        type=acc_type, price=price, stars=0.0, rating=rating, reviews=reviews,
        amenities=extract_amenities_basic(item), address=item.get("address", city_name),
        lon=lon, lat=lat, distance_km=dist
    )

def enrich_amenities_with_hotels_api(acc: Accommodation):
    if not API_KEY: return
    params = {"engine": "google_hotels", "q": f"{acc.name} {acc.city}", "hl": "vi", "gl": "vn", "api_key": API_KEY}
    try:
        props = GoogleSearch(params).get_dict().get("properties", [])
        if props:
            prop = props[0]
            new_ams = [str(am) for am in prop.get("amenities", []) if isinstance(am, str)]
            if new_ams: acc.amenities = list(set(acc.amenities + new_ams))
    except: pass

def stage1_fill_db_from_maps(q: SearchQuery, target_new=30, max_pages=3):
    city_norm = normalize_city(q.city)
    city_geo = smart_geocode(f"{city_norm}, Vietnam")
    if not city_geo: return {}, None
    
    db = load_accommodation_db()
    queries = [f"hotel in {city_norm}", f"homestay in {city_norm}"]
    if q.types: queries = [f"{t} in {city_norm}" for t in q.types] + queries
    
    new_added, pages = 0, 0
    for query_text in list(set(queries)):
        if new_added >= target_new or pages >= max_pages: break
        if not API_KEY: break
            
        params = {"engine": "google_maps", "type": "search", "q": query_text, "ll": f"@{city_geo['lat']},{city_geo['lon']},13z", "api_key": API_KEY, "hl": "vi"}
        try:
            res = GoogleSearch(params).get_dict().get("local_results", [])
            pages += 1
            for item in res:
                acc = parse_maps_item_to_acc(item, city_norm, city_geo['lat'], city_geo['lon'])
                if acc and acc.id not in db:
                    db[acc.id] = acc_to_dict(acc)
                    new_added += 1
        except: continue

    save_accommodation_db(db)
    return db, (city_geo['lon'], city_geo['lat'])

def recommend_top5_pipeline(q: SearchQuery):
    db, center = stage1_fill_db_from_maps(q)
    if not center: return [], None, "Không tìm thấy địa điểm."
    
    candidates = []
    city_norm = normalize_city(q.city)
    for d in db.values():
        if normalize_city(d.get("city", "")) == city_norm:
            candidates.append(dict_to_acc(d))
            
    # Enrich 10 ứng viên tốt nhất trước khi lọc kỹ
    for acc in candidates[:10]:
        if not acc.amenities: enrich_amenities_with_hotels_api(acc)

    top5, note = filter_with_relaxation(candidates, q, top_k=5)
    return top5, center, note

# ==============================================================================
# 5. OSRM & CHAT (LOGIC ROUTE MỚI)
# ==============================================================================

def describe_osrm_step(step: dict, profile: str = "driving") -> str:
    maneuver = step.get("maneuver", {})
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or step.get("ref") or "").strip()
    dist = _format_distance(step.get("distance", 0.0))
    side = maneuver.get("modifier", "")
    side_text = "bên phải" if side == "right" else ("bên trái" if side == "left" else "")

    if profile == "walking":
        action = {"right": "rẽ phải", "left": "rẽ trái", "straight": "đi thẳng", "uturn": "quay lại"}.get(modifier, "rẽ")
        if maneuver.get("type") == "depart": return f"🚶 Bắt đầu đi bộ từ {name or 'điểm xuất phát'}."
        if maneuver.get("type") == "arrive": return f"🏁 Đã đến nơi (hãy nhìn {side_text})."
        if name: return f"{action.capitalize()} vào {name}, đi bộ {dist}."
        return f"{action.capitalize()}, đi bộ khoảng {dist}."
    
    # Logic cho xe
    action = {"right": "rẽ phải", "left": "rẽ trái", "straight": "đi thẳng", "uturn": "quay đầu xe"}.get(modifier, "rẽ")
    if maneuver.get("type") == "depart": return f"🚀 Bắt đầu di chuyển từ {name or 'điểm xuất phát'}."
    if maneuver.get("type") == "arrive": return f"🏁 Đã đến điểm đến."
    if maneuver.get("type") == "roundabout": return f"🔄 Vào vòng xuyến, ra lối thứ {maneuver.get('exit')}."
    if name: return f"{action.capitalize()} vào {name}, đi {dist}."
    return f"Đi tiếp {dist}."

def analyze_route_complexity(dist_km, dur_min, steps, profile):
    score = 0
    reasons = []
    if dur_min > 60: score += 2; reasons.append("Thời gian di chuyển lâu.")
    if dist_km > 20: score += 1; reasons.append("Quãng đường khá xa.")
    if steps > 25: score += 1; reasons.append("Đường đi nhiều ngã rẽ.")
    
    level = "high" if score >= 3 else ("medium" if score >= 2 else "low")
    label = {"low": "Dễ đi", "medium": "Trung bình", "high": "Phức tạp"}[level]
    return {"level": level, "label": label, "summary": "Lộ trình chi tiết bên dưới.", "reasons": reasons}

def recommend_transport_mode(dist_km, dur_min):
    if dist_km <= 2: return "walking", "Gần, nên đi bộ."
    if dist_km <= 10: return "cycling", "Vừa phải, có thể đi xe máy/xe đạp."
    elif dist_km <= 30:
        return "cycling", "Quãng đường trung bình, phù hợp đi xe máy. Nếu mang nhiều hành lý hoặc muốn thoải mái có thể gọi ô tô."
    elif dist_km <= 100:
        return "driving", "Quãng đường khá xa, nên đi ô tô hoặc xe máy để đảm bảo thời gian và sự thoải mái."
    else:
        return "driving", "Quãng đường rất xa, đi ô tô hoặc máy bay là lựa chọn duy nhất để đảm bảo an toàn và tiết kiệm thời gian." 

def process_bot_reply(text): return text.replace("Tôi", "mình").replace("tôi", "mình")

# ==============================================================================
# 6. API ENDPOINTS
# ==============================================================================

@app.route('/api/recommend-hotel', methods=['POST', 'OPTIONS'])
def recommend_api():
    if request.method == 'OPTIONS': return '', 204
    try:
        d = request.json
        query = SearchQuery(
            city=d.get("city", ""), 
            price_min=float(d.get("price_min", 0)),
            price_max=float(d.get("price_max", 0)), 
            types=d.get("types", []),
            rating_min=float(d.get("rating_min", 0)), 
            radius_km=float(d.get("radius_km", 5)),
            amenities_preferred=d.get("amenities_preferred", []),
            priority=d.get("priority", "balanced")
        )

        print(f"🔍 Searching: {query.city} | Priority: {query.priority}")
        results, center, note = recommend_top5_pipeline(query)
        final_results = results[:5]

        response_list = []
        for acc in final_results:
            response_list.append({
                "id": acc.id, "name": acc.name, "price": acc.price,
                "rating": acc.rating, "reviews": acc.reviews,
                "address": acc.address, "amenities": acc.amenities,
                "stars": acc.stars, "type": acc.type,
                "lat": acc.lat, "lon": acc.lon,
                "score": getattr(acc, "match_score", 0.0), # Trả về điểm score để Frontend hiển thị nếu cần
                "img": "https://via.placeholder.com/300?text=Hotel" 
            })

        return jsonify({
            "results": response_list,
            "center": {"lat": center[1], "lon": center[0]} if center else None,
            "note": note
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/route', methods=['POST', 'OPTIONS'])
def api_get_route():
    if request.method == 'OPTIONS': return '', 204
    try:
        d = request.json
        src, dst, profile = d.get("src"), d.get("dst"), d.get("profile", "driving")
        osrm_mode = 'foot' if profile == 'walking' else ('bike' if profile == 'cycling' else 'driving')
        
        url = f"{OSRM_BASE_URL}/route/v1/{osrm_mode}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}?overview=full&geometries=geojson&steps=true"
        r = requests.get(url, timeout=5)
        if r.status_code != 200: return jsonify({"status": "error"}), 500
        
        route = r.json()["routes"][0]
        factor = 12.0 if profile == "walking" else 3.0
        dur_min = (route["duration"]/60.0) * factor
        dist_km = route["distance"]/1000.0
        
        steps = [describe_osrm_step(s, profile) for leg in route["legs"] for s in leg["steps"]]
        complexity = analyze_route_complexity(dist_km, dur_min, len(steps), profile)
        rec_mode, rec_msg = recommend_transport_mode(dist_km, dur_min)

        return jsonify({
            "status": "success",
            "path": [[lat, lon] for lon, lat in route["geometry"]["coordinates"]],
            "info": {
                "distance_text": f"{dist_km:.1f} km", "duration_text": f"~{int(dur_min)} phút",
                "complexity": complexity, "recommendation": {"mode": rec_mode, "message": rec_msg}
            },
            "instructions": steps
        })
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat_api():
    if request.method == 'OPTIONS': return '', 204
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + request.json.get("messages", [])
        if len(msgs) == 1: return jsonify({"reply": BOT_GREETING})
        res = ollama.chat(model=OLLAMA_MODEL, messages=msgs)
        return jsonify({"reply": process_bot_reply(res['message']['content'])})
    except: return jsonify({"reply": "Lỗi chat server."}), 500

@app.route('/health', methods=['GET'])
def health(): return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    print("✅ Server Optimized (Logic from App.py Integrated)")
    app.run(host='0.0.0.0', port=8000, debug=True)