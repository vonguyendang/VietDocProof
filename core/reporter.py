import pandas as pd
import json

class Reporter:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.records = []
        
    def add_record(self, record):
        """
        record dict containing required fields: file_name, section_name, paragraph_index, etc.
        """
        self.records.append(record)
        
    def generate_reports(self, stats_summary):
        df = pd.DataFrame(self.records)
        
        # Save CSV
        if not df.empty:
            df.to_csv(self.output_dir / "report.csv", index=False)
        else:
            pd.DataFrame(columns=["file_name", "paragraph_index", "original_text"]).to_csv(self.output_dir / "report.csv", index=False)
        
        # Save JSON
        with open(self.output_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump({
                "stats": stats_summary,
                "changes": self.records
            }, f, ensure_ascii=False, indent=2)
            
        # Save HTML
        html_content = f"<html><head><meta charset='utf-8'><title>VietDocProof Report</title></head><body>"
        html_content += f"<h1>VietDocProof Report</h1><h2>Statistics</h2><pre>{json.dumps(stats_summary, indent=2, ensure_ascii=False)}</pre><h2>Changes</h2>"
        if not df.empty:
            html_content += df.to_html(index=False)
        else:
            html_content += "<p>No changes recorded.</p>"
        html_content += "</body></html>"
        
        with open(self.output_dir / "report.html", "w", encoding="utf-8") as f:
            f.write(html_content)
