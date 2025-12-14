import time
import streamlit as st
import pyrebase
import pandas as pd
import pydeck as pdk
import firebase_admin
import requests
from dataclasses import dataclass
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
import os
from deep_translator import GoogleTranslator

# Initialize recommendations to an empty list
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []


def translate_text(text, target_lang="en"):
    try:
        if not text.strip():
            return text
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as e:
        print("Translation error:", e)
        return text


lang = st.selectbox(
    "🌐 Ngôn ngữ",
    ["vi", "en"],
    index=0,
)
st.session_state["lang"] = lang


# API_KEY = st.secrets["serpapi_key"]
API_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"

BOT_GREETING = "Xin chào! Hôm nay bạn đã nghĩ muốn đi đâu chưa?"

# ===================== MÔ-ĐUN THUẬT TOÁN GỢI Ý NƠI Ở =====================

@dataclass
class Accommodation:
    """
    Đại diện cho 1 nơi ở sau khi đã nạp từ API OpenStreetMap/Overpass.
    (price, rating hiện tại có thể là giá trị giả lập trong bản demo.)
    """
    id: str
    name: str
    city: str
    type: str           # hotel / hostel / apartment / ...
    price: float        # giá ước lượng VND/đêm
    stars: float        # 0–5
    rating: float       # 0–10
    capacity: int       # sức chứa tối đa
    amenities: List[str]
    address: str
    lon: float
    lat: float
    distance_km: float  # khoảng cách tới tâm thành phố (km)


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
    rating_min: float              # rating tối thiểu (0–10)
    amenities_required: List[str]  # tiện ích bắt buộc (phải có)
    amenities_preferred: List[str] # tiện ích ưu tiên (có thì cộng điểm)
    radius_km: float               # bán kính tìm kiếm quanh thành phố (km)
    priority: str = "balanced"     # 'balanced' / 'cheap' / 'near_center' / 'amenities'



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


def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery) -> List[Accommodation]:
    """
    Thử lọc theo nhiều mức "gắt" khác nhau.
    Trả về:
      - filtered: list[Accommodation]
      - note: chuỗi giải thích mức nới lỏng (để hiển thị lên UI).
    """

    required_lower = [x.lower() for x in q.amenities_required]

    def _do_filter(rating_min: float,
                   amenity_mode: str = "all",
                   price_relax: float = 1.0) -> List[Accommodation]:
        """
        amenity_mode:
          - 'all'    : phải có TẤT CẢ tiện ích bắt buộc
          - 'any'    : có ÍT NHẤT MỘT tiện ích bắt buộc
          - 'ignore' : bỏ qua tiện ích bắt buộc
        price_relax:
          - 1.0  : giữ nguyên khoảng giá
          - >1.0 : nới rộng khoảng giá (ví dụ 1.2 = rộng thêm 20%)
        """
        # Tính lại khoảng giá sau khi nới
        pmin = q.price_min
        pmax = q.price_max

        if price_relax > 1.0 and pmax > 0 and pmax > pmin:
            center = (pmin + pmax) / 2
            half_span = (pmax - pmin) / 2
            extra = half_span * (price_relax - 1.0)
            pmin = max(0, center - half_span - extra)
            pmax = center + half_span + extra

        filtered_local = []
        for a in accommodations:
            # Giá
            if pmin > 0 and a.price < pmin:
                continue
            if pmax > 0 and a.price > pmax:
                continue

            # Sức chứa
            if a.capacity < q.group_size:
                continue

            # Loại chỗ ở
            if q.types and (a.type not in q.types):
                continue

            # Rating
            if a.rating < rating_min:
                continue

            # Tiện ích
            have_lower = [am.lower() for am in a.amenities]

            if required_lower:
                if amenity_mode == "all":
                    if any(req not in have_lower for req in required_lower):
                        continue
                elif amenity_mode == "any":
                    if not any(req in have_lower for req in required_lower):
                        continue
                # 'ignore' thì bỏ qua check tiện ích

            filtered_local.append(a)

        return filtered_local

    levels = []

    # Level 0: gắt nhất – giống hiện tại
    levels.append({
        "desc": "Các gợi ý dưới đây thỏa **đầy đủ** tiêu chí bạn đã chọn.",
        "amenity_mode": "all",
        "rating_min": q.rating_min,
        "price_relax": 1.0,
    })

    # Level 1: cho phép chỉ cần thỏa MỘT phần tiện ích bắt buộc
    if q.amenities_required:
        levels.append({
            "desc": "Không có nơi ở nào đáp ứng đủ tất cả tiện ích bắt buộc. "
                    "Hệ thống ưu tiên các nơi đáp ứng **một phần** tiện ích bạn chọn.",
            "amenity_mode": "any",
            "rating_min": q.rating_min,
            "price_relax": 1.0,
        })

    # Level 2: bỏ điều kiện tiện ích, hạ rating_min xuống 1 điểm
    levels.append({
        "desc": "Không có nơi ở nào đáp ứng đầy đủ rating/tiện ích. "
                "Hệ thống đã nới lỏng rating tối thiểu và tiện ích bắt buộc "
                "để vẫn gợi ý các nơi gần với nhu cầu của bạn.",
        "amenity_mode": "ignore",
        "rating_min": max(0.0, q.rating_min - 1.0),
        "price_relax": 1.0,
    })

    # Level 3: tiếp tục nới rộng khoảng giá
    levels.append({
        "desc": "Không có nơi ở nào thỏa hết tiêu chí trong khoảng giá hiện tại. "
                "Hệ thống đã nới rộng khoảng giá một chút để tìm thêm lựa chọn phù hợp.",
        "amenity_mode": "ignore",
        "rating_min": max(0.0, q.rating_min - 1.0),
        "price_relax": 1.2,
    })

    for cfg in levels:
        cand = _do_filter(
            rating_min=cfg["rating_min"],
            amenity_mode=cfg["amenity_mode"],
            price_relax=cfg["price_relax"],
        )
        if cand:
            return cand, cfg["desc"]

    # Nếu đến đây vẫn trống thì trả tất cả cho chắc (rất hiếm khi xảy ra)
    return accommodations, (
        "Dữ liệu khu vực này khá hạn chế, hệ thống đã gợi ý các nơi ở gần nhất "
        "với yêu cầu của bạn trong phạm vi hiện có."
    )


def clamp01(x: float) -> float:
    """Giới hạn giá trị trong [0,1] để tránh <0 hoặc >1."""
    return max(0.0, min(1.0, x))

