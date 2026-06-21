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

def process_file_ui(file_obj, mode, highlight):
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
        logs = []
        display_logs = ""
        for log_msg in process_document(input_path, output_path, current_config, runner, logger):
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
            
    submit_btn.click(
        fn=process_file_ui,
        inputs=[file_input, mode_radio, highlight_check],
        outputs=[file_output, summary_output, report_html, log_output, result_group]
    )

if __name__ == "__main__":
    print("Khởi động VietDocProof Wizard...")
    demo.queue().launch(inbrowser=True, server_name="127.0.0.1", server_port=7860, share=True)
