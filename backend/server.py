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

# Lấy API Key từ environment variable
API_KEY = os.getenv("SERPAPI_KEY", "55a38717134583be0bd08237ab34117bc212f65e5b62c597804c8747855fe741")

# DB_PATH = "accommodation_cache.json"  <-- Đã bỏ dùng file này
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

@dataclass
class SearchQuery:
    city: str
    price_min: float
    price_max: float
    types: List[str]
    rating_min: float
    radius_km: float
    amenities_preferred: List[str] = None
    priority: str = "balanced" # <--- THÊM DÒNG NÀY

# ==============================================================================
# 2. HÀM DATABASE / CACHE (ĐÃ VÔ HIỆU HÓA FILE JSON)
# ==============================================================================

# Biến toàn cục lưu dữ liệu tạm trong RAM thay vì file
ram_db = {}

def normalize_city(city: str) -> str:
    if not city: return ""
    return city.strip().lower()

def acc_to_dict(a: Accommodation) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "city": normalize_city(a.city),
        "type": a.type,
        "price": a.price,
        "stars": a.stars,
        "rating": a.rating,
        "reviews": a.reviews,
        "amenities": list(a.amenities or []),
        "address": a.address,
        "lon": a.lon,
        "lat": a.lat,
        "distance_km": a.distance_km,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def dict_to_acc(d: dict) -> Accommodation:
    return Accommodation(
        id=d["id"],
        name=d["name"],
        city=normalize_city(d.get("city", "")),
        type=d.get("type", "hotel"),
        price=d.get("price", 0.0),
        stars=d.get("stars", 0.0),
        rating=d.get("rating", 0.0),
        reviews=int(d.get("reviews") or 0),
        amenities=d.get("amenities", []),
        address=d.get("address", ""),
        lon=d.get("lon", 0.0),
        lat=d.get("lat", 0.0),
        distance_km=d.get("distance_km", 0.0),
    )

def load_accommodation_db() -> dict:
    # ❌ Đã bỏ phần đọc file JSON
    # Trả về ram_db (dữ liệu đang có trong bộ nhớ hiện tại)
    return ram_db

def save_accommodation_db(db: dict) -> None:
    # ❌ Đã bỏ phần ghi file JSON
    # Cập nhật vào biến ram_db để dùng tiếp cho các request sau (đến khi tắt server)
    global ram_db
    ram_db = db
    # Không làm gì thêm (pass)
    pass

def is_fresh_record(cached: dict, days: int = 7) -> bool:
    ts = cached.get("updated_at")
    if not ts: return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        return (now_utc - dt) < timedelta(days=days)
    except Exception:
        return False

# ==============================================================================
# 3. HÀM HELPER & PARSING
# ==============================================================================

def haversine_km(lon1, lat1, lon2, lat2):
    try:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    except:
        return 0.0

def parse_review_count(x) -> int:
    if x is None: return 0
    if isinstance(x, dict):
        for k in ("count", "total", "value", "reviews"):
            if k in x: return parse_review_count(x[k])
        return 0
    s = str(x).strip().lower()
    m = re.search(r"([\d.,]+)\s*([km])\b", s)
    if m:
        num_str = m.group(1).replace(",", ".")
        try:
            num = float(num_str)
            mult = 1000 if m.group(2) == "k" else 1_000_000
            return int(num * mult)
        except: return 0
    digits = re.sub(r"\D", "", s)
    return int(digits) if digits else 0

