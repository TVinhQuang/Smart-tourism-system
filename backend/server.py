from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import requests
from dataclasses import dataclass, field
from typing import List, Optional
import math
import random
import polyline
from geopy.geocoders import Nominatim
from serpapi import GoogleSearch
import re
import json
import os
from datetime import date, timedelta, datetime, timezone

# Khởi tạo Flask App
app = Flask(__name__)
CORS(app)

# ==================== CONFIG & CONSTANTS ====================
DB_PATH = "accommodation_cache.json"
# Lưu ý: Nên dùng biến môi trường cho API Key trong thực tế
API_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"
PAGE_SIZE = 20

# ==================== DATA CLASSES ====================
@dataclass
class Accommodation:
    id: str
    name: str
    city: str
    type: str
    price: float
    stars: float = 0.0
    rating: float = 0.0
    reviews: int = 0
    capacity: int = 0
    amenities: List[str] = field(default_factory=list)
    address: str = ""
    lon: float = 0.0
    lat: float = 0.0
    distance_km: float = 0.0

@dataclass
class SearchQuery:
    city: str
    group_size: int
    price_min: float
    price_max: float
    types: List[str]
    rating_min: float
    amenities_preferred: List[str]
    radius_km: Optional[float]
    priority: str = "balanced"
    stars_min: int = 0
    checkin: Optional[date] = None
    checkout: Optional[date] = None
    adults: int = 2
    children: int = 0

