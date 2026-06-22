# Hướng dẫn sử dụng VietDocProof

VietDocProof là một công cụ AI tự động đọc và sửa lỗi chính tả, lỗi dấu câu tiếng Việt cho tài liệu Word (.docx) mà **không làm vỡ định dạng (Format Preservation)** của file gốc. Tài liệu này hướng dẫn chi tiết cách sử dụng các tính năng từ cơ bản đến nâng cao.

## 1. Cài đặt

Yêu cầu: Python 3.9 trở lên.

```bash
# Clone source code hoặc tải thư mục dự án
cd VietDocProof

# Tạo môi trường ảo
python3 -m venv venv
source venv/bin/activate

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt
pip install Levenshtein
```

## 2. Các phương thức sử dụng

### 2.1. Sử dụng giao diện Web UI (Khuyên dùng)
Giao diện trực quan, hỗ trợ kéo thả file và có tab dành riêng cho tính năng Review & Đánh giá của người dùng.

```bash
python3 wizard.py
```
Hệ thống sẽ mở ra ở địa chỉ: `http://127.0.0.1:7860`.

**Các bước sử dụng UI:**
1. Kéo thả file `.docx` vào khu vực tải lên.
2. Chọn **Chế độ sửa lỗi**:
   - `Safe`: Chỉ sửa các lỗi chắc chắn, bảo toàn độ chính xác cao nhất.
   - `Review`: Chế độ cân bằng, có thể cho phép nhiều từ bị thay đổi hơn.
   - `Aggressive`: Sửa lỗi mạnh tay, nguy cơ thay đổi văn phong gốc (Rephrase) cao hơn.
3. (Tùy chọn) Bật tính năng **Thử nghiệm: Hybrid Corrector**. Chế độ này sử dụng kết hợp từ điển và mô hình PhoBERT để sửa riêng các cụm từ sai chính tả mà không làm thay đổi cả câu.
4. Bấm **Bắt đầu sửa lỗi** và theo dõi tiến trình (Terminal log ngay trên màn hình).
5. Khi hoàn thành, file `.docx` đã sửa sẽ hiện ra để tải xuống. (Những từ được sửa có thể được bôi đỏ nếu chọn tùy chọn Highlight).

### 2.2. Sử dụng Command Line (CLI)
Dùng cho mục đích tự động hóa hoặc chạy hàng loạt.

```bash
python3 cli.py \
    --input ./samples/input/sample.docx \
    --output ./samples/output/sample_corrected.docx \
    --report ./samples/report \
    --mode safe
```

## 3. Human-in-the-loop: Tính năng Review & Feedback

VietDocProof được thiết kế siêu an toàn bằng bộ phát hiện "Rephrase Detector". Khi AI đề xuất sửa đổi làm thay đổi quá nhiều (vượt ngưỡng Edit Ratio hoặc Length Delta) hoặc đụng chạm đến danh từ riêng (Entity), đề xuất đó sẽ bị **TỪ CHỐI** để bảo vệ văn bản gốc của bạn.

Tuy nhiên, bạn có thể xem lại những đề xuất bị từ chối này, đánh giá chúng, và giúp phần mềm tự động tinh chỉnh (Tuning) lại các ngưỡng cho lần chạy sau.

### Bước 1: Xem lại các đề xuất (Review)
1. Sau khi chạy xong quá trình sửa lỗi trên UI (`wizard.py`), hãy chuyển sang Tab **"Góp ý & Đánh giá (Review)"**.
2. Tại đây, bạn sẽ thấy một bảng dữ liệu (Dataframe) ghi lại toàn bộ lịch sử chỉnh sửa (được duyệt hoặc bị từ chối). Cột **Reason** sẽ giải thích vì sao từ đó bị từ chối (vd: `length_delta_exceeded`).

### Bước 2: Gắn nhãn (Labeling)
1. Nhấp đúp vào ô trống ở cột **User Label** tương ứng với lỗi bạn muốn đánh giá.
2. Gõ `Chuẩn` nếu bạn cho rằng đề xuất sửa của AI là đúng và phần mềm nên cho phép (Bị đánh rớt oan).
3. Gõ `Sai` hoặc `Rephrase` nếu bạn đồng ý với phần mềm là AI đã đề xuất sai.
4. (Tùy chọn) Nhập từ bạn cho là đúng vào cột **User Suggested**.

### Bước 3: Lưu Feedback
Bấm nút **Lưu Feedback & Xuất CSV**. Dữ liệu sẽ được lưu an toàn vào tệp `user_data/feedback.csv`.

### Bước 4: Chạy tính năng Machine Learning học lại ngưỡng an toàn
Sau khi bạn đã đánh giá ít nhất 10 trường hợp trong CSV, bạn có thể chạy script đào tạo:

```bash
python3 scripts/train_thresholds.py
```

Script này sẽ sử dụng Machine Learning (Logistic Regression) phân tích các đánh giá của bạn (dựa trên Edit ratio, Length delta, Confidence) và sẽ **gợi ý lại các thông số cấu hình an toàn nhất** dành riêng cho loại văn bản của bạn.

## 4. Tùy chỉnh Cấu hình (config/default.yaml)

Tất cả tinh chỉnh quan trọng đều nằm trong file `config/default.yaml`. 

```yaml
engine:
  mode: "safe" 
  highlight_fallback: true # Bật/Tắt bôi đỏ text được sửa

diff_engine:
  edit_ratio: 0.20 # Ngưỡng tối đa cho phép từ thay đổi so với câu gốc
  length_delta_ratio: 0.30 # Ngưỡng tối đa về sự chênh lệch độ dài
  user_lexicon: # Danh sách từ vựng/Danh từ riêng của bạn (Tuyệt đối không bị sửa)
    - VietinBank
    - Apple
    - Cần Thơ

hybrid:
  confidence_threshold: 0.85 # Độ tự tin tối thiểu của PhoBERT để áp dụng từ sửa đổi
```

**Mẹo**: Bạn có thể cập nhật `user_lexicon` để thêm các từ viết tắt chuyên ngành, tên công ty, hoặc thuật ngữ địa phương. Hệ thống sẽ tự động bỏ qua chúng khi báo lỗi.

## 5. Cấu trúc Thư mục

- `core/`: Logic chính (Model Runner, Document Processor, Diff Engine, Hybrid Runner).
- `config/`: File cấu hình `default.yaml`.
- `scripts/`: Chứa các kịch bản phụ trợ như `benchmark.py` (Chạy đo lường) và `train_thresholds.py` (Học lại ngưỡng an toàn).
- `user_data/`: Nơi lưu trữ file `feedback.csv` của bạn.
- `samples/`: Chứa các tệp DOCX mẫu để bạn chạy thử nghiệm.
- `wizard.py` và `cli.py`: Các công cụ khởi động giao diện ứng dụng.
