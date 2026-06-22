import os
import sys
import docx
import difflib
from pathlib import Path
from tqdm import tqdm

sys.path.append(str(Path(__file__).parent.parent))

from core.model_runner import ModelRunner
from core.document_processor import process_document
from utils.logging_utils import setup_logging

def get_text_from_docx(path):
    doc = docx.Document(path)
    return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])

def align_and_evaluate(input_text, expected_text, actual_text):
    # Simplistic word-level evaluation
    # This is a basic diff-based metric
    in_words = input_text.split()
    exp_words = expected_text.split()
    act_words = actual_text.split()
    
    # We want to find differences between input and expected
    sm_exp = difflib.SequenceMatcher(None, in_words, exp_words)
    expected_edits = []
    for tag, i1, i2, j1, j2 in sm_exp.get_opcodes():
        if tag != 'equal':
            expected_edits.append({
                'type': tag,
                'in_start': i1, 'in_end': i2,
                'in_text': " ".join(in_words[i1:i2]),
                'exp_text': " ".join(exp_words[j1:j2])
            })
            
    sm_act = difflib.SequenceMatcher(None, in_words, act_words)
    actual_edits = []
    for tag, i1, i2, j1, j2 in sm_act.get_opcodes():
        if tag != 'equal':
            actual_edits.append({
                'type': tag,
                'in_start': i1, 'in_end': i2,
                'in_text': " ".join(in_words[i1:i2]),
                'act_text': " ".join(act_words[j1:j2])
            })
            
    # Now compare actual vs expected edits
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    correct_fixes = []
    missed_fixes = []
    wrong_fixes = []
    
    # A simple overlap checker
    def overlaps(e1, e2):
        return max(e1['in_start'], e2['in_start']) < min(e1['in_end'], e2['in_end'])
        
    matched_actual = set()
    for exp_edit in expected_edits:
        matched = False
        for i, act_edit in enumerate(actual_edits):
            if overlaps(exp_edit, act_edit):
                matched = True
                matched_actual.add(i)
                if exp_edit['exp_text'] == act_edit['act_text']:
                    true_positives += 1
                    correct_fixes.append((exp_edit['in_text'], act_edit['act_text']))
                else:
                    false_positives += 1
                    wrong_fixes.append((exp_edit['in_text'], exp_edit['exp_text'], act_edit['act_text']))
                break
        if not matched:
            false_negatives += 1
            missed_fixes.append((exp_edit['in_text'], exp_edit['exp_text']))
            
    for i, act_edit in enumerate(actual_edits):
        if i not in matched_actual:
            false_positives += 1
            wrong_fixes.append((act_edit['in_text'], "N/A (Should not change)", act_edit['act_text']))
            
    return {
        'TP': true_positives,
        'FP': false_positives,
        'FN': false_negatives,
        'correct_fixes': correct_fixes,
        'missed_fixes': missed_fixes,
        'wrong_fixes': wrong_fixes
    }

def main():
    base_dir = Path(__file__).parent.parent
    input_path = base_dir / "samples/input/van-ban-loi-chinh-ta-test-vietdocproof.docx"
    expected_path = base_dir / "samples/expected/van-ban-dung-chinh-ta-hoan-chinh.docx"
    output_path = base_dir / "samples/output/baseline.docx"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    import yaml
    with open(base_dir / "config/default.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    config['engine']['mode'] = 'aggressive'  # Evaluate on aggressive to see full capabilities
    
    logger = setup_logging()
    runner = ModelRunner(model_name=config['model']['name'])
    
    print("Running baseline processing...")
    for msg in process_document(input_path, output_path, config, runner, logger):
        pass
        
    print("Evaluating...")
    input_text = get_text_from_docx(input_path)
    expected_text = get_text_from_docx(expected_path)
    actual_text = get_text_from_docx(output_path)
    
    res = align_and_evaluate(input_text, expected_text, actual_text)
    
    report_lines = []
    report_lines.append("# Baseline Evaluation Report")
    report_lines.append("")
    report_lines.append(f"- **True Positives (Sửa đúng)**: {res['TP']}")
    report_lines.append(f"- **False Positives (Sửa sai/Sửa dư)**: {res['FP']}")
    report_lines.append(f"- **False Negatives (Bỏ sót)**: {res['FN']}")
    
    precision = res['TP'] / (res['TP'] + res['FP']) if (res['TP'] + res['FP']) > 0 else 0
    recall = res['TP'] / (res['TP'] + res['FN']) if (res['TP'] + res['FN']) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    report_lines.append(f"- **Precision**: {precision:.2f}")
    report_lines.append(f"- **Recall**: {recall:.2f}")
    report_lines.append(f"- **F1 Score**: {f1:.2f}")
    report_lines.append("")
    
    report_lines.append("## Các lỗi bỏ sót (False Negatives - Samples)")
    for in_txt, exp_txt in res['missed_fixes'][:20]:
        report_lines.append(f"- `[{in_txt}]` -> Expected: `[{exp_txt}]`")
        
    report_lines.append("\n## Các lỗi sửa sai (False Positives - Samples)")
    for in_txt, exp_txt, act_txt in res['wrong_fixes'][:20]:
        report_lines.append(f"- `[{in_txt}]` -> Expected: `[{exp_txt}]` | Actual: `[{act_txt}]`")
        
    report_lines.append("\n## Các lỗi sửa đúng (True Positives - Samples)")
    for in_txt, act_txt in res['correct_fixes'][:20]:
        report_lines.append(f"- `[{in_txt}]` -> `[{act_txt}]`")
        
    report_content = "\n".join(report_lines)
    
    with open(base_dir / "evaluate_report.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("Evaluation complete. Report saved to evaluate_report.md")

if __name__ == "__main__":
    main()
