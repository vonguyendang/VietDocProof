import os
from pathlib import Path
import yaml
import traceback
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Input, RadioSet, RadioButton, Checkbox, Button, Static, Label, ProgressBar, RichLog
from textual.worker import Worker, get_current_worker
from textual import work
import logging

from utils.logging_utils import setup_logging
from core.document_processor import process_document

import threading
from tqdm import tqdm
# Fix ValueError: bad value(s) in fds_to_keep in macOS inside worker threads
tqdm.set_lock(threading.RLock())

class TuiLogHandler(logging.Handler):
    def __init__(self, log_widget):
        super().__init__()
        self.log_widget = log_widget

    def emit(self, record):
        msg = self.format(record)
        try:
            self.log_widget.app.call_from_thread(self.log_widget.write, msg)
        except Exception:
            pass

class VietDocProofApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    #left-panel {
        width: 35%;
        height: 100%;
        border-right: solid green;
        padding: 1 2;
    }
    
    #right-panel {
        width: 65%;
        height: 100%;
        padding: 1 2;
    }
    
    .section-title {
        text-style: bold;
        color: yellow;
        margin-bottom: 1;
        margin-top: 1;
    }
    
    #start-btn {
        width: 100%;
        margin-top: 2;
        background: green;
        color: white;
    }
    
    #status-line {
        text-style: bold;
        color: cyan;
        margin-bottom: 1;
    }
    
    RichLog {
        border: solid blue;
        height: 1fr;
    }
    """
    
    TITLE = "VietDocProof TUI"

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            # Left Panel
            with Vertical(id="left-panel"):
                yield Label("📂 Đường dẫn Input:", classes="section-title")
                yield Input(placeholder="VD: ./samples/input/sample.docx", id="input-path")
                
                yield Label("Loại Input:", classes="section-title")
                with RadioSet(id="input-type"):
                    yield RadioButton("File Đơn", value=True)
                    yield RadioButton("Thư mục (Batch)")
                    
                yield Label("Chế độ sửa lỗi:", classes="section-title")
                with RadioSet(id="correction-mode"):
                    yield RadioButton("Safe (An toàn)", value=True, id="mode-safe")
                    yield RadioButton("Review (Nghi ngờ)", id="mode-review")
                    yield RadioButton("Aggressive (Mạnh tay)", id="mode-aggressive")
                    
                yield Label("Thử nghiệm:", classes="section-title")
                yield Checkbox("Bật Hybrid Corrector", id="hybrid-check")
                
                yield Label("Hệ thống:", classes="section-title")
                yield Checkbox("Bật Log Debug (Chi tiết)", id="debug-check")
                
                yield Button("🚀 Bắt đầu xử lý", id="start-btn", variant="success")
                
            # Right Panel
            with Vertical(id="right-panel"):
                yield Label("Trạng thái: Nhàn rỗi", id="status-line")
                yield ProgressBar(id="progress-bar", show_eta=False)
                yield Label("Terminal Logs:", classes="section-title")
                yield RichLog(id="log-window", highlight=True, markup=True)
                
        yield Footer()

    def on_mount(self) -> None:
        # Tải config mặc định
        self.config_path = "config/default.yaml"
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.logger = logging.getLogger("VietDocProofTUI")
        self.logger.setLevel(logging.INFO)
        log_window = self.query_one("#log-window", RichLog)
        handler = TuiLogHandler(log_window)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            self.start_processing()

    def update_status(self, text: str, color: str = "cyan"):
        status_line = self.query_one("#status-line", Label)
        status_line.update(f"Trạng thái: [{color}]{text}[/]")

    def log_message(self, msg: str):
        self.logger.info(msg)

    def start_processing(self) -> None:
        input_val = self.query_one("#input-path", Input).value.strip()
        
        if not input_val:
            self.update_status("Lỗi: Chưa nhập đường dẫn", "red")
            return
            
        input_path = Path(input_val)
        if not input_path.exists():
            self.update_status("Lỗi: Đường dẫn không tồn tại", "red")
            return
            
        # Vô hiệu hóa các control
        self.query_one("#start-btn", Button).disabled = True
        self.query_one("#input-path", Input).disabled = True
        
        # Read UI states
        input_type_idx = self.query_one("#input-type", RadioSet).pressed_index
        is_file = (input_type_idx == 0)
        
        mode_idx = self.query_one("#correction-mode", RadioSet).pressed_index
        modes = ["safe", "review", "aggressive"]
        mode = modes[mode_idx] if mode_idx is not None else "safe"
        
        use_hybrid = self.query_one("#hybrid-check", Checkbox).value
        use_debug = self.query_one("#debug-check", Checkbox).value
        
        self.query_one("#progress-bar", ProgressBar).progress = 0
        self.query_one("#log-window", RichLog).clear()
        
        self.update_status("Đang tải mô hình...", "yellow")
        
        # Chạy task nền
        self.run_processing_task(input_path, is_file, mode, use_hybrid, use_debug)

    @work(exclusive=True, thread=True)
    def run_processing_task(self, input_path: Path, is_file: bool, mode: str, use_hybrid: bool, use_debug: bool) -> None:
        worker = get_current_worker()
        
        try:
            if use_debug:
                self.logger.setLevel(logging.DEBUG)
                self.log_message("Đã bật chế độ Debug")
            else:
                self.logger.setLevel(logging.INFO)
            # Prepare config
            current_config = self.config.copy()
            current_config['engine']['mode'] = mode
            
            # Load model lazily
            self.log_message("Khởi tạo mô hình trí tuệ nhân tạo...")
            if use_hybrid:
                from core.hybrid_runner import HybridRunner
                runner = HybridRunner(config=current_config.get('hybrid', {}))
                self.log_message("Đã tải Hybrid Corrector.")
            else:
                from core.model_runner import ModelRunner
                runner = ModelRunner(
                    model_name=current_config['model']['name'],
                    max_length=current_config['model']['max_length'],
                    batch_size=current_config['model']['batch_size']
                )
                self.log_message(f"Đã tải Seq2Seq Model: {current_config['model']['name']}.")
            
            if worker.is_cancelled: return
            
            output_dir = Path("samples/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            files_to_process = []
            if is_file:
                files_to_process.append(input_path)
            else:
                files_to_process = list(input_path.glob("*.docx"))
                
            if not files_to_process:
                self.app.call_from_thread(self.update_status, "Lỗi: Không tìm thấy file .docx", "red")
                self.app.call_from_thread(self._re_enable_ui)
                return
                
            self.app.call_from_thread(self.update_status, "Đang xử lý tài liệu...", "yellow")
            
            # Giả lập progress bar (do process_document hiện tại return string log, 
            # để tích hợp progress bar thật ta chia đều 100% cho số lượng file)
            total_files = len(files_to_process)
            
            for i, doc_file in enumerate(files_to_process):
                if worker.is_cancelled: break
                
                out_file = output_dir / f"tui_{doc_file.name}"
                self.log_message(f"Bắt đầu xử lý: {doc_file.name}")
                
                for log_msg in process_document(doc_file, out_file, current_config, runner, self.logger):
                    if worker.is_cancelled: return
                    # Logging is handled by the custom handler inside process_document
                    pass
                
                # Cập nhật progress bar
                progress = (i + 1) / total_files * 100
                self.app.call_from_thread(self._update_progress, progress)
                self.log_message(f"Hoàn tất lưu file tại: {out_file}")
                
            self.app.call_from_thread(self.update_status, "Hoàn tất!", "green")
            
        except Exception as e:
            err_msg = f"Lỗi nghiêm trọng: {str(e)}\n{traceback.format_exc()}"
            self.log_message(err_msg)
            self.app.call_from_thread(self.update_status, "Đã có lỗi xảy ra", "red")
            
        finally:
            self.app.call_from_thread(self._re_enable_ui)

    def _update_progress(self, value: float):
        pb = self.query_one("#progress-bar", ProgressBar)
        pb.update(total=100)
        pb.progress = value

    def _re_enable_ui(self):
        self.query_one("#start-btn", Button).disabled = False
        self.query_one("#input-path", Input).disabled = False

if __name__ == "__main__":
    app = VietDocProofApp()
    app.run()
