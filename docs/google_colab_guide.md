# Hướng dẫn chạy VietDocProof trên Google Colab (Miễn phí & Tốc độ tối đa)

Google Colab cung cấp môi trường chạy Python miễn phí trên đám mây, được trang bị GPU (Card đồ họa) mạnh mẽ giúp tăng tốc độ xử lý AI lên gấp nhiều lần so với CPU thông thường.

Dưới đây là hướng dẫn chi tiết để thiết lập và chạy dự án này trên Colab với tốc độ tối đa sau khi mã nguồn đã được đẩy lên GitHub.

## 1. Thiết lập môi trường Google Colab
1. Truy cập [Google Colab](https://colab.research.google.com/) và tạo một Sổ tay mới (New Notebook).
2. **Bật GPU (Bắt buộc để đạt tốc độ cao nhất):**
   - Trên thanh menu, chọn **Runtime** > **Change runtime type**.
   - Tại mục **Hardware accelerator**, chọn **T4 GPU** (GPU này miễn phí và có 16GB VRAM, rất lý tưởng cho dự án).
   - Bấm **Save**.

## 2. Tải mã nguồn, Cài đặt và Tối ưu cấu hình
Copy toàn bộ khối mã (code block) dưới đây, dán vào một ô (cell) trong Colab và nhấn nút Play (hoặc `Shift + Enter`) để thực thi. 

Đoạn mã này sẽ:
- Clone (tải) mã nguồn trực tiếp từ GitHub của bạn.
- Cài đặt các thư viện cần thiết.
- **Tự động cấu hình lại `batch_size=32`** (kích thước lô xử lý) để tận dụng hết 16GB VRAM của card T4 GPU, thay vì mức 4 mặc định. Điều này giúp xử lý văn bản nhanh gấp nhiều lần.

```python
# 1. Tải dự án từ GitHub (Hãy thay thế URL dưới đây bằng URL repository thực tế của bạn nếu cần)
!git clone https://github.com/vonguyendang/VietDocProof.git

# 2. Di chuyển vào thư mục dự án
%cd VietDocProof

# 3. Cài đặt các thư viện yêu cầu (Transformers, PyTorch, python-docx,...)
!pip install -r requirements.txt

# 4. TỐI ƯU TỐC ĐỘ: Sửa file config để tăng tốc độ xử lý lô (batch processing)
import yaml
import os
import shutil

config_path = 'config/default.yaml'
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Tăng batch size lên 32 để tận dụng tối đa 16GB VRAM của T4 GPU
    config['model']['batch_size'] = 32
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    print("✅ Đã cấu hình xong GPU và tối ưu batch_size = 32!")
else:
    print("❌ Không tìm thấy file config/default.yaml")

# Tạo sẵn thư mục input và output nếu chưa có
os.makedirs('input', exist_ok=True)
os.makedirs('output', exist_ok=True)
os.makedirs('report', exist_ok=True)
```

## 3. Tải file cần xử lý lên Colab
1. Ở thanh menu bên trái của Colab, chọn biểu tượng hình thư mục (**Files**).
2. Bạn sẽ thấy thư mục `VietDocProof` vừa được clone về. Mở rộng thư mục đó.
3. Kéo thả các file Word (`.docx`) cần sửa vào thư mục `VietDocProof/input/`. (Nếu chưa thấy thư mục `input`, bạn có thể click chuột phải chọn *Refresh* hoặc *New folder*).

## 4. Chạy Tool để sửa lỗi văn bản
Sau khi đã tải xong các file cần xử lý, tạo một ô code (cell) mới trên Colab và dán lệnh sau:

```bash
!python cli.py --input ./input --output ./output --report ./report --mode safe
```

**Chú thích các tham số:**
- `--input ./input`: Đường dẫn thư mục chứa các file word gốc.
- `--output ./output`: Nơi xuất file word đã sửa.
- `--report ./report`: Nơi xuất các file báo cáo lịch sử chỉnh sửa (CSV, HTML).
- `--mode safe`: Chế độ tự động sửa đổi. Có thể đổi thành `review` hoặc `aggressive`.

## 5. Tải kết quả về máy tính
1. Trong panel bên trái (Files), mở thư mục theo đường dẫn `VietDocProof/output`.
2. Bạn sẽ thấy các file Word đã được xử lý (ví dụ: `sample_corrected.docx`).
3. Click chuột phải vào file cần lấy và chọn **Download**. Bạn cũng có thể tải về các file báo cáo tại thư mục `VietDocProof/report`.

---
**💡 Tips & Lưu ý:**
- **Lần chạy đầu tiên:** Hệ thống sẽ cần tải model AI (`bmd1905/vietnamese-correction-v2`) từ HuggingFace về, có thể mất 1-2 phút. Từ các file tiếp theo hoặc lần chạy sau (nếu không reset runtime), tốc độ xử lý sẽ rất nhanh.
- **Không tắt trình duyệt:** Nếu bạn đóng tab trình duyệt, phiên Colab sẽ bị ngắt kết nối sau một khoảng thời gian.
- **Bộ nhớ tạm thời:** Máy chủ Colab sẽ tự động xóa toàn bộ file (bao gồm mã nguồn và file kết quả) nếu bạn ngắt kết nối quá lâu (khoảng 12 tiếng). Hãy nhớ **Download kết quả về ngay** sau khi xử lý xong!
