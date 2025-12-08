// =============================================
// CẤU HÌNH API
// =============================================
const API_BASE_URL = 'http://localhost:5000/api';

// =============================================
// API: GỢI Ý NƠI Ở
// =============================================
async function searchAccommodations(formData) {
    try {
        const response = await fetch(`${API_BASE_URL}/accommodations/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Lỗi không xác định');
        }
        
        return data.data;
        
    } catch (error) {
        console.error('Search error:', error);
        alert('Lỗi khi tìm kiếm: ' + error.message);
        return null;
    }
}

// =============================================
// API: TÌM ĐƯỜNG
// =============================================
async function calculateRoute(origin, destination, profile = 'driving') {
    try {
        const response = await fetch(`${API_BASE_URL}/route/calculate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                origin: origin,
                destination: destination,
                profile: profile
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Lỗi không xác định');
        }
        
        return data.data;
        
    } catch (error) {
        console.error('Route error:', error);
        alert('Lỗi khi tính đường: ' + error.message);
        return null;
    }
}

// =============================================
// API: GEOCODING
// =============================================
async function geocodeLocation(query) {
    try {
        const response = await fetch(`${API_BASE_URL}/geocode`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Lỗi không xác định');
        }
        
        return data.data;
        
    } catch (error) {
        console.error('Geocoding error:', error);
        alert('Lỗi khi tìm địa chỉ: ' + error.message);
        return null;
    }
}

// =============================================
// XỬ LÝ FORM GỢI Ý NƠI Ở
// =============================================
document.addEventListener('DOMContentLoaded', function() {
    const accForm = document.getElementById('accommodation-form');
    
    if (accForm) {
        accForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Hiển thị loading
            showLoading();
            
            // Lấy dữ liệu từ form
            const formData = {
                city: document.getElementById('acc_city').value,
                group_size: parseInt(document.getElementById('group_size').value),
                price_min: parseFloat(document.getElementById('price_min').value),
                price_max: parseFloat(document.getElementById('price_max').value),
                types: getSelectedCheckboxes('acc_types'),
                rating_min: parseFloat(document.getElementById('rating_min').value),
                amenities_required: getSelectedCheckboxes('amenities_required'),
                amenities_preferred: getSelectedCheckboxes('amenities_preferred'),
                radius_km: parseFloat(document.getElementById('radius_km').value),
                priority: document.getElementById('priority').value
            };
            
            // Gọi API
            const results = await searchAccommodations(formData);
            
            // Ẩn loading
            hideLoading();
            
            // Hiển thị kết quả
            if (results) {
                displayAccommodationResults(results);
            }
        });
    }
});

// =============================================
// XỬ LÝ FORM TÌM ĐƯỜNG
// =============================================
document.addEventListener('DOMContentLoaded', function() {
    const routeForm = document.getElementById('route-form');
    
    if (routeForm) {
        routeForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Hiển thị loading
            showLoading();
            
            // Lấy dữ liệu từ form
            const origin = document.getElementById('origin').value;
            const destinationLat = parseFloat(document.getElementById('dest_lat').value);
            const destinationLon = parseFloat(document.getElementById('dest_lon').value);
            const destinationName = document.getElementById('dest_name').value;
            const profile = document.getElementById('profile').value;
            
            const destination = {
                lat: destinationLat,
                lon: destinationLon,
                name: destinationName
            };
            
            // Gọi API
            const routeData = await calculateRoute(origin, destination, profile);
            
            // Ẩn loading
            hideLoading();
            
            // Hiển thị kết quả
            if (routeData) {
                displayRouteResults(routeData);
            }
        });
    }
});

// =============================================
// HIỂN THỊ KẾT QUẢ NƠI Ở
// =============================================
function displayAccommodationResults(data) {
    const container = document.getElementById('results-container');
    const resultsList = document.getElementById('results-list');
    
    if (!container || !resultsList) return;
    
    // Xóa kết quả cũ
    resultsList.innerHTML = '';
    
    // Hiển thị relaxation note
    if (data.relaxation_note) {
        const noteDiv = document.createElement('div');
        noteDiv.className = 'info-message';
        noteDiv.textContent = data.relaxation_note;
        resultsList.appendChild(noteDiv);
    }
    
    // Hiển thị từng nơi ở
    data.results.forEach((item, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'result-item';
        
        itemDiv.innerHTML = `
            <h3>#${index + 1}. ${item.name}</h3>
            <p><strong>Loại:</strong> ${item.type}</p>
            <p><strong>Giá:</strong> ${item.price > 0 ? formatPrice(item.price) : 'Đang cập nhật'}</p>
            <p><strong>Rating:</strong> ${item.rating.toFixed(1)}/10 (${item.stars}⭐)</p>
            <p><strong>Khoảng cách:</strong> ${item.distance_km.toFixed(2)} km</p>
            <p><strong>Tiện ích:</strong> ${item.amenities.join(', ') || 'Không có thông tin'}</p>
            <p><strong>Địa chỉ:</strong> ${item.address}</p>
            <p><strong>Score:</strong> ${item.score.toFixed(3)}</p>
            <button onclick="selectAccommodation('${item.id}', ${item.lat}, ${item.lon}, '${item.name}')">
                Xem bản đồ
            </button>
        `;
        
        resultsList.appendChild(itemDiv);
    });
    
    // Hiển thị container
    container.classList.add('show');
}

