import time
import streamlit as st
import pyrebase
import pandas as pd
import pydeck as pdk
import firebase_admin
import requests
from dataclasses import dataclass, field
from typing import List
import math
import random
import polyline
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from firebase_admin import credentials, firestore
from firebase_admin import auth as admin_auth
from collections import deque
from datetime import datetime, timezone
from ollama import Client
from streamlit_extras.stylable_container import stylable_container
from serpapi import GoogleSearch
import re
import json, os
from datetime import date, timedelta
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional


DB_PATH = "accommodation_cache.json"

def load_accommodation_db() -> dict:
    """
    Đọc file JSON Lines → dict[id] = dict_thuộc_tính.
    Mỗi dòng trong file là 1 object JSON.
    """
    if not os.path.exists(DB_PATH):
        return {}

    db: dict[str, dict] = {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                acc_id = rec.get("id")
                if not acc_id:
                    continue

                db[acc_id] = rec
    except Exception:
        return {}

    return db

def save_accommodation_db(db: dict) -> None:
    """
    Ghi dict[id] → file JSON Lines.
    Mỗi nơi ở = 1 dòng JSON (form ngang, dễ đếm).
    """
    dir_name = os.path.dirname(DB_PATH)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    with open(DB_PATH, "w", encoding="utf-8") as f:
        for rec in db.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def normalize_city(city: str) -> str:
    """Chuẩn hoá tên thành phố cho nội bộ & DB."""
    if not city:
        return ""
    return city.strip().lower()


API_KEY = st.secrets["serpapi_key"]

BOT_GREETING = "Xin chào! Hôm nay bạn đã nghĩ muốn đi đâu chưa?"

# ===================== MÔ-ĐUN THUẬT TOÁN GỢI Ý NƠI Ở =====================


@dataclass
class Accommodation:
    id: str
    name: str
    city: str
    type: str
    price: float

    # ⭐ Loại sao chính thức (hotel class 1–5, lấy từ Google Hotels)
    stars: float = 0.0

    # 📊 Điểm review người dùng (0–5, lấy từ Google Maps)
    rating: float = 0.0

    # 🧮 Số lượt đánh giá
    reviews: int = 0

    capacity: int = 0
    amenities: List[str] = field(default_factory=list)
    address: str = ""
    lon: float = 0.0
    lat: float = 0.0
    distance_km: float = 0.0

def acc_to_dict(a: Accommodation) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "city": normalize_city(a.city),
        "type": a.type,
        "price": a.price,
        "stars": a.stars,
        "rating": a.rating,
        "reviews": getattr(a, "reviews", None),
        "amenities": list(a.amenities or []),
        "address": a.address,
        "lon": a.lon,
        "lat": a.lat,
        "distance_km": a.distance_km,
        "source": "serpapi_google_maps",
        "updated_at": datetime.utcnow().isoformat()
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

        # ✅ FIX: thêm dòng này
        reviews = int(d.get("reviews") or 0),

        capacity=4,
        amenities=d.get("amenities", []),
        address=d.get("address", ""),
        lon=d.get("lon", 0.0),
        lat=d.get("lat", 0.0),
        distance_km=d.get("distance_km", 0.0),
    )


@dataclass
class SearchQuery:
    """
    Gói toàn bộ input người dùng cho thuật toán gợi ý.
    Sau này ta sẽ build SearchQuery từ form trên web.
    """
    city: str                      # tên thành phố điểm đến
    group_size: int                # số người
    price_min: float               # ngân sách tối thiểu (cho 1 đêm)
    price_max: float               # ngân sách tối đa
    types: List[str]               # loại chỗ ở mong muốn: ["hotel","homestay",...]
    rating_min: float              # điểm đánh giá tối thiểu (0–5)
    amenities_preferred: List[str] # tiện ích ưu tiên (có thì cộng điểm)
    radius_km: Optional[float]     # bán kính tìm kiếm quanh thành phố (km), có thể là số hoặc None 
    priority: str = "balanced"     # 'balanced' / 'cheap' / 'near_center' / 'amenities'

    # ✅ NEW: sao tối thiểu (chỉ áp dụng hotel/resort), 0 = không yêu cầu
    stars_min: int = 0

    # --- mới thêm ---
    checkin: Optional[date] = None
    checkout: Optional[date] = None
    adults: int = 2
    children: int = 0


# ===================== MÔ-ĐUN TIỆN ÍCH BẢN ĐỒ VÀ ĐỊNH TUYẾN =====================
@st.cache_data(ttl=3600)
def get_osrm_route(start_lon, start_lat, end_lon, end_lat, profile="driving"):
    """
    Gọi OSRM Public API để lấy dữ liệu đường đi (Encoded Polyline).
    Trả về danh sách các cặp tọa độ (lat, lon) cho Folium.
    """
    # CHÚ Ý: OSRM yêu cầu tọa độ theo định dạng {longitude},{latitude}
    coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    
    # Endpoint công cộng của OSRM
    OSRM_URL = f"http://router.project-osrm.org/route/v1/{profile}/{coordinates}?overview=full"
    
    try:
        response = requests.get(OSRM_URL)
        response.raise_for_status() 
        data = response.json()
        
        if data["code"] == "Ok" and data["routes"]:
            encoded_polyline = data["routes"][0]["geometry"]
            # Giải mã chuỗi polyline
            decoded_route = polyline.decode(encoded_polyline)
            return decoded_route
        else:
            print(f"Lỗi OSRM: {data.get('code', 'Unknown Error')}")
            return None
            
    except requests.RequestException as e:
        print(f"Lỗi khi gọi OSRM API: {e}")
        return None


def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5,):
    """
    Thử lọc theo nhiều mức "gắt" khác nhau.
    Bổ sung:
      - Lọc theo khoảng cách tới trung tâm (radius_km).
      - Khi nới lỏng, có thể tăng nhẹ bán kính và khoảng giá.
    Trả về:
      - filtered: list[Accommodation]
      - note: chuỗi giải thích mức nới lỏng (để hiển thị lên UI).
    """

    def _do_filter(
        rating_min: float,
        amenity_mode: str = "all",
        price_relax: float = 1.0,
        radius_relax: float = 1.5,
    ) -> List[Accommodation]:
        """
        price_relax:
          - 1.0  : giữ nguyên khoảng giá
          - >1.0 : nới rộng khoảng giá (ví dụ 1.2 = rộng thêm 20%)
        radius_relax:
          - 1.0  : giữ nguyên bán kính user chọn
          - >1.0 : cho phép xa hơn một chút (vd 1.2 = xa hơn 20%)
        """
        # --- 1) Nới khoảng giá (nếu có) ---
        pmin = q.price_min
        pmax = q.price_max

        if price_relax > 1.0 and pmax > 0 and pmax > pmin:
            center = (pmin + pmax) / 2
            half_span = (pmax - pmin) / 2
            extra = half_span * (price_relax - 1.0)
            pmin = max(0, center - half_span - extra)
            pmax = center + half_span + extra

        # --- 2) Nới bán kính (nếu có) ---
        radius_limit = q.radius_km or 0.0
        if radius_limit > 0:
            dist_limit = radius_limit * radius_relax
        else:
            dist_limit = None  # không giới hạn

        filtered_local: List[Accommodation] = []
        for a in accommodations:
            # 2.1. Khoảng cách tới trung tâm
            if dist_limit is not None and a.distance_km > dist_limit:
                continue

            # 2.2. Giá
            if pmin > 0 and a.price < pmin:
                continue
            if pmax > 0 and a.price > pmax:
                continue

            # 2.3. Sức chứa
            if a.capacity < q.group_size:
                continue

            # 2.4. Loại chỗ ở
            if q.types and (a.type not in q.types):
                continue

            # 2.5. Rating
            if a.rating < rating_min:
                continue

            # ⭐ lọc sao tối thiểu - chỉ áp dụng hotel/resort
            if getattr(q, "stars_min", 0.0) > 0 and a.type in ("hotel", "resort"):
                if (a.stars or 0.0) < q.stars_min:
                    continue

            # 2.6. Tiện ích
            filtered_local.append(a)

        return filtered_local

    # ========== Định nghĩa các mức nới lỏng ==========
    levels = []

    # Level 0: gắt nhất – giống hiện tại, dùng radius đúng như user chọn
    levels.append({
        "desc": "Các gợi ý dưới đây thỏa **đầy đủ** tiêu chí bạn đã chọn.",
        "amenity_mode": "all",
        "rating_min": q.rating_min,
        "price_relax": 1.0,
        "radius_relax": 1.0,
    })

    # Level 1: cho phép chỉ cần thỏa MỘT phần tiện ích bắt buộc
    levels.append({
        "desc": "Không có nơi ở nào đáp ứng đủ tất cả tiện ích bắt buộc. "
                "Hệ thống ưu tiên các nơi đáp ứng **một phần** tiện ích bạn chọn.",
        "amenity_mode": "any",
        "rating_min": q.rating_min,
        "price_relax": 1.0,
        "radius_relax": 1.0,
    })

    # Level 2: bỏ điều kiện tiện ích, hạ rating_min, tăng nhẹ bán kính
    levels.append({
        "desc": "Không có nơi ở nào đáp ứng đầy đủ rating/tiện ích. "
                "Hệ thống đã nới lỏng rating tối thiểu, bỏ tiện ích bắt buộc "
                "và cho phép tìm xa trung tâm hơn một chút.",
        "amenity_mode": "ignore",
        "rating_min": max(0.0, q.rating_min - 100.0),
        "price_relax": 1.0,
        "radius_relax": 1.2,
    })

    # Level 3: tiếp tục nới rộng khoảng giá + bán kính
    levels.append({
        "desc": "Không có nơi ở nào thỏa hết tiêu chí trong phạm vi hiện tại. "
                "Hệ thống đã nới rộng khoảng giá và bán kính tìm kiếm để "
                "tìm thêm lựa chọn phù hợp nhất có thể.",
        "amenity_mode": "ignore",
        "rating_min": max(0.0, q.rating_min - 100.0),
        "price_relax": 1.2,
        "radius_relax": 1.5,
    })

     # ========== Chạy lần lượt từng level, CỘNG DỒN tới đủ top_k ==========
    collected: List[Accommodation] = []
    used_ids = set()
    used_note: str | None = None

    # ========== Chạy lần lượt từng level và GOM KẾT QUẢ ==========
    TARGET_K = 5  # số lượng tối thiểu muốn có để xếp hạng (Top 5)

    final: List[Accommodation] = []
    note = ""

    for cfg in levels:
        cand = _do_filter(
            rating_min=cfg["rating_min"],
            amenity_mode=cfg["amenity_mode"],
            price_relax=cfg["price_relax"],
            radius_relax=cfg["radius_relax"],
        )

        if cand:
            # ghi lại mô tả của level đầu tiên có kết quả
            if not note:
                note = cfg["desc"]

            # thêm vào final, tránh trùng id
            existing_ids = {a.id for a in final}
            for a in cand:
                if a.id not in existing_ids:
                    final.append(a)
                    existing_ids.add(a.id)

        # nếu đã đủ (hoặc hơn) TARGET_K thì dừng, không cần nới thêm
        if len(final) >= TARGET_K:
            break

    if final:
        return final, note

    # Nếu chạy hết mà vẫn không có gì (dữ liệu cực ít) → fallback như cũ
    return accommodations, (
        "Dữ liệu khu vực này khá hạn chế, hệ thống đã gợi ý các nơi ở gần nhất "
        "với yêu cầu của bạn trong phạm vi hiện có."
    )


def clamp01(x: float) -> float:
    """Giới hạn giá trị trong [0,1] để tránh <0 hoặc >1."""
    return max(0.0, min(1.0, x))

def has_amenity(have_lower: set[str], code: str) -> bool:
    """
    Kiểm tra xem một chỗ ở (have_lower) có tiện ích 'code' hay không,
    bằng cách dò theo danh sách keyword (substring).
    """
    KEYWORDS = {
        "wifi": ["wifi", "wi-fi"],
        "breakfast": ["breakfast", "bữa sáng", "ăn sáng"],
        "pool": ["pool", "bể bơi", "hồ bơi"],
        "parking": ["parking", "chỗ đỗ xe", "bãi đỗ xe"],
        "airport_shuttle": ["airport shuttle", "đưa đón sân bay"],
        "gym": ["fitness", "gym", "trung tâm thể dục"],
        "restaurant": ["restaurant", "nhà hàng"],
        "bar": ["bar", "quầy bar"],
        # nếu sau này cậu thêm code tiện ích mới (spa, sauna, …) thì bổ sung ở đây
    }

    # Nếu không có mapping đặc biệt thì dùng luôn code làm keyword
    keywords = KEYWORDS.get(code, [code])

    for text in have_lower:
        for kw in keywords:
            if kw in text:
                return True
    return False


