console.log("homepage.js loaded");

const dummyList = [
    {
        name: "Intercontinental Saigon Hotel & Residences (JW Marriott Hotel & Suites Saigon",
        price: 3900000,
        rating: 4.6,
        desc: {
            vi: "Khách sạn ở vị trí thuận lợi, nổi bật với kiến trúc hiện đại, sang trọng, mang tầm nhìn toàn cảnh thành phố với cửa sổ kính từ trần đến sàn, cung cấp nhiều tiện ích, bao gồm hồ bơi ngoài trời và tầm nhìn ra Nhà thờ Đức Bà, spa đầy đủ dịch vụ, phòng gym hiện đại.",
            en: "The hotel boasts a convenient location, striking modern and luxurious architecture, panoramic city views through floor-to-ceiling windows, and a range of amenities including an outdoor swimming pool with views of Notre Dame Cathedral, a full-service spa, and a modern gym."
        },
        address: "Góc đường Hai Bà Trưng và Lê Duẩn, phường Bến Nghé, Quận 1, TP Hồ Chí Minh",
        lat: 17.7818, lon: 106.7011,
        img: "https://digital.ihg.com/is/image/ihg/intercontinental-ho-chi-minh-city-9755934213-4x3",
        amenities: ["amenity_pool", "amenity_wifi","amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Sofitel Legend Metropole Hanoi",
        price: 5000000,
        rating: 4.7,
        desc: {
            vi: "Khách sạn nằm vị trí đắc địa ngay trung tâm, gần Nhà Hát Lớn và hồ Hoàn Kiếm. Với hơn một thế kỷ lịch sử, khách sạn mang đậm kiến trúc Pháp cổ điển, được coi là một di sản sống của Hà Nội, khách sạn còn có hầm trú bom lịch sử thời chiến cho du khách tham quan, với đầy đủ tiện nghi, hồ bơi ngoài trời, spa, nhà hàng chất lượng, tinh tế.",
            en: "The hotel boasts a prime location in the heart of the city, near the Hanoi Opera House and Hoan Kiem Lake. With over a century of history, the hotel features classic French architecture and is considered a living heritage of Hanoi. It also includes a historical wartime bomb shelter for guests to visit, and offers a full range of amenities, including an outdoor swimming pool, spa, and fine dining restaurants."
        },
            address: "15 phường Ngô Quyền, Tràng Tiến, quận Hoàn Kiếm, Thủ đô Hà Nội",
        lat: 21.0255, lon: 105.8555,
        img: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRO_Rjfb6dShZU_eUs1CPsbFx3Qt6o-WAhgiQ&s",
        // Dữ liệu tiện ích dạng KEY
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Resort Regent Phu Quoc Island",
        price: 20000000,
        rating: 4.9,
        // Dữ liệu mô tả đa ngôn ngữ
        desc: {
            vi: "Là một khu nghĩ dưỡng sang trọng bậc nhất trên đảo Phú Quốc, mang đến trải nghiệm nghĩ dưỡng độc bản, nhiều hồ bơi tuyệt đẹp, kiến trúc xanh mát và trung tamam thể dục & spa hiện đại, nơi đây nổi bật với kiến trúc tinh tế nhưng vẫn gần gũi với thiên nhiên, các phòng, suite và villa được trang bị nội thất hiện đại tiện nghi, với nhiều chi tiết độc đáo.",
            en: "As one of the most luxurious resorts on Phu Quoc Island, offering a unique vacation experience with stunning swimming pools, lush green architecture, and a modern fitness and spa center, this resort stands out with its sophisticated yet nature-friendly architecture. The rooms, suites, and villas are furnished with modern amenities and feature many unique details."
        },
        address: "Bãi Trường, xã Dương Tơ, Phú Quốc",
        lat: 10.18879, lon: 103.96685,
        img: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRQIvb6qGpU92yyq-ABd7mheHC5ixfo68Wyeg&s",
        // Dữ liệu tiện ích dạng KEY
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Vinpearl Resort & Spa Ha Long Bay",
        price: 2000000,
        rating: 4.9,
        desc: {
            vi: "Khu nghĩ dưỡng là 1 lâu đài sang trọng nằm biệt lập trên đảo Rều, vị trí một hòn đảo riêng biệt là điểm nhấn chính, mang lại sự riêng tư và yên bình. Resort có kiến trúc Pháp kết hợp sự hài hòa với nét Việt Nam, sang trọng và tinh tế. Các phòng nghĩ rất sạch sẽ, view đẹp và được trang bị hiện đại. ",
            en: "The resort is a luxurious castle situated in isolation on Reu Island. Its secluded island location is the main highlight, offering privacy and tranquility. The resort features French architecture harmoniously blended with Vietnamese elements, creating a luxurious and sophisticated atmosphere. The rooms are very clean, offer beautiful views, and are equipped with modern amenities."
        },
        address: "Đảo Rều, Đường Đỗ Sĩ Họa, Bãi Cháy, Hạ Long, Quảng Ninh",
        lat: 20.9421456, lon: 107.02544,
        img: "https://statics.vinpearl.com/styles/1920x1004/public/2025_01/Thi%E1%BA%BFt%20k%E1%BA%BF%20ch%C6%B0a%20c%C3%B3%20t%C3%AAn%20(3)_1737706065.png.webp?itok=TEuCLNtO?v=20251210",
        amenities: ["amenity_breakfast", "amenity_wifi", "amenity_pool", "amenity_parking"]
    },
    {
        name: "The Reverie SaiGon",
        price: 9000000,
        rating: 4.6,
        desc: {
            vi: "Với thiết kế độc đáo, khách sạn là một tuyệt sắc kiến trúc, kết hợp hài hòa giữa phong cách cổ điển châu Âu và sự hiện đại tinh tế.",
            en: "With its unique design, the hotel is a masterpiece of architecture, harmoniously blending classic European style with sophisticated modernity."
        },
        address: "Tòa nhà Times Square, 22-36 Đại lộ Nguyễn Huệ & 57-69F Đường Đồng Khởi, phường Bến Nghé, Quận 1, TP Hồ Chí Minh",
        lat: 10.7766, lon: 106.7046,
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/261534199.jpg?k=a814e0ccf607d334377f8a6f2beba859066823e545c8004e61d5b0183a318287&o=",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    },
    {
        name: "Sunrise Premium Resort Hoi An",
        price: 1800000,
        rating: 4.3,
        desc: {
            vi: "Là một khu nghĩ dưỡng 5 sao sang trọng, nổi tiếng với vị trí mặt tiền bãi biển Cửa Đại xinh đẹp và dịch vụ đẳng cấp quốc tế, thiết kế phòng ốc mang truyền thống Việt Nam, mang đến sự kết hợp hài hòa với phong cách hiện đại, mang lại cảm giác thoải mái và tiện nghi, và còn có các nhà hàng Á-Âu, dịch vụ đưa đón sân bay. ",
            en: "As a luxurious 5-star resort, renowned for its prime beachfront location on the beautiful Cua Dai beach and world-class service, the resort features rooms designed in a traditional Vietnamese style, which offers a harmonious blend with modern style, providing a comfortable and convenient feel, and there are also Asian and European restaurants, and airport shuttle service."
        },
        address: "Đường Âu Cơ,Bãi biển Cửa Đại, Hội An, tỉnh Quảng Nam",
        lat: 15.8940, lon: 108.3535,
        img: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRhWxTimfsPS6bJKFCn1dYmku5uxHlGYVggrQ&s",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Anantara Mui Ne Resort",
        price: 4000000,
        rating: 4.6,
        desc: {
            vi: "Khu nghĩ dưỡng 5 sao sang trọng, nằm dọc bãi biển Mũi Né, nổi tiếng với sự kết hợp hài hòa giữa kiến trúc truyền thống Việt Nam và tiện nghi hiện đại, nhiều hồ bơi vô cực, phục vụ ẩm thực Á-Âu phong phú suốt cả ngày",
            en: "This luxurious 5-star resort, situated along Mui Ne beach, is renowned for its harmonious blend of traditional Vietnamese architecture and modern amenities, featuring numerous infinity pools and a rich Asian-European culinary experience throughout the day."
        },
        address: "12A đường Nguyễn Đình Chiểu, phường Hàm Tiến, thành phố Phan Thiết, tỉnh Bình Thuận",
        lat: 10.9408, lon: 108.1918,
        img: "https://q-xx.bstatic.com/xdata/images/hotel/max500/601523257.jpg?k=eaf22d0445a4872cb4e47fc821cb3252509884d3376423b17e924aefb0fc96d5&o=",
        amenities: ["amenity_wifi", "amenity_breakfast", "amenity_pool"]
    },
    {
        name: "Vinpearl Resort Nha Trang",
        price: 2200000,
        rating: 4.9,
        desc: {
            vi: "Resort là 1 phần của quần thể nghỉ dưỡng phức hợp, mang đến không gian nghĩ dưỡng sang trọng, yên tĩnh với view biển tuyệt đẹp và bãi biển riêng, có đầy đủ tiện ích như spa, điểm ăn uống với view biển đẹp và bãi biển riêng.",
            en: "The resort is part of a larger resort complex, offering a luxurious and tranquil retreat with stunning ocean views and a private beach, complete with amenities such as a spa and dining options with beautiful ocean views and a private beach."
        },
        address: "Đảo Hòn Tre, phường Vĩnh Nguyên, Thành phố Nha Trang, tỉnh Khánh Hòa",
        lat: 12.2209, lon: 109.2474,
        img: "https://statics.vinpearl.com/styles/1920x1004/public/2024_08/vinpearl-resort-nha-trang_1722527321.jpg.webp?itok=sqiH1Gvc?v=20251210",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    },
    {
        name: "Maia Resort Qui Nhon",
        price: 6400000,
        rating: 4.9,
        desc: {
            vi: "Khu nghỉ sở hữu 88 căn biệt thự với thiết kế không gian mở, nơi này mang đến một bãi biển riêng tư, yên bình với nhiều cây xanh mát và tầm nhìn tuyệt đẹp ra Vịnh Phương Mai, thiết kế nội thất hoàn hảo, rộng rãi, sạch sẽ, mang lại cảm giác thư giãn.",
            en: "The resort boasts 88 villas with an open-plan design, offering a private, peaceful beach surrounded by lush greenery and stunning views of Phuong Mai Bay. The interiors are perfectly designed, spacious, clean, and provide a relaxing atmosphere."
        },
        address: "Khu Kinh tế Nhơn Hội, Xã Cát Tiến, huyện Phù Cát, tỉnh Bình Định",
        lat: 13.6698, lon: 109.2081,
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/271813286.jpg?k=8c1fdcf3b4d751fffd2482706ec9f23b3cb5d13318ac8df94b41d3bf5cd4a0ed&o=",
        amenities: ["amenity_wifi", "amenity_pool", "amenity_parking"]
    },
    {
        name: "Caravelle SaiGon",
        price: 2200000,
        rating: 4.5,
        desc: {
            vi: "Khách sạn mở từ năm 1959 gắn liền với nhiều sự kiện lịch sử của Sài Gòn, nổi tiếng với buffet hải sản tại nhà hàng Nineteen.",
            en: "Hotel opened in 1959, the hotel is associated with many historical events in Saigon and is famous for its seafood buffet at the Nineteen restaurant."
        },
        address: "19 - 23 Công trường Lam Sơn, phường Bến NGhé, quận 1, TP Hồ Chí Minh.",
        lat: 10.7760, lon: 106.7036,
        img: "https://lh3.googleusercontent.com/p/AF1QipON3b9pT__cTQ-i6XRQURnoiqZ8rdmHLnoUhMfk=w324-h312-n-k-no",
        amenities: ["amenity_wifi", "amenity_pool", "amenity_parking"]
    },
    {
        name: "Muong Thanh Can Tho",
        price: 1350000,
        rating: 4.4,
        desc: {
            vi: "Khách sạn 5 sao nổi tiếng nhất Cần Thơ, tọa lạc ở vị trí đắc địa ngay trung tâm Bến Ninh Kiều, mang đến tầm nhìn toàn cảnh sông Hậu và thành phố. Khách sạn có 308 phòng được trang bị tiện nghi hiện đại, cung cấp nhiều tiện ích bao gồm hơ bơi ngoài trời, massage, spa.",
            en: "Can Tho's most renowned 5-star hotel boasts a prime location in the heart of Ninh Kieu Wharf, offering panoramic views of the Hau River and the city. The hotel features 308 rooms equipped with modern amenities and offers a range of facilities including an outdoor swimming pool, massage services, and a spa."
        },
        address: "Khu E1, Cồn Cái Khế, phường Cái Khế, quận Ninh Kiều, TP Cần Thơ",
        lat: 10.0424, lon: 105.7903,
        img: "https://booking.muongthanh.com/images/hotels/hotels/original/_mg_1150_ok_1678844121_1698131857.jpg",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Dalat Palace Heritage Hotel",
        price: 3000000,
        rating: 4.5,
        desc: {
            vi: "Khách sạn mang đậm phong cách kiến trúc Edwardian và Art Deco, tái hiện lại vẻ đẹp quý phái thời thuộc địa Pháp, nằm ngay trung tâm thành phố, đối diện hồ Xuân Hương.",
            en: "The hotel, with its distinctive Edwardian and Art Deco architectural style, recreates the elegant beauty of the French colonial era and is located right in the city center, opposite Xuan Huong Lake."
        },
        address: "Số 02 Đường Trần Phú, phường Xuân Hương, thành phố Đà Lạt, tỉnh Lâm Đồng.",
        lat: 11.9416, lon: 108.4348,
        img: "https://lh3.googleusercontent.com/p/AF1QipMA3dmc6SrKjg4gaj2rErnBn8xtc4pYDK549R17=w324-h312-n-k-no",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    },
    {
        name: "Anantara Hoi An Resort",
        price: 5000000,
        rating: 4.7,
        desc: {
            vi: "Resort ven sông Thu Bồn được thiết kế với kiến trúc Pháp cổ điển pha lẫn nét Á Đông, không gian yên bình và dịch vụ 5 sao, spa với các liệu pháp truyền thống.",
            en: "The Thu Bon Riverfront resort is designed with classic French architecture blended with East Asian touches, offering a peaceful atmosphere and 5-star service, including a spa with traditional treatments."
        },
        address: "1 Phố Đào Duy Từ, phường Cẩm Phô, Hội An, tỉnh Quảng Nam.",
        lat: 15.8906, lon: 108.3242,
        img: "https://dynamic-media-cdn.tripadvisor.com/media/photo-o/2a/0d/7d/07/anantara-hoi-an-resort.jpg?w=500&h=-1&s=1",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "InterContinental Hanoi Westlake",
        price: 5000000,
        rating: 4.7,
        desc: {
            vi: "Khách sạn có thiết kế đẹp, sang trọng với các phòng nghỉ được xây dựng trên mặt hồ, dịch vụ được đánh giá là chuyên nghiệp, nhân viên nhiệt tình, thân thiện, các tiện nghi gồm nhà hàng, spa, phòng tập gym ,buffet khen gợi là kết hợp Á-Âu.",
            en: "The hotel boasts a beautiful, luxurious design with rooms built over the lake, the service was rated as professional, and the staff were enthusiastic and friendly, and amenities including a restaurant, spa, gym, and a complimentary Asian-European fusion buffet."
        },
        address: "05 Phố Từ Hoa, Quảng An, quận Tây Hồ, Thủ đô Hà Nội",
        lat: 21.0504, lon: 105.8306,
        img: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRFPfIlDBCifpwaRRsVAd1ZSy-zAfQu7MDQtA&s",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },

    {
        name: "Park Hyatt SaiGon",
        price: 10000000,
        rating: 4.9,
        desc: {
            vi: "Khách sạn 5 sao sang trọng nổi bật với vẻ đẹp cổ điển, kiến trúc Pháp sang trọng và nội thất tinh tế, cung cấp đầy đủ các tiện nghi đẳng cấp, khuôn viên nhiệt đới, nhiều lựa chọn ẩm thực, khách sạn có hồ bơi ngoài trời, spa, phòng tập gym.",
            en: "This luxurious 5-star hotel stands out with its classic beauty, elegant French architecture, and sophisticated interiors, offering a full range of upscale amenities, tropical grounds, diverse dining options, an outdoor swimming pool, a spa, and a gym."
        },
        address: "2 Công trường Lam Sơn, phường Bến Nghé, Quận 1, TP Hồ Chí Minh",
        lat: 10.7766, lon: 106.7024,
        img: "https://assets.hyatt.com/content/dam/hyatt/hyattdam/images/2020/03/15/2356/Park-Hyatt-Saigon-P670-Park-Lounge.jpg/Park-Hyatt-Saigon-P670-Park-Lounge.16x9.jpg?imwidth=2560",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },




];

window.homeResults = dummyList;

function renderAccommodationList() {
    const container = document.getElementById("accommodation-list");
    if (!container) return;
    container.innerHTML = "";

    // 1. Lấy ngôn ngữ hiện tại từ bộ nhớ (mặc định là 'vi')
    const currentLang = localStorage.getItem('userLang') || 'vi'; 

    dummyList.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "accommodation-card"; 
        
        // 2. CHỌN MÔ TẢ ĐÚNG NGÔN NGỮ
        // Nếu không tìm thấy ngôn ngữ hiện tại thì lấy tiếng Việt làm mặc định
        const description = item.desc[currentLang] || item.desc['vi'];

        card.innerHTML = `
            <div style="height:200px; overflow:hidden;">
                 <img src="${item.img}" style="width:100%; height:100%; object-fit:cover;" alt="${item.name}">
            </div>
            <div class="accommodation-content" style="padding:15px; display: flex; flex-direction: column; flex-grow: 1;">
                <h3 class="accommodation-title">${item.name}</h3>
                
                <p class="accommodation-description" style="color:#666;">${description}</p>
                
                <div style="margin-top: auto;">
                    <div class="price-rating-row" style="display:flex; justify-content:space-between; margin-top:15px;">
                        <div class="accommodation-price" style="font-weight:bold; color:#4a6cf7;">${item.price.toLocaleString()} VND</div>
                        <div class="accommodation-rating">★ ${item.rating}</div>
                    </div>

                    <button class="map-button" 
                        data-i18n="btn_view_map" 
                        style="width:100%; margin-top:15px; padding:10px; background:#eee; border:none; border-radius:5px; cursor:pointer;"
                        onclick="openRoutingModal(${index})">
                        Xem bản đồ
                    </button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });

    if (typeof applyTranslations === "function") {
        applyTranslations();
    }
}

window.renderAccommodationList = renderAccommodationList;
renderAccommodationList();