# ==================== DATABASE HELPERS ====================
def load_accommodation_db() -> dict:
    if not os.path.exists(DB_PATH):
        return {}
    db = {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    rec = json.loads(line)
                    acc_id = rec.get("id")
                    if acc_id: db[acc_id] = rec
                except json.JSONDecodeError:
                    continue
    except Exception:
        return {}
    return db

def save_accommodation_db(db: dict) -> None:
    dir_name = os.path.dirname(DB_PATH)
    if dir_name: os.makedirs(dir_name, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        for rec in db.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def normalize_city(city: str) -> str:
    return city.strip().lower() if city else ""

def acc_to_dict(a: Accommodation) -> dict:
    return {
        "id": a.id, "name": a.name, "city": normalize_city(a.city),
        "type": a.type, "price": a.price, "stars": a.stars,
        "rating": a.rating, "reviews": getattr(a, "reviews", 0),
        "amenities": list(a.amenities or []), "address": a.address,
        "lon": a.lon, "lat": a.lat, "distance_km": a.distance_km,
        "source": "serpapi_google_maps",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def dict_to_acc(d: dict) -> Accommodation:
    return Accommodation(
        id=d["id"], name=d["name"], city=normalize_city(d.get("city", "")),
        type=d.get("type", "hotel"), price=d.get("price", 0.0),
        stars=d.get("stars", 0.0), rating=d.get("rating", 0.0),
        reviews=int(d.get("reviews") or 0), capacity=4,
        amenities=d.get("amenities", []), address=d.get("address", ""),
        lon=d.get("lon", 0.0), lat=d.get("lat", 0.0),
        distance_km=d.get("distance_km", 0.0),
    )

# ==================== UTILS & GEOCODING ====================
def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def serpapi_geocode(q: str):
    print(f"DEBUG: Geocoding '{q}' via SerpApi...")
    params = {"engine": "google_maps", "q": q, "type": "search", "api_key": API_KEY, "hl": "vi"}
    try:
        results = GoogleSearch(params).get_dict()
        if "error" in results: return None
        
        place = None
        if "local_results" in results and results["local_results"]:
            place = results["local_results"][0]
        elif "place_results" in results:
            place = results["place_results"]
            
        if place:
            return {
                "name": place.get("title"),
                "lat": place["gps_coordinates"]["latitude"],
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
        return None
    except Exception as e:
        print(f"Geocode Error: {e}")
        return None

def smart_geocode(q: str):
    loc = serpapi_geocode(q)
    if loc: return loc
    print(f"DEBUG: Fallback Geocoding '{q}' via Nominatim...")
    try:
        geocoder = Nominatim(user_agent="smart_tourism_backend")
        res = geocoder.geocode(q, exactly_one=True, addressdetails=True, language="en")
        if res:
            return {"name": res.address, "lat": res.latitude, "lon": res.longitude, "address": res.address}
    except Exception as e:
        print(f"Nominatim Error: {e}")
    return None

# ==================== PARSING & ENRICHMENT HELPERS ====================
# (Đã chuyển từ app.py sang để server chạy được logic stage 3)

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

def extract_amenities_from_google_property(prop: dict) -> list[str]:
    # (Đã đem mapping từ app.py)
    GOOGLE_AMENITY_KEYWORDS = {
        "wifi": "wifi", "free parking": "parking", "parking": "parking",
        "pool": "pool", "gym": "gym", "fitness": "gym", "restaurant": "restaurant",
        "bar": "bar", "breakfast": "breakfast", "spa": "spa",
        "air-conditioned": "air_conditioning", "shuttle": "airport_shuttle"
    }
    result_codes = set()
    raw_amenities = prop.get("amenities", []) or []
    desc = str(prop.get("description", "")).lower()
    
    # Check list
    for raw in raw_amenities:
        text = str(raw).lower()
        for key, code in GOOGLE_AMENITY_KEYWORDS.items():
            if key in text: result_codes.add(code)
    # Check description
    for key, code in GOOGLE_AMENITY_KEYWORDS.items():
        if key in desc: result_codes.add(code)
            
    return list(result_codes)

def enrich_amenities_with_hotels_api(acc: Accommodation, api_key: str):
    params = {"engine": "google_hotels", "q": f"{acc.name} {acc.city}", "hl": "vi", "gl": "vn", "api_key": api_key}
    try:
        data = GoogleSearch(params).get_dict()
        props = data.get("properties") or []
        if not props: return

        prop0 = props[0]
        full_amenities = []
        for am in prop0.get("amenities") or []:
            if isinstance(am, str): full_amenities.append(am.strip())
        
        groups = ((prop0.get("amenities_detailed") or {}).get("groups") or [])
        for g in groups:
            for item in g.get("list", []):
                if item.get("title"): full_amenities.append(item.get("title").strip())
        
        if full_amenities:
            acc.amenities = list(dict.fromkeys(full_amenities + acc.amenities))
    except Exception:
        pass

def enrich_hotel_class_one_with_hotels_api(acc: Accommodation, api_key: str, checkin=None, checkout=None, adults=2, children=0):
    params = {"engine": "google_hotels", "q": f"{acc.name} {acc.city}", "hl": "vi", "gl": "vn", "api_key": api_key}
    if checkin: params["check_in_date"] = checkin.isoformat()
    if checkout: params["check_out_date"] = checkout.isoformat()
    params["adults"] = adults
    
    try:
        data = GoogleSearch(params).get_dict()
        props = data.get("properties") or []
        if not props: return
        
        prop0 = props[0]
        hotel_class = prop0.get("extracted_hotel_class")
        if hotel_class is None:
            raw_class = prop0.get("hotel_class")
            if isinstance(raw_class, str):
                m = re.search(r"(\d+)", raw_class)
                if m: hotel_class = int(m.group(1))
        
        if hotel_class is not None:
            acc.stars = float(hotel_class)
    except Exception:
        pass

# ==================== LOGIC: FILL & RANKING ====================

def build_query_phrases(city: str, wanted_types: List[str]) -> List[str]:
    city = city.strip()
    wanted_types = [t.lower() for t in (wanted_types or [])]
    base = [f"khách sạn ở {city}", f"homestay ở {city}", f"resort ở {city}", f"apartment {city}"]
    type_specific = []
    if "hotel" in wanted_types: type_specific.append(f"khách sạn ở {city}")
    if "homestay" in wanted_types: type_specific.append(f"homestay ở {city}")
    if "resort" in wanted_types: type_specific.append(f"resort ở {city}")
    
    pool = list(dict.fromkeys(base + type_specific))
    random.shuffle(pool)
    return pool

def serpapi_google_maps_search(query: str, city_lat: float, city_lon: float, start: int) -> list:
    params = {
        "engine": "google_maps", "type": "search", "google_domain": "google.com.vn",
        "q": query, "ll": f"@{city_lat},{city_lon},8z", "api_key": API_KEY,
        "hl": "vi", "start": start,
    }
    return GoogleSearch(params).get_dict().get("local_results", []) or []

def parse_maps_item_to_acc(item: dict, city_name: str, city_lat: float, city_lon: float, radius_km: Optional[float]) -> Optional[Accommodation]:
    raw_name = (item.get("title") or item.get("name") or "").strip()
    if not raw_name: return None
    
    data_id = item.get("data_id") or hash(raw_name + str(item.get("address", "")))
    
    # Price
    raw_price = item.get("price")
    price = 0.0
    if raw_price:
        s = str(raw_price)
        m = re.search(r"\d+(?:[.,]\d+)?", s)
        val = float(m.group(0).replace(",", ".")) if m else 0.0
        if "₫" in s or val >= 50000: price = val
        else: price = val * 26405
        
    rating = float(item.get("rating") or 0.0)
    reviews = parse_review_count(item.get("reviews") or item.get("user_ratings_total"))
    
    # Amenities
    amenities = extract_amenities_from_google_property(item)
    desc = str(item).lower()
    if "pool" in desc: amenities.append("pool")
    if "wifi" in desc: amenities.append("wifi")
    amenities = list(dict.fromkeys(amenities))
    
    # GPS
    gps = item.get("gps_coordinates") or {}
    lat, lon = gps.get("latitude"), gps.get("longitude")
    if not lat or not lon: return None
    
    dist = haversine_km(city_lon, city_lat, lon, lat)
    
    # Type detection logic (simplified)
    acc_type = "hotel"
    text_type = (str(item.get("type")) + str(item.get("title"))).lower()
    if "homestay" in text_type: acc_type = "homestay"
    elif "resort" in text_type: acc_type = "resort"
    elif "apartment" in text_type: acc_type = "apartment"
    
    if radius_km is not None and dist > radius_km: return None
    
    return Accommodation(
        id=str(data_id), name=raw_name, city=normalize_city(city_name),
        type=acc_type, price=price, rating=rating, reviews=reviews,
        amenities=amenities, address=item.get("address", city_name),
        lon=lon, lat=lat, distance_km=dist
    )

def has_amenity(have_lower: set[str], code: str) -> bool:
    KEYWORDS = {
        "wifi": ["wifi"], "breakfast": ["breakfast", "bữa sáng"], 
        "pool": ["pool", "bể bơi"], "parking": ["parking", "đỗ xe"]
    }
    keywords = KEYWORDS.get(code, [code])
    for text in have_lower:
        for kw in keywords:
            if kw in text: return True
    return False

def score_accommodation(a: Accommodation, q: SearchQuery) -> float:
    mode = getattr(q, "priority", "balanced")
    
    # 1. Price
    Pmin, Pmax = q.price_min, q.price_max
    if Pmax > Pmin and a.price > 0:
        t = clamp01((a.price - Pmin) / (Pmax - Pmin))
        if mode == "cheap": S_price = 1.0 - t
        elif mode == "balanced": S_price = 1.0 - abs(t - 0.5) * 2.0
        else: S_price = t
    else: S_price = 1.0
    
    # 2. Rating & Stars
    S_rating = clamp01(a.rating / 5.0)
    is_hr = a.type in ("hotel", "resort")
    if is_hr and a.stars > 0:
        S_stars = clamp01(a.stars / 5.0)
        w_rating, w_stars = 0.28, 0.05
    else:
        S_stars = 0.0
        w_rating, w_stars = 0.33, 0.0
        
    # 3. Amenities
    have = set(x.lower() for x in a.amenities)
    pref = set(x.lower() for x in q.amenities_preferred)
    S_amen = sum(1 for c in pref if has_amenity(have, c)) / len(pref) if pref else 1.0
    
    # 4. Distance
    r_lim = q.radius_km or 0.0
    S_dist = (1.0 - min(a.distance_km / r_lim, 1.0)) if r_lim > 0 else 1.0
    
    return 0.32*S_price + w_stars*S_stars + w_rating*S_rating + 0.15*S_amen + 0.20*S_dist

def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    # (Giữ logic từ app.py)
    def _do(rating_min, amenity_mode="all", price_relax=1.0, radius_relax=1.0):
        pmin, pmax = q.price_min, q.price_max
        if price_relax > 1.0 and pmax > pmin:
            half = (pmax - pmin)/2
            extra = half * (price_relax - 1.0)
            pmin = max(0, (pmin+pmax)/2 - half - extra)
            pmax = (pmin+pmax)/2 + half + extra
            
        r_lim = (q.radius_km or 0.0) * radius_relax
        
        res = []
        for a in accommodations:
            if r_lim > 0 and a.distance_km > r_lim: continue
            if pmin > 0 and a.price < pmin: continue
            if pmax > 0 and a.price > pmax: continue
            if q.types and a.type not in q.types: continue
            if a.rating < rating_min: continue
            if q.stars_min > 0 and a.type in ("hotel", "resort") and a.stars < q.stars_min: continue
            res.append(a)
        return res

    levels = [
        {"desc": "Thỏa mãn đầy đủ tiêu chí.", "rat": q.rating_min, "p": 1.0, "r": 1.0},
        {"desc": "Nới lỏng tiện ích.", "rat": q.rating_min, "p": 1.0, "r": 1.0},
        {"desc": "Nới lỏng rating, bán kính nhẹ.", "rat": max(0, q.rating_min - 1.0), "p": 1.0, "r": 1.2},
        {"desc": "Nới rộng giá và bán kính.", "rat": max(0, q.rating_min - 1.0), "p": 1.2, "r": 1.5},
    ]

    final, note = [], ""
    seen = set()
    
    for lvl in levels:
        cands = _do(lvl["rat"], price_relax=lvl["p"], radius_relax=lvl["r"])
        if cands:
            if not note: note = lvl["desc"]
            for a in cands:
                if a.id not in seen:
                    final.append(a)
                    seen.add(a.id)
        if len(final) >= top_k: break
        
    return final, note

def rank_accommodations(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    filtered, note = filter_with_relaxation(accommodations, q, top_k)
    if not filtered: return [], note
    
    scored = [{"score": score_accommodation(a, q), "accommodation": a} for a in filtered]
    # Sort: Score desc, Rating desc, Reviews desc, Dist asc
    scored.sort(key=lambda x: (-x["score"], -x["accommodation"].rating, -x["accommodation"].reviews, x["accommodation"].distance_km))
    return scored[:top_k], note

# ==================== 3-STAGE PIPELINE ====================
def stage1_fill_db_from_maps(q: SearchQuery, target_new=50, max_pages=8):
    city_name = normalize_city(q.city)
    geo = smart_geocode(city_name + ", Vietnam")
    if not geo: raise ValueError("City not found")
    
    lat, lon = geo["lat"], geo["lon"]
    db = load_accommodation_db()
    queries = build_query_phrases(city_name, q.types)
    
    starts = list(range(0, PAGE_SIZE*10, PAGE_SIZE))
    attempts = [(qq, s) for qq in queries for s in starts]
    random.shuffle(attempts)
    
    new_added, pages = 0, 0
    for qq, s in attempts:
        if new_added >= target_new or pages >= max_pages: break
        
        try: results = serpapi_google_maps_search(qq, lat, lon, s)
        except: results = []
        pages += 1
        if not results: continue
        
        added_page = 0
        for item in results:
            acc = parse_maps_item_to_acc(item, city_name, lat, lon, radius_km=None)
            if acc and acc.id not in db:
                db[acc.id] = acc_to_dict(acc)
                new_added += 1
                added_page += 1
                if new_added >= target_new: break
        if added_page == 0: break
        
    save_accommodation_db(db)
    return db, (lon, lat), {"new_added": new_added, "pages_used": pages}

def stage2_rank_from_db(q: SearchQuery, db: dict, top_n=30):
    city_norm = normalize_city(q.city)
    all_acc = []
    for d in db.values():
        if normalize_city(d.get("city", "")) == city_norm:
            try: all_acc.append(dict_to_acc(d))
            except: continue
    return rank_accommodations(all_acc, q, top_k=top_n)

def is_fresh(rec: dict, days=7) -> bool:
    ts = rec.get("updated_at")
    if not ts: return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) < timedelta(days=days)
    except: return False

def stage3_enrich_topN_and_rerank(topN_items: list, q: SearchQuery, db: dict, top_k=5):
    if not API_KEY:
        accs = [x["accommodation"] for x in topN_items]
        return rank_accommodations(accs, q, top_k)
    
    for item in topN_items:
        acc = item["accommodation"]
        cached = db.get(acc.id)
        
        # Restore cache if available
        if cached:
            if cached.get("amenities"): acc.amenities = cached["amenities"]
            if cached.get("stars"): acc.stars = float(cached["stars"])
            
        # Enrich if missing
        if not acc.amenities: enrich_amenities_with_hotels_api(acc, API_KEY)
        if acc.type in ("hotel", "resort") and acc.stars <= 0:
            enrich_hotel_class_one_with_hotels_api(acc, API_KEY, q.checkin, q.checkout, q.adults, q.children)
            
        new_rec = acc_to_dict(acc)
        # Update logic: merge if fresh, overwrite if stale/new
        if cached and is_fresh(cached):
            for k in ["amenities", "stars", "rating"]:
                if new_rec.get(k) and not cached.get(k): cached[k] = new_rec[k]
            db[acc.id] = cached
        else:
            db[acc.id] = new_rec
            
    save_accommodation_db(db)
    accs = [x["accommodation"] for x in topN_items]
    return rank_accommodations(accs, q, top_k)

def perform_recommendation(q: SearchQuery):
    t0 = time.perf_counter()
    db, center, s1 = stage1_fill_db_from_maps(q)
    t1 = time.perf_counter()
    top30, note2 = stage2_rank_from_db(q, db)
    t2 = time.perf_counter()
    top5, note3 = stage3_enrich_topN_and_rerank(top30, q, db)
    t3 = time.perf_counter()
    
    return top5, center, (note3 or note2), {
        "stage1": t1-t0, "stage2": t2-t1, "stage3": t3-t2, "total": t3-t0
    }

# ==================== ROUTING HELPERS ====================

def describe_osrm_step(step: dict, lang: str = 'vi') -> str:
    # Logic dịch step sang text (được lấy từ app.py)
    maneuver = step.get("maneuver", {})
    type_ = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    dist = step.get("distance", 0.0)
    
    dist_str = f"{int(dist)} m" if dist < 1000 else f"{dist/1000:.1f} km"
    
    # Simple mapping for brevity (bạn có thể dùng TRANS dict nếu muốn full multi-lang)
    dir_map = {
        "right": "rẽ phải", "slight right": "chếch phải", 
        "left": "rẽ trái", "slight left": "chếch trái",
        "straight": "đi thẳng", "uturn": "quay đầu"
    }
    action = dir_map.get(modifier, "rẽ")
    
    if type_ == "depart": return f"Bắt đầu từ {name or 'điểm xuất phát'}."
    if type_ == "arrive": return "Đến điểm đến."
    if type_ in ("turn", "end of road", "fork"):
        return f"Đi {dist_str} rồi {action} vào {name}." if name else f"Đi {dist_str} rồi {action}."
    if name: return f"Đi tiếp {dist_str} trên {name}."
    return f"Đi tiếp {dist_str}."

def recommend_transport_mode(distance_km: float, lang: str = 'vi'):
    # Logic gợi ý phương tiện
    if distance_km <= 1.5:
        return "walking", "Quãng đường ngắn, đi bộ là tốt nhất."
    elif distance_km <= 7:
        return "walking", "Khá gần, đi bộ hoặc xe đạp đều ổn."
    elif distance_km <= 300:
        return "driving", "Nên đi xe máy hoặc ô tô."
    return "driving", "Rất xa, cân nhắc xe khách hoặc máy bay."

def analyze_route_complexity(route_data: dict, profile: str, lang: str = 'vi'):
    dist = route_data.get("distance_km", 0)
    steps = len(route_data.get("steps_raw", []))
    
    lvl, lbl = "low", "Dễ"
    summ = "Đường đi đơn giản."
    reasons = []
    
    if dist > 20:
        lvl, lbl = "medium", "Trung bình"
        reasons.append("Quãng đường khá xa.")
    if steps > 20:
        lvl, lbl = "high", "Phức tạp"
        reasons.append("Nhiều ngã rẽ.")
        
    return lvl, lbl, summ, reasons

# ==================== API ENDPOINTS ====================

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400

        # Parse date strings to date objects
        def parse_date(d_str):
            return datetime.strptime(d_str, "%Y-%m-%d").date() if d_str else None

        # Construct SearchQuery object from JSON
        q = SearchQuery(
            city=data.get("city", "Hồ Chí Minh"),
            group_size=data.get("group_size", 2),
            price_min=float(data.get("price_min", 0)),
            price_max=float(data.get("price_max", 0)),
            types=data.get("types", []),
            rating_min=float(data.get("rating_min", 0)),
            amenities_preferred=data.get("amenities_preferred", []),
            radius_km=data.get("radius_km"),
            priority=data.get("priority", "balanced"),
            stars_min=data.get("stars_min", 0),
            checkin=parse_date(data.get("checkin")),
            checkout=parse_date(data.get("checkout")),
            adults=int(data.get("adults", 2)),
            children=int(data.get("children", 0))
        )
        
        # Run Algorithm
        top5, center, note, timing = perform_recommendation(q)
        
        # Serialize Result
        results_json = []
        for item in top5:
            # Convert Accommodation object back to dict for JSON response
            acc_dict = acc_to_dict(item["accommodation"])
            # Add the score explicitly
            acc_dict["_score"] = item["score"]
            results_json.append(acc_dict)

        return jsonify({
            "status": "success",
            "city_center": {"lon": center[0], "lat": center[1]},
            "results": results_json,
            "note": note,
            "timing": timing
        })

    except Exception as e:
        print(f"Recommend API Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/route', methods=['POST'])
def api_get_route():
    data = request.json
    print(f"DEBUG ROUTE REQ: {data}")
    
    src = data.get("src")
    dst = data.get("dst")
    profile = data.get("profile", "driving")
    lang = data.get("lang", "vi")

    if not src or not dst:
        return jsonify({"status": "error", "message": "Missing src/dst"}), 400

    osrm_mode = 'driving'
    if profile in ['foot', 'walking', 'di_bo']: osrm_mode = 'walking'
    elif profile in ['cycling', 'bike', 'xe_dap']: osrm_mode = 'cycling'

    url = f"https://router.project-osrm.org/route/v1/{osrm_mode}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}?overview=full&geometries=geojson&steps=true"
    
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200: return jsonify({"status": "error", "message": "OSRM Error"})
        
        res = r.json()
        if not res.get("routes"): return jsonify({"status": "error", "message": "No route found"})
        
        route = res["routes"][0]
        dist_km = route["distance"] / 1000.0
        
        # Re-calc duration
        if osrm_mode == 'walking': dur_min = (dist_km / 5.0) * 60
        elif osrm_mode == 'cycling': dur_min = (dist_km / 15.0) * 60
        else: dur_min = route["duration"] / 60.0

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
                "complexity_level": lvl,
                "complexity_label": lbl,
                "complexity_summary": summ,
                "recommendation_msg": rec_msg,
                "analysis_details": reasons
            },
            "instructions": instructions
        })

    except Exception as e:
        print(f"Route API Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)