#mô-đun “Scoring & Ranking module”
def score_accommodation(a: Accommodation, q: SearchQuery) -> float:
    """
    Tính điểm xếp hạng cho 1 nơi ở theo nhiều tiêu chí.

    Trọng số:
      - Giá: 32%
      - Rating:
          + Hotel / Resort: 28% rating user + 5% hạng sao
          + Homestay / Apartment / Hostel: 33% rating user, KHÔNG dùng sao
      - Vị trí: 20%
      - Tiện ích: 15%

    Tuỳ chế độ ưu tiên (priority) mà CÁCH CHẤM GIÁ (S_price) sẽ khác:
      - cheap      : giá càng gần MIN càng tốt (tiết kiệm).
      - balanced   : giá ở GIỮA khoảng min–max là tối ưu.
      - near_center / amenities :
                     giá càng gần MAX (dùng nhiều ngân sách đổi lấy chất lượng).
    Các thành phần khác (sao, rating, tiện ích, khoảng cách) giữ nguyên trọng số.
    """
    mode = getattr(q, "priority", "balanced")

    # ----- 1. Điểm GIÁ (S_price) -----
    Pmin, Pmax = q.price_min, q.price_max
    if Pmax > Pmin and a.price > 0:
        # Chuẩn hoá giá về [0,1] trong khoảng user muốn
        t = (a.price - Pmin) / (Pmax - Pmin)
        t = clamp01(t)  # 0 = sát min, 1 = sát max

        if mode == "cheap":
            # Càng gần min càng tốt
            S_price = 1.0 - t
        elif mode == "balanced":
            # 0.5 là tốt nhất, 0 hoặc 1 là tệ nhất
            S_price = 1.0 - abs(t - 0.5) * 2.0   # luôn trong [0,1]
        else:
            # near_center, amenities: càng gần max càng tốt
            S_price = t
    else:
        # Không đặt được khoảng giá rõ ràng → không phạt theo giá
        S_price = 1.0

    # ----- 2. Điểm ĐÁNH GIÁ -----
    # 2.2. Điểm review user (rating 0–5) -> chuẩn hoá 0..1
    S_rating = clamp01((a.rating or 0.0) / 5.0)

    # 2.1. Sao loại 1 (hotel class 1–5) -> chuẩn hoá 0..1
    is_hotel_resort = a.type in ("hotel", "resort")

    if is_hotel_resort and (a.stars or 0.0) > 0:
        # Chỉ hotel/resort có sao mới có thêm 5% sao
        S_rating = S_rating
        S_stars  = clamp01(a.stars / 5.0)
        w_rating = 0.28
        w_stars  = 0.05
    else:
        # Các loại khác: không dùng sao, dồn luôn 5% sang rating
        S_rating = S_rating
        S_stars  = 0.0
        w_rating = 0.33  # 28% + 5% dồn vào rating
        w_stars  = 0.0

    # (Nếu sau này cậu muốn cộng thêm hiệu ứng "nhiều lượt đánh giá thì tin hơn",
    # mình có thể nhân nhẹ thêm 1 factor dựa trên a.reviews.)

    # ----- 3. Điểm TIỆN ÍCH (chỉ dùng amenities_preferred) -----
    have = set(x.lower() for x in a.amenities)
    pref = set(x.lower() for x in q.amenities_preferred)

    if pref:
        # Đếm xem có bao nhiêu code tiện ích user chọn mà chỗ ở này thực sự có
        matched = sum(
            1 for code in pref
            if has_amenity(have, code)
        )
        S_amen = matched / len(pref)
    else:
        # user không chọn tiện ích nào → không phạt, cho điểm trung bình cao
        S_amen = 1.0

    # ----- 4. Điểm KHOẢNG CÁCH -----
    # Nếu user không chọn giới hạn khoảng cách, radius_km sẽ là None
    # -> ta coi như 0 km = không giới hạn
    radius_limit = q.radius_km or 0.0

    if radius_limit > 0:
        # Càng gần hơn radius_limit thì điểm càng cao.
        S_dist = 1.0 - min(a.distance_km / radius_limit, 1.0)
    else:
        # Không giới hạn khoảng cách -> không phạt theo khoảng cách
        S_dist = 1.0

    # ----- 5. TRỌNG SỐ CỐ ĐỊNH (không đổi theo priority) -----
    #  - Giá: 32%
    #  - Tiện ích: 15%
    #  - Khoảng cách: 20%
    w_price  = 0.32
    w_amen   = 0.15
    w_dist   = 0.20

    # ----- 6. Tổng hợp điểm -----
    score = (
        w_price  * S_price  +
        w_stars  * S_stars  +
        w_rating * S_rating +
        w_amen   * S_amen   +
        w_dist   * S_dist
    )
    return score



