document.addEventListener("DOMContentLoaded", function() {
    // 1. Cấu hình: Danh sách các trang KHÔNG hiện chatbot
    // Lưu ý: Điền đúng đường dẫn URL mà trình duyệt hiển thị
    const excludedPages = [
        "/login",           // Ví dụ: http://localhost:8000/login
        "/login.html",      // Ví dụ: http://localhost:8000/login.html
        "signin",
        "dang-nhap"
    ];

    // 2. Kiểm tra URL hiện tại
    const currentPath = window.location.pathname.toLowerCase();
    const isExcluded = excludedPages.some(page => currentPath.includes(page));

    // 3. Nếu ĐANG ở trang login thì DỪNG LẠI, không làm gì cả
    if (isExcluded) {
        return; 
    }

    // 4. Nếu KHÔNG phải trang login, tiêm HTML của Chatbot vào trang
    injectChatbotHTML();
});

function injectChatbotHTML() {
    // Nội dung HTML của Chatbot (đã thu gọn vào biến string)
    const chatbotHTML = `
        <div class="chat-widget-wrapper">
            <div id="greeting-bubble" class="chat-mini-bubble">
                Xin chào! Hôm nay bạn đã nghĩ muốn đi đâu chưa?
            </div>
            <button id="chat-fab" class="chat-fab-button" onclick="toggleChat()">
                🤖
            </button>
        </div>

        <div id="chat-dialog" class="chat-dialog-overlay" style="display: none;">
            <div class="chat-dialog-container">
                <div class="chat-header">
                    <span>Trò chuyện với Mika</span>
                    <button class="close-btn" onclick="toggleChat()">✖</button>
                </div>
                <div class="chat-body" id="chat-body">
                    <div class="message-row bot">
                        <div class="avatar">🤖</div>
                        <div class="message-content">Xin chào! Tôi có thể giúp gì cho bạn?</div>
                    </div>
                </div>
                <div class="chat-footer">
                    <input type="text" placeholder="Nhập tin nhắn..." id="chat-input">
                    <button onclick="sendMessage()">➤</button>
                </div>
            </div>
        </div>
    `;

    // Chèn HTML vào cuối thẻ <body>
    document.body.insertAdjacentHTML('beforeend', chatbotHTML);
    
    // Gắn sự kiện phím Enter cho ô input (vì HTML giờ mới được tạo ra)
    document.getElementById('chat-input').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}

// --- Các hàm xử lý logic cũ giữ nguyên bên dưới ---

function toggleChat() {
    const dialog = document.getElementById('chat-dialog');
    const bubble = document.getElementById('greeting-bubble');
    
    if (dialog.style.display === 'none' || dialog.style.display === '') {
        dialog.style.display = 'flex';
        if(bubble) bubble.style.display = 'none';
    } else {
        dialog.style.display = 'none';
        if(bubble) bubble.style.display = 'block';
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value;
    if (text.trim() === "") return;

    const chatBody = document.getElementById('chat-body');
    
    // 1. Lấy UID (Nếu user đã đăng nhập, UID sẽ có giá trị, nếu không thì null)
    const userUid = localStorage.getItem("user_uid"); 

    // 2. Hiển thị tin nhắn User NGAY LẬP TỨC (để tạo cảm giác mượt mà)
    const userMsgHTML = `
        <div class="message-row user">
            <div class="avatar">👤</div>
            <div class="message-content">${text}</div>
        </div>`;
    chatBody.insertAdjacentHTML('beforeend', userMsgHTML);
    input.value = ""; // Xóa ô nhập liệu
    chatBody.scrollTop = chatBody.scrollHeight; // Cuộn xuống cuối

    // 3. Hiển thị hiệu ứng Loading (...)
    const loadingId = "loading-" + Date.now();
    const loadingHTML = `
        <div class="message-row bot" id="${loadingId}">
            <div class="avatar">🤖</div>
            <div class="message-content">...</div>
        </div>`;
    chatBody.insertAdjacentHTML('beforeend', loadingHTML);
    chatBody.scrollTop = chatBody.scrollHeight;

    // 4. Gọi API Backend
    try {
        // Đảm bảo port khớp với server.py (8000 hoặc 5000)
        const response = await fetch('http://127.0.0.1:8000/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                message: text,
                uid: userUid // Gửi kèm UID để server lưu lịch sử (QUAN TRỌNG)
            })
        });

        const data = await response.json();
        
        // 5. Xóa hiệu ứng loading
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        // 6. Hiển thị câu trả lời từ Bot
        const botMsgHTML = `
            <div class="message-row bot">
                <div class="avatar">🤖</div>
                <div class="message-content">${data.reply}</div>
            </div>`;
        chatBody.insertAdjacentHTML('beforeend', botMsgHTML);

    } catch (error) {
        console.error("Lỗi Chatbot:", error);
        
        // Xóa loading nếu lỗi
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        // Thông báo lỗi cho người dùng
        const errHTML = `
            <div class="message-row bot">
                <div class="avatar">🤖</div>
                <div class="message-content" style="color: red;">Lỗi kết nối server!</div>
            </div>`;
        chatBody.insertAdjacentHTML('beforeend', errHTML);
    }
    
    // Cuộn xuống cuối cùng sau khi bot trả lời
    chatBody.scrollTop = chatBody.scrollHeight;
}