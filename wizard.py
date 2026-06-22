import gradio as gr
import os
import tempfile
import yaml
from pathlib import Path
from core.model_runner import ModelRunner
from core.document_processor import process_document
from utils.logging_utils import setup_logging

# Load default config
config_path = "config/default.yaml"
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Global runner so we don't reload the model on every request
print("Loading AI Model. This may take a minute...")
runner = ModelRunner(
    model_name=config['model']['name'],
    max_length=config['model']['max_length'],
    batch_size=config['model']['batch_size']
)
logger = setup_logging()

def process_file_ui(file_obj, mode, highlight, experimental_check):
    if file_obj is None:
        yield gr.update(), "Vui lòng tải lên một file .docx", gr.update(), gr.update(), gr.update()
        return
        
    input_path = Path(file_obj.name)
    
    if not input_path.name.endswith(".docx"):
        yield gr.update(), "Chỉ hỗ trợ file Word định dạng .docx", gr.update(), gr.update(), gr.update()
        return
        
    # Create temp directory for outputs
    temp_dir = Path(tempfile.mkdtemp())
    output_path = temp_dir / f"corrected_{input_path.name}"
    
    # Update config dynamically based on UI inputs
    current_config = config.copy()
    current_config['engine']['mode'] = mode
    current_config['engine']['highlight_fallback'] = highlight
    
    try:
        if experimental_check:
            from core.hybrid_runner import HybridRunner
            current_runner = HybridRunner(config=current_config.get('hybrid', {}))
        else:
            current_runner = runner
            
        logs = []
        display_logs = ""
        for log_msg in process_document(input_path, output_path, current_config, current_runner, logger):
            if log_msg:
                logs.append(log_msg)
                # Keep last 200 lines to prevent browser lag but maintain history
                if len(logs) > 200:
                    logs = logs[-200:]
                
                display_logs = "\n".join(logs)
                # KHI ĐANG CHẠY: ẩn vùng KẾT QUẢ
                yield gr.update(), "⏳ **Đang phân tích và sửa lỗi...**", gr.update(), display_logs, gr.update()
        
        # Read the report summary
        report_json_path = temp_dir / "report.json"
        if report_json_path.exists():
            import json
            with open(report_json_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
                stats = report_data.get('stats', {})
                
                summary = f"""### Thống kê sửa lỗi
- **Số đoạn văn đã quét**: {stats.get('total_paragraphs', 0)}
- **Số câu đã sửa**: {stats.get('total_changed_sentences', 0)} / {stats.get('total_sentences', 0)}
- **Tỉ lệ từ thay đổi**: {stats.get('changed_word_ratio_percent', 0)}%
- **Các từ đã sửa**: {stats.get('total_changes_applied', 0)}
"""
        else:
            summary = "Xử lý hoàn tất, nhưng không tìm thấy báo cáo thống kê."
            
        report_html_path = temp_dir / "report.html"
        html_out = str(report_html_path) if report_html_path.exists() else None
            
        # KHI HOÀN TẤT: Hiện vùng KẾT QUẢ lên
        yield str(output_path), summary, html_out, display_logs, gr.update(visible=True)
    except Exception as e:
        import traceback
        error_msg = f"Đã xảy ra lỗi trong quá trình xử lý:\n{str(e)}\n\n{traceback.format_exc()}"
        yield gr.update(), "❌ **Lỗi xử lý**", gr.update(), error_msg, gr.update(visible=True)

# Build Gradio Interface
with gr.Blocks(title="VietDocProof Wizard", theme=gr.themes.Soft(primary_hue="blue")) as demo:
    gr.Markdown(
        "<h1 style='text-align: center; margin-bottom: 10px;'>🧙‍♂️ VietDocProof Wizard</h1>\n"
        "<p style='text-align: center; font-size: 1.1em;'>Trợ lý AI tự động đọc và sửa lỗi chính tả, lỗi dấu câu tiếng Việt cho tài liệu Word mà <b>không làm mất định dạng (format)</b> gốc.</p>"
    )
    
    with gr.Tabs():
        with gr.Tab("Sửa Lỗi & Kết quả"):
            with gr.Row():
                # Nửa bên trái: Thao tác và Kết quả
                with gr.Column(scale=1):
                    gr.Markdown("### 🛠 THAO TÁC")
                    file_input = gr.File(label="1. Kéo thả file .docx vào đây", file_types=[".docx"])
                    
                    mode_radio = gr.Radio(
                        choices=["safe", "review", "aggressive"], 
                        value="safe", 
                        label="2. Tùy chỉnh chế độ sửa lỗi",
                        info="Safe: Sửa lỗi chắc chắn | Review: Thêm các lỗi nghi ngờ | Aggressive: Sửa mạnh tay"
                    )
                    
                    highlight_check = gr.Checkbox(
                        value=True, 
                        label="Bôi đỏ các từ đã sửa để dễ theo dõi",
                    )
                    
                    experimental_check = gr.Checkbox(
                        value=False,
                        label="Bật tính năng Thử nghiệm: Hybrid Corrector (PhoBERT + Dictionary)",
                        info="Thay vì seq2seq dễ gây viết lại câu (Rephrase), Hybrid sẽ chỉ tập trung vào các từ nghi ngờ sai."
                    )
                    
                    submit_btn = gr.Button("🚀 3. Bắt đầu sửa lỗi", variant="primary", size="lg")
                    
                    # Kết quả bị ẩn ban đầu để giữ giao diện cân xứng
                    result_group = gr.Group(visible=False)
                    with result_group:
                        gr.Markdown("---")
                        gr.Markdown("### 📥 KẾT QUẢ")
                        summary_output = gr.Markdown("Chưa có dữ liệu thống kê.")
                        
                        with gr.Row():
                            file_output = gr.File(label="Tải xuống file đã sửa (.docx)")
                            report_html = gr.File(label="Tải xuống báo cáo chi tiết (.html)")
                        
                # Nửa bên phải: Log Terminal
                with gr.Column(scale=1):
                    gr.Markdown("### 🤖 TIẾN TRÌNH")
                    log_output = gr.Code(label="Tiến trình xử lý (Terminal Logs)", language="shell", interactive=False, lines=60)
                    
        with gr.Tab("Góp ý & Đánh giá (Review)"):
            gr.Markdown("### Bảng Đánh giá đề xuất sửa lỗi")
            gr.Markdown("Vui lòng xem lại các thay đổi bên dưới. Cột **User Label** hãy nhập `Chuẩn`, `Sai` hoặc `Rephrase`. Cột **User Suggested** để bạn nhập văn bản thay thế (nếu cần).")
            
            review_df = gr.Dataframe(
                headers=["ID", "Original Text", "Corrected Text", "Status", "Reason", "User Label", "User Suggested"],
                datatype=["str", "str", "str", "str", "str", "str", "str"],
                col_count=(7, "fixed"),
                interactive=True,
                wrap=True
            )
            
            save_feedback_btn = gr.Button("💾 Lưu Feedback & Xuất CSV", variant="primary")
            feedback_status = gr.Markdown("")
            review_state = gr.State()

    def process_and_load_review(file_obj, mode, highlight, experimental_check):
        import json
        
        # Generator wrapper to yield updates and finally the dataframe
        gen = process_file_ui(file_obj, mode, highlight, experimental_check)
        
        last_output = None
        for output in gen:
            last_output = output
            yield output + (gr.update(), gr.update(), gr.update())
            
        # After processing, read review_data.json
        if file_obj is None:
            return
            
        temp_dir = Path(last_output[0]).parent
        review_json_path = temp_dir / "review_data.json"
        
        df_data = []
        raw_data = []
        if review_json_path.exists():
            with open(review_json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                for item in raw_data:
                    df_data.append([
                        item['edit_id'],
                        item['original_text'],
                        item['corrected_text'],
                        item['status'],
                        item['reason'],
                        "", # User Label
                        ""  # User Suggested
                    ])
                    
        yield last_output + (gr.update(value=df_data), raw_data, gr.update(value="Đã tải dữ liệu đánh giá. Sẵn sàng lưu feedback!"))

    submit_btn.click(
        fn=process_and_load_review,
        inputs=[file_input, mode_radio, highlight_check, experimental_check],
        outputs=[file_output, summary_output, report_html, log_output, result_group, review_df, review_state, feedback_status]
    )
    
    def save_feedback(df, raw_data, experimental_check):
        import csv
        from pathlib import Path
        import datetime
        
        if not raw_data or df is None:
            return "❌ Không có dữ liệu để lưu."
            
        user_data_dir = Path("user_data")
        user_data_dir.mkdir(exist_ok=True)
        csv_path = user_data_dir / "feedback.csv"
        
        file_exists = csv_path.exists()
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "document_id", "paragraph_id", "edit_id", "model_mode",
                    "original_text", "corrected_text", "user_suggested_text",
                    "user_label", "status", "reason", "edit_ratio", "length_delta_ratio", "confidence", "timestamp"
                ])
                
            model_mode = "hybrid" if experimental_check else "seq2seq"
            
            # Match dataframe back to raw data
            # df is a pandas DataFrame or list of lists
            # Since interactive=True, gradio passes pandas dataframe
            df_records = df.to_dict('records') if hasattr(df, 'to_dict') else df
            
            for row in df_records:
                # row could be dict if pandas, or list if basic
                if isinstance(row, dict):
                    e_id = row.get("ID", "")
                    u_lbl = row.get("User Label", "")
                    u_sug = row.get("User Suggested", "")
                else:
                    e_id, _, _, _, _, u_lbl, u_sug = row
                    
                if not u_lbl:
                    continue # Only save if user provided a label
                    
                # Find raw item
                raw_item = next((item for item in raw_data if item['edit_id'] == e_id), None)
                if raw_item:
                    writer.writerow([
                        raw_item['document_id'],
                        raw_item['paragraph_id'],
                        raw_item['edit_id'],
                        model_mode,
                        raw_item['original_text'],
                        raw_item['corrected_text'],
                        u_sug,
                        u_lbl,
                        raw_item['status'],
                        raw_item['reason'],
                        raw_item['edit_ratio'],
                        raw_item['length_delta_ratio'],
                        raw_item['confidence'],
                        datetime.datetime.now().isoformat()
                    ])
                    
        return f"✅ Đã lưu Feedback thành công vào `{csv_path}`."

    save_feedback_btn.click(
        fn=save_feedback,
        inputs=[review_df, review_state, experimental_check],
        outputs=[feedback_status]
    )

if __name__ == "__main__":
    print("Khởi động VietDocProof Wizard...")
    demo.queue().launch(inbrowser=True, server_name="127.0.0.1", server_port=7860, share=True)