def smart_geocode(query: str):
    """Wrapper cho SerpAPI Geocoding có Hardcode để tránh lỗi"""
    q_lower = query.lower()
    
    # Danh sách tọa độ cứng
    if "hồ chí minh" in q_lower or "ho chi minh" in q_lower or "tphcm" in q_lower:
        return {"lat": 10.7769, "lon": 106.7009}
    if "hà nội" in q_lower or "ha noi" in q_lower:
        return {"lat": 21.0285, "lon": 105.8542}
    if "đà nẵng" in q_lower or "da nang" in q_lower:
        return {"lat": 16.0544, "lon": 108.2022}
    if "đà lạt" in q_lower or "da lat" in q_lower:
        return {"lat": 11.9404, "lon": 108.4583}
    if "vũng tàu" in q_lower or "vung tau" in q_lower:
        return {"lat": 10.34599, "lon": 107.08426}

    if not API_KEY:
        print("⚠️ Warning: No SERPAPI_KEY found")
        return None

    params = {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "api_key": API_KEY,
        "hl": "vi"
    }
    try:
        res = GoogleSearch(params).get_dict()
        if "local_results" in res and res["local_results"]:
            place = res["local_results"][0]
            gps = place.get("gps_coordinates", {})
            return {"lat": gps.get("latitude"), "lon": gps.get("longitude")}
        if "place_results" in res:
            gps = res["place_results"].get("gps_coordinates", {})
            return {"lat": gps.get("latitude"), "lon": gps.get("longitude")}
    except Exception as e:
        print(f"Lỗi Geocoding: {e}")
    return None

def extract_amenities_basic(item: dict) -> list[str]:
    """
    Trích xuất và CHUẨN HÓA tiện ích để tránh trùng lặp.
    Ví dụ: 'Wi-fi miễn phí', 'Wlan' -> Gom hết thành 'Wifi'
    """
    # 1. Định nghĩa từ điển Mapping (Từ chuẩn -> Các từ khóa nhận diện)
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

    found_amenities = set()
    
    # Gộp tất cả text liên quan lại để quét 1 lần
    raw_list = item.get("amenities", [])
    full_text = (str(raw_list) + " " + str(item.get("description", "")) + " " + item.get("title", "")).lower()

    # 2. Quét và gộp nhóm
    for std_name, keywords in mapping.items():
        # Nếu tìm thấy bất kỳ từ khóa nào trong nhóm
        if any(kw in full_text for kw in keywords):
            found_amenities.add(std_name)

    # 3. (Tùy chọn) Nếu muốn giữ lại các tiện ích lạ không nằm trong danh sách trên
    # thì uncomment đoạn dưới. Tuy nhiên, để giao diện sạch như Shopee/Traveloka 
    # thì nên chỉ trả về danh sách chuẩn ở trên.
    
    # for r in raw_list:
    #     if isinstance(r, str):
    #         r_lower = r.lower()
    #         # Chỉ thêm nếu từ này chưa được cover bởi mapping
    #         is_mapped = False
    #         for keywords in mapping.values():
    #             if any(kw in r_lower for kw in keywords):
    #                 is_mapped = True
    #                 break
    #         if not is_mapped:
    #             found_amenities.add(r)

    return sorted(list(found_amenities))

# ==============================================================================
# 4. CORE ALGORITHMS
# ==============================================================================

