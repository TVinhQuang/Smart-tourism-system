from flask import Blueprint, request, jsonify
from core_logic import describe_osrm_step, haversine_km, draw_map
from server import fetch_google_hotels
import requests

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