// =============================================
// HIỂN THỊ KẾT QUẢ TÌM ĐƯỜNG
// =============================================
function displayRouteResults(data) {
    const container = document.getElementById('route-results-container');
    const resultsList = document.getElementById('route-results-list');
    
    if (!container || !resultsList) return;
    
    // Xóa kết quả cũ
    resultsList.innerHTML = '';
    
    // Thông tin tổng quan
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'route-summary';
    summaryDiv.innerHTML = `
        <h3>📍 Lộ trình: ${data.src.name} → ${data.dst.name}</h3>
        <p><strong>Khoảng cách:</strong> ${data.distance_text}</p>
        <p><strong>Thời gian:</strong> ${data.duration_text}</p>
        <p><strong>Phương tiện:</strong> ${translateProfile(data.profile)}</p>
    `;
    resultsList.appendChild(summaryDiv);
    
    // Độ phức tạp
    if (data.complexity) {
        const complexityDiv = document.createElement('div');
        complexityDiv.className = `complexity-${data.complexity.level}`;
        complexityDiv.innerHTML = `
            <h4>Độ phức tạp: ${data.complexity.label}</h4>
            <p>${data.complexity.summary}</p>
            ${data.complexity.reasons.length > 0 ? 
                '<ul>' + data.complexity.reasons.map(r => `<li>${r}</li>`).join('') + '</ul>' 
                : ''}
        `;
        resultsList.appendChild(complexityDiv);
    }
    
    // Gợi ý phương tiện
    if (data.recommended_mode) {
        const recDiv = document.createElement('div');
        recDiv.className = 'info-message';
        recDiv.innerHTML = `
            <p><strong>💡 Gợi ý:</strong> ${data.recommended_mode.explanation}</p>
        `;
        resultsList.appendChild(recDiv);
    }
    
    // Hướng dẫn từng bước
    if (data.steps && data.steps.length > 0) {
        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'route-steps';
        stepsDiv.innerHTML = '<h4>📜 Hướng dẫn từng bước:</h4>';
        
        const stepsList = document.createElement('ol');
        data.steps.forEach(step => {
            const li = document.createElement('li');
            li.textContent = step;
            stepsList.appendChild(li);
        });
        
        stepsDiv.appendChild(stepsList);
        resultsList.appendChild(stepsDiv);
    }
    
    // Hiển thị container
    container.classList.add('show');
    
    // Vẽ bản đồ (nếu có thư viện Leaflet)
    if (typeof L !== 'undefined' && data.geometry) {
        drawMap(data);
    }
}

// =============================================
// VẼ BẢN ĐỒ (LEAFLET)
// =============================================
function drawMap(routeData) {
    const mapContainer = document.getElementById('map');
    if (!mapContainer) return;
    
    // Xóa bản đồ cũ
    mapContainer.innerHTML = '';
    
    // Tạo bản đồ mới
    const map = L.map('map').setView(
        [routeData.src.lat, routeData.src.lon], 
        12
    );
    
    // Thêm tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Marker điểm xuất phát
    L.marker([routeData.src.lat, routeData.src.lon], {
        icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41]
        })
    })
    .bindPopup(`<b>Xuất phát</b><br>${routeData.src.name}`)
    .addTo(map);
    
    // Marker điểm đến
    L.marker([routeData.dst.lat, routeData.dst.lon], {
        icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41]
        })
    })
    .bindPopup(`<b>Điểm đến</b><br>${routeData.dst.name}`)
    .addTo(map);
    
    // Vẽ đường đi
    if (routeData.geometry && routeData.geometry.length > 0) {
        const polyline = L.polyline(routeData.geometry, {
            color: 'blue',
            weight: 5,
            opacity: 0.7
        }).addTo(map);
        
        // Zoom để fit toàn bộ đường
        map.fitBounds(polyline.getBounds());
    }
}

// =============================================
// CÁC HÀM TIỆN ÍCH
// =============================================

function getSelectedCheckboxes(name) {
    const checkboxes = document.querySelectorAll(`input[name="${name}"]:checked`);
    return Array.from(checkboxes).map(cb => cb.value);
}

function formatPrice(price) {
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(price);
}

function translateProfile(profile) {
    const map = {
        'driving': 'Ô tô / Xe máy',
        'walking': 'Đi bộ',
        'cycling': 'Xe đạp'
    };
    return map[profile] || profile;
}

function showLoading() {
    const loader = document.getElementById('loading-overlay');
    if (loader) loader.style.display = 'flex';
}

function hideLoading() {
    const loader = document.getElementById('loading-overlay');
    if (loader) loader.style.display = 'none';
}

function selectAccommodation(id, lat, lon, name) {
    // Lưu thông tin nơi ở được chọn
    sessionStorage.setItem('selected_accommodation', JSON.stringify({
        id: id,
        lat: lat,
        lon: lon,
        name: name
    }));
    
    // Chuyển sang trang tìm đường
    window.location.href = 'routing.html';
}

// Load thông tin nơi ở đã chọn (cho trang routing)
function loadSelectedAccommodation() {
    const data = sessionStorage.getItem('selected_accommodation');
    if (data) {
        const acc = JSON.parse(data);
        document.getElementById('dest_lat').value = acc.lat;
        document.getElementById('dest_lon').value = acc.lon;
        document.getElementById('dest_name').value = acc.name;
        
        // Hiển thị thông tin
        const info = document.getElementById('destination-info');
        if (info) {
            info.innerHTML = `<p>📍 Điểm đến: <strong>${acc.name}</strong></p>`;
        }
    }
}