def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    def _do_filter(rating_min, price_relax=1.0, radius_relax=1.0):
        pmin = q.price_min
        pmax = q.price_max

        if price_relax > 1.0 and pmax > 0 and pmax > pmin:
            center = (pmin + pmax) / 2
            half_span = (pmax - pmin) / 2
            extra = half_span * (price_relax - 1.0)
            pmin = max(0, center - half_span - extra)
            pmax = center + half_span + extra

        dist_limit = (q.radius_km * radius_relax) if q.radius_km > 0 else None

        filtered = []
        for a in accommodations:
            # ... (các điều kiện cũ) ...
            if dist_limit and a.distance_km > dist_limit: continue
            if pmin > 0 and a.price < pmin: continue
            if pmax > 0 and a.price > pmax: continue
            if q.types and (a.type not in q.types): continue
            if a.rating < rating_min: continue
            
            # --- THÊM LOGIC LỌC TIỆN ÍCH TẠI ĐÂY ---
            if q.amenities_preferred:
                # Chuyển tiện ích khách sạn về chữ thường để so sánh
                hotel_amenities_lower = [am.lower() for am in a.amenities]
                
                # Kiểm tra: Nếu thiếu bất kỳ tiện ích ưu tiên nào -> Bỏ qua khách sạn này
                # (Logic AND: Cần Bữa sáng VÀ Wifi -> Phải có đủ cả 2)
                missing_amenity = False
                for req_am in q.amenities_preferred:
                    # Mapping từ khóa Frontend (ví dụ "Breakfast") sang từ khóa Backend tìm thấy ("Bữa sáng", "breakfast")
                    req_lower = req_am.lower()
                    
                    # Logic so sánh tương đối
                    found = False
                    
                    # Mapping nhanh cho Bữa sáng (vì Frontend gửi 'Breakfast' nhưng data có thể là 'Bữa sáng')
                    check_list = [req_lower]
                    if req_lower == "breakfast": check_list.append("bữa sáng")
                    if req_lower == "pool": check_list = ["pool", "hồ bơi", "bể bơi"]
                    if req_lower == "parking": check_list = ["parking", "đỗ xe", "giữ xe"]
                    
                    for item in hotel_amenities_lower:
                        if any(k in item for k in check_list):
                            found = True
                            break
                    
                    if not found:
                        missing_amenity = True
                        break
                
                if missing_amenity: continue 
            # ---------------------------------------

            filtered.append(a)
        # === LOGIC SẮP XẾP MỚI DỰA TRÊN PRIORITY ===
        if q.priority == "cheap":
            # Ưu tiên 1: Giá rẻ (tăng dần). 
            # (Mẹo: Giá = 0 để xuống cuối vì có thể là lỗi data)
            filtered.sort(key=lambda x: x.price if x.price > 10000 else 9999999999)
            
        elif q.priority == "near_center":
            # Ưu tiên 2: Gần trung tâm (distance_km tăng dần)
            filtered.sort(key=lambda x: x.distance_km)
            
        elif q.priority == "amenities":
            # Ưu tiên 3: Nhiều tiện ích (đếm số lượng amenities giảm dần)
            # Khách sạn nào "Đang cập nhật" (list rỗng) sẽ tự động bị đẩy xuống dưới cùng
            filtered.sort(key=lambda x: len(x.amenities), reverse=True)
            
        else: 
            # Mặc định (Balanced): Rating cao -> Review nhiều -> Giá tốt
            filtered.sort(key=lambda x: (x.rating, x.reviews), reverse=True)
        # ============================================

        return filtered

    levels = [
        {"desc": "Thỏa mãn đầy đủ tiêu chí.", "rating_min": q.rating_min, "price_relax": 1.0, "radius_relax": 1.0},
        {"desc": "Đã nới lỏng rating tối thiểu.", "rating_min": max(0.0, q.rating_min - 0.5), "price_relax": 1.0, "radius_relax": 1.0},
        {"desc": "Đã mở rộng bán kính tìm kiếm.", "rating_min": max(0.0, q.rating_min - 1.0), "price_relax": 1.0, "radius_relax": 1.5},
        {"desc": "Đã nới rộng khoảng giá và bán kính.", "rating_min": 0.0, "price_relax": 1.3, "radius_relax": 2.0},
    ]

    final_list = []
    final_note = ""
    used_ids = set()

    for cfg in levels:
        candidates = _do_filter(cfg["rating_min"], cfg["price_relax"], cfg["radius_relax"])
        if candidates:
            if not final_note: final_note = cfg["desc"]
            for c in candidates:
                if c.id not in used_ids:
                    final_list.append(c)
                    used_ids.add(c.id)
        if len(final_list) >= top_k:
            break
    
    # Cắt danh sách đúng bằng top_k (ví dụ 5) trước khi trả về
    return final_list[:top_k], final_note

