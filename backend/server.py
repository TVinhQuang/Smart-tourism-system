from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from typing import List
from serpapi import GoogleSearch
import re
from translator import translate_text
from dataclasses import dataclass
import math
import folium
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

# ==================== CONSTANTS ====================
API_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"
SERPAPI_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

# ==================== DATA CLASSES ====================
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

# ==================== TỪ ĐIỂN DỊCH THUẬT ====================
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

# ==================== HELPER FUNCTIONS ====================

def _get_text(lang, key):
    return TRANS.get(lang, TRANS["vi"]).get(key, "")

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

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

# ==================== GEOCODING ====================

def serpapi_geocode(q: str):
    """Geocode địa điểm sử dụng SerpAPI"""
    HARDCODED_KEY = API_KEY
    
    print(f"DEBUG: Đang Geocode '{q}' với SerpApi...")

    params = {
        "engine": "google_maps",
        "q": q,
        "type": "search",
        "api_key": HARDCODED_KEY,
        "hl": "vi"
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            print(f"DEBUG: ❌ SerpApi Error: {results['error']}")
            return None
            
        # TH1: local_results
        if "local_results" in results and len(results["local_results"]) > 0:
            place = results["local_results"][0]
            print(f"DEBUG: ✅ Tìm thấy (local_results): {place.get('title')}")
            return {
                "name": place.get("title"),
                "lat": place["gps_coordinates"]["latitude"],
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
            
        # TH2: place_results
        if "place_results" in results:
            place = results["place_results"]
            print(f"DEBUG: ✅ Tìm thấy (place_results): {place.get('title')}")
            return {
                "name": place.get("title"),
                "lat": place["gps_coordinates"]["latitude"],
                "lon": place["gps_coordinates"]["longitude"],
                "address": place.get("address", "")
            }
            
        print("DEBUG: ⚠️ Không tìm thấy tọa độ nào trong phản hồi của Google Maps.")
        print(f"DEBUG: Keys nhận được: {list(results.keys())}") 
        return None

    except Exception as e:
        print(f"DEBUG: ❌ Lỗi ngoại lệ trong serpapi_geocode: {e}")
        return None

# ==================== ROUTING FUNCTIONS ====================

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

def osrm_route(src, dst, profile="driving"):
    """
    Tính lộ trình bằng OSRM public
    """
    url = (
        f"https://router.project-osrm.org/route/v1/"
        f"{profile}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}"
    )
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
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

        coords = route["geometry"]["coordinates"]
        geometry = [(lat, lon) for lon, lat in coords]

        legs = route.get("legs", [])
        step_descriptions = []
        for leg in legs:
            for step in leg.get("steps", []):
                desc = describe_osrm_step(step)
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

def draw_map(src, dst, route):
    """
    Vẽ bản đồ Folium với Polyline từ Google Maps.
    """
    m = folium.Map(
        location=[src["lat"], src["lon"]],
        zoom_start=12,
        tiles="OpenStreetMap",
    )

    folium.Marker(
        [src["lat"], src["lon"]],
        tooltip="Xuất phát",
        popup=src["name"],
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    folium.Marker(
        [dst["lat"], dst["lon"]],
        tooltip="Đích đến",
        popup=dst["name"],
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    if route and route.get("geometry"):
        path_coords = route["geometry"]
        
        folium.PolyLine(
            locations=path_coords,
            color="blue",
            weight=5,
            opacity=0.7,
            tooltip=f"{route.get('distance_text')} - {route.get('duration_text')}"
        ).add_to(m)

        m.fit_bounds(path_coords)
    else:
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

# ==================== ACCOMMODATION FUNCTIONS ====================

def detect_acc_type(item) -> str:
    """Suy luận loại chỗ ở từ text của Google Maps"""
    name = (item.get("title") or "").lower()
    main_type = (item.get("type") or "").lower()
    extra_types = " ".join(t.lower() for t in item.get("types", []) if t)
    text = " ".join([name, main_type, extra_types])

    if any(kw in text for kw in ["homestay", "guest house", "nhà nghỉ", "nhà trọ"]):
        return "homestay"

    if "resort" in text:
        return "resort"

    if "hostel" in text:
        return "hostel"

    if any(kw in text for kw in ["apartment", "căn hộ", "condotel", "serviced apartment"]):
        return "apartment"

    return "hotel"

def fetch_google_hotels(
    city_name: str,
    radius_km: float = 5.0,
    wanted_types: List[str] | None = None,
):
    """
    Lấy danh sách khách sạn bằng SerpAPI
    """
    if wanted_types is None:
        wanted_types = []
    wanted_types = [t.lower() for t in wanted_types]

    city_geo = serpapi_geocode(city_name + ", Vietnam")
    if not city_geo:
        print(f"[ERROR] Không tìm thấy tọa độ thành phố: {city_name}")
        return [], None

    city_lat, city_lon = city_geo["lat"], city_geo["lon"]

    def build_search_query(city: str, types: List[str]) -> str:
        if not types or len(types) > 2:
            return f"khách sạn homestay hostel apartment ở {city}"
        s = set(types)

        if s == {"hotel"}:
            return f"khách sạn ở {city}"
        if s == {"homestay"}:
            return f"homestay, guest house, nhà nghỉ ở {city}"
        if s == {"hostel"}:
            return f"hostel, backpacker hostel ở {city}"
        if s == {"apartment"}:
            return f"căn hộ, serviced apartment ở {city}"

        return f"khách sạn homestay hostel apartment ở {city}"

    REAL_API_KEY = SERPAPI_KEY
    search_query = build_search_query(city_name, wanted_types)

    params = {
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com.vn",
        "q": search_query,
        "ll": f"@{city_lat},{city_lon},14z",
        "api_key": REAL_API_KEY,
        "hl": "vi",
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        local_results = results.get("local_results", [])
    except Exception as e:
        print(f"[ERROR] Lỗi khi gọi SerpAPI: {e}")
        return [], (city_lon, city_lat)

    accommodations: List[Accommodation] = []

    for item in local_results:
        raw_name = (item.get("title") or item.get("name") or "").strip()
        if not raw_name:
            continue
        name = raw_name

        data_id = item.get("data_id")
        if data_id is None:
            data_id = hash(name + str(item.get("address", "")))
        acc_id = str(data_id)

        # Price processing
        raw_price = item.get("price")
        price = 0.0

        if raw_price:
            s = str(raw_price)
            m = re.search(r"\d+(?:[.,]\d+)?", s)
            if m:
                value = float(m.group(0).replace(",", "."))
            else:
                value = 0.0

            if "₫" in s or value >= 50_000:
                price = value
            else:
                price = value * 25_000

            if price < 200_000:
                price = 700_000.0

        # Rating
        rating_val = item.get("rating")
        try:
            rating = float(rating_val) if rating_val is not None else 0.0
        except Exception:
            rating = 0.0

        stars = max(0.0, min(5.0, rating))
        rating_10 = rating * 2.0

        # Amenities
        amenities: List[str] = []
        desc = str(item).lower()

        def add_if(keywords, tag):
            for kw in keywords:
                if kw in desc:
                    amenities.append(tag)
                    break

        add_if(["wifi", "wi-fi"], "wifi")
        add_if(["free breakfast", "breakfast", "bữa sáng", "ăn sáng"], "breakfast")
        add_if(["pool", "swimming pool", "bể bơi"], "pool")
        add_if(["parking", "bãi đỗ xe", "chỗ đỗ xe"], "parking")

        amenities = list(dict.fromkeys(amenities))

        # GPS coordinates
        gps = item.get("gps_coordinates") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            continue

        dist = haversine_km(city_lon, city_lat, lon, lat)
        acc_type = detect_acc_type(item)

        acc = Accommodation(
            id=acc_id,
            name=name,
            city=city_name,
            type=acc_type,
            price=price,
            stars=stars,
            rating=rating_10,
            capacity=4,
            amenities=amenities,
            address=item.get("address", city_name),
            lon=lon,
            lat=lat,
            distance_km=dist,
        )
        accommodations.append(acc)

    return accommodations, (city_lon, city_lat)

def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery):
    def _do_filter(rating_min, amenity_mode="all", price_relax=1.0):
        pmin, pmax = q.price_min, q.price_max
        if price_relax > 1.0 and pmax > pmin:
            center = (pmin + pmax)/2.0
            half = (pmax - pmin)/2.0
            extra = half*(price_relax-1.0)
            pmin = max(0, center-half-extra)
            pmax = center+half+extra
        out = []
        required_lower = [x.lower() for x in q.amenities_required]
        for a in accommodations:
            if pmin>0 and a.price < pmin: continue
            if pmax>0 and a.price > pmax: continue
            if a.capacity < q.group_size: continue
            if q.types and (a.type not in q.types): continue
            if a.rating < rating_min: continue
            have=[am.lower() for am in a.amenities]
            if required_lower:
                if amenity_mode=="all":
                    if any(req not in have for req in required_lower): continue
                elif amenity_mode=="any":
                    if not any(req in have for req in required_lower): continue
            out.append(a)
        return out

    levels = [
        {"desc":"Strict", "amenity_mode":"all","rating_min":q.rating_min,"price_relax":1.0},
    ]
    if q.amenities_required:
        levels.append({"desc":"Relax any","amenity_mode":"any","rating_min":q.rating_min,"price_relax":1.0})
    levels.append({"desc":"Lower rating","amenity_mode":"ignore","rating_min":max(0,q.rating_min-1.0),"price_relax":1.0})
    levels.append({"desc":"Expand price","amenity_mode":"ignore","rating_min":max(0,q.rating_min-1.0),"price_relax":1.2})

    for cfg in levels:
        cand = _do_filter(cfg["rating_min"], cfg["amenity_mode"], cfg["price_relax"])
        if cand:
            return cand, cfg["desc"]
    return accommodations, "Very limited data"
 
def score_accommodation(a: Accommodation, q: SearchQuery) -> float:
    Pmin, Pmax = q.price_min, q.price_max
    if Pmax > Pmin:
        Pc = (Pmin + Pmax)/2.0
        denom = max(1.0, (Pmax - Pmin)/2.0)
        S_price = 1.0 - min(abs(a.price - Pc)/denom, 1.0)
    else:
        S_price = 1.0
    S_stars = clamp01(a.stars / 5.0)
    S_rating = clamp01(a.rating / 10.0)
    have = set(x.lower() for x in a.amenities)
    req = set(x.lower() for x in q.amenities_required)
    pref = set(x.lower() for x in q.amenities_preferred)
    if req or pref:
        match_req = len(have.intersection(req))
        match_pref = len(have.intersection(pref))
        matched_score = match_req + 0.5 * match_pref
        max_possible = max(1.0, len(req) + 0.5 * len(pref))
        S_amen = matched_score / max_possible
    else:
        S_amen = 1.0
    if q.radius_km > 0:
        S_dist = 1.0 - min(a.distance_km / q.radius_km, 1.0)
    else:
        S_dist = 1.0

    mode = getattr(q, "priority", "balanced")
    if mode == "cheap":
        w_price, w_stars, w_rating, w_amen, w_dist = 0.40, 0.15, 0.20, 0.15, 0.10
    elif mode == "near_center":
        w_price, w_stars, w_rating, w_amen, w_dist = 0.20, 0.10, 0.20, 0.15, 0.35
    elif mode == "amenities":
        w_price, w_stars, w_rating, w_amen, w_dist = 0.20, 0.10, 0.20, 0.40, 0.10
    else:
        w_price, w_stars, w_rating, w_amen, w_dist = 0.25, 0.20, 0.25, 0.20, 0.10

    return (w_price*S_price + w_stars*S_stars + w_rating*S_rating + w_amen*S_amen + w_dist*S_dist)

def rank_accommodations(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    """
    Lọc và xếp hạng accommodations
    """
    filtered, relax_note = filter_with_relaxation(accommodations, q)

    if not filtered:
        return [], relax_note

    scored = []
    for a in filtered:
        s = score_accommodation(a, q)
        scored.append({
            "score": s,
            "accommodation": a,
        })

    scored.sort(
        key=lambda item: (item["score"], item["accommodation"].rating),
        reverse=True
    )
    return scored[:top_k], relax_note

# ==================== API ENDPOINTS ====================

@app.route('/api/route', methods=['POST'])
def api_get_route():
    data = request.json
    src = data.get("src")
    dst = data.get("dst")
    profile = data.get("profile", "driving")
    lang = data.get("lang", "vi")

    if not src or not dst:
        return jsonify({"status": "error"}), 400

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

@app.route('/api/recommend', methods=['POST'])
def recommend_api():
    data = request.json
    lang = data.get("lang", "vi")

    query = SearchQuery(
        city=data.get("city"),
        group_size=int(data.get("group_size", 1)),
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
    ranked_results, note = rank_accommodations(accommodations, query, top_k=10)

    results = []
    for item in ranked_results:
        acc = item["accommodation"]
        results.append({
            "id": acc.id,
            "name": translate_text(acc.name, lang),
            "price": acc.price,
            "rating": acc.rating,
            "stars": acc.stars,
            "address": translate_text(acc.address, lang),
            "amenities": acc.amenities,
            "distance_km": acc.distance_km,
            "score": item["score"],
            "lat": acc.lat,
            "lon": acc.lon
        })

    return jsonify({
        "results": results,
        "relaxation_note": translate_text(note, lang),
        "center": {"lat": center[1], "lon": center[0]} if center else None
    })

# ==================== MAIN ====================

if __name__ == '__main__':
    app.run(debug=True, port=5000)