from flask import Flask, request, jsonify
from flask_cors import CORS
from core_logic import Accommodation, SearchQuery, haversine_km, describe_osrm_step, rank_accommodations    
import requests
from typing import List
from serpapi import GoogleSearch
import re
app = Flask(__name__)
CORS(app)

SERPAPI_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"

def serpapi_geocode(q: str):
    # 1. GÁN CỨNG KEY (Để đảm bảo hàm này luôn có key đúng)
    # Bạn thay key của bạn vào đây:
    HARDCODED_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"
    
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
    REAL_API_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"

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

@app.route('/api/recommend', methods=['POST'])
def recommend_api():
    data = request.json
    
    # 1. Tạo đối tượng SearchQuery từ dữ liệu gửi lên
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

    # 2. Tìm kiếm dữ liệu (Dùng hàm fetch_google_hotels đã viết)
    # Lưu ý: fetch_google_hotels trả về (list, center_coords)
    accommodations, center = fetch_google_hotels(query.city, query.radius_km, query.types)

    # 3. Chấm điểm và lọc (Dùng hàm rank_accommodations từ core_logic)
    ranked_results, note = rank_accommodations(accommodations, query, top_k=10)

    # 4. Chuẩn bị dữ liệu trả về JSON
    response_list = []
    for item in ranked_results:
        acc = item["accommodation"]
        response_list.append({
            "id": acc.id,
            "name": acc.name,
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
        "results": response_list,
        "relaxation_note": note,
        "center": {"lat": center[1], "lon": center[0]} if center else None
    })

if __name__ == "__main__":
    app.run(port=5000, debug=True)