def parse_maps_item_to_acc(item: dict, city_name: str, city_lat: float, city_lon: float) -> Optional[Accommodation]:
    raw_name = (item.get("title") or item.get("name") or "").strip()
    if not raw_name: return None
    
    data_id = item.get("data_id")
    if not data_id: data_id = str(hash(raw_name + str(item.get("address", ""))))
    
    raw_price = item.get("price")
    price = 0.0
    if raw_price:
        s = str(raw_price)
        m = re.search(r"\d+(?:[.,]\d+)?", s)
        if m:
            val = float(m.group(0).replace(",", "."))
            if val < 5000 and "₫" not in s: 
                price = val * 26000
            else:
                price = val

    try: rating = float(item.get("rating", 0.0))
    except: rating = 0.0
    
    reviews = parse_review_count(item.get("reviews") or item.get("user_ratings_total"))
    
    def detect_type(txt):
        txt = txt.lower()
        if any(x in txt for x in ["homestay", "nhà nghỉ", "guest house"]): return "homestay"
        if "resort" in txt: return "resort"
        if "hostel" in txt: return "hostel"
        if "apartment" in txt or "căn hộ" in txt: return "apartment"
        return "hotel"

    type_str = item.get("type", "") + " " + raw_name
    acc_type = detect_type(type_str)

    gps = item.get("gps_coordinates", {})
    lat = gps.get("latitude")
    lon = gps.get("longitude")
    if lat is None or lon is None: return None
    
    dist = haversine_km(city_lon, city_lat, lon, lat)

    return Accommodation(
        id=str(data_id),
        name=raw_name,
        city=normalize_city(city_name),
        type=acc_type,
        price=price,
        stars=0.0,
        rating=rating,
        reviews=reviews,
        amenities=extract_amenities_basic(item),
        address=item.get("address", city_name),
        lon=float(lon),
        lat=float(lat),
        distance_km=dist
    )

def enrich_amenities_with_hotels_api(acc: Accommodation):
    if not API_KEY: return
    params = {
        "engine": "google_hotels",
        "q": f"{acc.name} {acc.city}",
        "hl": "vi", "gl": "vn", "api_key": API_KEY
    }
    try:
        data = GoogleSearch(params).get_dict()
        props = data.get("properties", [])
        if not props: return
        prop = props[0]
        
        if not acc.stars:
            cls = prop.get("extracted_hotel_class") or prop.get("hotel_class")
            if cls:
                if isinstance(cls, int) or isinstance(cls, float): acc.stars = float(cls)
                elif isinstance(cls, str):
                    m = re.search(r"(\d+)", cls)
                    if m: acc.stars = float(m.group(1))

        new_ams = []
        for am in prop.get("amenities", []):
            if isinstance(am, str): new_ams.append(am)
        groups = (prop.get("amenities_detailed") or {}).get("groups") or []
        for g in groups:
            for item in g.get("list", []):
                t = item.get("title")
                if t: new_ams.append(t)
        
        if new_ams:
            acc.amenities = list(set(acc.amenities + new_ams))
            
    except Exception as e:
        print(f"Enrich error for {acc.name}: {e}")