#mô-đun “Scoring & Ranking module”
def score_accommodation(a: Accommodation, q: SearchQuery) -> float:
    """
    Tính điểm xếp hạng cho 1 nơi ở theo nhiều tiêu chí.

    - S_price  : 1 nếu giá gần mức mong muốn, 0 nếu chênh lệch quá lớn.
    - S_stars  : sao / 5.
    - S_rating : rating / 10.
    - S_amen   : tỉ lệ tiện ích yêu cầu + ưu tiên được đáp ứng.
    - S_dist   : càng gần tâm city (so với bán kính radius_km) thì điểm càng cao.

    Tổng hợp: 
    Score = 0.25*S_price + 0.20*S_stars + 0.25*S_rating + 0.20*S_amen + 0.10*S_dist
    """

    # ----- 1. Điểm GIÁ -----
    Pmin, Pmax = q.price_min, q.price_max
    if Pmax > Pmin:
        Pc = (Pmin + Pmax) / 2.0                  # giá mục tiêu ở giữa khoảng
        denom = max(1.0, (Pmax - Pmin) / 2.0)     # "nửa khoảng" để chuẩn hoá
        S_price = 1.0 - min(abs(a.price - Pc) / denom, 1.0)
    else:
        # Nếu user không đặt khoảng giá rõ ràng, cho tất cả = 1
        S_price = 1.0

    # ----- 2. Điểm SAO & RATING -----
    S_stars = clamp01(a.stars / 5.0)       # 0–5 sao -> 0–1
    S_rating = clamp01(a.rating / 10.0)    # 0–10 rating -> 0–1

    # ----- 3. Điểm TIỆN ÍCH -----
    have = set(x.lower() for x in a.amenities)
    req = set(x.lower() for x in q.amenities_required)
    pref = set(x.lower() for x in q.amenities_preferred)

    if req or pref:
        match_req = len(have.intersection(req))
        match_pref = len(have.intersection(pref))

        # required trọng số 1.0, preferred trọng số 0.5
        matched_score = match_req + 0.5 * match_pref
        max_possible = max(1.0, len(req) + 0.5 * len(pref))
        S_amen = matched_score / max_possible
    else:
        S_amen = 1.0  # user không yêu cầu tiện ích gì đặc biệt

    # ----- 4. Điểm KHOẢNG CÁCH -----
    # distance_km: khoảng cách tới tâm thành phố; so với radius_km
    if q.radius_km > 0:
        S_dist = 1.0 - min(a.distance_km / q.radius_km, 1.0)
    else:
        S_dist = 1.0

    # ----- 5. Chọn trọng số theo chế độ ưu tiên -----
    mode = getattr(q, "priority", "balanced")

    if mode == "cheap":
        # Ưu tiên GIÁ rẻ
        w_price, w_stars, w_rating, w_amen, w_dist = 0.40, 0.15, 0.20, 0.15, 0.10
    elif mode == "near_center":
        # Ưu tiên GẦN TRUNG TÂM
        w_price, w_stars, w_rating, w_amen, w_dist = 0.20, 0.10, 0.20, 0.15, 0.35
    elif mode == "amenities":
        # Ưu tiên TIỆN ÍCH
        w_price, w_stars, w_rating, w_amen, w_dist = 0.20, 0.10, 0.20, 0.40, 0.10
    else:
        # Cân bằng (mặc định) – như ban đầu
        w_price, w_stars, w_rating, w_amen, w_dist = 0.25, 0.20, 0.25, 0.20, 0.10

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

def geocode(q: str):
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


# def serpapi_geocode(q: str):
#     # 1. GÁN CỨNG KEY (Để đảm bảo hàm này luôn có key đúng)
#     # Bạn thay key của bạn vào đây:
#     # HARDCODED_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"
    
#     print(f"DEBUG: Đang Geocode '{q}' với SerpApi...")

#     params = {
#         "engine": "google_maps",
#         "q": q,
#         "type": "search",
#         "api_key": HARDCODED_KEY, # Dùng key cứng tại đây
#         "hl": "vi"
#     }
    
#     try:
#         # Gọi API
#         search = GoogleSearch(params)
#         results = search.get_dict()
        
#         # 2. KIỂM TRA LỖI TỪ API
#         if "error" in results:
#             print(f"DEBUG: ❌ SerpApi Error: {results['error']}")
#             return None
            
#         # 3. XỬ LÝ KẾT QUẢ (Thử nhiều trường hợp)
#         # Trường hợp 1: local_results (Kết quả địa điểm cụ thể)
#         if "local_results" in results and len(results["local_results"]) > 0:
#             place = results["local_results"][0]
#             print(f"DEBUG: ✅ Tìm thấy (local_results): {place.get('title')}")
#             return {
#                 "name": place.get("title"),
#                 "lat": place["gps_coordinates"]["latitude"],
#                 "lon": place["gps_coordinates"]["longitude"],
#                 "address": place.get("address", "")
#             }
            
#         # Trường hợp 2: place_results (Kết quả chính xác duy nhất)
#         if "place_results" in results:
#             place = results["place_results"]
#             print(f"DEBUG: ✅ Tìm thấy (place_results): {place.get('title')}")
#             return {
#                 "name": place.get("title"),
#                 "lat": place["gps_coordinates"]["latitude"],
#                 "lon": place["gps_coordinates"]["longitude"],
#                 "address": place.get("address", "")
#             }
            
#         # Nếu không tìm thấy gì
#         print("DEBUG: ⚠️ Không tìm thấy toạ độ nào trong phản hồi của Google Maps.")
#         # In thử các keys để debug xem Google trả về cái gì
#         print(f"DEBUG: Keys nhận được: {list(results.keys())}") 
#         return None

#     except Exception as e:
#         print(f"DEBUG: ❌ Lỗi ngoại lệ trong serpapi_geocode: {e}")
#         return None

def serpapi_geocode(q: str):
    """
    Sử dụng Nominatim để tìm tọa độ chính xác cho bản đồ OSRM.
    """
    try:
        # Thêm user_agent để không bị chặn
        geolocator = Nominatim(user_agent="my_travel_app_fix_final_v2")
        location = geolocator.geocode(q, exactly_one=True, addressdetails=True, timeout=10)
        if location:
            return {
                "name": location.address,
                "lat": location.latitude,
                "lon": location.longitude
            }
    except Exception as e:
        print(f"Nominatim error: {e}")
    
    return None


# def osrm_route(src, dst, profile="driving"):
#     """
#     Tính lộ trình bằng OSRM public:
#       - src, dst: dict có keys 'lat', 'lon', 'name'
#       - profile: 'driving' / 'walking' / 'cycling'

#     Trả về:
#       {
#         distance_km: float,
#         duration_min: float,
#         geometry: list[(lat, lon)],
#         steps: list[str],
#         distance_text: str,
#         duration_text: str
#       }
#     """
#     url = (
#         f"https://router.project-osrm.org/route/v1/"
#         f"{profile}/{src['lon']},{src['lat']};{dst['lon']},{dst['lat']}"
#     )
#     params = {
#         "overview": "full",       # lấy full đường đi
#         "geometries": "geojson",  # geometry dạng GeoJSON
#         "steps": "true",          # lấy chi tiết từng bước
#     }

#     try:
#         r = requests.get(url, params=params, timeout=20)
#         r.raise_for_status()
#         data = r.json()

#         if data.get("code") != "Ok" or not data.get("routes"):
#             print("⚠️ OSRM trả về code:", data.get("code"))
#             return None

#         route = data["routes"][0]

#         distance_km = route["distance"] / 1000.0
#         duration_min = route["duration"] / 60.0

#         # ---- 1) Chuyển geometry GeoJSON -> list[(lat, lon)] cho draw_map ----
#         coords = route["geometry"]["coordinates"]    # [[lon, lat], ...]
#         geometry = [(lat, lon) for lon, lat in coords]

#         # ---- 2) Tạo list hướng dẫn từng bước ----
#         legs = route.get("legs", [])
#         step_descriptions = []
#         for leg in legs:
#             for step in leg.get("steps", []):
#                 desc = describe_osrm_step(step)      # đã có sẵn phía trên
#                 if desc:
#                     step_descriptions.append(desc)

