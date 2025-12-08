import requests
import math
import re
from dataclasses import dataclass
from typing import List
from serpapi import GoogleSearch
from deep_translator import GoogleTranslator
API_KEY = "484389b5b067640d3df6e554063f22f10f0b24f784c8c91e489f330a150d5a69"

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


class AccommodationService:
    
    def __init__(self):
        self.api_key = API_KEY
    
    def get_recommendations(self, query_data):
        """
        Nhận input từ frontend, trả về top 5 nơi ở
        """
        city = query_data['city']
        radius_km = query_data.get('radius_km', 5.0)
        wanted_types = query_data.get('types', [])
        
        # 1. Lấy danh sách nơi ở từ Google Maps
        accommodations, city_center = self._fetch_google_hotels(city, radius_km, wanted_types)
        
        if not accommodations:
            return {
                'results': [],
                'city_center': city_center,
                'relaxation_note': 'Không tìm thấy nơi ở nào trong khu vực này.'
            }
        
        # 2. Lọc và xếp hạng
        filtered, relax_note = self._filter_and_rank(accommodations, query_data)
        
        # 3. Chuyển đổi sang JSON-friendly format
        results = []
        for item in filtered[:5]:
            acc = item['accommodation']
            results.append({
                'id': acc.id,
                'name': acc.name,
                'city': acc.city,
                'type': acc.type,
                'price': acc.price,
                'stars': acc.stars,
                'rating': acc.rating,
                'capacity': acc.capacity,
                'amenities': acc.amenities,
                'address': acc.address,
                'lon': acc.lon,
                'lat': acc.lat,
                'distance_km': acc.distance_km,
                'score': item['score']
            })
        
        return {
            'results': results,
            'city_center': city_center,
            'relaxation_note': relax_note
        }
    
    def _geocode_city(self, city_name):
        """Lấy tọa độ thành phố"""
        params = {
            "engine": "google_maps",
            "q": city_name + ", Vietnam",
            "type": "search",
            "api_key": self.api_key,
            "hl": "vi"
        }
        
        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            
            if "local_results" in results and len(results["local_results"]) > 0:
                place = results["local_results"][0]
                return {
                    "lat": place["gps_coordinates"]["latitude"],
                    "lon": place["gps_coordinates"]["longitude"]
                }
            
            if "place_results" in results:
                place = results["place_results"]
                return {
                    "lat": place["gps_coordinates"]["latitude"],
                    "lon": place["gps_coordinates"]["longitude"]
                }
            
            return None
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None
    
    def _fetch_google_hotels(self, city_name, radius_km, wanted_types):
        """Lấy danh sách khách sạn từ Google Maps"""
        city_geo = self._geocode_city(city_name)
        if not city_geo:
            return [], None
        
        city_lat, city_lon = city_geo["lat"], city_geo["lon"]
        
        # Tạo query search
        search_query = self._build_search_query(city_name, wanted_types)
        
        params = {
            "engine": "google_maps",
            "type": "search",
            "q": search_query,
            "ll": f"@{city_lat},{city_lon},14z",
            "api_key": self.api_key,
            "hl": "vi"
        }
        
        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            local_results = results.get("local_results", [])
        except Exception as e:
            print(f"Google Maps search error: {e}")
            return [], (city_lon, city_lat)
        
        accommodations = []
        
        for item in local_results:
            acc = self._parse_accommodation(item, city_name, city_lat, city_lon)
            if acc:
                accommodations.append(acc)
        
        return accommodations, (city_lon, city_lat)
    
    def _build_search_query(self, city, types):
        """Tạo query tìm kiếm phù hợp"""
        if not types or len(types) > 2:
            return f"khách sạn homestay hostel apartment ở {city}"
        
        s = set(types)
        if s == {"hotel"}:
            return f"khách sạn ở {city}"
        if s == {"homestay"}:
            return f"homestay guest house nhà nghỉ ở {city}"
        if s == {"hostel"}:
            return f"hostel backpacker hostel ở {city}"
        if s == {"apartment"}:
            return f"căn hộ serviced apartment ở {city}"
        
        return f"khách sạn homestay hostel apartment ở {city}"
    
    def _parse_accommodation(self, item, city_name, city_lat, city_lon):
        """Chuyển đổi dữ liệu Google Maps thành Accommodation object"""
        
        name = (item.get("title") or "").strip()
        if not name:
            return None
        
        data_id = item.get("data_id")
        if data_id is None:
            data_id = hash(name + str(item.get("address", "")))
        
        # Giá
        raw_price = item.get("price")
        price = 0.0
        if raw_price:
            s = str(raw_price)
            m = re.search(r"\d+(?:[.,]\d+)?", s)
            if m:
                value = float(m.group(0).replace(",", "."))
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
        except:
            rating = 0.0
        
        stars = max(0.0, min(5.0, rating))
        rating_10 = rating * 2.0
        
        # Tiện ích
        amenities = []
        desc = str(item).lower()
        
        if any(kw in desc for kw in ["wifi", "wi-fi"]):
            amenities.append("wifi")
        if any(kw in desc for kw in ["breakfast", "bữa sáng"]):
            amenities.append("breakfast")
        if any(kw in desc for kw in ["pool", "bể bơi"]):
            amenities.append("pool")
        if any(kw in desc for kw in ["parking", "bãi đỗ xe"]):
            amenities.append("parking")
        
        # Tọa độ
        gps = item.get("gps_coordinates") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        
        if lat is None or lon is None:
            return None
        
        try:
            lat = float(lat)
            lon = float(lon)
        except:
            return None
        
        # Khoảng cách
        dist = self._haversine_km(city_lon, city_lat, lon, lat)
        
        # Loại chỗ ở
        acc_type = self._detect_type(item)
        
        return Accommodation(
            id=str(data_id),
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
            distance_km=dist
        )
    
    def _detect_type(self, item):
        """Nhận diện loại chỗ ở"""
        name = (item.get("title") or "").lower()
        main_type = (item.get("type") or "").lower()
        extra_types = " ".join(t.lower() for t in item.get("types", []) if t)
        text = " ".join([name, main_type, extra_types])
        
        if any(kw in text for kw in ["homestay", "guest house", "nhà nghỉ"]):
            return "homestay"
        if "resort" in text:
            return "resort"
        if "hostel" in text:
            return "hostel"
        if any(kw in text for kw in ["apartment", "căn hộ", "condotel"]):
            return "apartment"
        
        return "hotel"
    
    def _filter_and_rank(self, accommodations, query_data):
        """Lọc và xếp hạng nơi ở"""
        filtered = []
        
        for acc in accommodations:
            # Lọc giá
            if query_data.get('price_min', 0) > 0 and acc.price < query_data['price_min']:
                continue
            if query_data.get('price_max', 0) > 0 and acc.price > query_data['price_max']:
                continue
            
            # Lọc rating
            if acc.rating < query_data.get('rating_min', 0):
                continue
            
            # Lọc loại
            types = query_data.get('types', [])
            if types and acc.type not in types:
                continue
            
            filtered.append(acc)
        
        # Tính điểm và xếp hạng
        scored = []
        for acc in filtered:
            score = self._calculate_score(acc, query_data)
            scored.append({
                'accommodation': acc,
                'score': score
            })
        
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        relax_note = "Các gợi ý dưới đây thỏa đầy đủ tiêu chí bạn đã chọn."
        if len(scored) == 0:
            relax_note = "Không tìm thấy nơi ở phù hợp. Thử nới lỏng tiêu chí."
        
        return scored, relax_note
    
    def _calculate_score(self, acc, query_data):
        """Tính điểm cho nơi ở"""
        score = 0.0
        
        # Điểm giá (25%)
        price_min = query_data.get('price_min', 0)
        price_max = query_data.get('price_max', 0)
        if price_max > price_min:
            price_center = (price_min + price_max) / 2
            price_range = (price_max - price_min) / 2
            if price_range > 0:
                price_score = 1 - min(abs(acc.price - price_center) / price_range, 1.0)
                score += 0.25 * price_score
        
        # Điểm rating (25%)
        score += 0.25 * (acc.rating / 10.0)
        
        # Điểm sao (20%)
        score += 0.20 * (acc.stars / 5.0)
        
        # Điểm khoảng cách (10%)
        radius = query_data.get('radius_km', 5.0)
        if radius > 0:
            dist_score = 1 - min(acc.distance_km / radius, 1.0)
            score += 0.10 * dist_score
        
        # Điểm tiện ích (20%)
        req = set(query_data.get('amenities_required', []))
        pref = set(query_data.get('amenities_preferred', []))
        have = set(acc.amenities)
        
        if req or pref:
            match_req = len(have & req)
            match_pref = len(have & pref)
            max_possible = max(1.0, len(req) + 0.5 * len(pref))
            amenity_score = (match_req + 0.5 * match_pref) / max_possible
            score += 0.20 * amenity_score
        else:
            score += 0.20
        
        return score
    
    def _haversine_km(self, lon1, lat1, lon2, lat2):
        """Tính khoảng cách giữa 2 điểm"""
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = phi2 - phi1
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c