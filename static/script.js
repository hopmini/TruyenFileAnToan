// scripts.js
// Nơi đây sẽ chứa các mã JavaScript chung cho toàn bộ ứng dụng
// Hiện tại, các mã JavaScript liên quan đến tải file đã được di chuyển vào file upload.html
// và file_info.html để dễ quản lý hơn.

// Tuy nhiên, bạn có thể thêm các chức năng chung ở đây, ví dụ:
// - Xử lý đóng mở sidebar (nếu có)
// - Xử lý modal
// - Xử lý thông báo (nếu không dùng flash messages của Flask)

document.addEventListener('DOMContentLoaded', () => {
    // Ví dụ: Tự động ẩn các thông báo flash sau vài giây
    const flashMessages = document.querySelectorAll('.alert');
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transition = 'opacity 0.5s ease-out';
            setTimeout(() => msg.remove(), 500); // Remove after transition
        }, 5000); // Ẩn sau 5 giây
    });
});