def stage1_fill_db_from_maps(q: SearchQuery, target_new=20, max_pages=3):
    city_norm = normalize_city(q.city)
    city_geo = smart_geocode(f"{city_norm}, Vietnam")
    if not city_geo: return {}, None
    
    city_lat, city_lon = city_geo["lat"], city_geo["lon"]
    db = load_accommodation_db()
    
    queries = [f"hotel in {city_norm}", f"homestay in {city_norm}", f"resort in {city_norm}"]
    if q.types:
        queries = [f"{t} in {city_norm}" for t in q.types] + queries
    
    new_added = 0
    pages_used = 0
    
    for query_text in list(set(queries)):
        if new_added >= target_new or pages_used >= max_pages: break
        
        if not API_KEY:
            print("⚠️ Skipping API call - No API Key")
            break
            
        params = {
            "engine": "google_maps", "type": "search",
            "q": query_text, 
            "ll": f"@{city_lat},{city_lon},13z",
            "api_key": API_KEY, "hl": "vi", "start": 0
        }
        try:
            res = GoogleSearch(params).get_dict()
            local_results = res.get("local_results", [])
            pages_used += 1
            
            for item in local_results:
                acc = parse_maps_item_to_acc(item, city_norm, city_lat, city_lon)
                if acc and acc.id not in db:
                    db[acc.id] = acc_to_dict(acc)
                    new_added += 1
        except Exception as e:
            print(f"Maps API Error: {e}")
            continue

    save_accommodation_db(db)
    return db, (city_lon, city_lat)

def stage2_rank_from_db(q: SearchQuery, db: dict, top_n=30):
    city_norm = normalize_city(q.city)
    candidates = []
    for d in db.values():
        if normalize_city(d.get("city", "")) == city_norm:
            candidates.append(dict_to_acc(d))
    
    ranked, note = filter_with_relaxation(candidates, q, top_k=top_n)
    return ranked[:top_n], note

def stage3_enrich_and_final_rank(candidates: List[Accommodation], q: SearchQuery, db: dict, top_k=5):
    updated_count = 0
    for acc in candidates:
        cached = db.get(acc.id)
        needs_update = (not is_fresh_record(cached)) or (acc.type in ["hotel", "resort"] and acc.stars == 0)
        
        if needs_update and API_KEY:
            enrich_amenities_with_hotels_api(acc)
            db[acc.id] = acc_to_dict(acc)
            updated_count += 1
            if updated_count >= 5: break 
    
    if updated_count > 0:
        save_accommodation_db(db)
    
    final_list, note = filter_with_relaxation(candidates, q, top_k=top_k)
    return final_list, note

def recommend_top5_pipeline(q: SearchQuery):
    db, center = stage1_fill_db_from_maps(q)
    if not center: return [], None, "Không tìm thấy địa điểm."
    
    top30, note2 = stage2_rank_from_db(q, db)
    top5, note3 = stage3_enrich_and_final_rank(top30, q, db)
    
    final_note = note3 if note3 else note2
    return top5, center, final_note

# ==============================================================================
# 5. OSRM & CHAT FUNCTIONS (ALGORITHM MỚI)
# ==============================================================================

def _format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{int(round(meters))} m"
    km = meters / 1000.0
    return f"{km:.1f} km"

def describe_osrm_step(step: dict) -> str:
    maneuver = step.get("maneuver", {})
    step_type = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    if not name:
        name = (step.get("ref") or "").strip()

    distance = step.get("distance", 0.0)
    dist_str = _format_distance(distance)

    dir_map = {
        "right": "rẽ phải", "slight right": "chếch sang phải", "sharp right": "quẹo gắt sang phải",
        "left": "rẽ trái", "slight left": "chếch sang trái", "sharp left": "quẹo gắt sang trái",
        "straight": "đi thẳng", "uturn": "quay đầu xe",
    }
    action = dir_map.get(modifier, "rẽ")

    if step_type == "depart":
        return f"🚀 Bắt đầu di chuyển từ {name if name else 'điểm xuất phát'}."
    
    if step_type == "arrive":
        side = maneuver.get("modifier", "")
        side_text = "ở bên phải" if side == "right" else ("ở bên trái" if side == "left" else "")
        return f"🏁 Đã đến điểm đến {side_text}."

    if step_type == "roundabout":
        exit_nr = maneuver.get("exit")
        return f"🔄 Vào vòng xuyến, đi theo lối ra thứ {exit_nr}."

    if step_type in ("turn", "end of road", "fork", "merge", "new name", "continue"):
        if modifier == "straight":
            if name: return f"⬆️ Đi thẳng {dist_str} trên {name}."
            return f"⬆️ Đi thẳng {dist_str}."
        else:
            if name: return f"{action.capitalize()} vào {name}, đi tiếp {dist_str}."
            return f"{action.capitalize()}, sau đó đi {dist_str}."

    if name:
        return f"Đi tiếp {dist_str} trên {name}."
    return f"Đi tiếp {dist_str}."

