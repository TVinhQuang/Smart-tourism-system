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