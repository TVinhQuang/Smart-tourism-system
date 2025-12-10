from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from typing import List
from serpapi.google_search import GoogleSearch
import re
from flask import Flask, request, jsonify
from translator import translate_text
from dataclasses import dataclass
from typing import List
import math
import folium
from deep_translator import GoogleTranslator
from routing import haversine_km, describe_osrm_step
app = Flask(__name__)
CORS(app)

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

SERPAPI_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

@app.route('/api/recommend', methods=['POST'])
def recommend_api():
    data = request.json
    lang = data.get("lang", "vi")

    # Create search query
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

    # Crawl Google
    accommodations, center = fetch_google_hotels(query.city, query.radius_km, query.types)

    # Ranking
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



def serpapi_geocode(q: str):
    # 1. GÁN CỨNG KEY (Để đảm bảo hàm này luôn có key đúng)
    # Bạn thay key của bạn vào đây:
    HARDCODED_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"
    
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

def fetch_google_hotels(
    city_name: str,
    radius_km: float = 5.0,
    wanted_types: List[str] | None = None,
):
    """
    Lấy danh sách khách sạn bằng SerpAPI, không dùng Streamlit.
    Trả về (danh_sách_khách_sạn, (lon, lat)).
    """
    if wanted_types is None:
        wanted_types = []
    wanted_types = [t.lower() for t in wanted_types]

    # 1. Lấy tọa độ thành phố
    city_geo = serpapi_geocode(city_name + ", Vietnam")
    if not city_geo:
        print(f"[ERROR] Không tìm thấy tọa độ thành phố: {city_name}")
        return [], None  # hoặc raise Exception("Không tìm thấy tọa độ")

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

    # 2. Gọi API SerpAPI
    REAL_API_KEY = "b8b60f1e9d32eea6e9851ded875c4e5997487c94952a990c39dbbf5081551a68"

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

    accommodations: List[Accommodation] = []

    def detect_acc_type(item) -> str:
        """Suy luận loại chỗ ở từ text của Google Maps: hotel/homestay/hostel/resort/apartment."""
        name = (item.get("title") or "").lower()
        main_type = (item.get("type") or "").lower()
        extra_types = " ".join(t.lower() for t in item.get("types", []) if t)
        text = " ".join([name, main_type, extra_types])

        # Ưu tiên homestay / guest house / nhà nghỉ
        if any(kw in text for kw in ["homestay", "guest house", "nhà nghỉ", "nhà trọ"]):
            return "homestay"

        # Resort
        if "resort" in text:
            return "resort"

        # Hostel
        if "hostel" in text:
            return "hostel"

        # Căn hộ / apartment
        if any(kw in text for kw in ["apartment", "căn hộ", "condotel", "serviced apartment"]):
            return "apartment"

        # Mặc định là hotel
        return "hotel"


    # 3. Duyệt từng địa điểm
    for item in local_results:
        # --- 1. TÊN & ID (bỏ những cái không có tên) ---
        raw_name = (item.get("title") or item.get("name") or "").strip()
        if not raw_name:
            # Không chơi "Khách sạn không tên" nữa
            continue
        name = raw_name

        data_id = item.get("data_id")
        if data_id is None:
            # ID dựa trên tên + địa chỉ cho ổn định (không random)
            data_id = hash(name + str(item.get("address", "")))
        acc_id = str(data_id)

        # 2. Giá (Price)  → chuẩn hóa về VND/đêm
        raw_price = item.get("price")
        price = 0.0

        if raw_price:
            s = str(raw_price)

            # Lấy số đầu tiên, cho phép có . hoặc ,
            m = re.search(r"\d+(?:[.,]\d+)?", s)
            if m:
                value = float(m.group(0).replace(",", "."))
            else:
                value = 0.0

            # Nếu chuỗi có ký hiệu "₫" hoặc số đã rất lớn → coi là VND sẵn
            if "₫" in s or value >= 50_000:
                price = value
            else:
                # Còn lại thường là USD / giá ngoại tệ → đổi sang VND
                # ước lượng 1 USD ≈ 25,000 VND
                price = value * 25_000

            # Fallback cuối cùng (KHÔNG random):
            # nếu vẫn quá thấp (< 200k) thì gán mức trung bình 700k/đêm
            if price < 200_000:
                price = 700_000.0


        # --- 3. RATING & "SỐ SAO" --- 
        rating_val = item.get("rating")
        try:
            rating = float(rating_val) if rating_val is not None else 0.0  # thang 0–5 như Google
        except Exception:
            rating = 0.0

        # Sao nội bộ: xấp xỉ bằng rating, kẹp trong [0, 5]
        stars = max(0.0, min(5.0, rating))
        rating_10 = rating * 2.0  # giữ thang 0–10 cho thuật toán & UI hiện tại

        # --- 4. TIỆN ÍCH (amenities) – chỉ dựa trên text từ API ---
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

        # bỏ trùng, nhưng không thêm gì theo số sao nữa
        amenities = list(dict.fromkeys(amenities))

        # --- 5. TỌA ĐỘ (GPS) – nếu thiếu thì bỏ luôn, KHÔNG random ---
        gps = item.get("gps_coordinates") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        if lat is None or lon is None:
            # Không có toạ độ thật thì không route/map được => bỏ qua
            continue
        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            continue

        # Khoảng cách tới tâm thành phố
        dist = haversine_km(city_lon, city_lat, lon, lat)

        acc_type = detect_acc_type(item)


        # --- 6. Tạo object Accommodation ---
        acc = Accommodation(
            id=acc_id,
            name=name,
            city=city_name,
            type=acc_type,       # Google Maps search này chủ yếu là hotel
            price=price,
            stars=stars,
            rating=rating_10,
            capacity=4,         # giả định cố định, KHÔNG random
            amenities=amenities,
            address=item.get("address", city_name),
            lon=lon,
            lat=lat,
            distance_km=dist,
        )
        accommodations.append(acc)

    return accommodations, (city_lon, city_lat)

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery):
    # simplified: try strict then relax a bit
    def _do_filter(rating_min, amenity_mode="all", price_relax=1.0):
        pmin, pmax = q.price_min, q.price_max
        # expand price
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
    # simplified scoring (you can replace with your full function)
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

    # weights based on priority (keep same as in your app)
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
    - Lọc theo nhiều mức "gắt" khác nhau (strict -> nới lỏng).
    - Tính score cho từng nơi & sắp xếp giảm dần.
    - Trả về (top_k, relaxation_note)
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



if __name__ == "__main__":
    app.run(port=5000, debug=True)