def analyze_route_complexity(distance_km, duration_min, steps_count, profile):
    difficulty_score = 0
    reasons = []

    if duration_min > 90:
        difficulty_score += 3
        reasons.append(f"Thời gian di chuyển rất lâu (~{int(duration_min // 60)}h{int(duration_min % 60)}p), dễ gây mệt mỏi.")
    elif duration_min > 45:
        difficulty_score += 2
        reasons.append(f"Thời gian di chuyển khá lâu (~{int(duration_min)} phút).")
    elif duration_min > 25:
        difficulty_score += 1

    if distance_km > 30:
        difficulty_score += 2
        reasons.append(f"Quãng đường xa ({distance_km:.1f} km).")
    elif distance_km > 15:
        difficulty_score += 1
        reasons.append("Quãng đường tương đối dài so với di chuyển nội thành.")

    if steps_count > 30:
        difficulty_score += 2
        reasons.append(f"Đường đi rất rắc rối, có tới {steps_count} lần chuyển hướng.")
    elif steps_count > 18:
        difficulty_score += 1
        reasons.append("Lộ trình có nhiều ngã rẽ, cần chú ý quan sát bản đồ.")

    if duration_min > 0:
        avg_speed = distance_km / (duration_min / 60.0)
        if profile == "driving" and avg_speed < 15:
            difficulty_score += 2
            reasons.append("Cảnh báo: Tốc độ di chuyển dự kiến rất chậm (khu vực đông đúc/kẹt xe).")

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
    if distance_km <= 2.0:
        return "walking", "Quãng đường ngắn, đi bộ hoặc xe đạp là lựa chọn tốt cho sức khỏe, tiết kiệm chi phí."
    elif distance_km <= 5:
        return "cycling", "Quãng đường khá ngắn, đi xe đạp hoặc xe máy sẽ nhanh và tiện lợi hơn."
    elif distance_km <= 30:
        return "cycling", "Quãng đường trung bình, phù hợp đi xe máy. Có thể gọi ô tô nếu mang hành lý."
    elif distance_km <= 100:
        return "driving", "Quãng đường khá xa, nên đi ô tô hoặc xe máy để đảm bảo sức khỏe."
    else:
        return "driving", "Quãng đường rất xa, đi ô tô là lựa chọn an toàn nhất."

def process_bot_reply(full_text: str) -> str:
    reply = full_text.strip()
    reply = re.sub(r'\bTôi\b', 'mình', reply)
    reply = re.sub(r'\btôi\b', 'mình', reply)
    
    if not reply.endswith('?'):
        reply += "\n\n_Bạn cần hỗ trợ gì thêm không?_"
    return reply

# ==============================================================================
# 6. API ENDPOINTS
# ==============================================================================

