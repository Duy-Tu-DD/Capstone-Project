# Ứng Dụng Điều Khiển Robot ABB CRB15000 thông qua giao thức EGM, RWS và Xử lý ảnh bằng ngôn ngữ Python

## 📌 Giới thiệu

Ứng dụng này cung cấp giao diện đồ họa toàn diện để điều khiển robot ABB CRB15000, tích hợp các tính năng:
    - Điều khiển qua giao thức EGM (Externally Guided Motion)
    - Quản lý qua Robot Web Services (RWS)
    - Điều khiển bằng cử chỉ tay thông qua camera
    - Giám sát trạng thái robot thời gian thực

## 🧠 Tính năng chính
### 1. Điều khiển EGM
- Kết nối với robot qua UDP
- Điều chỉnh vị trí (X, Y, Z) và góc quay (RX, RY, RZ)
- Hiển thị phản hồi từ robot
- Nút giữ để điều chỉnh liên tục

### 2. Quản lý qua RWS
- Kết nối an toàn với controller
- Quản lý chế độ vận hành (Auto/Manual)
- Điều khiển trạng thái động cơ
- Quản lý chương trình RAPID
- Điều chỉnh tốc độ robot (0-100%)

### 3. Điều khiển bằng cử chỉ tay
- Nhận diện bàn tay với MediaPipe
- 3 chế độ điều khiển:
    - **Hand Mode**: Điều khiển kẹp (gripper)
    - **Position Mode**: Điều chỉnh vị trí
    - **Rotation Mode**: Điều chỉnh góc quay
- Tương tác trực quan qua giao diện camera

### 4. Hệ thống giám sát
- Hiển thị trạng thái EGM
- Giám sát trạng thái RAPID
- Ghi nhật ký hệ thống
- Hiển thị thông tin controller

## 💻 Yêu cầu hệ thống
- Python 3.7+
- Hệ điều hành: Windows
- Camera (để sử dụng tính năng điều khiển bằng tay)

## 🔧 Cài đặt

    1. Clone repository hoặc tải mã nguồn:

        git clone git clone https://github.com/Duy-Tu-DD/Capstone-Project.git
        cd Capstone-Project/Project_Robot

    2. Cài đặt các thư viện cần thiết:
    pip install PyQt5 opencv-python mediapipe protobuf requests numpy pyqtgraph ws4py

    3. Khởi chạy ứng dụng:
    python Project_Robot.py

## 📘 Hướng dẫn sử dụng
    ### Kết nối RWS
        1. Nhập IP controller (mặc định: 192.168.125.1)
        2. Nhập port (mặc định: 443)
        3. Nhập username (mặc định: Admin)
        4. Nhập password (mặc định: robotics)
        5. Nhấn Connect RWS

    ### Kết nối EGM
        1. Nhập IP robot (mặc định: 192.168.125.10)
        2. Nhập port (mặc định: 6510)
        3. Nhấn Start EGM

    ### Sử dụng camera
        1. Chọn camera từ danh sách
        2. Nhấn Start Camera
        3. Enable Hand Tracking để bật nhận diện tay
        4. Hand Control Mode để vào chế độ điều khiển bằng tay

    ### Cử chỉ điều khiển
        - Hand Mode:
            1. 👊 Nắm tay (0 ngón): Đóng kẹp
            2. ✋ Mở tay (5 ngón): Mở kẹp
        - Position Mode:
            1. Chạm nút +X/-X, +Y/-Y, +Z/-Z để điều chỉnh vị trí
            2. Chạm nút Reset về vị trí mặc định (X=500, Y=0, Z=600)
        - Rotation Mode:
            1. Chạm nút +RX/-RX, +RY/-RY, +RZ/-RZ để điều chỉnh góc
            2. Chạm nút Reset về góc mặc định (RX=180, RY=0, RZ=180)

## Cấu trúc giao diện
    Ứng dụng chia thành 3 phần chính:

    1. EGM Control Panel:
        - Kết nối EGM
        - Điều khiển vị trí và góc quay
        - Hiển thị phản hồi từ robot

    2. Camera Control Panel:
        - Xem trực tiếp camera
        - Các nút điều khiển camera
        - Giao diện điều khiển bằng tay

    3. RWS Control Panel:
        - Kết nối RWS
        - Thông tin controller
        - Điều khiển kẹp
        - Quản lý chế độ vận hành
        - Điều khiển động cơ và RAPID
        - Điều chỉnh tốc độ

## 💡 Lưu ý quan trọng
    - Đảm bảo robot và controller đã được cấu hình đúng trước khi sử dụng
    - Các giá trị IP mặc định có thể cần thay đổi tùy vào cấu hình mạng của bạn
    - Khi sử dụng điều khiển bằng tay, đảm bảo:
    - Camera được kết nối và hoạt động
    - Bàn tay nằm trong khung hình camera
    - Đủ ánh sáng để camera nhận diện tay

## 🛠️ Xử lý sự cố
    - Lỗi kết nối EGM:  Kiểm tra địa chỉ IP và port
                        Đảm bảo robot đang ở chế độ EGM
                        Kiểm tra kết nối mạng

    - Lỗi kết nối RWS:  Xác nhận thông tin đăng nhập
                        Kiểm tra kết nối mạng tới controller
                        Đảm bảo cổng 443 không bị chặn

    - Camera không hoạt động:   Kiểm tra camera có được kết nối
                                Thử chọn camera khác trong danh sách
                                Đảm bảo không có ứng dụng nào khác đang sử dụng camera

# Tác giả
Đỗ Đăng Duy Tú - 105200391 - 20TDHCLC1 
Quách Thiện Đức - 105200358 - 20TDHCLC1
Nguyễn Hữu Nam Thành - 105200386 - 20TDHCLC1
