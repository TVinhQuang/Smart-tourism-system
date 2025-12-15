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
        reviews = int(d.get("reviews") or 0),
        capacity=4,
        amenities=d.get("amenities", []),
        address=d.get("address", ""),
        lon=d.get("lon", 0.0),
        lat=d.get("lat", 0.0),
        distance_km=d.get("distance_km", 0.0),
    )

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
