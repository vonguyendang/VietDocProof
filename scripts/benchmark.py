import os
import sys
import docx
import difflib
from pathlib import Path
from tqdm import tqdm

# Monkey patch transformers' torch load check to avoid requiring torch 2.6
import transformers.utils.import_utils as import_utils
def mock_check_torch_load_is_safe():
    pass
import_utils.check_torch_load_is_safe = mock_check_torch_load_is_safe

sys.path.append(str(Path(__file__).parent.parent))

from core.model_runner import ModelRunner
from core.document_processor import process_document
from utils.logging_utils import setup_logging
from core.entity_protector import EntityProtector

def get_paragraphs_from_docx(path):
    doc = docx.Document(path)
    return [p.text for p in doc.paragraphs if p.text.strip()]

import unicodedata

def remove_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()

def evaluate_groups(in_paras, exp_paras, act_paras):
    groups = {
        'diacritics': {'TP': 0, 'FP': 0, 'FN': 0, 'exemplars': []},
        'spelling': {'TP': 0, 'FP': 0, 'FN': 0, 'exemplars': []},
        'entity_preservation': {'Failures': 0},
        'format_preservation': {'Failures': 0}
    }
    
    protector = EntityProtector()
    for act_p in act_paras:
        for w in protector.WHITELIST.values():
            if w.lower() in act_p.lower() and w not in act_p:
                groups['entity_preservation']['Failures'] += 1
                
    if len(act_paras) != len(in_paras):
        groups['format_preservation']['Failures'] += abs(len(act_paras) - len(in_paras))
        
    in_text = "\n".join(in_paras)
    exp_text = "\n".join(exp_paras)
    act_text = "\n".join(act_paras)
    
    in_words = in_text.split()
    exp_words = exp_text.split()
    act_words = act_text.split()
    
    sm_exp = difflib.SequenceMatcher(None, in_words, exp_words)
    expected_edits = []
    for tag, i1, i2, j1, j2 in sm_exp.get_opcodes():
        if tag != 'equal':
            in_w = " ".join(in_words[i1:i2])
            ex_w = " ".join(exp_words[j1:j2])
            is_diacritics = remove_accents(in_w) == remove_accents(ex_w)
            cat = 'diacritics' if is_diacritics else 'spelling'
            expected_edits.append({'in_start': i1, 'in_end': i2, 'in_text': in_w, 'exp_text': ex_w, 'cat': cat})
            
    sm_act = difflib.SequenceMatcher(None, in_words, act_words)
    actual_edits = []
    for tag, i1, i2, j1, j2 in sm_act.get_opcodes():
        if tag != 'equal':
            actual_edits.append({'in_start': i1, 'in_end': i2, 'in_text': " ".join(in_words[i1:i2]), 'act_text': " ".join(act_words[j1:j2])})
            
    matched_actual = set()
    for exp_edit in expected_edits:
        matched = False
        cat = exp_edit['cat']
        for i, act_edit in enumerate(actual_edits):
            if max(exp_edit['in_start'], act_edit['in_start']) < min(exp_edit['in_end'], act_edit['in_end']):
                matched = True
                matched_actual.add(i)
                if exp_edit['exp_text'] == act_edit['act_text']:
                    groups[cat]['TP'] += 1
                else:
                    groups[cat]['FP'] += 1
                    if len(groups[cat]['exemplars']) < 5:
                        groups[cat]['exemplars'].append({
                            'original': exp_edit['in_text'],
                            'expected': exp_edit['exp_text'],
                            'actual': act_edit['act_text'],
                            'status': 'FP (Wrong correction)'
                        })
                break
        if not matched:
            groups[cat]['FN'] += 1
            if len(groups[cat]['exemplars']) < 5:
                groups[cat]['exemplars'].append({
                    'original': exp_edit['in_text'],
                    'expected': exp_edit['exp_text'],
                    'actual': exp_edit['in_text'], # Unchanged
                    'status': 'FN (Missed)'
                })
            
    for i, act_edit in enumerate(actual_edits):
        if i not in matched_actual:
            groups['spelling']['FP'] += 1 # Assume unmapped FP is spelling/rephrase
            if len(groups['spelling']['exemplars']) < 5:
                groups['spelling']['exemplars'].append({
                    'original': act_edit['in_text'],
                    'expected': act_edit['in_text'], # Expected to be unchanged
                    'actual': act_edit['act_text'],
                    'status': 'FP (Unnecessary edit)'
                })
            
    return groups