def rank_accommodations(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    """
    - Lọc theo nhiều mức "gắt" khác nhau (strict -> nới lỏng).
    - Tính score cho từng nơi & sắp xếp giảm dần.
    - Trả về (top_k, relaxation_note)
    """
    filtered, relax_note = filter_with_relaxation(accommodations, q, top_k=top_k)

    if not filtered:
        return [], relax_note

    scored = []
    for a in filtered:
        s = score_accommodation(a, q)
        scored.append({
            "score": s,
            "accommodation": a,
        })

    def sort_key(item):
        acc = item["accommodation"]
        score = item["score"]

        rating = acc.rating or 0.0       # điểm user 0–5
        reviews = acc.reviews or 0       # số lượt đánh giá
        dist = acc.distance_km or 1e9
        price = acc.price if acc.price and acc.price > 0 else 1e9

        # sort tăng dần → dùng số âm cho những cái muốn giảm dần
        return (
            -round(score, 6),   # 1. score tổng
            -rating,            # 2. điểm user
            -reviews,           # 3. số review
            dist,               # 4. gần hơn
            price,              # 5. rẻ hơn
            acc.name.lower(),   # 6. tên (ổn định thứ tự)
        )

    scored.sort(key=sort_key)
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

#def geocode(q: str):
    """
    Geocode 1 địa chỉ/tên điểm bất kỳ (dùng cho điểm xuất phát).
    """
    g = Nominatim(user_agent="st_route_demo")
    try:
        loc = g.geocode(q, exactly_one=True, addressdetails=True, language="en")
        if not loc:
            return None
        return {"name": loc.address, "lat": loc.latitude, "lon": loc.longitude}
    except Exception:
        return None


def serpapi_geocode(q: str):
    # 1. GÁN CỨNG KEY (Để đảm bảo hàm này luôn có key đúng)
    # Bạn thay key của bạn vào đây:
    # HARDCODED_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"
    
    print(f"DEBUG: Đang Geocode '{q}' với SerpApi...")

    params = {
        "engine": "google_maps",
        "q": q,
        "type": "search",
        "api_key": API_KEY, # Dùng key cứng tại đây
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


@st.cache_data(ttl=3600, show_spinner=False)
def smart_geocode(q: str):
    """
    Geocode thông minh:
      - Thử SerpAPI (Google Maps) trước.
      - Nếu SerpAPI lỗi hoặc không trả về kết quả,
        fallback sang Nominatim (OpenStreetMap).
    Trả về dict: {name, lat, lon, address} hoặc None nếu vẫn thất bại.
    """
    # Thử SerpAPI trước
    loc = serpapi_geocode(q)
    if loc is not None:
        return loc

    print(f"DEBUG: ⚠️ SerpApi không tìm được '{q}', fallback sang Nominatim...")

    try:
        geocoder = Nominatim(user_agent="smart_tourism_fallback")
        res = geocoder.geocode(q, exactly_one=True, addressdetails=True, language="en")
        if not res:
            print("DEBUG: Nominatim cũng không tìm thấy kết quả.")
            return None

        return {
            "name": res.address,
            "lat": res.latitude,
            "lon": res.longitude,
            "address": res.address,
        }
    except Exception as e:
        print(f"DEBUG: ❌ Lỗi Nominatim fallback: {e}")
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



def serpapi_route(src, dst, profile="driving"):
    """
    Tính lộ trình bằng SerpApi Google Maps Directions.
    Trả về:
      - distance_km, duration_min
      - geometry: list[(lat, lon)] để Folium vẽ PolyLine
      - steps: danh sách câu hướng dẫn ngắn gọn
    """

    # map profile UI -> travel_mode của SerpApi
    travel_mode_map = {
        "driving": 0,   # ô tô / xe máy
        "walking": 2,   # đi bộ
        "cycling": 1,   # xe đạp
    }
    travel_mode = travel_mode_map.get(profile, 6)   # 6 = “Best”

    params = {
        "engine": "google_maps_directions",                      # ✅ ĐỔI ENGINE
        "start_coords": f"{src['lat']},{src['lon']}",
        "end_coords": f"{dst['lat']},{dst['lon']}",
        "api_key": API_KEY,
        "hl": "vi",
        "distance_unit": 0,                                      # 0 = km
        "travel_mode": travel_mode,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        # Nếu có lỗi từ SerpApi
        if "error" in results:
            print("❌ SerpApi Error:", results["error"])
            return None

        directions = results.get("directions")
        if not directions:
            print("⚠️ Không tìm thấy 'directions' trong kết quả SerpApi.")
            print("Keys:", list(results.keys()))
            return None

        # Lấy phương án đường đi đầu tiên
        d = directions[0]

        distance_m = d.get("distance", 0)        # mét
        duration_s = d.get("duration", 0)        # giây

        # 1) Build list toạ độ (lat, lon) để vẽ PolyLine
        geometry = []
        geometry.append((src["lat"], src["lon"]))    # điểm xuất phát

        for trip in d.get("trips", []):
            for detail in trip.get("details", []):
                gps = detail.get("gps_coordinates")
                if gps:
                    geometry.append(
                        (gps.get("latitude"), gps.get("longitude"))
                    )

        geometry.append((dst["lat"], dst["lon"]))    # điểm đến

        # 2) Tạo list câu hướng dẫn từng bước
        steps = []
        for trip in d.get("trips", []):
            for detail in trip.get("details", []):
                title = detail.get("title", "")
                dist_text = detail.get("formatted_distance", "")
                # VD: "Rẽ phải vào đường Nguyễn Văn Cừ (300 m)"
                if title or dist_text:
                    steps.append(f"{title} ({dist_text})")

        return {
            "distance_km": distance_m / 1000.0,
            "duration_min": duration_s / 60.0,
            "geometry": geometry,
            "steps": steps,
            "distance_text": d.get("formatted_distance"),
            "duration_text": d.get("formatted_duration"),
        }

    except Exception as e:
        print("❌ LỖI SYSTEM trong serpapi_route:", e)
        return None


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


#def geocode_city(city_name: str):
    """
    Dùng Nominatim để lấy toạ độ (lat, lon) của một thành phố.
    Trả về dict {"name", "lat", "lon"} hoặc None nếu lỗi.
    """
    geocoder = Nominatim(user_agent="smart_tourism_demo")
    try:
        loc = geocoder.geocode(city_name, exactly_one=True, addressdetails=True, language="en")
        if not loc:
            return None
        return {
            "name": loc.address,
            "lat": loc.latitude,
            "lon": loc.longitude,
        }
    except Exception:
        return None


def fetch_full_amenities_from_hotels_api(acc: Accommodation, q: SearchQuery) -> list[str]:
    """
    Gọi SerpAPI Google Hotels cho riêng 1 nơi ở, 
    trả về danh sách tiện ích dạng text (Tiếng Việt) đầy đủ.
    """

    if not API_KEY:
        return []

    # Query: tên nơi ở + thành phố, dùng ngôn ngữ / vùng Việt Nam
    params = {
        "engine": "google_hotels",
        "api_key": API_KEY,
        "q": f"{acc.name} {q.city}",
        "hl": "vi",
        "gl": "vn",
        "currency": "VND",
        "no_cache": "true",
    }

    # Nếu có ngày nhận / trả phòng thì gửi kèm (không bắt buộc)
    if q.checkin and isinstance(q.checkin, date):
        params["check_in_date"] = q.checkin.strftime("%Y-%m-%d")
    if q.checkout and isinstance(q.checkout, date):
        params["check_out_date"] = q.checkout.strftime("%Y-%m-%d")
    if q.adults:
        params["adults"] = q.adults

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        print(f"[DEBUG] Lỗi gọi google_hotels cho '{acc.name}': {e}")
        return []

    props = results.get("properties") or []
    if not props:
        return []

    # Lấy property đầu tiên (phù hợp nhất)
    prop = props[0]

    raw_amenities = prop.get("amenities") or []

    # Ở đây Google đã trả sẵn list text Tiếng Việt (vd: 'Hồ bơi ngoài trời')
    full_amenities = [str(a).strip() for a in raw_amenities if str(a).strip()]

    return full_amenities


def enrich_hotel_class_one_with_hotels_api(
    acc: Accommodation,
    api_key: str,
    checkin=None,
    checkout=None,
    adults: int = 2,
    children: int = 0,
) -> None:
    """Chỉ lấy sao loại 1 (hotel_class) cho 1 acc bằng SerpAPI google_hotels."""

    params = {
        "engine": "google_hotels",
        "q": f"{acc.name} {acc.city}",
        "hl": "vi",
        "gl": "vn",
        "api_key": api_key,
    }

    if checkin:
        params["check_in_date"] = checkin.isoformat()
    if checkout:
        params["check_out_date"] = checkout.isoformat()

    # tùy SerpAPI có dùng hay không, nhưng thêm cũng không hại
    params["adults"] = adults
    params["children"] = children

    try:
        data = GoogleSearch(params).get_dict()
    except Exception:
        return

    props = data.get("properties") or []
    if not props:
        return

    prop0 = props[0]

    hotel_class = prop0.get("extracted_hotel_class")
    if hotel_class is None:
        raw_class = prop0.get("hotel_class")
        if isinstance(raw_class, str):
            m = re.search(r"(\d+)", raw_class)
            if m:
                hotel_class = int(m.group(1))

    try:
        if hotel_class is not None:
            acc.stars = float(hotel_class)
    except Exception:
        pass



def enrich_amenities_with_hotels_api(acc: Accommodation, api_key: str):
    """
    Gọi Google Hotels để lấy FULL amenities cho 1 chỗ ở.
    Nếu tìm không ra thì giữ nguyên acc.amenities hiện tại.
    """
    params = {
        "engine": "google_hotels",
        "q": f"{acc.name} {acc.city}",
        "hl": "vi",
        "gl": "vn",
        "api_key": api_key,
    }

    try:
        search = GoogleSearch(params)
        data = search.get_dict()
    except Exception:
        return  # lỗi mạng / quota… thì thôi

    props = data.get("properties") or []
    if not props:
        return

    prop0 = props[0]

    full_amenities: list[str] = []

    # 1) field 'amenities' (một list string)
    for am in prop0.get("amenities") or []:
        if isinstance(am, str):
            full_amenities.append(am.strip())

    # 2) field 'amenities_detailed' (groups/list/title)
    groups = ((prop0.get("amenities_detailed") or {}).get("groups") or [])
    for g in groups:
        for item in g.get("list", []):
            title = item.get("title")
            if title:
                full_amenities.append(title.strip())

    if not full_amenities:
        return

    # Gộp với tiện ích cũ, bỏ trùng – ưu tiên list đầy đủ mới
    merged = list(dict.fromkeys(full_amenities + acc.amenities))
    acc.amenities = merged


def fetch_google_hotels(city_name: str,
    radius_km: float = 5.0,
    wanted_types: List[str] | None = None,
    checkin: Optional[date] = None,
    checkout: Optional[date] = None,
    adults: int = 2,
    children: int = 0,):
    """
    Lấy danh sách khách sạn quanh một thành phố bằng SerpAPI (Google Maps).
    Dữ liệu dùng tối đa những gì API có, KHÔNG random thêm:
      - name, address, rating, price, gps_coordinates
      - tiện ích: dò từ text (wifi, breakfast, pool, parking)
    Nếu thiếu các thông tin quan trọng (không tên, không toạ độ) thì bỏ qua.
    """
    if wanted_types is None:
        wanted_types = []
    wanted_types = [t.lower() for t in wanted_types]

    # city_name từ SearchQuery đã là chữ thường rồi,
    # nhưng cứ chuẩn hoá thêm cho chắc
    city_name = normalize_city(city_name)

    # 1. Lấy tọa độ thành phố
    city_geo = smart_geocode(city_name + ", Vietnam")
    if not city_geo:
        st.error(f"Không tìm thấy tọa độ thành phố: {city_name}")
        return [], None

    city_lat, city_lon = city_geo["lat"], city_geo["lon"]

    def build_search_query(city: str, types: List[str]) -> str:
        # Budget cao → ưu tiên từ khoá "cao cấp / 5 sao / resort"
        if price_min >= 3_000_000:
            return f"khách sạn 5 sao, resort cao cấp ở {city}"
            
        # Không chọn gì hoặc chọn nhiều loại → lấy rộng
        if not types or len(types) > 2:
            return f"khách sạn homestay hostel apartment resort ở {city}"
        
        s = set(types)
        if s == {"hotel"}:
            return f"khách sạn ở {city}"
        if s == {"homestay"}:
            # ưu tiên homestay / guest house / nhà nghỉ
            return f"homestay, guest house, nhà nghỉ ở {city}"
        if s == {"hostel"}:
            return f"hostel, backpacker hostel ở {city}"
        if s == {"apartment"}:
            return f"căn hộ, serviced apartment ở {city}"
        if s == {"resort"}:
            return f"resort ở {city}"

        # Các tổ hợp khác (vd hotel + homestay, hotel + resort...)
        return f"khách sạn homestay hostel apartment resort ở {city}"


    # 2. Gọi API SerpAPI – Google Maps search

    search_query = build_search_query(city_name, wanted_types)
    all_results = []
    for start in [0, 20, 40]:  # muốn nhiều hơn nữa, thêm 60, 80,... vào đây
        params = {
            "engine": "google_maps",
            "type": "search",
            "google_domain": "google.com.vn",
            "q": search_query,                     # ⬅ dùng query tuỳ loại
            "ll": f"@{city_lat},{city_lon},8z",
            "api_key": API_KEY,
            "hl": "vi",
            "start": start,       # 👈 phân trang
        }

        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            local_results = results.get("local_results", [])
        except Exception as e:
            st.error(f"Lỗi khi gọi SerpAPI: {e}")
            continue

        if not local_results:
            break      # hết kết quả thì dừng vòng for

        all_results.extend(local_results)
    
    if not all_results:
        return [], (city_lon, city_lat)

    db = load_accommodation_db()   # ✅ load DB hiện tại

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
    for item in all_results:
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
                price = value * 26_405

            # Fallback cuối cùng (KHÔNG random):
            # nếu vẫn quá thấp (< 200k) thì gán mức trung bình 700k/đêm
            # if price < 200_000:
            #     price = 700_000.0


        # 3. Điểm review (0–5) từ Google Maps
        rating_raw = item.get("rating")
        try:
            rating = float(rating_raw)
        except (TypeError, ValueError):
            rating = 0.0
        # 3.2. Số lượt đánh giá (reviews)
        reviews_raw = (item.get("reviews")
        or item.get("user_ratings_total")
        or item.get("reviews_count"))
        try:
            reviews = parse_review_count(reviews_raw)
        except (TypeError, ValueError, AttributeError):
            reviews = 0
        # 3.3. Sao loại 1 (hotel class) tạm thời chưa có → để 0,
        # lát nữa sẽ dùng Google Hotels API để bổ sung.
        hotel_class = 0.0

        # --- 4. TIỆN ÍCH (amenities) – chỉ dựa trên text từ API ---
        amenities = extract_amenities_from_google_property(item)
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

        # 🔍 Chỉ lọc theo bán kính nếu radius_km có giá trị (user đã chọn)
        if radius_km is not None and dist > radius_km:
            continue

        # --- 6. Tạo object Accommodation ---
        acc = Accommodation(
            id=acc_id,
            name=name,
            city=city_name,
            type=acc_type,
            price=price,
            # Sao loại 1 chưa biết: 0.0, sẽ được cập nhật bằng Hotels API
            stars=hotel_class,
            # Điểm review của user (0–5)
            rating=rating,
            # Số lượt đánh giá
            reviews=reviews,
            capacity=4,
            amenities=amenities,
            address=item.get("address", city_name),
            lon=lon,
            lat=lat,
            distance_km=dist,
        )

        cached = db.get(acc.id)
        # 1) ưu tiên lấy từ DB trước (nhanh)
        if cached:
            if cached.get("amenities"):
                acc.amenities = cached["amenities"]
            if cached.get("stars") is not None:
                try:
                    acc.stars = float(cached["stars"])
                except Exception:
                    pass

            # ✅ NEW: giữ rating/reviews tốt từ DB nếu API thiếu
            try:
                if (acc.rating or 0) <= 0 and (cached.get("rating") or 0) > 0:
                    acc.rating = float(cached["rating"])
            except:
                pass

            try:
                if (acc.reviews or 0) <= 0 and (cached.get("reviews") or 0) > 0:
                    acc.reviews = int(cached["reviews"])
            except:
                pass

        # 2) nếu thiếu amenities -> enrich amenities như cũ
        if not acc.amenities:
            enrich_amenities_with_hotels_api(acc, API_KEY)

        # 3) nếu là hotel/resort và thiếu stars -> enrich sao NGAY LÚC NÀY
        if acc.type in ("hotel", "resort") and (acc.stars is None or acc.stars <= 0):
            enrich_hotel_class_one_with_hotels_api(
                acc,
                API_KEY,
                checkin=checkin,
                checkout=checkout,
                adults=adults,
                children=children,
            )

        # ✅ Ghi / cập nhật vào DB (không bao giờ trùng id)
        db[acc.id] = acc_to_dict(acc)

    # # Sau khi gom được danh sách chỗ ở từ Google Maps,
    # # dùng Google Hotels để bổ sung sao loại 1 cho một số chỗ
    # try:
    #     enrich_hotel_class_with_hotels_api(accommodations, SearchQuery(
    #         city=city_name,
    #         group_size=2,
    #         price_min=0,
    #         price_max=0,
    #         types=[],
    #         rating_min=0.0,
    #         amenities_preferred=[],
    #         radius_km=radius_km,
    #         priority="balanced",
    #         checkin=checkin,
    #         checkout=checkout,
    #         adults=adults,
    #         children=children,
    #     ))
    # except Exception:
    #     # có lỗi thì bỏ qua, sao loại 1 sẽ vẫn là 0
    #     st.warning(f"Không lấy được hạng sao từ Google Hotels: {e}")
    #     pass

    # ✅ Lưu lại file sau khi merge
    save_accommodation_db(db)

    # Nếu API trả ít hơn 5 chỗ → lấy thêm từ cache cho đủ data
    if len(accommodations) < 5:
        cached = load_accommodation_db()
        seen_ids = {a.id for a in accommodations}

        extra = []
        for d in cached.values():
            if d.get("city", "").lower() != city_name.lower():
                continue
            if d["id"] in seen_ids:
                continue
            extra.append(dict_to_acc(d))

        # gộp thêm (có thể giới hạn, ví dụ chỉ lấy thêm 20)
        accommodations.extend(extra[:20])


    return accommodations, (city_lon, city_lat)


PAGE_SIZE = 20

def build_query_phrases(city: str, wanted_types: List[str]) -> List[str]:
    """
    Tạo pool query phrase để làm giàu DB.
    Có cả tiếng Việt + tiếng Anh + luxury.
    """
    city = city.strip()
    wanted_types = [t.lower() for t in (wanted_types or [])]

    base = [
        f"khách sạn ở {city}",
        f"homestay ở {city}",
        f"hostel ở {city}",
        f"căn hộ dịch vụ ở {city}",
        f"resort ở {city}",
        f"apartment {city}",
        f"serviced apartment {city}",
        f"guest house {city}",
        # luxury / 5-star (để tăng chance ra “luxury”)
        f"khách sạn cao cấp ở {city}",
        f"khách sạn 5 sao ở {city}",
        f"luxury hotel {city}",
        f"5 star hotel {city}",
    ]

    # Nếu user có chọn type, thêm query “theo type” để tăng đa dạng
    type_specific = []
    if "hotel" in wanted_types:
        type_specific += [f"khách sạn ở {city}", f"hotel {city}"]
    if "homestay" in wanted_types:
        type_specific += [f"homestay ở {city}", f"guest house {city}"]
    if "hostel" in wanted_types:
        type_specific += [f"hostel ở {city}", f"backpacker hostel {city}"]
    if "apartment" in wanted_types:
        type_specific += [f"căn hộ ở {city}", f"serviced apartment {city}"]
    if "resort" in wanted_types:
        type_specific += [f"resort ở {city}", f"beach resort {city}"]

    pool = list(dict.fromkeys(base + type_specific))
    random.shuffle(pool)
    return pool


def serpapi_google_maps_search(query: str, city_lat: float, city_lon: float, start: int) -> list:
    """
    Gọi SerpAPI Google Maps (type=search) 1 trang.
    Trả về local_results list.
    """
    params = {
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com.vn",
        "q": query,
        "ll": f"@{city_lat},{city_lon},8z",
        "api_key": API_KEY,
        "hl": "vi",
        "start": start,
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results.get("local_results", []) or []

def parse_review_count(x) -> int:
    if x is None:
        return 0

    # nếu lỡ SerpAPI trả dict
    if isinstance(x, dict):
        for k in ("count", "total", "value", "reviews"):
            if k in x:
                return parse_review_count(x[k])
        return 0

    s = str(x).strip().lower()

    # bắt dạng 1.2k / 1,2k / 1.2m...
    m = re.search(r"([\d.,]+)\s*([km])\b", s)
    if m:
        num_str = m.group(1).replace(",", ".")  # 1,2k -> 1.2
        try:
            num = float(num_str)
            mult = 1000 if m.group(2) == "k" else 1_000_000
            return int(num * mult)
        except:
            return 0

    # bắt dạng "1.234", "1,234", "1.234 đánh giá" -> lấy hết chữ số
    digits = re.sub(r"\D", "", s)
    return int(digits) if digits else 0



def parse_maps_item_to_acc(item: dict, city_name: str, city_lat: float, city_lon: float, radius_km: Optional[float]) -> Optional[Accommodation]:
    """
    Parse 1 item từ local_results (Google Maps) -> Accommodation (chỉ data Maps).
    KHÔNG gọi Hotels ở đây.
    """
    raw_name = (item.get("title") or item.get("name") or "").strip()
    if not raw_name:
        return None
    name = raw_name

    data_id = item.get("data_id")
    if data_id is None:
        data_id = hash(name + str(item.get("address", "")))
    acc_id = str(data_id)

    # price
    raw_price = item.get("price")
    price = 0.0
    if raw_price:
        s = str(raw_price)
        m = re.search(r"\d+(?:[.,]\d+)?", s)
        value = float(m.group(0).replace(",", ".")) if m else 0.0
        if "₫" in s or value >= 50_000:
            price = value
        else:
            price = value * 26_405

    # rating + reviews
    rating_raw = item.get("rating")
    try:
        rating = float(rating_raw)
    except (TypeError, ValueError):
        rating = 0.0

    reviews_raw = (
    item.get("reviews")
    or item.get("user_ratings_total")
    or item.get("reviews_count")
    )
    reviews = parse_review_count(reviews_raw)
    try:
        reviews = parse_review_count(reviews_raw)
    except (TypeError, ValueError, AttributeError):
        reviews = 0

    # amenities basic từ text
    amenities = extract_amenities_from_google_property(item)
    desc = str(item).lower()

    def add_if(keywords, tag):
        for kw in keywords:
            if kw in desc:
                amenities.append(tag)
                break

    add_if(["wifi", "wi-fi"], "wifi")
    add_if(["free breakfast", "breakfast", "bữa sáng", "ăn sáng"], "breakfast")
    add_if(["pool", "swimming pool", "bể bơi", "hồ bơi"], "pool")
    add_if(["parking", "bãi đỗ xe", "chỗ đỗ xe"], "parking")
    amenities = list(dict.fromkeys(amenities))

    # gps
    gps = item.get("gps_coordinates") or {}
    lat = gps.get("latitude")
    lon = gps.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        lat = float(lat); lon = float(lon)
    except Exception:
        return None

    # distance
    dist = haversine_km(city_lon, city_lat, lon, lat)

    # type detect
    def detect_acc_type(item) -> str:
        name_ = (item.get("title") or "").lower()
        main_type = (item.get("type") or "").lower()
        extra_types = " ".join(t.lower() for t in item.get("types", []) if t)
        text = " ".join([name_, main_type, extra_types])

        if any(kw in text for kw in ["homestay", "guest house", "nhà nghỉ", "nhà trọ"]):
            return "homestay"
        if "resort" in text:
            return "resort"
        if "hostel" in text:
            return "hostel"
        if any(kw in text for kw in ["apartment", "căn hộ", "condotel", "serviced apartment"]):
            return "apartment"
        return "hotel"

    acc_type = detect_acc_type(item)

    # radius filter (nếu muốn)
    if radius_km is not None and dist > radius_km:
        return None

    return Accommodation(
        id=acc_id,
        name=name,
        city=normalize_city(city_name),
        type=acc_type,
        price=price,
        stars=0.0,              # stage1 chưa enrich
        rating=rating,          # lấy từ Maps API
        reviews=reviews,
        capacity=4,
        amenities=amenities,
        address=item.get("address", city_name),
        lon=lon,
        lat=lat,
        distance_km=dist,
    )


def stage1_fill_db_from_maps(q: SearchQuery, target_new: int = 50, max_pages: int = 8) -> tuple[dict, tuple[float, float], dict]:
    # """
    # Lần 1:
    # - Random query phrase + random start
    # - Chỉ gọi Google Maps
    # - Mục tiêu thêm target_new bản ghi mới vào DB
    # - Dừng nếu new_added>=target_new OR pages_used>=max_pages OR added_this_page==0
    # Trả về:
    #   - db dict (đã update)
    #   - city_center (lon,lat)
    #   - stat dict (new_added, pages_used)
    # """
    city_name = normalize_city(q.city)
    city_geo = smart_geocode(city_name + ", Vietnam")
    if not city_geo:
        raise ValueError(f"Không tìm thấy tọa độ thành phố: {city_name}")

    city_lat, city_lon = float(city_geo["lat"]), float(city_geo["lon"])
    city_center = (city_lon, city_lat)

    db = load_accommodation_db()
    queries = build_query_phrases(city_name, q.types)

    # random start offsets
    starts = list(range(0, PAGE_SIZE * 10, PAGE_SIZE))  # 0..180 (10 trang) -> nhưng sẽ bị giới hạn max_pages = 8
    random.shuffle(starts)

    new_added = 0
    pages_used = 0

    # tạo danh sách “attempts” (query,start) rồi shuffle để random thứ tự
    attempts = [(qq, stt) for qq in queries for stt in starts]
    random.shuffle(attempts)

    for (qq, stt) in attempts:
        if new_added >= target_new:
            break
        if pages_used >= max_pages:
            break

        local_results = []
        try:
            local_results = serpapi_google_maps_search(qq, city_lat, city_lon, stt)
        except Exception:
            # lỗi quota/mạng => coi như page rỗng
            local_results = []

        pages_used += 1

        added_this_page = 0
        for item in local_results:
            acc = parse_maps_item_to_acc(item, city_name, city_lat, city_lon, radius_km=None)  # stage1: không giới hạn radius để DB giàu
            if not acc:
                continue
            if acc.id in db:
                continue

            db[acc.id] = acc_to_dict(acc)
            added_this_page += 1
            new_added += 1

            if new_added >= target_new:
                break

        # ✅ điều kiện dừng theo đúng ý cậu
        if added_this_page == 0:
            break

    save_accommodation_db(db)

    stat = {"new_added": new_added, "pages_used": pages_used}
    return db, city_center, stat

def stage2_rank_from_db(q: SearchQuery, db: dict, top_n: int = 30):
    """
    Lần 2: không gọi API.
    Load từ db theo city -> rank -> top_n.
    """
    city_norm = normalize_city(q.city)
    all_acc = []
    for d in db.values():
        if normalize_city(d.get("city", "")) != city_norm:
            continue
        try:
            all_acc.append(dict_to_acc(d))
        except Exception:
            continue

    topN, relax_note = rank_accommodations(all_acc, q, top_k=top_n)
    return topN, relax_note

def is_fresh_record(cached: dict, days: int = 7) -> bool:
    ts = cached.get("updated_at")
    if not ts:
        return False
    try:
        # hỗ trợ cả "...Z" (UTC)
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))

        # nếu dt là naive thì ép sang UTC (phòng hờ)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

    except Exception:
        return False

    now_utc = datetime.now(timezone.utc)
    return (now_utc - dt) < timedelta(days=days)

def stage3_enrich_topN_and_rerank(topN_items: list, q: SearchQuery, db: dict, top_k: int = 5):
    """
    Lần 3:
    - enrich amenities + stars cho TopN (Hotels API)
    - update DB
    - rerank -> top_k
    """
    if not API_KEY:
        # không có key => bỏ enrich, rerank luôn
        accs = [it["accommodation"] for it in topN_items]
        top5, note = rank_accommodations(accs, q, top_k=top_k)
        return top5, note

    # enrich từng acc trong TopN
    for it in topN_items:
        acc = it["accommodation"]

        # cache trước nếu có
        cached = db.get(acc.id)
        if cached:
            if cached.get("amenities"):
                acc.amenities = cached["amenities"]
            if cached.get("stars") is not None:
                try:
                    acc.stars = float(cached["stars"])
                except Exception:
                    pass

        # amenities
        if not acc.amenities:
            try:
                enrich_amenities_with_hotels_api(acc, API_KEY)
            except Exception:
                pass

        # stars (chỉ hotel/resort)
        if acc.type in ("hotel", "resort") and (acc.stars is None or acc.stars <= 0):
            try:
                enrich_hotel_class_one_with_hotels_api(
                    acc,
                    API_KEY,
                    checkin=q.checkin,
                    checkout=q.checkout,
                    adults=q.adults,
                    children=q.children,
                )
            except Exception:
                pass

        new_rec = acc_to_dict(acc)
        cached = db.get(acc.id)

        # Nếu record còn "tươi" < 7 ngày => KHÔNG overwrite (tránh mất dữ liệu cũ)
        if cached and is_fresh_record(cached, days=7):
            # Nhưng vẫn cho phép "bổ sung" nếu DB thiếu mà new_rec có
            for k in ["amenities", "stars", "rating", "reviews", "price"]:
                if (cached.get(k) in (None, 0, 0.0, [], "")) and (new_rec.get(k) not in (None, 0, 0.0, [], "")):
                    cached[k] = new_rec[k]
            db[acc.id] = cached
        else:
            db[acc.id] = new_rec

    save_accommodation_db(db)

    # rerank lại sau enrich
    accs = [it["accommodation"] for it in topN_items]
    top5, relax_note = rank_accommodations(accs, q, top_k=top_k)
    return top5, relax_note


def recommend_top5_three_stage(q: SearchQuery, target_new: int = 50, top_n: int = 30, top_k: int = 5):
    t0 = time.perf_counter()

    # Stage 1: fill DB (Maps only)
    db, city_center, stat1 = stage1_fill_db_from_maps(q, target_new=target_new, max_pages=8)
    t1 = time.perf_counter()

    # Stage 2: DB only rank top30
    top30, note2 = stage2_rank_from_db(q, db, top_n=top_n)
    t2 = time.perf_counter()

    # Stage 3: enrich top30 then rerank top5
    top5, note3 = stage3_enrich_topN_and_rerank(top30, q, db, top_k=top_k)
    t3 = time.perf_counter()

    timing = {
        "stage1_maps_fill": t1 - t0,
        "stage2_db_rank":   t2 - t1,
        "stage3_hotels":    t3 - t2,
        "total":            t3 - t0,
        "new_added":        stat1["new_added"],
        "pages_used":       stat1["pages_used"],
    }
    # note ưu tiên stage3 (vì là kết quả cuối)
    relax_note = note3 or note2
    return top5, city_center, relax_note, timing



#def recommend_top5_from_api(q: SearchQuery):
    """
    ...
    Trả về:
      - danh sách top-5
      - toạ độ tâm city
      - relaxation_note: giải thích mức nới tiêu chí
    """
    accommodations, city_center = fetch_osm_accommodations(
        city_name=q.city,
        radius_km=q.radius_km,
        max_results=50,
    )

    if not accommodations:
        return [], city_center, (
            "Không tìm thấy dữ liệu chỗ ở nào quanh khu vực này từ OpenStreetMap. "
            "Bạn có thể thử tăng bán kính tìm kiếm hoặc chọn thành phố khác."
        )

    top5, relax_note = rank_accommodations(accommodations, q, top_k=5)
    return top5, city_center, relax_note


st.set_page_config(page_title="Tourism_Symstem", page_icon="💬")
MODEL = "llama3.2:1b"
client = Client(
    host='http://qkoin-34-11-248-204.a.free.pinggy.link'
)

def ollama_stream(history_messages):
    # --- Làm sạch messages ---
    cleaned = []

    for msg in history_messages:
        if msg["role"] in ("user", "assistant") and msg["content"].strip():
            cleaned.append(msg)

    # Xóa mọi assistant đứng đầu
    while cleaned and cleaned[0]["role"] == "assistant":
        cleaned.pop(0)

    # Nếu rỗng → thêm user bắt đầu
    if not cleaned:
        cleaned = [{"role": "user", "content": "Hello"}]

    # Gửi request an toàn cho Ollama
    response = client.chat(
        model=MODEL,
        messages=cleaned
    )

    return response["message"]["content"]

def ollama_generate_itinerary(prompt: str):
    """
    Gửi một prompt tạo lịch trình đến Ollama và trả về kết quả.
    Sử dụng logic tương tự như ollama_stream nhưng chỉ với 1 prompt.
    """
    response = client.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response['message']['content']

def save_message(uid: str, role: str, content: str):
    doc = {
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc)
    }
    db.collection("chats").document(uid).collection("messages").add(doc)

def load_last_messages(uid: str, limit: int = 8):
    q = (db.collection("chats").document(uid)
        .collection("messages")
        .order_by("ts", direction=firestore.Query.DESCENDING)
        .limit(limit))
    docs = list(q.stream())
    docs.reverse()
    out = []
    for d in docs:
        data = d.to_dict()
        out.append({"role": data.get("role", "assistant"),
                    "content": data.get("content", "")})
    return out

params = st.query_params
raw_token = params.get("id_token")
if isinstance(raw_token, list):
    id_token = raw_token[0]
else:
    id_token = raw_token
    
if id_token and not st.session_state.get("user"):
    id_token = params["id_token"][0]
    try:
        decoded = admin_auth.verify_id_token(id_token)
        st.session_state.user = {
            "email": decoded.get("email"),
            "uid": decoded.get("uid"),
            "idToken": id_token,
        }
        msgs = []
        try:
            msgs = load_last_messages(st.session_state.user["uid"], limit=8)
        except Exception:
            pass
        st.session_state.messages = deque(
            msgs if msgs else [{"role": "assistant", "content": BOT_GREETING}
],
            maxlen=8
        )
        st.experimental_set_query_params()
        st.success("Đăng nhập Google thành công!")
        st.rerun()
    except Exception as e:
        st.error(f"Xác thực Google thất bại: {e}")


@st.cache_resource
def get_firebase_clients():
    # Pyrebase (Auth)
    firebase_cfg = st.secrets["firebase_client"]
    firebase_app = pyrebase.initialize_app(firebase_cfg)
    auth = firebase_app.auth()

    # Admin (Firestore)
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase_admin"]))
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    return auth, db

auth, db = get_firebase_clients()


if "user" not in st.session_state:
    st.session_state.user = None 

if "messages" not in st.session_state:
    st.session_state.messages = deque([
        {"role": "assistant", "content": BOT_GREETING}
    ], maxlen=8)
else:
    if not isinstance(st.session_state.messages, deque):
        st.session_state.messages = deque(st.session_state.messages[-8:], maxlen=8)

if "chat_open" not in st.session_state:
    st.session_state.chat_open = False

if "just_opened_chat" not in st.session_state:
    st.session_state.just_opened_chat = False

# Lưu kết quả gợi ý nơi ở (Top 5 + thông tin city center) để hiển thị sau
if "accommodation_results" not in st.session_state:
    st.session_state.accommodation_results = None

# Lưu nơi ở được chọn để hiển thị map (KHẮC PHỤC LỖI ATTRIBUTEERROR)
if "selected_acc_id" not in st.session_state:
    st.session_state.selected_acc_id = None
    
# Kết quả route (để vẽ map giống file cũ)
if "route_result" not in st.session_state:
    st.session_state.route_result = None

# Trạng thái ẩn/hiện danh sách bước đi
if "show_route_steps" not in st.session_state:
    st.session_state.show_route_steps = False


def login_form():
    st.markdown("<h3 style='text-align: center;'>Đăng nhập</h3>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", key="email_login")
        password = st.text_input("Mật khẩu", type="password", key="password_login")
        
        # Cấu trúc: [Đệm, Nút Đăng nhập, Nút Đăng ký]
        col_pad, col_login, col_signup = st.columns([1, 0.95, 0.355]) 
        
        with col_login:
            # SỬA: Dùng CSS để căn giữa nút Đăng nhập trong cột của nó
            st.markdown(
                """
                <style>
                /* Căn giữa nút Đăng nhập trong cột */
                .stForm > div > div > div:nth-child(5) > div > div:nth-child(2) > div button { 
                    margin-left: 50%;
                    transform: translateX(-50%);
                }
                </style>
                """, unsafe_allow_html=True
            )
            
            # Nút Đăng nhập
            with stylable_container(
                "black",
                css_styles="""
                button {
                    background-color: #0DDEAA;
                    color: black;
                    width: 150px;       /* Chiều rộng nút */
                    height: 43px;       /* Chiều cao nút */
                    font-size: 30px;    /* Kích cỡ chữ */
                    margin-top: -15px; /* Thêm 10px khoảng trống phía trên, đẩy nút xuống 10px */
                    margin-bottom: 5px;
                }""",
            ):
                login = st.form_submit_button("Đăng nhập")
        
        with col_signup:
            # Nút Đăng ký (nằm ở lề phải)
            goto_signup = st.form_submit_button("Chưa có tài khoản? Đăng ký", type="primary")

    if goto_signup:
        st.session_state["show_signup"] = True
        st.session_state["show_login"] = False
        st.rerun()

    if login:
        # 1️⃣ Kiểm tra nhập trống trước khi gọi Firebase
        if not email.strip() or not password:
            st.warning("Vui lòng nhập đầy đủ Email và Mật khẩu.")
            return

        try:
            # 2️⃣ Gọi Firebase để đăng nhập
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state.user = {
                "email": email,
                "uid": user["localId"],
                "idToken": user["idToken"]
            }
            msgs = load_last_messages(st.session_state.user["uid"], limit=8)
            if msgs:
                st.session_state.messages = deque(msgs, maxlen=8)
                if st.session_state.messages[0]["role"] != "user":
                    st.session_state.messages.appendleft({
                        "role": "user",
                        "content": "Bắt đầu cuộc trò chuyện."
                    })
            else:
                st.session_state.messages = deque([
                    {"role": "assistant", "content": BOT_GREETING}
                ], maxlen=8)

            st.success("Đăng nhập thành công!")
            st.rerun()

        except Exception as e:
            # 3️⃣ Log chi tiết cho dev (trong terminal) nếu cần debug
            print("Firebase login error:", e)

            # 4️⃣ Thông báo gọn cho người dùng
            st.error("Email hoặc mật khẩu không đúng. Vui lòng nhập lại.")

def signup_form():
    st.subheader("Đăng ký")
    with st.form("signup_form", clear_on_submit=False):
        email = st.text_input("Email", key="email_signup")
        password = st.text_input("Mật khẩu (≥6 ký tự)", type="password", key="password_signup")
        
        # Cấu trúc: [Đệm, Nút Đăng ký, Nút Đăng nhập (quay lại)]
        col_pad, col_signup_btn, col_login_btn = st.columns([1, 0.85, 0.36]) 
        
        with col_signup_btn:
            # SỬA: Dùng CSS để căn giữa nút Tạo tài khoản
            st.markdown(
                """
                <style>
                /* Căn giữa nút Tạo tài khoản trong cột (sử dụng ID 'black-1' để phân biệt) */
                div[data-testid="stForm"] > div > div:nth-child(5) > div > div:nth-child(2) > div button {
                    margin-left: 50%;
                    transform: translateX(-50%);
                }
                </style>
                """, unsafe_allow_html=True
            )
            
            # Nút Tạo tài khoản
            with stylable_container(
                "black-1",
                css_styles="""
                button {
                    background-color: #0DD0DE;
                    color: black;
                }""",
            ):
                signup = st.form_submit_button("Tạo tài khoản")
        
        with col_login_btn:
            # Nút Đăng nhập (quay lại)
            goto_login = st.form_submit_button("Đã có tài khoản? Đăng nhập", type="primary")

    if goto_login:
        st.session_state["show_signup"] = False
        st.session_state["show_login"] = True
        st.rerun()

    if signup:
        try:
            user = auth.create_user_with_email_and_password(email, password)
            st.success("Tạo tài khoản thành công! Vui lòng đăng nhập.")
            time.sleep(3)
            st.session_state["show_signup"] = False
            st.session_state["show_login"] = True
            st.rerun()
        except Exception as e:
            st.error(f"Đăng ký thất bại: {e}")

@st.dialog("Trợ lý Mika")
def chat_dialog():
    if not st.session_state.user:
        st.info("Bạn cần đăng nhập để chat và lưu lịch sử.")
        return
    
    # 1. Định nghĩa khu vực chat (container)
    chat_body = st.container(height=600, border=True)

    # 2. Đảm bảo lịch sử chat được tải lần đầu
    if st.session_state.get("messages") is None:
        st.session_state["messages"] = get_chat_history(st.session_state.user["uid"]) if st.session_state.user else []
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": "Chào bạn, tôi là Mika, trợ lý du lịch AI của bạn. Tôi có thể giúp bạn lên kế hoạch chuyến đi hoặc tìm chỗ ở."})

    # 3. Hiển thị tất cả tin nhắn đã có trong lịch sử (bao gồm cả tin nhắn user vừa gửi)
    with chat_body:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # 4. Xử lý Input
    user_input = st.chat_input("Nhập tin nhắn...", key="dialog_input")
        
    if user_input:
        # A. Cập nhật và lưu tin nhắn người dùng
        st.session_state.messages.append({"role": "user", "content": user_input})
        if st.session_state.user:
            save_message(st.session_state.user["uid"], "user", user_input)
            
        # B. TẠO PHẢN HỒI (Streamlit sẽ rerun ngay sau khi input được gửi)
        try:
            with chat_body:
                # Tạo khu vực cho tin nhắn AI
                with st.chat_message("assistant"):
                    with st.spinner("Mika đang trả lời..."):
                        full_reply = ollama_stream(list(st.session_state.messages))
                        st.markdown(full_reply)

            # C. Lưu và cập nhật lịch sử với phản hồi AI
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
            if st.session_state.user:
                save_message(st.session_state.user["uid"], "assistant", full_reply)
                
        except requests.RequestException as e:
            with chat_body:
                with st.chat_message("assistant"):
                    st.error(f"Lỗi Ollama: {e}")
                    
        # KHÔNG DÙNG st.rerun() Ở ĐÂY.

@st.dialog("🗺️ Bản đồ & hướng dẫn đường đi")
def route_dialog():
    """
    Hộp thoại hiển thị bản đồ lộ trình + (nếu có) hướng dẫn từng bước.
    """
    if not st.session_state.route_result:
        st.warning(
            "Chưa có lộ trình để hiển thị. "
            "Vui lòng nhập điểm xuất phát và bấm 'Tìm đường đi đến nơi ở này' trước."
        )
        return

    data = st.session_state.route_result
    route = data["route"]

    # Thông tin tổng quãng đường + thời gian
    st.markdown(
        f"**Quãng đường:** ~{route['distance_km']:.2f} km  ·  "
        f"**Thời gian ước tính:** ~{route['duration_min']:.1f} phút"
    )

    # 🗺️ Bản đồ lộ trình (Folium)
    m = draw_map(data["src"], data["dst"], route)
    st_folium(m, height=520, width=None, returned_objects=[])

    # Nếu route có kèm 'steps' (phiên bản nâng cấp), thì hiển thị thêm
    steps = route.get("steps") if isinstance(route, dict) else None
    if steps:
        # collapsed mặc định, chỉ hiện khi user bấm vào
        with st.expander("📜 Bấm để xem hướng dẫn từng bước trên đường đi", expanded=False):
            col1, col2 = st.columns(2)
            n = len(steps)
            half = (n + 1) // 2

            with col1:
                for idx, text in enumerate(steps[:half], start=1):
                    st.markdown(f"{idx}. {text}")

            with col2:
                for idx, text in enumerate(steps[half:], start=half + 1):
                    st.markdown(f"{idx}. {text}")
    else:
        st.caption(
            "OSRM chưa trả về danh sách bước chi tiết cho lộ trình này, "
            "nên chỉ hiển thị tổng quãng đường và thời gian."
        )


# app.py (Vị trí: TRƯỚC dòng st.markdown("<h1...") )

# app.py (Vị trí mới: TRƯỚC dòng st.markdown("<h1...") )

if st.session_state.user:
    # Chia 3 cột: [Đệm trái rất lớn, Thông tin Email, Nút Đăng xuất]
    # Tỉ lệ [7, 2, 1] giúp đẩy nội dung sang phải
    col_left_pad, col_info, col_logout = st.columns([7, 2, 1]) 
    
    with col_info:
        # SỬA LỖI: THÊM margin-top: -10px; để kéo text lên
        st.markdown(
            f"""
            <div style='
                text-align: right; 
                font-weight: bold;
                font-size: 14px;
                margin-top: 10px; /* <--- KÉO TEXT LÊN 10px */
            '>
                <span style='
                    color: white; 
                    text-decoration: underline; 
                    white-space: nowrap;
                '>Đang đăng nhập: {st.session_state.user['email']}</span>
            </div>
            """, 
            unsafe_allow_html=True
        )

    with col_logout:
        # Nút Đăng xuất (sử dụng CSS để căn chỉnh)
        st.markdown(
            """
            <style>
            /* Target nút Đăng xuất cụ thể trong cột này */
            div[data-testid="stColumn"]:nth-child(3) button { 
                margin-top: -40px; /* <--- KÉO NÚT LÊN 10px để căn ngang */
                height: 30px; 
                font-size: 14px; 
            }
            </style>
            """, 
            unsafe_allow_html=True
        )
        if st.button("Đăng xuất", type="primary", key="logout_button_final"):
            st.session_state.user = None
            st.session_state.chat_open = False
            st.rerun()


st.markdown("<h1 style='text-align: center;'>Đặt tên hệ thống Login</h1>", unsafe_allow_html=True)

if "show_signup" not in st.session_state:
    st.session_state["show_signup"] = False
if "show_login" not in st.session_state:
    st.session_state["show_login"] = True

def format_vnd(value: float | int) -> str:
    """
    Định dạng số tiền theo kiểu Việt: 1.500.000 VND
    """
    return f"{value:,.0f}".replace(",", ".") + " VND"

def normalize_google_amenities(raw_amenities: list[str]) -> list[str]:
    """
    Nhận list tiện ích raw từ Google Hotels (chuỗi tiếng Anh),
    trả về list mã tiện ích nội bộ (wifi, spa, gym, ...)
    """
    result = set()
    for raw in raw_amenities or []:
        text = str(raw).lower()
        for key, code in GOOGLE_AMENITY_KEYWORDS.items():
            if key in text:
                result.add(code)
    return list(result)

def extract_amenities_from_google_property(prop: dict) -> list[str]:
    """
    Nhận JSON 1 khách sạn từ SerpAPI Google Hotels,
    trả về list mã tiện ích chuẩn hóa (wifi, spa, gym, ...)
    """
    result_codes = set()

    # 1) Field amenities chuẩn (nếu có)
    raw_amenities = prop.get("amenities", []) or []
    for raw in raw_amenities:
        text = str(raw).lower()
        for key, code in GOOGLE_AMENITY_KEYWORDS.items():
            if key in text:
                result_codes.add(code)

    # 2) Có thể tận dụng thêm phần description nếu muốn bắt được nhiều hơn
    desc = str(prop.get("description", "")).lower()
    for key, code in GOOGLE_AMENITY_KEYWORDS.items():
        if key in desc:
            result_codes.add(code)

    return list(result_codes)


# --- Bắt đầu: Phần Gợi ý Nơi Ở (Đã chỉnh sửa cho tương tác & 5 Dòng) ---

# Chỉ hiển thị giao diện gợi ý nơi ở khi người dùng đã đăng nhập
if st.session_state.user:
    # 1. ĐỊNH NGHĨA CỘT (Cần thiết để có bố cục 50%/50%)
    col_left, col_right = st.columns([0.75, 1.25]) 

    # ==========================
    # KHU VỰC CỘT TRÁI (FORM)
    # ==========================
    # Các loại hình nơi ở mà hệ thống hỗ trợ
    TYPE_OPTIONS = [
        ("hotel", "Khách sạn"),
        ("homestay", "Homestay"),
        ("apartment", "Căn hộ"),
        ("hostel", "Hostel"),
        ("resort", "Resort"),
    ]

    # Map từ text tiện ích của Google Hotels -> mã nội bộ của mình
    GOOGLE_AMENITY_KEYWORDS = {
        "free wifi": "wifi",
        "free wi-fi": "wifi",
        "wi-fi": "wifi",
        "wifi": "wifi",

        "free parking": "parking",
        "parking": "parking",

        "indoor pool": "pool",
        "outdoor pool": "pool",
        "pool": "pool",

        "fitness center": "gym",
        "fitness centre": "gym",
        "gym": "gym",

        "restaurant": "restaurant",
        "bar": "bar",

        "free breakfast": "breakfast",
        "complimentary breakfast": "breakfast",
        "breakfast included": "breakfast",

        "spa": "spa",

        "beach access": "beach_access",
        "beachfront": "beach_access",

        "air-conditioned": "air_conditioning",
        "air conditioning": "air_conditioning",

        "family rooms": "family_rooms",
        "family-friendly": "family_rooms",

        "airport shuttle": "airport_shuttle",
        "shuttle": "airport_shuttle",

        "pet-friendly": "pet_friendly",
        "pets allowed": "pet_friendly",
    }

    # Các tiện ích chuẩn hóa mà hệ thống hiểu
    AMENITY_OPTIONS = {
        "Wi-Fi miễn phí": "wifi",
        "Bữa sáng": "breakfast",
        "Hồ bơi": "pool",
        "Chỗ đỗ xe": "parking",
        "Spa": "spa",
        "Phòng gym / Fitness": "gym",
        "Nhà hàng": "restaurant",
        "Bar": "bar",
        "Thân thiện thú cưng": "pet_friendly",
        "Đưa đón sân bay": "airport_shuttle",
        "Phòng gia đình": "family_rooms",
        "Điều hòa": "air_conditioning",
        "Truy cập bãi biển": "beach_access",
    }

    AMENITY_LABELS_BY_CODE = {code: label for label, code in AMENITY_OPTIONS.items()}


    with col_left:
        st.markdown("## 🏨 Gợi ý Nơi Ở Phù Hợp")
        with st.form("recommendation_input_form"):
            st.write("Nhập nhu cầu nơi ở, hệ thống sẽ gợi ý Top 5 địa điểm phù hợp nhất xung quanh thành phố điểm đến.")

            # 1. Thành phố điểm đến
            acc_raw = st.text_input("Thành phố Điểm đến", value="Hồ Chí Minh", key="acc_city_destination")
            acc_city = normalize_city(acc_raw)

            # 2. Ngày nhận phòng / trả phòng
            col_dates = st.columns(2)
            with col_dates[0]:
                checkin = st.date_input(
                    "Ngày nhận phòng",
                    value=date.today(),
                    min_value=date.today(),
                    key="checkin_date"
                )
            with col_dates[1]:
                # Ngày trả phòng sớm nhất phải sau ngày nhận phòng 1 ngày
                min_checkout = checkin + timedelta(days=1)

                # Nếu session đang lưu ngày cũ < min_checkout thì auto đẩy lên min_checkout
                if "checkout_date" in st.session_state:
                    old_checkout = st.session_state.checkout_date
                    if old_checkout < min_checkout:
                        st.session_state.checkout_date = min_checkout

                checkout = st.date_input(
                    "Ngày trả phòng",
                    value=min_checkout,          # giá trị mặc định (khi chưa có trong session)
                    min_value=min_checkout,      # không cho chọn trước ngày này
                    key="checkout_date",)
            # 3. Số khách: người lớn + trẻ em
            col_guests = st.columns(2)
            with col_guests[0]:
                adults = st.number_input(
                    "Người lớn",
                    min_value=1, max_value=20,
                    value=2, step=1,
                    key="adults_input"
                )
            with col_guests[1]:
                children = st.number_input(
                    "Trẻ em",
                    min_value=0, max_value=10,
                    value=0, step=1,
                    key="children_input"
                )
            total_guests = int(adults + children)

            # 4. Khoảng giá (tính theo 1 đêm, VND)
            st.markdown("#### Ngân sách của bạn (mỗi đêm)")

            MIN_PRICE = 0
            MAX_PRICE = 8_000_000

            price_min_default = 300_000
            price_max_default = 1_500_000

            price_min, price_max = st.slider(
                "Ngân sách của bạn (mỗi đêm)",
                min_value=MIN_PRICE,
                max_value=MAX_PRICE,
                value=(price_min_default, price_max_default),  # 2 đầu slider
                step=50_000,
                key="price_range_slider",
            )

            # User kéo tới max -> hiểu là "8tr+"
            unlimited_max = (price_max >= MAX_PRICE)

            if unlimited_max:
                st.caption(
                    f"Khoảng giá: từ {price_min:,.0f} VND trở lên (không giới hạn tối đa, "
                    f"mốc hiển thị: {MAX_PRICE:,.0f} VND+)"
                )
            else:
                st.caption(
                    f"Khoảng giá: {price_min:,.0f} VND – {price_max:,.0f} VND"
                )

            # 5. Loại hình nơi ở
            st.markdown("#### Loại hình nơi ở")

            type_cols = st.columns(2)  # chia 2 cột cho gọn
            selected_types = []

            for i, (value, label) in enumerate(TYPE_OPTIONS):
                with type_cols[i % 2]:
                    checked = st.checkbox(
                        label,
                        key=f"type_{value}",
                    )
                    if checked:
                        selected_types.append(value)

            # nếu user bỏ tick hết thì coi như chọn tất cả (tránh query rỗng)
            if not selected_types:
                selected_types = [v for v, _ in TYPE_OPTIONS]


            # 6. Rating tối thiểu & Bán kính tìm kiếm
            col_rating, col_radius = st.columns(2)
            # ===== SỐ SAO TỐI THIỂU (các ô tick) =====
            with col_rating:
                st.markdown("**Số sao tối thiểu**")

                star3 = st.checkbox("Từ 3 sao trở lên", key="star_3plus")
                star4 = st.checkbox("Từ 4 sao trở lên", key="star_4plus")
                star5 = st.checkbox("5 sao", key="star_5")

                selected_stars = []
                if star3:
                    selected_stars.append(3.0)
                if star4:
                    selected_stars.append(4.0)
                if star5:
                    selected_stars.append(5.0)

                # Nếu user tick nhiều ô, mình chọn NGƯỠNG CAO NHẤT (lọc gắt hơn).
                # Nếu không tick ô nào => không giới hạn số sao (0.0).
                stars_min = min(selected_stars) if selected_stars else 0.0
                
                rating_min = 0.0
            
            # ===== KHOẢNG CÁCH TỪ TRUNG TÂM (các ô tick) =====
            with col_radius:
                st.markdown("**Khoảng cách từ trung tâm**")

                dist1 = st.checkbox("Dưới 1 km", key="dist_lt1")
                dist3 = st.checkbox("Dưới 3 km", key="dist_lt3")
                dist5 = st.checkbox("Dưới 5 km", key="dist_lt5")

                selected_dists = []
                if dist1:
                    selected_dists.append(1.0)
                if dist3:
                    selected_dists.append(3.0)
                if dist5:
                    selected_dists.append(5.0)

                # Nếu user tick nhiều ô, mình lấy khoảng cách NHỎ NHẤT (lọc gắt hơn).
                # Nếu không tick ô nào => dùng DEFAULT_RADIUS_KM (hiểu là "toàn khu vực tìm kiếm").
                radius_km = max(selected_dists) if selected_dists else None


            # 7. Tiện ích bắt buộc & ưu tiên (dùng checkbox để form gọn hơn)
            st.markdown("#### Tiện ích")
            selected_amenities = []
            with st.expander("Tiện ích bạn quan tâm", expanded=False):
                amen_cols = st.columns(2)
                for i, (label, code) in enumerate(AMENITY_OPTIONS.items()):
                    with amen_cols[i % 2]:
                        checked = st.checkbox(
                            label,
                            key=f"amen_{code}_{i}",
                        )
                        if checked:
                            selected_amenities.append(code)


            # 7.3 Chế độ ưu tiên xếp hạng
            priority_label_map = {
                "Cân bằng (giá, rating, tiện ích, khoảng cách)": "balanced",
                "Ưu tiên giá rẻ": "cheap",
                "Ưu tiên gần trung tâm": "near_center",
                "Ưu tiên tiện ích": "amenities",
            }

            priority_choice = st.selectbox(
                "Bạn muốn hệ thống ưu tiên điều gì khi xếp hạng?",
                list(priority_label_map.keys()),
                index=0,
                key="priority_select",
            )
            priority_code = priority_label_map[priority_choice]


            submit_acc = st.form_submit_button("🔍 Gợi ý Top 5 nơi ở", key="submit_acc_button")

            # ===== XỬ LÝ KHI NHẤN NÚT GỢI Ý =====
            if submit_acc:
                if not acc_city.strip():
                    st.error("Vui lòng nhập Thành phố Điểm đến.")
                elif price_min > 0 and price_max > 0 and price_min > price_max:
                    st.error("Giá tối thiểu phải nhỏ hơn hoặc bằng giá tối đa.")
                else:
                    # Tạo SearchQuery từ input người dùng
                    # Nếu user kéo tới 8tr+ thì coi như KHÔNG GIỚI HẠN giá tối đa
                    effective_price_max = 0.0 if unlimited_max else float(price_max)
                    q = SearchQuery(
                        city=acc_city.strip(),
                        group_size=total_guests,
                        price_min=float(price_min),
                        price_max=effective_price_max,
                        types=selected_types,  
                        rating_min=float(rating_min),
                        amenities_preferred=selected_amenities,
                        radius_km=radius_km,
                        priority=priority_code,
                        stars_min=stars_min,  
                        checkin=checkin,
                        checkout=checkout,
                        adults=int(adults),
                        children=int(children),
                    )

                    with st.spinner("Đang tìm kiếm và xếp hạng các nơi ở phù hợp..."):
                        try:
                            top5, city_center, relax_note, timing = recommend_top5_three_stage(
                                q,
                                target_new=50,   # ✅ mặc định luôn 50 như cậu muốn
                                top_n=30,
                                top_k=5
                            )

                            st.session_state.accommodation_results = {
                                "query": q,
                                "city_center": city_center,
                                "results": top5,
                                "relaxation_note": relax_note,
                            }
                            st.session_state.selected_acc_id = None

                            # lưu timing chi tiết từng stage
                            st.session_state.last_timing = timing

                        except Exception as e:
                            st.error(f"Lỗi khi chạy pipeline 3-stage: {e}")
                            st.session_state.accommodation_results = None
                    #     try:
                    #         # 🕒 T0: bắt đầu gọi API
                    #         t0 = time.perf_counter()

                    #         accommodations, city_center = fetch_google_hotels(
                    #             city_name=q.city,
                    #             radius_km=q.radius_km,
                    #             wanted_types=q.types,      # ⬅ truyền loại user chọn
                    #             checkin=q.checkin,      # ✅ ngày nhận phòng
                    #             checkout=q.checkout,    # ✅ ngày trả phòng
                    #             adults=q.adults,        # ✅ số người lớn
                    #             children=q.children,    # ✅ số trẻ em
                    #         )

                    #         # 🕒 T1: API xong
                    #         t1 = time.perf_counter()

                    #         # 2) Gộp thêm dữ liệu từ file DB làm “đệm” nếu API trả quá ít
                    #         cached = load_accommodation_db()          # hàm cậu đã viết trước đó
                    #         if len(accommodations) < 10:              # ngưỡng, muốn khác thì đổi
                    #             seen_ids = {a.id for a in accommodations}
                    #             extra = []

                    #             for d in cached.values():
                    #                 # chỉ lấy những nơi ở cùng thành phố
                    #                 if d.get("city", "").lower() != q.city.lower():
                    #                     continue
                    #                 # tránh trùng id
                    #                 if d["id"] in seen_ids:
                    #                     continue
                    #                 extra.append(dict_to_acc(d))      # chuyển dict -> Accommodation

                    #             # gộp thêm tối đa 50 chỗ từ DB
                    #             accommodations.extend(extra[:50])
                            
                    #         # 3) Xếp hạng và lấy Top 5
                    #         top5, relax_note = rank_accommodations(accommodations, q, 5)
                    #         # 🕒 T2: xếp hạng xong
                    #         t2 = time.perf_counter()

                    #         st.session_state.accommodation_results = {
                    #             "query": q,
                    #             "city_center": city_center,
                    #             "results": top5,
                    #             "relaxation_note": relax_note,
                    #         }
                    #         st.session_state.selected_acc_id = None # Reset khi tìm kiếm mới
                        
                    #         st.session_state.last_timing = {
                    #             "api":  t1 - t0,
                    #             "rank": t2 - t1,
                    #             "total": t2 - t0,
                    #         }
                        
                    #     except requests.RequestException as e:
                    #         st.error(f"Lỗi khi gọi API OpenStreetMap/Overpass: {e}")
                    #         st.session_state.accommodation_results = None

                    st.rerun()
    
    # ==========================
    # KHU VỰC CỘT PHẢI (KẾT QUẢ TOP 5/CHI TIẾT VÀ BẢN ĐỒ)
    # ==========================
    with col_right:
        results_state = st.session_state.accommodation_results
        
        # 1. HIỂN THỊ KẾT QUẢ KHI CHƯA CÓ NƠI Ở NÀO ĐƯỢC CHỌN (SHOW ALL 5 ROWS)
        if results_state and results_state.get("results") and st.session_state.selected_acc_id is None:
            note = results_state.get("relaxation_note")
            if note:
                st.info(note)

            q = results_state["query"]
            priority_text = {
                "balanced": "Cân bằng giữa giá, rating, tiện ích và khoảng cách",
                "cheap": "Ưu tiên giá rẻ",
                "near_center": "Ưu tiên gần trung tâm thành phố",
                "amenities": "Ưu tiên nhiều tiện ích",
            }.get(getattr(q, "priority", "balanced"), "Cân bằng")

            st.caption(f"Chế độ ưu tiên hiện tại: **{priority_text}**")


            st.markdown("## 🔝 Top 5 nơi ở được đề xuất")
            raw_top5 = results_state["results"]

            # ❗ Loại trùng theo acc.id
            seen_ids = set()
            top5 = []
            for item in raw_top5:
                acc = item["accommodation"]
                if acc.id in seen_ids:
                    continue
                seen_ids.add(acc.id)
                top5.append(item)

            # 💡 Debug: hiển thị lại điều kiện đã dùng cho lần gợi ý này
            q_used = results_state["query"]
            
            display_pmax = (
                f"{int(MAX_PRICE):,}+"
                if q_used.price_max == 0
                else f"{int(q_used.price_max):,}"
            )

            display_radius = (
                f"{q_used.radius_km} km"
                if q_used.radius_km is not None
                else "không giới hạn"
            )

            display_pmax = (
                f"{int(MAX_PRICE):,}+"
                if q_used.price_max == 0
                else f"{int(q_used.price_max):,}"
            )

            display_radius = (
                f"{q_used.radius_km} km"
                if q_used.radius_km is not None
                else "không giới hạn"
            )

            st.caption(
                f"⚙️ Điều kiện lần gợi ý này: "
                f"Giá từ {int(q_used.price_min):,} VND đến {display_pmax} VND | "
                f"Rating tối thiểu: {q_used.rating_min} | "
                f"Bán kính: {display_radius}"
            )

            timing = st.session_state.get("last_timing")
            if timing:
                st.caption(
                    f"⏱ Stage1(Maps fill): {timing['stage1_maps_fill']:.2f}s "
                    f"(+{timing['new_added']} mới, {timing['pages_used']} trang) · "
                    f"Stage2(DB rank): {timing['stage2_db_rank']:.2f}s · "
                    f"Stage3(Hotels enrich): {timing['stage3_hotels']:.2f}s · "
                    f"Tổng: {timing['total']:.2f}s"
                )
            
            for i, item in enumerate(top5):
                acc = item["accommodation"]
                score = item["score"]
                rank = i + 1

                # Mỗi item sẽ là một dòng mới (Row)
                with st.container(border=True): 
                    
                        
                        # Tạo 2 cột bên trong dòng (4 phần cho thông tin, 1 phần cho nút)
                        row_col_info, row_col_button = st.columns([4, 1])

                        with row_col_info:
                            # 1. Tên và loại hình
                            st.markdown(f"**#{rank}. {acc.name}** ({acc.type})")
                            
                            # 2. Giá, Rating, Khoảng cách
                            if acc.price and acc.price > 0:
                                price_text = format_vnd(acc.price)
                            else:
                                price_text = "đang cập nhật"
                            
                            # Chỉ hiện sao cho hotel & resort có sao > 0
                            show_stars = (
                                acc.type in ("hotel", "resort")
                                # and acc.stars is not None
                                # and acc.stars > 0

                            )

                            if show_stars:
                                if acc.stars is None or acc.stars <= 0:
                                    stars_text = " | **Hạng sao:** (chưa cập nhật)"
                                else:
                                    stars_text = f" | **Hạng sao:** {int(acc.stars)}⭐"
                            else:
                                stars_text = ""  # không show sao cho homestay / apartment / hostel
                            st.markdown(
                                f"**Giá:** {price_text} | "
                                f"**Rating:** {acc.rating:.1f}/5 ({acc.reviews} đánh giá) | "
                                f"{stars_text} | "
                                f"**Khoảng cách đến trung tâm:** {acc.distance_km:.2f} km"
                            )

                            # --- 3. Tiện ích NỔI BẬT + điểm tổng ---
                            if acc.amenities:
                                labels = [
                                    AMENITY_LABELS_BY_CODE.get(code, code)
                                    for code in acc.amenities
                                ]
                                top_labels = labels[:4]  # chỉ show tối đa 4 tiện ích trên card
                                st.caption(
                                    "Tiện ích nổi bật: " + ", ".join(top_labels) +
                                    f" | Điểm gợi ý tổng hợp: {score:.3f}"
                                )
                            else:
                                st.caption(
                                    f"Tiện ích nổi bật: (chưa có thông tin) | Điểm gợi ý tổng hợp: {score:.3f}"
                                )
                            
                            # --- 4. Nút xem TIỆN ÍCH CHI TIẾT (Hotel API) ---
                            if API_KEY:
                                btn_key = f"btn_amen_{acc.id}_{i}"
                                if st.button(
                                    "Xem tiện ích chi tiết",
                                    key=btn_key,
                                ):
                                    full_amenities = fetch_full_amenities_from_hotels_api(acc, q_used)

                                    if not full_amenities:
                                        # nếu Hotels không có, fallback: dùng luôn acc.amenities hiện có
                                        if acc.amenities:
                                            st.info("Hiện chỉ có danh sách tiện ích cơ bản:")
                                            for am in acc.amenities:
                                                st.write(f"• {am}")
                                        else:
                                            st.info("Chưa tìm được danh sách tiện ích cho nơi ở này.")
                                    else:
                                        with st.expander("Danh sách tiện ích chi tiết", expanded=True):
                                            for amen in full_amenities:
                                                st.markdown(f"- {amen}")


                        with row_col_button:
                            # SỬ DỤNG st.button THÔNG THƯỜNG VỚI KEY DUY NHẤT
                            if st.button(f"Xem Bản Đồ", key=f"select_acc_btn_{acc.id}"):
                                st.session_state.selected_acc_id = acc.id
                                st.rerun() # Giữ lại rerun vì nó chuyển đổi trạng thái hiển thị

        # 2. HIỂN THỊ CHI TIẾT KHI CÓ NƠI Ở ĐƯỢC CHỌN (SHOW 1 COLUMN LỚN)
        elif results_state and results_state.get("results") and st.session_state.selected_acc_id is not None:
            # Lọc ra nơi ở đã chọn
            selected_item = next(
                (item for item in results_state["results"] if item["accommodation"].id == st.session_state.selected_acc_id), 
                None
            )
            
            if selected_item:
                acc = selected_item["accommodation"]
                st.markdown(f"## 🗺️ Vị trí: {acc.name}")
                st.info(f"Đang hiển thị vị trí chi tiết của **{acc.name}**. Nhấn 'Trở lại' để xem lại Top 5.")

                # Nút trở lại (nằm trong cột phải)
                if st.button("⬅️ Trở lại Top 5"):
                    st.session_state.selected_acc_id = None
                    st.rerun()
            else:
                st.session_state.selected_acc_id = None 
                st.rerun()

        elif results_state is not None and results_state.get("results") == []:
            note = results_state.get("relaxation_note")
            if note:
                st.info(note)
            else:
                st.info("Không có nơi ở nào thỏa điều kiện tìm kiếm hiện tại. Hãy thử nới lỏng tiêu chí hoặc tăng bán kính.")
        else:
            st.info("Nhập yêu cầu và nhấn nút 'Gợi ý' để xem Top 5 địa điểm.")

        # =========================================
        # KHU VỰC TÌM ĐƯỜNG (CHỈ INPUT)
        # =========================================
        if st.session_state.selected_acc_id is not None and results_state and results_state.get("results"):
            st.divider()

            # Lấy thông tin nơi ở đã chọn
            selected_item = next(
                (item for item in results_state["results"]
                 if item["accommodation"].id == st.session_state.selected_acc_id),
                None
            )

            if selected_item:
                acc = selected_item["accommodation"]

                st.markdown("### 🗺️ Tìm đường đi đến nơi ở này")
                st.write(f"Điểm đến hiện tại: **{acc.name} ({acc.city})**")

                # === Input điểm xuất phát + phương tiện ===
                origin_query = st.text_input(
                    "Điểm xuất phát (địa chỉ hoặc tên địa điểm)",
                    value="HCMUS, Ho Chi Minh City",
                    key="origin_query",
                )

                col_profile, col_zoom = st.columns(2)
                with col_profile:
                    profile = st.radio(
                        "Phương tiện",
                        ["driving", "walking", "cycling"],
                        horizontal=True,
                        key="route_profile",
                    )
                with col_zoom:
                    zoom = st.slider(
                        "Mức zoom bản đồ",
                        6, 18, 12,
                        key="map_zoom",
                    )

                # Nút tìm đường
                if st.button("🚗 Đường đi", key="find_route_btn"):
                    if not origin_query.strip():
                        st.error("Vui lòng nhập điểm xuất phát.")
                    else:
                        # 1) Geocode điểm xuất phát
                        with st.spinner("Đang tìm tọa độ điểm xuất phát..."):
                            src = smart_geocode(origin_query)



                        if not src:
                            st.error("Không tìm được tọa độ điểm xuất phát. Hãy nhập chi tiết hơn.")
                        else:
                            # 2) Chuẩn bị điểm đến
                            dst = {
                                "name": f"{acc.name} ({acc.city})",
                                "lat": acc.lat,
                                "lon": acc.lon,
                            }

                            # 3) Gọi OSRM tìm route
                            with st.spinner("Đang tính lộ trình bằng OSRM..."):
                                route = osrm_route(src, dst, profile=profile)

                            if not route:
                                st.warning("Không tìm được lộ trình phù hợp. Thử đổi phương tiện hoặc địa điểm.")
                            else:
                                st.session_state.route_result = {
                                    "src": src,
                                    "dst": dst,
                                    "profile": profile,
                                    "route": route,
                                }
                                # Mỗi lần tìm đường mới thì ẩn danh sách bước đi
                                st.session_state.show_route_steps = False

                                st.success(
                                    f"Lộ trình ~{route['distance_km']:.2f} km, "
                                    f"~{route['duration_min']:.1f} phút ({profile})."
                                )

                                # Gợi ý phương tiện (giữ nguyên đoạn dưới)
                                best_profile, explain = recommend_transport_mode(
                                    route["distance_km"], route["duration_min"]
                                )
                                labels = {
                                    "walking": "đi bộ",
                                    "cycling": "xe đạp",
                                    "driving": "ô tô / xe máy",
                                }

                                if best_profile == profile:
                                    st.info(
                                        f"Hệ thống đánh giá quãng đường khoảng "
                                        f"**{route['distance_km']:.1f} km** "
                                        f"({route['duration_min']:.0f} phút) và "
                                        f"phương tiện hiện tại (**{labels[profile]}**) "
                                        f"**là phù hợp**. {explain}"
                                    )
                                else:
                                    st.info(
                                        f"Hệ thống đánh giá quãng đường khoảng "
                                        f"**{route['distance_km']:.1f} km** "
                                        f"({route['duration_min']:.0f} phút). "
                                        f"Gợi ý nên di chuyển bằng **{labels[best_profile]}** – {explain} "
                                        f"Hiện tại bạn đang xem lộ trình cho **{labels[profile]}**; "
                                        "bạn có thể đổi phương tiện phía trên rồi bấm "
                                        "'Tìm đường' lại nếu muốn."
                                    )
                                # 🔔 SAU KHI TÍNH XONG LỘ TRÌNH → MỞ HỘP THOẠI MAP
                                route_dialog()

                                # --- Phân tích độ phức tạp lộ trình & cảnh báo ---
                                level, label_vi, summary, reasons = analyze_route_complexity(
                                    route, profile
                                )

                                if level == "low":
                                    st.success(
                                        f"**Độ phức tạp lộ trình: {label_vi}.** {summary}"
                                    )
                                elif level == "medium":
                                    st.info(
                                        f"**Độ phức tạp lộ trình: {label_vi}.** {summary}"
                                    )
                                else:
                                    st.warning(
                                        f"**Độ phức tạp lộ trình: {label_vi}.** {summary}"
                                    )

                                if reasons:
                                    bullet_text = "\n".join(f"- {r}" for r in reasons)
                                    st.markdown(
                                        "**Một vài lưu ý trên đường đi:**\n" + bullet_text
                                    )


                # Thêm chút info chi tiết chỗ ở (giữ từ bản map cũ của team)
                st.markdown(f"**Địa chỉ:** {acc.address}")
                st.markdown(f"**Khoảng cách tới TT:** {acc.distance_km:.2f} km")
                st.markdown(f"**Tiện ích:** {', '.join(acc.amenities) or 'Không có thông tin'}")


else:
    # Nếu chưa đăng nhập thì vẫn giữ logic cũ: hiển thị form đăng ký / đăng nhập
    if st.session_state.get("show_signup", False):
        signup_form()
    elif st.session_state.get("show_login", True):
        login_form()

# --- Kết thúc: Phần Gợi ý Nơi Ở ---

# st.markdown("<h5 style='text-align: center;'>Click 💬 để mở hộp thoại chat</h5>", unsafe_allow_html=True)

# --- MINI CHAT BOT Ở BÊN PHẢI, CUỘN THEO NỘI DUNG ---

fab_clicked = False  # để luôn có biến, kể cả khi chưa đăng nhập

if st.session_state.user:
    spacer, chat_col = st.columns([6, 1])  # đẩy bot về phía bên phải
    with chat_col:
        # Bubble lời chào
        st.markdown(
            """
            <div id="chat-mini-wrapper">
                <div class="chat-mini-bubble">
                    Xin chào! Hôm nay bạn đã nghĩ muốn đi đâu chưa?
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Nút icon bot
        with stylable_container(
            "chat-fab-container",
            css_styles="""
            button {
                background-color: #ffffff;
                color: #333333;
                border: none;
                width: 64px !important;
                height: 64px !important;
                border-radius: 50%;
                font-size: 30px;
            }""",
        ):
            fab_clicked = st.button("🤖", key="open_chat_fab", help="Mở trò chuyện với Mika")

if fab_clicked:
    st.session_state.chat_open = True
    st.session_state.just_opened_chat = True
    st.rerun()

if st.session_state.chat_open and st.session_state.just_opened_chat:
    chat_dialog()
    st.session_state.just_opened_chat = False




st.markdown("""
<style>
/* Container mini bot ở góc phải */
/* MINI BOT CHAT BÊN PHẢI – CUỘN THEO NỘI DUNG */

/* Wrapper chứa bubble, đặt nó sát lề phải của cột */
#chat-mini-wrapper {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    margin-top: 1.5rem;
    margin-right: 0.5rem;
}

/* Bong bóng lời chào */
#chat-mini-wrapper .chat-mini-bubble {
    background: #ffffff;
    color: #333333;
    padding: 8px 12px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    font-size: 13px;
    max-width: 260px;
    margin-bottom: 0.5rem;
}

