
from dataclasses import dataclass
from typing import List
import math
import folium
from deep_translator import GoogleTranslator
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