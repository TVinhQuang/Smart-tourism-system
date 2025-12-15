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

// --- Thêm biến toàn cục để lưu lịch sử chat ngay đầu file hoặc trước hàm sendMessage ---
let chatHistory = []; 

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value;
    if (text.trim() === "") return;

    const chatBody = document.getElementById('chat-body');
    
    // 1. Hiển thị tin nhắn User lên giao diện
    const userMsgHTML = `
        <div class="message-row user">
            <div class="avatar">👤</div>
            <div class="message-content">${text}</div>
        </div>`;
    chatBody.insertAdjacentHTML('beforeend', userMsgHTML);
    input.value = ""; // Xóa ô nhập liệu
    chatBody.scrollTop = chatBody.scrollHeight; // Cuộn xuống

    // 2. Cập nhật lịch sử chat (Client side)
    chatHistory.push({ "role": "user", "content": text });

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
        const response = await fetch('http://127.0.0.1:8000/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            // --- SỬA LỖI Ở ĐÂY: Gửi đúng key "messages" mà server cần ---
            body: JSON.stringify({ 
                messages: chatHistory 
            })
        });

        const data = await response.json();
        
        // 5. Xóa hiệu ứng loading
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        // 6. Hiển thị câu trả lời từ Bot
        // Nếu server trả về lỗi, data.reply có thể undefined, cần fallback
        const botReply = data.reply || "Xin lỗi, mình không nhận được phản hồi.";
        
        const botMsgHTML = `
            <div class="message-row bot">
                <div class="avatar">🤖</div>
                <div class="message-content">${botReply}</div>
            </div>`;
        chatBody.insertAdjacentHTML('beforeend', botMsgHTML);

        // 7. Cập nhật lịch sử chat với câu trả lời của Bot (để ngữ cảnh liên tục)
        chatHistory.push({ "role": "assistant", "content": botReply });

    } catch (error) {
        console.error("Lỗi Chatbot:", error);
        
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        const errHTML = `
            <div class="message-row bot">
                <div class="avatar">🤖</div>
                <div class="message-content" style="color: red;">Lỗi kết nối server!</div>
            </div>`;
        chatBody.insertAdjacentHTML('beforeend', errHTML);
    }
    
    chatBody.scrollTop = chatBody.scrollHeight;
}