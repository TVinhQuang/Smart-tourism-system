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
        img: "https://bevivu.com/wp-content/uploads/image8/2024/02/la-siesta-resort--spa070220241707301318.jpeg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/49826269.jpg?k=7a0126780287a91163402651478546554655",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/244780076.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/139176342.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/178398899.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/228879391.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/170551283.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/365910366.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/35088740.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/17298039.jpg",
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
        img: "https://cf.bstatic.com/xdata/images/hotel/max1024x768/20193833.jpg",
        amenities: ["amenity_pool", "amenity_wifi", "amenity_breakfast"]
    }

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