#         return {
#             "distance_km": distance_km,
#             "duration_min": duration_min,
#             "geometry": geometry,
#             "steps": step_descriptions,
#             "distance_text": f"~{distance_km:.2f} km",
#             "duration_text": f"~{duration_min:.1f} phút",
#         }

#     except Exception as e:
#         print("❌ Lỗi khi gọi OSRM:", e)
#         return None

def osrm_route(src, dst, profile="driving"):
    """
    Tính lộ trình OSRM chuẩn xác + Hệ số kẹt xe Việt Nam.
    """
    try:
        s_lat, s_lon = float(src['lat']), float(src['lon'])
        d_lat, d_lon = float(dst['lat']), float(dst['lon'])
    except ValueError:
        return None

    # OSRM yêu cầu: Longitude trước, Latitude sau
    url = (
        f"https://router.project-osrm.org/route/v1/"
        f"{profile}/{s_lon},{s_lat};{d_lon},{d_lat}"
    )
    
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return None

        route = data["routes"][0]
        distance_km = route["distance"] / 1000.0
        
        # SỬA LỖI: Nhân hệ số kẹt xe (3 lần cho xe, 12 lần cho đi bộ)
        traffic_factor = 3.0 if profile in ["driving", "cycling"] else 12
        duration_min = (route["duration"] / 60.0) * traffic_factor

        # SỬA LỖI: Đảo ngược tọa độ để vẽ Map đúng
        coords_geojson = route["geometry"]["coordinates"]
        geometry = [(lat, lon) for lon, lat in coords_geojson]

        # Xử lý steps (giữ nguyên logic lấy steps của bạn)
        legs = route.get("legs", [])
        step_descriptions = []
        for leg in legs:
            for step in leg.get("steps", []):
                desc = describe_osrm_step(step)
                if desc: step_descriptions.append(desc)

        return {
            "distance_km": distance_km,
            "duration_min": duration_min,
            "geometry": geometry,
            "steps": step_descriptions,
            "distance_text": f"{distance_km:.2f} km",
            "duration_text": f"~{duration_min:.0f} phút",
        }
    except Exception as e:
        print("Lỗi OSRM:", e)
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


# def describe_osrm_step(step: dict) -> str:
#     """
#     Nhận 1 step từ OSRM và trả về 1 câu mô tả ngắn gọn bằng tiếng Việt.

#     Ví dụ:
#       - 'Đi thẳng 500 m trên đường Nguyễn Văn Cừ.'
#       - 'Rẽ phải vào đường Lê Lợi.'
#       - 'Đến điểm đến ở bên phải.'
#     """
#     maneuver = step.get("maneuver", {})
#     step_type = maneuver.get("type", "")
#     modifier = (maneuver.get("modifier") or "").lower()
#     name = (step.get("name") or "").strip()
#     distance = step.get("distance", 0.0)  # mét
#     dist_str = _format_distance(distance)

#     # Mapping hướng rẽ
#     dir_map = {
#         "right": "rẽ phải",
#         "slight right": "chếch phải",
#         "sharp right": "quẹo gắt phải",
#         "left": "rẽ trái",
#         "slight left": "chếch trái",
#         "sharp left": "quẹo gắt trái",
#         "straight": "đi thẳng",
#         "uturn": "quay đầu",
#     }

#     # ---- Các trường hợp chính ----
#     if step_type == "depart":
#         if name:
#             return f"Bắt đầu từ {name}."
#         return "Bắt đầu từ điểm xuất phát."

#     if step_type == "arrive":
#         side = maneuver.get("modifier", "").lower()
#         if side in ("right", "left"):
#             side_vi = "bên phải" if side == "right" else "bên trái"
#             return f"Đến điểm đến ở {side_vi}."
#         return "Đến điểm đến."

#     if step_type in ("turn", "end of road", "fork"):
#         action = dir_map.get(modifier, "rẽ")
#         if name:
#             return f"Đi {dist_str} rồi {action} vào đường {name}."
#         else:
#             return f"Đi {dist_str} rồi {action}."

#     if step_type == "roundabout":
#         exit_nr = maneuver.get("exit")
#         if exit_nr:
#             return f"Vào vòng xuyến, đi hết lối ra thứ {exit_nr}."
#         else:
#             return "Vào vòng xuyến và tiếp tục theo hướng chính."

#     if step_type in ("merge", "on ramp", "off ramp"):
#         if name:
#             return f"Nhập làn/ra khỏi làn và tiếp tục trên {name} khoảng {dist_str}."
#         return f"Nhập làn/ra khỏi làn và tiếp tục khoảng {dist_str}."

#     # Fallback: mô tả chung chung
#     if name:
#         return f"Đi tiếp {dist_str} trên đường {name}."
#     return f"Đi tiếp {dist_str}."

def describe_osrm_step(step: dict) -> str:
    """
    Phiên bản nâng cấp: Dịch hướng dẫn đường đi OSRM sang tiếng Việt tự nhiên hơn.
    """
    maneuver = step.get("maneuver", {})
    step_type = maneuver.get("type", "")
    modifier = (maneuver.get("modifier") or "").lower()
    name = (step.get("name") or "").strip()
    # Nếu không có tên đường, thử dùng ref (số hiệu đường, vd: QL1A)
    if not name:
        name = (step.get("ref") or "").strip()

    distance = step.get("distance", 0.0)
    dist_str = _format_distance(distance)

    # Từ điển hướng
    dir_map = {
        "right": "rẽ phải", "slight right": "chếch sang phải", "sharp right": "quẹo gắt sang phải",
        "left": "rẽ trái", "slight left": "chếch sang trái", "sharp left": "quẹo gắt sang trái",
        "straight": "đi thẳng", "uturn": "quay đầu xe",
    }
    action = dir_map.get(modifier, "rẽ")

    # 1. Khởi hành
    if step_type == "depart":
        return f"🚀 Bắt đầu di chuyển từ {name if name else 'điểm xuất phát'}."
    
    # 2. Đến nơi
    if step_type == "arrive":
        side = maneuver.get("modifier", "")
        side_text = "ở bên phải" if side == "right" else ("ở bên trái" if side == "left" else "")
        return f"🏁 Đã đến điểm đến {side_text}."

    # 3. Vòng xuyến
    if step_type == "roundabout":
        exit_nr = maneuver.get("exit")
        return f"🔄 Vào vòng xuyến, đi theo lối ra thứ {exit_nr}."

    # 4. Các hành động rẽ / đi tiếp
    if step_type in ("turn", "end of road", "fork", "merge", "new name", "continue"):
        if modifier == "straight":
            if name: return f"⬆️ Đi thẳng {dist_str} trên {name}."
            return f"⬆️ Đi thẳng {dist_str}."
        else:
            if name: return f" {action.capitalize()} vào {name}, đi tiếp {dist_str}."
            return f" {action.capitalize()}, sau đó đi {dist_str}."

    # Mặc định
    if name:
        return f"Đi tiếp {dist_str} trên {name}."
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
    if distance_km <= 2.0:
        return "walking", "Quãng đường ngắn, đi bộ hoặc xe đạp là lựa chọn tốt cho sức khỏe, tiết kiệm chi phí và thoải mái ngắm cảnh xung quanh."
    elif distance_km <= 5:
        return "cycling", "Quãng đường khá ngắn, đi xe đạp hoặc xe máy sẽ nhanh và tiện lợi hơn. Nếu không mang hành lí và thời gian thoải mái thì có thể đi bộ."
    elif distance_km <= 30:
        return "cycling", "Quãng đường trung bình, phù hợp đi xe máy. Nếu mang nhiều hành lý hoặc muốn thoải mái có thể gọi ô tô."
    elif distance_km <= 100:
        return "driving", "Quãng đường khá xa, nên đi ô tô hoặc xe máy để đảm bảo thời gian và sự thoải mái."
    else:
        return "driving", "Quãng đường rất xa, đi ô tô hoặc máy bay là lựa chọn duy nhất để đảm bảo an toàn và tiết kiệm thời gian." 

