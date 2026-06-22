import os
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report
import yaml

def main():
    base_dir = Path(__file__).parent.parent
    csv_path = base_dir / "user_data/feedback.csv"
    
    if not csv_path.exists():
        print(f"Không tìm thấy dữ liệu feedback tại {csv_path}. Bạn cần dùng giao diện Review trên UI và nhấn 'Lưu Feedback & Xuất CSV' trước.")
        return
        
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Lỗi khi đọc file CSV: {e}")
        return
        
    if len(df) < 10:
        print(f"Dữ liệu feedback quá ít ({len(df)} dòng). Vui lòng đánh giá thêm ít nhất 10 dòng để mô hình có thể học ngưỡng hiệu quả.")
        return
        
    print(f"Đã tải {len(df)} dòng feedback.")
    
    # Chuẩn bị nhãn
    # Nhãn: "Chuẩn" -> 1 (Giữ lại edit), "Sai" / "Rephrase" -> 0 (Từ chối edit)
    df['label'] = df['user_label'].apply(lambda x: 1 if str(x).lower() == 'chuẩn' else 0)
    
    # Features
    features = ['edit_ratio', 'length_delta_ratio', 'confidence']
    X = df[features].fillna(0)
    y = df['label']
    
    if len(y.unique()) < 2:
        print("Dữ liệu chỉ chứa 1 loại nhãn (toàn Chuẩn hoặc toàn Sai). Mô hình không thể phân loại. Vui lòng thêm cả các trường hợp bị lỗi hoặc bị rephrase.")
        return
        
    # Logistic Regression
    print("\n--- Training Logistic Regression ---")
    clf = LogisticRegression(class_weight='balanced')
    clf.fit(X, y)
    
    y_pred = clf.predict(X)
    print("Classification Report:")
    print(classification_report(y, y_pred))
    
    # Extract approximate thresholds
    # Lấy hệ số (coefficients) để gợi ý tăng giảm ngưỡng
    coefs = clf.coef_[0]
    print("\nTrọng số các đặc trưng (Feature Importances):")
    for feat, coef in zip(features, coefs):
        print(f"- {feat}: {coef:.4f} (Âm có nghĩa là giá trị càng cao thì càng dễ bị đánh dấu là Sai)")
        
    # Suggest Thresholds
    print("\n--- Đề xuất điều chỉnh Ngưỡng (Thresholds) ---")
    # Thay vì tự động thay thế file YAML, ta tính giá trị trung bình của lớp "Chuẩn"
    safe_edits = df[df['label'] == 1]
    
    if len(safe_edits) > 0:
        suggested_edit_ratio = safe_edits['edit_ratio'].quantile(0.95)
        suggested_length_ratio = safe_edits['length_delta_ratio'].quantile(0.95)
        suggested_conf = safe_edits['confidence'].quantile(0.05) if 'hybrid' in df['model_mode'].values else 0.85
        
        print(f"Gợi ý cấu hình an toàn dựa trên bách phân vị của dữ liệu 'Chuẩn':")
        print(f"- diff_engine.edit_ratio: {suggested_edit_ratio:.2f}")
        print(f"- diff_engine.length_delta_ratio: {suggested_length_ratio:.2f}")
        print(f"- hybrid.confidence_threshold: {suggested_conf:.2f}")
        
        print("\nBạn có thể cập nhật các giá trị này vào file config/default.yaml")
    else:
        print("Không có case 'Chuẩn' nào để tính toán ngưỡng an toàn.")
        
if __name__ == "__main__":
    main()
