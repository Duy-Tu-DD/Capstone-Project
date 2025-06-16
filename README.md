# Capstone-Project
Phát triển hệ thống tương tác người-máy cho Robot ABB CRB15000
## 📌 Giới thiệu
Dự án Capstone này tập trung vào phát triển **hệ thống tương tác người-máy cho robot ABB CRB15000** sử dụng giao thức **EGM (Externally Guided Motion)**, **RWS(Robot Web Services)** và **Xử lý ảnh** tích hợp với **Robot Studio**. Hệ thống mang đến giải pháp điều khiển robot tiên tiến với các tính năng nổi bật:

- Điều khiển vị trí và hướng robot thời gian thực  
- Tích hợp mô phỏng Robot Studio  
- Điều khiển robot bằng **cử chỉ tay** qua webcam  
- Giao diện người dùng trực quan với **PyQt5**  
- Ghi nhật ký và giám sát trạng thái robot  
---
## 📁 Cấu trúc repository
    RobotControlProject/
    ├── EGM_RobotStudio/                  
    │   ├── Controller Data/CRB15000_5_95
    │   ├── Station
    │   ├── EGM.rsproj                    # Dự án chính
    │   └── README.md 
    ├── Project_Robot/                    
    │   ├── PythonApplication1/
    │   │   ├── egm_pb2.py                # Protobuf definitions
    │   │   ├── Project_Robot.py          # Ứng dụng chính
    │   │   └── ...                       # Các file hỗ trợ
    │   ├── Project_Robot.sln        
    │   └── README.md       
    └── README.md                         
---

## 🧠 Tính năng chính
  ### 1. Điều khiển EGM
  - Giao tiếp robot ABB CRB15000 qua giao thức UDP  
  - Điều khiển vị trí: **X, Y, Z** và góc quay: **RX, RY, RZ**  
  - Hiển thị phản hồi vị trí thời gian thực  
  - Hỗ trợ mô phỏng và robot thực  

  ### 2. Tích hợp Robot Studio
  - Chế độ vận hành: Auto / Manual  
  - Điều khiển động cơ: ON / OFF  
  - Quản lý chương trình RAPID: Run / Stop / Reset  
  - Tùy chỉnh tốc độ robot: 0–100%  

  ### 3. Điều khiển bằng cử chỉ tay
  - Sử dụng thư viện **MediaPipe** để nhận dạng bàn tay  
  - 3 chế độ điều khiển:
    - **Hand Mode:** Đóng/Mở kẹp
    - **Position Mode:** Điều chỉnh vị trí  
    - **Rotation Mode:** Điều chỉnh góc quay  
  - Tương tác qua webcam  

  ###  4. Giao diện người dùng (UI)

  - Xây dựng với **PyQt5**  
  - Giao diện chia thành 3 panel:
    - **EGM Control**
    - **Camera Control**
    - **RWS Control**  
  - Hỗ trợ nút giữ để điều chỉnh liên tục  
  - Hệ thống ghi nhật ký hoạt động  
---

## 💻 Yêu cầu hệ thống
### Phần mềm:

- Python 3.10+  
- ABB Robot Studio  
- Thư viện Python:
  - `PyQt5`, `opencv-python`, `mediapipe`, `protobuf`, `requests`, `numpy`, `pyqtgraph`, `ws4py`  
---

## ⚙️ Cài đặt và chạy chương trình

  ### Clone repository:

    ```bash
    git clone https://github.com/Duy-Tu-DD/Capstone-Project.git
    cd Capstone-Project/EGM_RobotStudio/PythonApplication1
    ```
  ### Cài đặt thư viện:

    ```bash
    pip install PyQt5 opencv-python mediapipe protobuf requests numpy pyqtgraph ws4py
    ```

## 📘 Hướng dẫn sử dụng nhanh

  ### 1. Kết nối với Robot Studio

  - Mở **Robot Studio**, tạo workspace mới  
  - Thêm robot **ABB CRB15000**  
  - Cấu hình EGM trong mục Configuration  

  ### 2. Kết nối với robot thật

  - Bật robot và kết nối mạng  
  - Nhập địa chỉ IP robot trong ứng dụng  
  - Thiết lập cổng EGM (mặc định: 6510)  
  - Nhấn "Start EGM"  

  ### 3. Điều khiển bằng cử chỉ tay

  - Nhấn "Start Camera" để bật webcam  
  - Kích hoạt "Enable Hand Tracking"  
  - Sử dụng các cử chỉ:
    - 👊 Nắm tay: Đóng kẹp  
    - ✋ Mở tay: Mở kẹp  
    - 👉 Chỉ tay: Di chuyển robot  

  ---

## 🎬 Video demo

📺 [Xem video demo hệ thống tại đây](#) *(https://dutudn-my.sharepoint.com/:v:/g/personal/105200391_sv1_dut_udn_vn/Ecb7_S5tIU9LjVKC1QkBP9UBnzPdVQcyaHhK1t52paEDyQ?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=WEk8Wn)*

---

# Tác giả
    Đỗ Đăng Duy Tú - 105200391 - 20TDHCLC1 
    Quách Thiện Đức - 105200358 - 20TDHCLC1
    Nguyễn Hữu Nam Thành - 105200386 - 20TDHCLC1
---

