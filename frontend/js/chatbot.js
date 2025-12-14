document.addEventListener("DOMContentLoaded", function() {
    // 1. Danh sách các đường dẫn muốn ẨN chatbot
    // Bạn hãy sửa lại cho đúng tên file hoặc đường dẫn trang login của bạn
    const excludedPages = [
       "../page/login.html", 
    ];

    // 2. Lấy đường dẫn hiện tại của trình duyệt
    const currentPath = window.location.pathname;

    // 3. Kiểm tra: Nếu đường dẫn hiện tại chứa từ khóa trong danh sách trên
    const isExcluded = excludedPages.some(page => currentPath.includes(page));

    if (isExcluded) {
        // Tìm thẻ bao quanh chatbot và ẩn nó đi
        const chatWidget = document.querySelector('.chat-widget-wrapper');
        if (chatWidget) {
            chatWidget.style.display = 'none'; // Ẩn hoàn toàn
        }
    }
});

function toggleChat() {
    const dialog = document.getElementById('chat-dialog');
    const bubble = document.getElementById('greeting-bubble');
    
    // Kiểm tra trạng thái hiện tại
    if (dialog.style.display === 'none' || dialog.style.display === '') {
        // Mở chat
        dialog.style.display = 'flex';
        // Ẩn bong bóng chào khi mở chat (tùy chọn, giống logic Streamlit rerender)
        bubble.style.display = 'none';
    } else {
        // Đóng chat
        dialog.style.display = 'none';
        // Hiện lại bong bóng (hoặc giữ ẩn tùy bạn)
        bubble.style.display = 'block';
    }
}

// Hàm gửi tin nhắn demo (để test giao diện)
function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value;
    if (text.trim() === "") return;

    const chatBody = document.getElementById('chat-body');

    // Tạo HTML cho tin nhắn User
    const userMsgHTML = `
        <div class="message-row user">
            <div class="avatar">👤</div>
            <div class="message-content">${text}</div>
        </div>
    `;
    
    // Thêm vào chat body
    chatBody.insertAdjacentHTML('beforeend', userMsgHTML);
    input.value = ""; // Xóa ô nhập
    
    // Cuộn xuống cuối
    chatBody.scrollTop = chatBody.scrollHeight;

    // Giả lập bot trả lời sau 1 giây
    setTimeout(() => {
        const botMsgHTML = `
            <div class="message-row bot">
                <div class="avatar">🤖</div>
                <div class="message-content">Đây là tin nhắn trả lời tự động.</div>
            </div>
        `;
        chatBody.insertAdjacentHTML('beforeend', botMsgHTML);
        chatBody.scrollTop = chatBody.scrollHeight;
    }, 1000);
}

// Cho phép nhấn Enter để gửi
document.getElementById('chat-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});