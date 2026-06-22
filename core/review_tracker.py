import json
import uuid
import datetime
from pathlib import Path

class ReviewTracker:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.review_data = []

    def add_edit(self, document_id, para_id, orig_text, corr_text, status, reason, edit_ratio=0.0, length_delta=0.0, confidence=0.0):
        edit_id = str(uuid.uuid4())
        self.review_data.append({
            "edit_id": edit_id,
            "document_id": document_id,
            "paragraph_id": para_id,
            "original_text": orig_text,
            "corrected_text": corr_text,
            "status": status,
            "reason": reason,
            "edit_ratio": edit_ratio,
            "length_delta_ratio": length_delta,
            "confidence": confidence,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def save(self):
        json_path = self.output_dir / "review_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.review_data, f, ensure_ascii=False, indent=2)
