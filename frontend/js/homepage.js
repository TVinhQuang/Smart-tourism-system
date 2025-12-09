console.log("homepage.js loaded");

const dummyList = [
    {
        name: "La Siesta Hoi An Resort & Spa",
        price: 2500000,
        rating: 9.3,
        // Dữ liệu mô tả đa ngôn ngữ
        desc: {
            vi: "Khu nghỉ dưỡng với 4 hồ bơi, kiến trúc xanh mát và spa đẳng cấp thế giới.",
            en: "Resort with 4 swimming pools, green architecture and world-class spa."
        },
        address: "134 Hùng Vương, Cẩm Phô, Hội An",
        lat: 15.8795, lon: 108.3181,
        img: "https://www.vietnambooking.com/wp-content/uploads/2021/08/La-Siesta-Hoi-An-Resort-Spa-3082021.jpg",
        // Dữ liệu tiện ích dạng KEY
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Hotel Royal Hoi An",
        price: 3200000,
        rating: 9.5,
        desc: {
            vi: "Khách sạn sang trọng bên sông Thu Bồn, mang phong cách Indochine lãng mạn.",
            en: "Luxury hotel by the Thu Bon River, featuring romantic Indochine style."
        },
        address: "39 Đào Duy Từ, Hội An",
        lat: 15.8770, lon: 108.3260,
        img: "https://hotelroyalhoian.vn/wp-content/uploads/2024/10/DJI_0140-3-1.webp",
        amenities: ["amenity_breakfast", "amenity_wifi", "amenity_pool", "amenity_parking"]
    },
    {
        name: "Sunrise Premium Resort Hoi An",
        price: 2800000,
        rating: 9.1,
        desc: {
            vi: "Resort ven biển với bãi tắm riêng và dịch vụ spa cao cấp.",
            en: "Beachfront resort with private beach and premium spa services."
        },
        address: "Au Co, Cửa Đại, Hội An",
        lat: 15.8940, lon: 108.3535,
        img: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRhWxTimfsPS6bJKFCn1dYmku5uxHlGYVggrQ&s",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Allegro Hoi An – Little Luxury Hotel",
        price: 2400000,
        rating: 9.4,
        desc: {
            vi: "Khách sạn boutique với thiết kế cổ điển và dịch vụ chăm sóc tận tâm.",
            en: "Boutique hotel featuring classic design and dedicated hospitality."
        },
        address: "86 Trần Hưng Đạo, Hội An",
        lat: 15.8801, lon: 108.3227,
        img: "https://dynamic-media-cdn.tripadvisor.com/media/photo-o/11/fc/0d/0f/outdoor-pool.jpg?w=900&h=500&s=1",
        amenities: ["amenity_wifi", "amenity_breakfast", "amenity_pool"]
    },
    {
        name: "Palm Garden Beach Resort & Spa",
        price: 2700000,
        rating: 9.0,
        desc: {
            vi: "Resort 5 sao giữa vườn dừa với bãi biển dài đẹp và spa thư giãn.",
            en: "Five-star resort among coconut gardens with long beautiful beach and relaxing spa."
        },
        address: "Lạc Long Quân, Cửa Đại, Hội An",
        lat: 15.8935, lon: 108.3462,
        img: "https://pix10.agoda.net/hotelImages/65107/-1/bbcc058b8e17b3ef51a37f315685ec80.jpg?ce=0&s=414x232",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    },
    {
        name: "Silk Sense Hoi An River Resort",
        price: 2600000,
        rating: 9.2,
        desc: {
            vi: "Khu nghỉ ven sông yên bình với hồ bơi ion siêu sạch và nhiều dịch vụ trải nghiệm.",
            en: "Peaceful riverside resort featuring ultra-clean ion pool and experience services."
        },
        address: "1 Đào Duy Từ, Hội An",
        lat: 15.8812, lon: 108.3289,
        img: "https://pix10.agoda.net/hotelImages/2225333/-1/6ae1ea5094fb92f2ae4d367aa1313303.jpg?ce=0&s=414x232",
        amenities: ["amenity_wifi", "amenity_pool", "amenity_parking"]
    },
    {
        name: "Little Riverside Hoi An – A Luxury Hotel",
        price: 3000000,
        rating: 9.6,
        desc: {
            vi: "Khách sạn sang trọng bên dòng sông Hoài với rooftop pool cực chill.",
            en: "Luxury hotel by the Hoai River with a super chill rooftop pool."
        },
        address: "09 Phan Bội Châu, Hội An",
        lat: 15.8756, lon: 108.3301,
        img: "https://dynamic-media-cdn.tripadvisor.com/media/photo-o/2d/b9/19/da/little-riverside-a-luxury.jpg?w=900&h=500&s=1",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    },
    {
        name: "Ann Retreat Resort & Spa",
        price: 2200000,
        rating: 9.3,
        desc: {
            vi: "Khu nghỉ dưỡng 5 sao thanh bình với thiết kế Indochine sang trọng.",
            en: "Peaceful 5-star retreat with elegant Indochine architecture."
        },
        address: "47 Lê Thánh Tông, Cẩm Phô, Hội An",
        lat: 15.8799, lon: 108.3147,
        img: "https://www.vietnambooking.com/wp-content/uploads/2020/09/combo-ann-retreat-resort-and-spa-10.jpg",
        amenities: ["amenity_wifi", "amenity_pool", "amenity_parking"]
    },
    {
        name: "Koi Resort & Spa Hoi An",
        price: 2900000,
        rating: 9.1,
        desc: {
            vi: "Resort được bao quanh bởi sông nước, phù hợp cho nghỉ dưỡng cao cấp.",
            en: "Resort surrounded by waterways, ideal for premium relaxation."
        },
        address: "Cửa Đại, Hội An",
        lat: 15.8932, lon: 108.3479,
        img: "https://pix10.agoda.net/hotelImages/1805134/-1/0fa21967541e6c1827b1629598ba70ec.jpg?ce=0&s=414x232",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast", "amenity_parking"]
    },
    {
        name: "Boutique Hoi An Resort",
        price: 2600000,
        rating: 9.0,
        desc: {
            vi: "Resort phong cách châu Âu với bãi biển riêng và hồ bơi lớn.",
            en: "Elegant European-style resort with private beach and large swimming pool."
        },
        address: "34 Lạc Long Quân, Hội An",
        lat: 15.8915, lon: 108.3455,
        img: "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSSUtN_JFEMd0NiPDxcgyRC6VNtdKXHU7-JxQ&s",
        amenities: ["amenity_pool", "amenity_wifi"]
    },
    {
        name: "Victoria Hoi An Beach Resort & Spa",
        price: 3100000,
        rating: 9.4,
        desc: {
            vi: "Resort kiểu làng chài độc đáo, có view biển cực đẹp và dịch vụ chu đáo.",
            en: "Unique fishing-village-style resort with beautiful sea view and great service."
        },
        address: "Cửa Đại, Hội An",
        lat: 15.8927, lon: 108.3493,
        img: "https://q-xx.bstatic.com/xdata/images/hotel/max500/463268389.jpg?k=28a934d62d358d83baf9f8c3ad9908989365a83ab3a690bb32238a3e05be8da4&o=",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    },
    {
        name: "Anantara Hoi An Resort",
        price: 3500000,
        rating: 9.5,
        desc: {
            vi: "Resort ven sông Hoài với kiến trúc Pháp cổ tinh tế, không gian yên bình và dịch vụ 5 sao.",
            en: "Riverside resort along the Hoai River, featuring elegant French-colonial architecture and 5-star services."
        },
        address: "1 Phạm Hồng Thái, Cẩm Châu, Hội An",
        lat: 15.8747, lon: 108.3304,
        img: "https://dynamic-media-cdn.tripadvisor.com/media/photo-o/2a/0d/7d/07/anantara-hoi-an-resort.jpg?w=500&h=-1&s=1",
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