# def analyze_route_complexity(route: dict, profile: str):
#     """
#     Phân tích độ phức tạp dựa trên dữ liệu từ Google Maps.
#     """
#     distance_km = route.get("distance_km", 0.0)
#     # Google tính duration rất chuẩn (đã bao gồm tắc đường nếu có dữ liệu), tin tưởng nó hơn tính toán thủ công
#     duration_min = route.get("duration_min", 0.0)
#     steps_list = route.get("steps", [])
#     steps_count = len(steps_list)

#     difficulty_score = 0
#     reasons = []

#     # 1. Phân tích quãng đường
#     if distance_km > 50:
#         difficulty_score += 3
#         reasons.append(f"Quãng đường rất dài ({distance_km:.1f} km), cần nghỉ ngơi giữa chừng.")
#     elif distance_km > 20:
#         difficulty_score += 2
#         reasons.append("Quãng đường khá dài, hãy chuẩn bị sức khỏe.")
    
#     # 2. Phân tích độ phức tạp của đường đi (số lượng ngã rẽ)
#     # Google thường gộp các hướng dẫn "đi thẳng" nên nếu steps nhiều nghĩa là phải rẽ nhiều
#     if steps_count > 25:
#         difficulty_score += 2
#         reasons.append(f"Lộ trình rất phức tạp với {steps_count} chỉ dẫn chuyển hướng.")
#     elif steps_count > 15:
#         difficulty_score += 1
#         reasons.append(f"Lộ trình có khá nhiều ngã rẽ ({steps_count} bước).")

#     # 3. Phân tích tốc độ trung bình (để phát hiện tắc đường/đường xấu)
#     if duration_min > 0 and distance_km > 0:
#         avg_speed = distance_km / (duration_min / 60.0) # km/h
        
#         if profile == "driving":
#             if avg_speed < 20: # Ô tô/xe máy mà < 20km/h là rất chậm
#                 difficulty_score += 2
#                 reasons.append("Tốc độ di chuyển dự kiến rất chậm (đường đông hoặc xấu).")
#         elif profile == "cycling":
#             if avg_speed < 8:
#                 difficulty_score += 1
#                 reasons.append("Tốc độ đạp xe dự kiến chậm hơn bình thường.")

#     # 4. Kết luận
#     if difficulty_score <= 1:
#         level = "low"
#         label_vi = "Dễ đi"
#         summary = "Lộ trình đơn giản, đường thông thoáng."
#     elif difficulty_score <= 3:
#         level = "medium"
#         label_vi = "Trung bình"
#         summary = "Lộ trình có chút thử thách về khoảng cách hoặc các ngã rẽ."
#     else:
#         level = "high"
#         label_vi = "Phức tạp"
#         summary = "Lộ trình khó, tốn nhiều thời gian hoặc đường đi phức tạp."

#     return level, label_vi, summary, reasons