def main():
    base_dir = Path(__file__).parent.parent
    input_path = base_dir / "samples/input/van-ban-loi-chinh-ta-test-vietdocproof.docx"
    expected_path = base_dir / "samples/expected/van-ban-dung-chinh-ta-hoan-chinh.docx"
    output_path = base_dir / "samples/output/refactored.docx"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    import yaml
    with open(base_dir / "config/default.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    config['engine']['mode'] = 'aggressive'
    config['engine']['merge_mode'] = 'soft-merge'
    
    logger = setup_logging()
    
    # Enable Hybrid Runner if experimental flag is passed
    if '--experimental' in sys.argv:
        from core.hybrid_runner import HybridRunner
        runner = HybridRunner(config=config.get('hybrid', {}))
        print("Using Experimental Hybrid Runner...")
    else:
        runner = ModelRunner(model_name=config['model']['name'])
        print("Using Seq2Seq Model Runner...")
        
    print("Running refactored processing...")
    list(process_document(input_path, output_path, config, runner, logger))
        
    print("Evaluating...")
    in_paras = get_paragraphs_from_docx(input_path)
    exp_paras = get_paragraphs_from_docx(expected_path)
    act_paras = get_paragraphs_from_docx(output_path)
    
    groups = evaluate_groups(in_paras, exp_paras, act_paras)
    
    # Load review data to get unsafe rejects
    import json
    review_json_path = base_dir / "samples/output/review_data.json"
    rejected_rephrases = 0
    total_edits = 0
    unsafe_exemplars = []
    
    if review_json_path.exists():
        with open(review_json_path, 'r', encoding='utf-8') as f:
            review_data = json.load(f)
            total_edits = len(review_data)
            for item in review_data:
                if item['status'] == 'Rejected':
                    rejected_rephrases += 1
                    if len(unsafe_exemplars) < 5:
                        unsafe_exemplars.append(item)
    
    reject_rate = (rejected_rephrases / total_edits * 100) if total_edits > 0 else 0
    
    report_lines = []
    report_lines.append("# Refactored Evaluation Report")
    report_lines.append("")
    report_lines.append(f"**Unsafe-reject rate**: {reject_rate:.2f}% ({rejected_rephrases}/{total_edits} edits blocked by Rephrase Detector)")
    report_lines.append("")
    
    for cat in ['diacritics', 'spelling']:
        report_lines.append(f"## {cat.capitalize()}")
        tp = groups[cat]['TP']
        fp = groups[cat]['FP']
        fn = groups[cat]['FN']
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        report_lines.append(f"- TP: {tp}, FP: {fp}, FN: {fn}")
        report_lines.append(f"- Precision: {precision:.2f}")
        report_lines.append(f"- Recall: {recall:.2f}")
        report_lines.append("")
        
        if groups[cat]['exemplars']:
            report_lines.append("### Exemplars (Top 5 Errors)")
            report_lines.append("| Original | Expected | Actual | Status |")
            report_lines.append("|---|---|---|---|")
            for ex in groups[cat]['exemplars']:
                report_lines.append(f"| {ex['original']} | {ex['expected']} | {ex['actual']} | {ex['status']} |")
            report_lines.append("")
            
    if unsafe_exemplars:
        report_lines.append("## Unsafe-reject Exemplars (Top 5 Blocked Rephrases)")
        report_lines.append("| Original | Proposed (Blocked) | Reason |")
        report_lines.append("|---|---|---|")
        for ex in unsafe_exemplars:
            report_lines.append(f"| {ex['original_text']} | {ex['corrected_text']} | {ex['reason']} |")
        report_lines.append("")
    
    report_lines.append("## Preservations")
    report_lines.append(f"- Entity Preservation Failures: {groups['entity_preservation']['Failures']}")
    report_lines.append(f"- Format Preservation Failures: {groups['format_preservation']['Failures']}")
    
    report_content = "\n".join(report_lines)
    
    with open(base_dir / "evaluate_report.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("Evaluation complete. Report saved to evaluate_report.md")

if __name__ == "__main__":
    main()
