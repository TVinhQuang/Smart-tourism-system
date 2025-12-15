def filter_with_relaxation(accommodations: List[Accommodation], q: SearchQuery, top_k: int = 5):
    """
    Hàm lọc và xếp hạng khách sạn.
    Cơ chế: Thử các mức độ từ Khắt khe -> Dễ tính.
    Nếu mức độ khắt khe tìm ra kết quả -> Trả về NGAY LẬP TỨC (Không trộn lẫn kết quả kém hơn).
    """
    def _do_filter(rating_min, price_relax=1.0, radius_relax=1.0):
        # 1. Tính toán giới hạn giá và khoảng cách cho mức độ này
        pmin = q.price_min
        pmax = q.price_max

        if price_relax > 1.0 and pmax > 0 and pmax > pmin:
            center = (pmin + pmax) / 2
            half_span = (pmax - pmin) / 2
            extra = half_span * (price_relax - 1.0)
            pmin = max(0, center - half_span - extra)
            pmax = center + half_span + extra

        dist_limit = (q.radius_km * radius_relax) if q.radius_km > 0 else None

        filtered = []
        for a in accommodations:
            # 2. Lọc cơ bản (Khoảng cách, Giá, Loại hình)
            if dist_limit is not None and a.distance_km > dist_limit: continue
            if pmin > 0 and a.price < pmin: continue
            if pmax > 0 and a.price > pmax: continue
            if q.types and (a.type not in q.types): continue
            
            # 3. Lọc theo Đánh giá (Rating)
            if a.rating < rating_min: continue
            
            # 4. Lọc theo Tiện ích Ưu tiên (Amenities)
            # Logic: Nếu người dùng chọn tiện ích A, khách sạn bắt buộc phải có A (hoặc tương đương)
            if q.amenities_preferred:
                hotel_amenities_lower = [am.lower() for am in a.amenities]
                missing_amenity = False
                
                for req_am in q.amenities_preferred:
                    req_lower = req_am.lower()
                    found = False
                    
                    # Mapping từ khóa thông minh
                    check_list = [req_lower]
                    if req_lower == "breakfast": check_list.append("bữa sáng")
                    if req_lower == "pool": check_list.extend(["pool", "hồ bơi", "bể bơi"])
                    if req_lower == "parking": check_list.extend(["parking", "đỗ xe", "giữ xe", "bãi xe"])
                    if req_lower == "wifi": check_list.extend(["wifi", "mạng", "internet"])
                    
                    for item in hotel_amenities_lower:
                        if any(k in item for k in check_list):
                            found = True
                            break
                    
                    if not found:
                        missing_amenity = True
                        break
                
                if missing_amenity: continue 

            filtered.append(a)
        
        # 5. Sắp xếp danh sách (Sorting) theo Chiến lược (Priority)
        if q.priority == "cheap":
            # Giá rẻ lên đầu (đẩy giá 0 xuống cuối)
            filtered.sort(key=lambda x: x.price if x.price > 10000 else 9999999999)
            
        elif q.priority == "near_center":
            # Gần trung tâm lên đầu
            filtered.sort(key=lambda x: x.distance_km)
            
        elif q.priority == "amenities":
            # Nhiều tiện ích lên đầu
            filtered.sort(key=lambda x: len(x.amenities), reverse=True)
            
        else: 
            # Mặc định (Balanced): Rating cao -> Review nhiều
            filtered.sort(key=lambda x: (x.rating, x.reviews), reverse=True)

        return filtered

    # --- CÁC MỨC ĐỘ NỚI LỎNG (RELAXATION LEVELS) ---
    levels = [
        # Mức 1: Tuyệt đối tuân thủ yêu cầu của bạn
        {"desc": "Thỏa mãn đầy đủ tiêu chí.", "rating_min": q.rating_min, "price_relax": 1.0, "radius_relax": 1.0},
        
        # Mức 2: Giảm 0.5 sao nếu Mức 1 không tìm thấy gì
        {"desc": "Đã nới lỏng rating tối thiểu.", "rating_min": max(0.0, q.rating_min - 0.5), "price_relax": 1.0, "radius_relax": 1.0},
        
        # Mức 3: Giảm 1.0 sao và mở rộng bán kính
        {"desc": "Đã mở rộng bán kính tìm kiếm.", "rating_min": max(0.0, q.rating_min - 1.0), "price_relax": 1.0, "radius_relax": 1.5},
        
        # Mức 4: Tìm mọi cách để có kết quả
        {"desc": "Đã nới rộng khoảng giá và bán kính.", "rating_min": 0.0, "price_relax": 1.3, "radius_relax": 2.0},
    ]

    # --- VÒNG LẶP CHÍNH ---
    for cfg in levels:
        candidates = _do_filter(cfg["rating_min"], cfg["price_relax"], cfg["radius_relax"])
        
        # QUAN TRỌNG: Nếu tìm thấy bất kỳ kết quả nào ở mức độ này -> TRẢ VỀ LUÔN.
        # Không đi tiếp xuống mức dưới để tránh lẫn lộn khách sạn kém chất lượng.
        if len(candidates) > 0:
            return candidates[:top_k], cfg["desc"]
            
    return [], "Không tìm thấy kết quả phù hợp."