def analyze_route_complexity(route: dict, profile: str):
    """
    Phân tích độ phức tạp lộ trình (Phiên bản tối ưu cho giao thông Việt Nam).
    Dựa trên: Thời gian di chuyển thực tế, Số lượng khúc cua, và Quãng đường.
    """
    distance_km = route.get("distance_km", 0.0)
    duration_min = route.get("duration_min", 0.0) # Thời gian này đã nhân hệ số kẹt xe ở bước trước
    steps_list = route.get("steps", [])
    steps_count = len(steps_list)

    difficulty_score = 0
    reasons = []

    # 1. Đánh giá theo THỜI GIAN (Quan trọng nhất ở VN)
    # Đi xe máy/ô tô mà trên 45 phút là bắt đầu mệt
    if duration_min > 90:
        difficulty_score += 3
        reasons.append(f"Thời gian di chuyển rất lâu (~{int(duration_min // 60)}h{int(duration_min % 60)}p), dễ gây mệt mỏi.")
    elif duration_min > 45:
        difficulty_score += 2
        reasons.append(f"Thời gian di chuyển khá lâu (~{int(duration_min)} phút).")
    elif duration_min > 25:
        difficulty_score += 1

    # 2. Đánh giá theo QUÃNG ĐƯỜNG
    # Ở nội thành, >15km là xa. Ngoại thành >30km là xa.
    if distance_km > 30:
        difficulty_score += 2
        reasons.append(f"Quãng đường xa ({distance_km:.1f} km).")
    elif distance_km > 15:
        difficulty_score += 1
        reasons.append("Quãng đường tương đối dài so với di chuyển nội thành.")

    # 3. Đánh giá theo ĐỘ RẮC RỐI (Số lượng ngã rẽ)
    # Quá nhiều ngã rẽ (trên 20) dễ bị lạc hoặc nhầm đường
    if steps_count > 30:
        difficulty_score += 2
        reasons.append(f"Đường đi rất rắc rối, có tới {steps_count} lần chuyển hướng.")
    elif steps_count > 18:
        difficulty_score += 1
        reasons.append("Lộ trình có nhiều ngã rẽ, cần chú ý quan sát bản đồ.")

    # 4. Đánh giá TỐC ĐỘ TRUNG BÌNH (Phát hiện kẹt xe nặng)
    # Nếu đi xe máy mà tốc độ < 15km/h => Kẹt xe hoặc đường rất xấu
    if duration_min > 0:
        avg_speed = distance_km / (duration_min / 60.0)
        if profile == "driving" and avg_speed < 15:
            difficulty_score += 2
            reasons.append("Cảnh báo: Tốc độ di chuyển dự kiến rất chậm (khu vực đông đúc/kẹt xe).")

    # --- KẾT LUẬN ---
    if difficulty_score <= 1:
        level = "low"
        label_vi = " Dễ đi"
        summary = "Lộ trình ngắn, đơn giản, phù hợp để đi ngay."
    elif difficulty_score <= 3:
        level = "medium"
        label_vi = " Trung bình"
        summary = "Lộ trình tốn chút thời gian hoặc cần chú ý các ngã rẽ."
    else:
        level = "high"
        label_vi = " Phức tạp"
        summary = "Lộ trình khó (xa, lâu hoặc tắc đường). Nên cân nhắc nghỉ ngơi hoặc chọn giờ thấp điểm."

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

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_osm_accommodations(city_name: str, radius_km: float = 5.0, max_results: int = 50):
    """
    Gọi OpenStreetMap (Overpass API) để lấy danh sách nơi ở quanh một thành phố.

    Bước:
    1) Geocode tên thành phố -> (lat_city, lon_city)
    2) Dùng Overpass query lấy các node/way/relation có tourism=hotel|hostel|guest_house|apartment
       trong bán kính radius_km quanh city.
    3) Convert về list[Accommodation], trong đó:
       - price, rating, capacity, amenities được GIẢ LẬP từ sao + một số tag.
    """

    # ----- 1. Geocode city -----
    city_geo = serpapi_geocode(city_name + ", Vietnam")
    if not city_geo:
        return [], None  # không tìm được city

    city_lat = city_geo["lat"]
    city_lon = city_geo["lon"]
    radius_m = int(radius_km * 1000)

    # ----- 2. Overpass query -----
    # Lấy các đối tượng có tourism là hotel, hostel, guest_house hoặc apartment
    query = f"""
    [out:json][timeout:25];
    (
      node["tourism"~"hotel|hostel|guest_house|apartment"](around:{radius_m},{city_lat},{city_lon});
      way["tourism"~"hotel|hostel|guest_house|apartment"](around:{radius_m},{city_lat},{city_lon});
      relation["tourism"~"hotel|hostel|guest_house|apartment"](around:{radius_m},{city_lat},{city_lon});
    );
    out center {max_results};
    """

    resp = requests.post(OVERPASS_URL, data=query)
    resp.raise_for_status()
    data = resp.json()

    elements = data.get("elements", [])
    accommodations: list[Accommodation] = []

    # ----- 3. Duyệt kết quả Overpass & convert -> Accommodation -----
    for el in elements:
        tags = el.get("tags", {})

        # 👉 Dùng id OSM để CỐ ĐỊNH random cho từng chỗ ở
        acc_id = str(el.get("id"))
        random.seed(acc_id)

        # Lấy lat, lon: node có sẵn; way/relation dùng 'center'
        if el["type"] == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:
            center = el.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue  # bỏ qua nếu không có toạ độ

        # Tên chỗ ở
        name = tags.get("name", "Chỗ ở không tên")

        # Thành phố: ưu tiên addr:city, fallback dùng city_name user nhập
        city = tags.get("addr:city", city_name)

        # Loại chỗ ở
        tourism_type = tags.get("tourism", "hotel")  # hotel / hostel / guest_house / apartment
        # Quy ước type đơn giản cho thuật toán
        if tourism_type == "guest_house":
            acc_type = "homestay"
        elif tourism_type == "apartment":
            acc_type = "apartment"
        elif tourism_type == "hostel":
            acc_type = "hostel"
        else:
            acc_type = "hotel"

        # Số sao: nếu OSM có tag 'stars' thì dùng, nếu không thì random theo phân bố
        raw_stars = tags.get("stars")
        if raw_stars:
            stars = float(raw_stars)
        else:
            # Phân bố "tự nhiên" hơn: 3★ nhiều nhất, 4★ & 2★ ít hơn, 1★ & 5★ hiếm
            r = random.random()
            if r < 0.05:
                stars = 1.0
            elif r < 0.25:
                stars = 2.0
            elif r < 0.75:
                stars = 3.0
            elif r < 0.95:
                stars = 4.0
            else:
                stars = 5.0

        # Giới hạn trong [1, 5]
        stars = max(1.0, min(5.0, stars))


        # GIẢ LẬP GIÁ dựa trên số sao (cho phù hợp thuật toán)
        base_by_star = {1: 300_000, 2: 450_000, 3: 700_000, 4: 1_000_000, 5: 1_500_000}
        base_price = base_by_star.get(int(stars), 700_000)
        # random nhẹ  ±10% cho giống thật
        price = base_price * (0.9 + 0.2 * random.random())

        # GIẢ LẬP RATING: phụ thuộc vào số sao, cộng thêm chút nhiễu Gaussian
        base_rating = 6 + 0.6 * stars   # 1★ ~ 6.6, 3★ ~ 7.8, 5★ ~ 9 (trung bình)
        rating = random.gauss(base_rating, 0.4)
        rating = max(5.0, min(9.8, rating))  # giới hạn 5.0-9.8 cho hợp lý

        # GIẢ LẬP SỨC CHỨA (cho đơn giản: 2-6 người)
        capacity = 2 + int(random.random() * 4)

        # Tiện ích: map từ một số tag OSM cơ bản
        amenities = []
        # WiFi
        internet = tags.get("internet_access")
        if internet in ("wlan", "yes", "free"):
            amenities.append("wifi")
        # Parking - có khá nhiều kiểu
        if tags.get("parking") in ("yes", "underground", "multi-storey"):
            amenities.append("parking")
        if tags.get("amenity") == "parking":
            amenities.append("parking")
        # Breakfast - rất ít nơi gắn thẳng, nhưng nếu có cứ lấy
        if tags.get("breakfast") == "yes":
            amenities.append("breakfast")
        # Pool - có thể xuất hiện dưới dạng leisure
        if tags.get("swimming_pool") == "yes" or tags.get("leisure") == "swimming_pool":
            amenities.append("pool")

        # Sau khi lấy từ OSM thật:
        amenities = list(set(amenities))  # bỏ trùng
        # Đoán thêm tiện ích dựa trên số sao
        # (để demo, ghi rõ trong báo cáo là "giả lập" khi thiếu dữ liệu)
        if stars >= 3 and "wifi" not in amenities:
            if random.random() < 0.7:
                amenities.append("wifi")

        if stars >= 3 and "breakfast" not in amenities:
            if random.random() < 0.5:
                amenities.append("breakfast")

        if stars >= 4 and "pool" not in amenities:
            if random.random() < 0.35:
                amenities.append("pool")

        if stars >= 2 and "parking" not in amenities:
            if random.random() < 0.6:
                amenities.append("parking")
        
        # Một số chỗ 4★–5★ hiếm hoi sẽ có đủ cả 4 tiện ích
        # (để demo có vài nơi "full service")
        if stars >= 4:
            # Chỉ những chỗ đã có ít nhất 2 tiện ích, và xác suất nhỏ (15%)
            if len(amenities) >= 2 and random.random() < 0.20:
                full_set = {"wifi", "breakfast", "pool", "parking"}
                amenities = list(set(amenities) | full_set)


        # Địa chỉ hiển thị
        address = tags.get("addr:full") or tags.get("addr:street") or tags.get("addr:housenumber") or city

        # Khoảng cách tới tâm city (km)
        distance_km = haversine_km(city_lon, city_lat, lon, lat)

        acc = Accommodation(
            id=str(el.get("id")),
            name=name,
            city=city,
            type=acc_type,
            price=price,
            stars=stars,
            rating=rating,
            capacity=capacity,
            amenities=amenities,
            address=address,
            lon=lon,
            lat=lat,
            distance_km=distance_km,
        )
        accommodations.append(acc)

    return accommodations, (city_lon, city_lat)


def fetch_google_hotels(city_name: str, radius_km: float = 5.0, wanted_types: List[str] | None = None,):
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


    # 1. Lấy tọa độ thành phố
    city_geo = serpapi_geocode(city_name + ", Vietnam")
    if not city_geo:
        st.error(f"Không tìm thấy tọa độ thành phố: {city_name}")
        return [], None

    city_lat, city_lon = city_geo["lat"], city_geo["lon"]

    def build_search_query(city: str, types: List[str]) -> str:
        # Không chọn gì hoặc chọn nhiều loại → lấy rộng
        if not types or len(types) > 2:
            return f"khách sạn homestay hostel apartment ở {city}"

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

        # Các tổ hợp khác (vd hotel + homestay, hotel + resort...)
        return f"khách sạn homestay hostel apartment ở {city}"


    # 2. Gọi API SerpAPI – Google Maps search
    REAL_API_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"  # giữ nguyên key của cậu

    search_query = build_search_query(city_name, wanted_types)

    params = {
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com.vn",
        "q": search_query,                     # ⬅ dùng query tuỳ loại
        "ll": f"@{city_lat},{city_lon},14z",
        "api_key": REAL_API_KEY,
        "hl": "vi",
    }


    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        local_results = results.get("local_results", [])
    except Exception as e:
        st.error(f"Lỗi khi gọi SerpAPI: {e}")
        return [], (city_lon, city_lat)

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