/* Thêm shadow + hover cho nút icon bot (nằm ngay sau wrapper) */
#chat-mini-wrapper + div button {
    box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}

#chat-mini-wrapper + div button:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 24px rgba(250,206,175,0.28);
}

            
div[data-testid="stDialog"] {
    left: 50%; 
    transform: translateX(-50%);
    background: transparent !important;
}
div[data-testid="stDialog"] > div:first-child {
    background: transparent !important;
    box-shadow: none !important;
}
.block-container {
    padding-left: 1rem; /* Giữ lại chút padding nhỏ nếu cần */
    padding-right: 1rem;
    max-width: 100%; /* Đảm bảo container không bị giới hạn chiều rộng */
}
/* Loại bỏ hoàn toàn padding của main-content */
section.main .block-container {
    padding-left: 0;
    padding-right: 0;
}
/* Đặt lại padding bên trong cột để nội dung không chạm sát lề (quan trọng) */
[data-testid="column"] {
    padding-left: 1rem; /* Thêm padding 1rem vào cột trái */
    padding-right: 1rem; /* Thêm padding 1rem vào cột phải */
}

/* CHỈNH SỬA ĐỂ CỘT TRÁI CHẠM SÁT LỀ TRÁI VÀ CỘT PHẢI CHẠM SÁT LỀ PHẢI */
/* Lấy cột đầu tiên (col_left) và cột cuối cùng (col_right) */
[data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
    padding-left: 0rem; /* Loại bỏ padding trái của cột trái */
}
[data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child {
    padding-right: 0rem; /* Loại bỏ padding phải của cột phải */
}

            
/* Ẩn thanh trượt cho toàn bộ Dialog Box (cửa sổ pop-up) */
div[data-testid="stDialog"] {
    /* ... (giữ lại các thuộc tính cũ: left, transform, background) ... */
    
    /* 1. Ẩn thanh trượt cho Webkit (Chrome, Safari) */
    -ms-overflow-style: none;  /* IE and Edge */
    scrollbar-width: none;     /* Firefox */
}

/* 2. Ẩn thanh trượt cho Webkit Browsers */
div[data-testid="stDialog"]::-webkit-scrollbar {
    display: none;
}

/* Áp dụng cho container chính của dialog để đảm bảo thanh trượt nội dung cũng bị ẩn */
div[data-testid="stDialog"] > div:first-child {
    /* ... (giữ lại các thuộc tính cũ: background, box-shadow) ... */
    
    /* Ẩn thanh trượt nội dung bên trong */
    -ms-overflow-style: none;
    scrollbar-width: none;
}
div[data-testid="stDialog"] > div:first-child::-webkit-scrollbar {
    display: none;
}


/* ================================================= */
/* TÙY CHỈNH GIAO DIỆN CHAT BOX (MESSAGE ALIGNMENT) */
/* ================================================= */

/* 1. Tin nhắn của USER (Căn phải, Avatar bên phải) */

/* Target: Container tin nhắn (căn phải toàn bộ) */
div[data-testid="stChatMessage"][data-user] {
    justify-content: flex-end; 
    padding-left: 15%; 
    padding-right: 0.5rem;
}

            
/* VỊ TRÍ NỘI DUNG CHAT USER: Đặt nội dung ở phía trước (bên trái) */
div[data-testid="stChatMessage"][data-user] .stChatMessageContent {
    background-color: #0DDEAA; 
    color: black;
    margin-right: 0.5rem; 
    order: 1; /* NỘI DUNG: Đặt nó ở vị trí đầu tiên (bên trái) */
    
    /* ... (giữ lại các thuộc tính border-radius) ... */
    border-top-right-radius: 4px; 
    border-bottom-right-radius: 4px;
    border-bottom-left-radius: 12px;
    border-top-left-radius: 12px !important;
}


/* VỊ TRÍ AVATAR USER: Đặt avatar ở phía sau (bên phải) */
div[data-testid="stChatMessage"][data-user] .stChatMessageAvatar {
    order: 2; 
}

/* Target: Bubble chứa nội dung tin nhắn của USER */
div[data-testid="stChatMessage"][data-user] .stChatMessageContent {
    background-color: #0DDEAA; 
    color: black;
    margin-right: 0.5rem; /* KHOẢNG CÁCH: giữa bubble và avatar */
    border-top-right-radius: 4px; 
    border-bottom-right-radius: 4px;
    border-bottom-left-radius: 12px;
    border-top-left-radius: 12px !important;
}

/* 2. Tin nhắn của ASSISTANT (Căn trái, Avatar bên trái) */

/* Target: Container tin nhắn (căn trái toàn bộ) */
div[data-testid="stChatMessage"]:not([data-user]) {
    justify-content: flex-start; 
    padding-right: 15%; 
    padding-left: 0.5rem;
}

/* VỊ TRÍ AVATAR ASSISTANT: Đặt avatar ở phía trước (bên trái) */
div[data-testid="stChatMessage"]:not([data-user]) .stChatMessageAvatar {
    order: 1; 
}

/* Target: Bubble chứa nội dung tin nhắn của ASSISTANT */
div[data-testid="stChatMessage"]:not([data-user]) .stChatMessageContent {
    background-color: #333333; 
    color: white;
    margin-left: 0.5rem; /* KHOẢNG CÁCH: giữa avatar và bubble */
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 12px;
    border-top-right-radius: 12px !important;
}

/* 3. Ẩn tên vai trò (role/user) nhưng giữ lại avatar */
div[data-testid="stChatMessage"] .stChatMessageHeader {
    display: none; 
}            


</style>
""", unsafe_allow_html=True)