@app.route('/api/recommend-hotel', methods=['POST', 'OPTIONS'])
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
            priority=d.get("priority", "balanced") # <--- THÊM DÒNG NÀY
        )
        # ... (phần còn lại giữ nguyên) ...

        print(f"🔍 Searching: {query.city}")
        
        # Gọi pipeline tìm kiếm
        results, center, note = recommend_top5_pipeline(query)

        # ✅ CẮT TOP 5: Đảm bảo chỉ lấy tối đa 5 kết quả tại đây
        final_results = results[:5]

        response_list = []
        for acc in final_results:
            response_list.append({
                "id": acc.id,
                "name": acc.name,
                "price": acc.price,
                "rating": acc.rating,
                "reviews": acc.reviews,
                "address": acc.address,
                "amenities": acc.amenities,
                "stars": acc.stars,
                "type": acc.type,
                "lat": acc.lat,
                "lon": acc.lon,
                "img": "https://via.placeholder.com/300?text=Hotel" 
            })

        return jsonify({
            "results": response_list,
            "center": {"lat": center[1], "lon": center[0]} if center else None,
            "note": note
        })
    except Exception as e:
        print(f"❌ Server Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/route', methods=['POST', 'OPTIONS'])
def api_get_route():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.json
        src, dst = data.get("src"), data.get("dst")
        profile = data.get("profile", "driving") 
        
        osrm_mode = 'foot' if profile in ['walking', 'foot'] else ('bike' if profile == 'cycling' else 'driving')
        
        osrm_url = (
            f"{OSRM_BASE_URL}/route/v1/{osrm_mode}/"
            f"{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}"
            f"?overview=full&geometries=geojson&steps=true"
        )
        
        try:
            r = requests.get(osrm_url, timeout=5)
        except requests.exceptions.ConnectionError:
            return jsonify({
                "status": "error", 
                "message": "Không kết nối được OSRM Local. Hãy kiểm tra Docker."
            }), 503

        if r.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"OSRM Error: {r.status_code}"
            }), 500
            
        res = r.json()
        if not res.get("routes"): 
            return jsonify({"status": "error", "message": "Không tìm thấy đường đi"}), 404

        route = res["routes"][0]
        
        traffic_factor = 3.0 if profile in ["driving", "cycling"] else 12.0
        duration_min = (route["duration"] / 60.0) * traffic_factor
        distance_km = route["distance"] / 1000.0
        
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                s = describe_osrm_step(step)
                if s: steps.append(s)

        complexity = analyze_route_complexity(distance_km, duration_min, len(steps), profile)
        rec_mode, rec_msg = recommend_transport_mode(distance_km, duration_min)

        return jsonify({
            "status": "success",
            "path": [[lat, lon] for lon, lat in route["geometry"]["coordinates"]],
            "info": {
                "distance_km": distance_km,
                "distance_text": f"{distance_km:.1f} km",
                "duration_min": duration_min,
                "duration_text": f"~{int(duration_min)} phút",
                "complexity": complexity, 
                "recommendation": {
                    "mode": rec_mode,
                    "message": rec_msg
                }
            },
            "instructions": steps
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat_api():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.json
        messages = data.get("messages", [])
        
        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            if m.get("role") in ("user", "assistant"):
                api_messages.append({"role": m["role"], "content": m["content"]})
        
        if len(api_messages) == 1: return jsonify({"reply": BOT_GREETING})

        response = ollama.chat(model=OLLAMA_MODEL, messages=api_messages)
        return jsonify({"reply": process_bot_reply(response['message']['content'])})
    except Exception as e:
        return jsonify({"reply": "Hệ thống đang bận, vui lòng thử lại sau."}), 500

@app.route('/api/generate-itinerary', methods=['POST', 'OPTIONS'])
def itinerary_api():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.json
        prompt = data.get("prompt", "")
        if not prompt: return jsonify({"error": "Missing prompt"}), 400
        
        full_prompt = f"{SYSTEM_PROMPT}\n\nHãy tạo lịch trình du lịch chi tiết dựa trên yêu cầu: {prompt}"
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": full_prompt}])
        return jsonify({"result": response['message']['content']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Server is running (No Cache)"}), 200

if __name__ == '__main__':
    print("=" * 60)
    print("✅ Smart Tourism Server Starting...")
    print("=" * 60)
    print("⚠️  CACHE MODE: OFF (File JSON Reading Disabled)")
    print(f"🌐 Server URL: http://127.0.0.1:8000")
    print(f"🔑 API Key: {'✅ Configured' if API_KEY else '❌ Missing'}")
    print(f"🚗 OSRM Service: {OSRM_BASE_URL}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8000, debug=True)