def recommend_top5_from_api(q: SearchQuery):
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


def home_page():
    st.markdown("<h1>🏠 Home</h1>", unsafe_allow_html=True)


    st.write("### 1️⃣ Thông tin cá nhân:")
    st.info("👉 Ví dụ: Tên, tuổi, email, thông tin cơ bản...")

    st.write("### 2️⃣ Hướng dẫn sử dụng web:")
    st.info("👉 Ví dụ: Cách tìm nơi ở, cách tìm đường đi, cách chat với trợ lý...")

    st.write("### 3️⃣ Nội dung trống:")
    st.info("👉 Bạn có thể để trống hoặc sử dụng để hiển thị thông báo, banner, quảng cáo...")

st.set_page_config(page_title="Tourism_Symstem", page_icon="💬")
MODEL = "llama3.2:1b"
client = Client(
    host='http://egfbk-34-31-77-101.a.free.pinggy.link'
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
    if db is None: return
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

if "current_page" not in st.session_state:
    st.session_state.current_page = "home"   # mặc định sau login về Home
    
# Tự động đăng nhập giả để test
if "user" not in st.session_state:
    st.session_state.user = {"email": "test@demo.com", "uid": "123"}
auth = None
db = None

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

            st.session_state.current_page = "home"
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
    user_translated = translate_text(user_input, "en") # dịch sang tiếng Anh cho AI hiểu tốt hơn

        
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
                        reply_translated = translate_text(full_reply, st.session_state["lang"])
                        st.markdown(full_reply)

            # C. Lưu và cập nhật lịch sử với phản hồi AI
            st.session_state.messages.append({"role": "assistant", "content": reply_translated})
            save_message("uid", "assistant", reply_translated)

                
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
        f"""
        <div style="padding:12px;border-radius:8px;background:#f0f2f6;color:#31333F;">
             🛣️Quãng đường: {route['distance_km']:.2f} km &nbsp;·&nbsp; ⏱️Thời gian ước tính: ~{route['duration_min']:.1f} phút
        </div>
        """,
        unsafe_allow_html=True,
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
                    step_trans = translate_text(steps, st.session_state["lang"])
                    st.markdown(f"{idx}. {text}")

            with col2:
                for idx, text in enumerate(steps[half:], start=half + 1):
                    step_trans = translate_text(steps, st.session_state["lang"])
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

auto_mode = st.toggle("Dịch toàn bộ trang")
st.session_state["auto_translate"] = auto_mode
def T(text):
    lang = st.session_state.get("lang", "vi")
    if st.session_state.get("auto_translate", False):
        return translate_text(text, lang)
    return text

st.write(T("Gợi ý nơi ở dựa trên nhu cầu của bạn"))

def navbar():
    st.markdown("""
        <style>
            .navbar {
                background-color: #0DDEAA;
                padding: 10px 20px;
                display: flex;
                align-items: center;
                gap: 10px;  /* khoảng cách nhỏ giữa các nút */
                border-bottom: 2px solid #0bbf91;
            }
            .nav-btn {
                background-color: #ffffff22;
                border: 1px solid #ffffff55;
                color: black;
                padding: 8px 14px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
            }
            .nav-btn:hover {
                background-color: white;
                color: black;
            }
            .active {
                background-color: white !important;
                color: black !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Sử dụng container để đặt nút sát nhau
    navbar_container = st.container()
    with navbar_container:
        cols = st.columns([0.15, 0.15, 0.70])  
        # 2 nút nằm bên trái, phần còn lại trống để dành cho tiện ích sau này

        with cols[0]:
            if st.button("🏠 Home", key="home_btn"):
                st.session_state.current_page = "home"

        with cols[1]:
            if st.button("🏨 Gợi ý", key="recommend_btn"):
                st.session_state.current_page = "recommend"


# --- Bắt đầu: Phần Gợi ý Nơi Ở (Đã chỉnh sửa cho tương tác & 5 Dòng) ---

# Chỉ hiển thị giao diện gợi ý nơi ở khi người dùng đã đăng nhập
if st.session_state.user:
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"

    navbar()

    if st.session_state.current_page == "home":
        home_page()
        st.stop()

    elif st.session_state.current_page == "recommend":
        # phần giao diện gợi ý nơi ở của bạn đặt ở đây
        recs = st.session_state.get("recommendations", [])

        if len(recs) == 0:
            st.info("Chưa có gợi ý nào. Vui lòng nhập thông tin để bắt đầu tìm kiếm.")
        else:
            for a in recs:
                st.write(T(a.accommodation.name))
                st.write(T(a.accommodation.address))
                relax_note = a.relax_note if hasattr(a, "relax_note") else ""
                st.write(T(relax_note))
                st.write(T(a.accommodation.description))
        pass


    # 1. ĐỊNH NGHĨA CỘT (Cần thiết để có bố cục 50%/50%)
    col_left, col_right = st.columns([1, 1]) 

    # ==========================
    # KHU VỰC CỘT TRÁI (FORM)
    # ==========================
    with col_left:
        title = translate_text("🏨 Gợi ý Nơi Ở Phù Hợp", st.session_state["lang"])
        st.markdown(f"## {title}")

        with st.form("recommendation_input_form"):
            st.write("Nhập nhu cầu nơi ở, hệ thống sẽ gợi ý Top 5 địa điểm phù hợp nhất xung quanh thành phố điểm đến (dữ liệu từ OpenStreetMap).")

            # 1. Thành phố điểm đến
            acc_city = st.text_input("Thành phố Điểm đến", value="Đà Nẵng", key="acc_city_destination")

            # 2. Số người
            group_size = st.number_input("Số người", min_value=1, max_value=20, value=2, step=1, key="group_size_input")

            # 3. Khoảng giá (tính theo 1 đêm, VND)
            col_price_1, col_price_2 = st.columns(2)
            with col_price_1:
                price_min = st.number_input(
                    "Giá tối thiểu mỗi đêm (VND)",
                    min_value=0,
                    value=300_000,
                    step=50_000,
                    key="price_min_input"
                )
            with col_price_2:
                price_max = st.number_input(
                    "Giá tối đa mỗi đêm (VND)",
                    min_value=0,
                    value=1_500_000,
                    step=50_000,
                    key="price_max_input"
                )

            # 4. Loại hình nơi ở
            types = st.multiselect(
                "Loại hình nơi ở",
                options=["hotel", "homestay", "hostel", "apartment"],
                default=["hotel", "homestay"],
                key="acc_types_multiselect"
            )

            # 5. Rating tối thiểu & Bán kính tìm kiếm
            col_rating, col_radius = st.columns(2)
            with col_rating:
                rating_min = st.slider("Rating tối thiểu", 0.0, 10.0, 7.5, 0.5, key="rating_min_slider")
            with col_radius:
                radius_km = st.slider("Bán kính tìm kiếm quanh thành phố (km)", 1.0, 20.0, 5.0, 1.0, key="radius_km_slider")

            # 6. Tiện ích bắt buộc & ưu tiên
            amenities_required = st.multiselect(
                "Tiện ích BẮT BUỘC phải có",
                options=["wifi", "breakfast", "pool", "parking"],
                default=["wifi"],
                key="amenities_req" # <--- THÊM KEY ĐỘC LẬP
            )

            amenities_preferred = st.multiselect(
                "Tiện ích ƯU TIÊN (có thì tốt)",
                options=["wifi", "breakfast", "pool", "parking"],
                default=["breakfast", "pool"],
                key="amenities_pref" # <--- THÊM KEY ĐỘC LẬP
            )

            # 7. Chế độ ưu tiên xếp hạng
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
                    q = SearchQuery(
                        city=acc_city.strip(),
                        group_size=int(group_size),
                        price_min=float(price_min),
                        price_max=float(price_max),
                        types=types,
                        rating_min=float(rating_min),
                        amenities_required=amenities_required,
                        amenities_preferred=amenities_preferred,
                        radius_km=float(radius_km),
                        priority=priority_code,
                    )

                    with st.spinner("Đang tìm kiếm và xếp hạng các nơi ở phù hợp..."):
                        try:
                            # accommodations, city_center = fetch_google_hotels(
                            #     city_name=q.city,
                            #     radius_km=q.radius_km,
                            #     wanted_types=q.types,      # ⬅ truyền loại user chọn
                            # )
                            # top5, relax_note = rank_accommodations(accommodations, q, 5)
                            accommodations, city_center = fetch_osm_accommodations(
                            city_name=q.city, radius_km=q.radius_km, max_results=50
                            )
                            top5, relax_note = rank_accommodations(accommodations, q, 5)


                            st.session_state.accommodation_results = {
                                "query": q,
                                "city_center": city_center,
                                "results": top5,
                                "relaxation_note": relax_note,
                            }
                            st.session_state.selected_acc_id = None # Reset khi tìm kiếm mới
                        except requests.RequestException as e:
                            st.error(f"Lỗi khi gọi API OpenStreetMap/Overpass: {e}")
                            st.session_state.accommodation_results = None

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
            top5 = results_state["results"]

            
            # 💡 Debug: hiển thị lại điều kiện đã dùng cho lần gợi ý này
            q_used = results_state["query"]
            st.caption(
                f"⚙️ Điều kiện lần gợi ý này: "
                f"Giá từ {int(q_used.price_min):,} đến {int(q_used.price_max):,} VND | "
                f"Rating tối thiểu: {q_used.rating_min} | "
                f"Bán kính: {q_used.radius_km} km")
            
            for i, item in enumerate(top5):
                acc = item["accommodation"]
                score = item["score"]
                rank = i + 1

                # Mỗi item sẽ là một dòng mới (Row)
                with st.container(border=True): 
                    
                        
                        # Tạo 2 cột bên trong dòng (4 phần cho thông tin, 1 phần cho nút)
                        row_col_info, row_col_button = st.columns([4, 1])

                        with row_col_info:
                            # 1. Tên và loại hình (markdown để giảm padding)
                            st.markdown(f"**#{rank}. {acc.name}** ({acc.type})")
                            
                            # 2. Giá, Rating, Khoảng cách (Kết hợp vào một dòng markdown để tiết kiệm chiều cao)
                            # Nếu price <= 0 coi như chưa có dữ liệu
                            if acc.price and acc.price > 0:
                                price_text = f"{int(acc.price):,} VND"
                            else:
                                price_text = "đang cập nhật"

                            st.markdown(
                                f"**Giá:** {price_text} | "
                                f"**Rating:** {acc.rating:.1f}/10 ({acc.stars}⭐) | "
                                f"**Cách trung tâm đó:** {acc.distance_km:.2f} km"
                            )

                            # 3. Tiện ích và Score (Dùng caption - chữ nhỏ hơn)
                            st.caption(f"Tiện ích: {', '.join(acc.amenities) or 'Không có thông tin'} | Score: **{score:.3f}**")

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
                #st.markdown(f"## 🗺️ Vị trí: {acc.name}")
                #st.info(f"Đang hiển thị vị trí chi tiết của **{acc.name}**. Nhấn 'Trở lại' để xem lại Top 5.")

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

            # --- SỬA ĐỔI: Bỏ chia cột, bỏ Slider Zoom, chỉ giữ lại Radio chọn phương tiện ---
            profile_label = st.radio(
                "Phương tiện",
                ["Car", "Walking", "Motorbike"],
                horizontal=True,
                key="route_profile",
            )
            
            # Map UI labels to OSRM/logic profile keys
            _PROFILE_MAP = {
                "Car": "driving",
                "Walking": "walking",
                "Motorbike": "cycling",
            }
            profile = _PROFILE_MAP.get(profile_label, "driving")
#                 # Nút tìm đường
#                 if st.button("🚗 Đường đi", key="find_route_btn"):
#                     if not origin_query.strip():
#                         st.error("Vui lòng nhập điểm xuất phát.")
#                     else:
#                         # 1) Geocode điểm xuất phát
#                         with st.spinner("Đang tìm tọa độ điểm xuất phát..."):
#                             src = serpapi_geocode(origin_query)


#                         if not src:
#                             st.error("Không tìm được tọa độ điểm xuất phát. Hãy nhập chi tiết hơn.")
#                         else:
#                             # 2) Chuẩn bị điểm đến
#                             dst = {
#                                 "name": f"{acc.name} ({acc.city})",
#                                 "lat": acc.lat,
#                                 "lon": acc.lon,
#                             }

#                             # 3) Gọi OSRM tìm route
#                             with st.spinner("Đang tính lộ trình bằng OSRM..."):
#                                 route = osrm_route(src, dst, profile=profile)

#                             if not route:
#                                 st.warning("Không tìm được lộ trình phù hợp. Thử đổi phương tiện hoặc địa điểm.")
#                             else:
#                                 st.session_state.route_result = {
#                                     "src": src,
#                                     "dst": dst,
#                                     "profile": profile,
#                                     "route": route,
#                                 }
#                                 # Mỗi lần tìm đường mới thì ẩn danh sách bước đi
#                                 st.session_state.show_route_steps = False

#                                 st.success(
#                                     f"Lộ trình ~{route['distance_km']:.2f} km, "
#                                     f"~{route['duration_min']:.1f} phút ({profile})."
#                                 )

#                                 # Gợi ý phương tiện (giữ nguyên đoạn dưới)
#                                 best_profile, explain = recommend_transport_mode(
#                                     route["distance_km"], route["duration_min"]
#                                 )
#                                 labels = {
#                                     "walking": "đi bộ",
#                                     "cycling": "xe đạp",
#                                     "driving": "ô tô / xe máy",
#                                 }

#                                 if best_profile == profile:
#                                     st.info(
#                                         f"Hệ thống đánh giá quãng đường khoảng "
#                                         f"**{route['distance_km']:.1f} km** "
#                                         f"({route['duration_min']:.0f} phút) và "
#                                         f"phương tiện hiện tại (**{labels[profile]}**) "
#                                         f"**là phù hợp**. {explain}"
#                                     )
#                                 else:
#                                     st.info(
#                                         f"Hệ thống đánh giá quãng đường khoảng "
#                                         f"**{route['distance_km']:.1f} km** "
#                                         f"({route['duration_min']:.0f} phút). "
#                                         f"Gợi ý nên di chuyển bằng **{labels[best_profile]}** – {explain} "
#                                         f"Hiện tại bạn đang xem lộ trình cho **{labels[profile]}**; "
#                                         "bạn có thể đổi phương tiện phía trên rồi bấm "
#                                         "'Tìm đường' lại nếu muốn."
#                                     )
#                                 # 🔔 SAU KHI TÍNH XONG LỘ TRÌNH → MỞ HỘP THOẠI MAP
#                                 route_dialog()

#                                 # --- Phân tích độ phức tạp lộ trình & cảnh báo ---
#                                 level, label_vi, summary, reasons = analyze_route_complexity(
#                                     route, profile
#                                 )

#                                 if level == "low":
#                                     st.success(
#                                         f"**Độ phức tạp lộ trình: {label_vi}.** {summary}"
#                                     )
#                                 elif level == "medium":
#                                     st.info(
#                                         f"**Độ phức tạp lộ trình: {label_vi}.** {summary}"
#                                     )
#                                 else:
#                                     st.warning(
#                                         f"**Độ phức tạp lộ trình: {label_vi}.** {summary}"
#                                     )

#                                 if reasons:
#                                     bullet_text = "\n".join(f"- {r}" for r in reasons)
#                                     st.markdown(
#                                         "**Một vài lưu ý trên đường đi:**\n" + bullet_text
#                                     )


#                 # Thêm chút info chi tiết chỗ ở (giữ từ bản map cũ của team)
#                 st.markdown(f"**Địa chỉ:** {acc.address}")
#                 st.markdown(f"**Khoảng cách tới TT:** {acc.distance_km:.2f} km")
#                 st.markdown(f"**Tiện ích:** {', '.join(acc.amenities) or 'Không có thông tin'}")


# else:
#     # Nếu chưa đăng nhập thì vẫn giữ logic cũ: hiển thị form đăng ký / đăng nhập
#     if st.session_state.get("show_signup", False):
#         signup_form()
#     elif st.session_state.get("show_login", True):
#         login_form()

                    # Nút tìm đường (LOGIC MỚI - ĐÃ SỬA TOÀN BỘ LỖI)
                # Nút tìm đường (LOGIC MỚI - ĐÃ CẬP NHẬT GIAO DIỆN)
            if st.button("🚗 Đường đi", key="find_route_btn"):
                # 1. QUAN TRỌNG: Tắt Chat để không bị lỗi "Only one dialog"
                st.session_state.chat_open = False
                
                if not origin_query.strip():
                    st.error("Vui lòng nhập điểm xuất phát.")
                else:
                    with st.spinner("Đang tìm tọa độ & tính toán lộ trình..."):
                        # a. Tìm tọa độ (Geocode)
                        src = serpapi_geocode(origin_query)
                        
                        if not src:
                            st.error(f"Không tìm thấy địa điểm: '{origin_query}'.")
                        else:
                            dst = {
                                "name": f"{acc.name} ({acc.city})",
                                "lat": acc.lat, "lon": acc.lon,
                            }
                            # b. Tìm đường OSRM
                            route = osrm_route(src, dst, profile=profile)
                            
                            if not route:
                                st.warning("Không tìm được lộ trình. Vui lòng thử lại.")
                            else:
                                # c. Lưu kết quả
                                st.session_state.route_result = {
                                    "src": src, "dst": dst,
                                    "profile": profile, "route": route,
                                }
                                st.session_state.show_route_steps = False

                                # --- SỬA ĐỔI 1: Cập nhật nội dung hiển thị khung xám ---
                                st.markdown(
                                    f"""
                                    <div style="
                                        padding: 12px;
                                        border-radius: 8px;
                                        background: #f0f2f6;
                                        color: #31333F;
                                        border: 1px solid #d0d0d5;
                                    ">
                                        🛣️ <b>Quãng đường:</b> {route['distance_km']:.2f} km &nbsp;·&nbsp; 
                                        ⏱️ <b>Thời gian ước tính:</b> ~{route['duration_min']:.1f} phút
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                
                                # --- SỬA ĐỔI 2: Thêm khoảng cách (Spacing) giữa khung Lộ trình và Gợi ý ---
                                st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
                                
                                
                                # e. Hiển thị Gợi ý phương tiện (Khung Xanh Dương - st.info)
                                best, exp = recommend_transport_mode(route['distance_km'], route['duration_min'])
                                st.info(f"💡 **Gợi ý:** {exp}")


                                # f. Hiển thị Lưu ý (Khung Màu thay đổi) bên dưới gợi ý
                                lvl, lbl, smm, reasons = analyze_route_complexity(route, profile)
                                note_msg = f"**⚠️Lưu ý:** {lbl} – {smm}"
                                
                                if lvl == "low":
                                    st.success(note_msg) # Xanh lá
                                elif lvl == "medium":
                                    st.warning(note_msg) # Vàng
                                else:
                                    st.error(note_msg)   # Đỏ
                                
                                # g. Mở Bản đồ sau cùng
                                route_dialog()

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
s
/* 3. Ẩn tên vai trò (role/user) nhưng giữ lại avatar */
div[data-testid="stChatMessage"] .stChatMessageHeader {
    display: none; 
}            


</style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        /* Style option mới */
        .custom-menu-item {
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
        }
        .custom-menu-item:hover {
            background: #f0f0f0;
        }
    </style>

    <script>
    // Đợi menu hiện ra rồi chèn thêm item
    const waitForMenu = setInterval(() => {
        const menu = window.parent.document.querySelector('[data-testid="stMainMenu"] ul');
        if (menu) {
            clearInterval(waitForMenu);

            // Nếu đã thêm rồi thì không thêm nữa
            if (window.__customLangAdded) return;
            window.__customLangAdded = true;

            // Tạo mục menu mới
            const li = document.createElement("li");
            li.className = "custom-menu-item";
            li.innerText = "🌐 Language";
            li.onclick = () => window.parent.postMessage({type: "open-language"}, "*");

            menu.appendChild(li);
        }
    }, 500);
    </script>
""", unsafe_allow_html=True)

# Khi user click "Language", menu sẽ gửi postMessage lên Streamlit frontend.
lang_event = st.query_params.get("lang_event")

# Sidebar / Dialog language selector (hiện khi user click)
if st.session_state.get("show_language_dialog", False):
    st.sidebar.header("🌐 Chọn ngôn ngữ")

    lang = st.sidebar.radio(
        "Language:",
        ["vi", "en", "fr", "ja", "ko", "zh"],
        index=0 if "lang" not in st.session_state else
        ["vi", "en", "fr", "ja", "ko", "zh"].index(st.session_state["lang"])
    )

    st.session_state["lang"] = lang
    st.sidebar.success("Đã chọn ngôn ngữ: " + lang)

# Listen for JS events
st.markdown("""
<script>
window.addEventListener("message", (event) => {
    if (event.data.type === "open-language") {
        window.location.search = "?lang_event=1";
    }
});
</script>
""", unsafe_allow_html=True)

# Khi bấm "Language" thì mở sidebar
if "lang_event" in st.query_params:
    st.session_state["show_language_dialog"] = True
