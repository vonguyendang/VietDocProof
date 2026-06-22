import os
import sys
import yaml
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.model_runner import ModelRunner
from core.document_processor import process_document
from utils.logging_utils import setup_logging
from scripts.benchmark import get_paragraphs_from_docx, evaluate_groups
from core.stats import StatsTracker

def test_config(config_overrides, label):
    print(f"\n{'='*50}\nTesting Configuration: {label}")
    base_dir = Path(__file__).parent.parent
    input_path = base_dir / "samples/input/van-ban-loi-chinh-ta-test-vietdocproof.docx"
    expected_path = base_dir / "samples/expected/van-ban-dung-chinh-ta-hoan-chinh.docx"
    output_path = base_dir / f"samples/output/benchmark_{label}.docx"
    
    with open(base_dir / "config/default.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    config['engine']['mode'] = 'aggressive'
    config['engine']['merge_mode'] = 'soft-merge'
    
    # Apply overrides to ModelRunner indirectly
    runner = ModelRunner(model_name=config['model']['name'])
    
    # We patch the runner generate params temporarily
    original_generate = runner.model.generate
    
    def patched_generate(**kwargs):
        # Remove old generate params that we want to override
        for key in ['num_beams', 'repetition_penalty', 'no_repeat_ngram_size', 'temperature', 'do_sample']:
            kwargs.pop(key, None)
            
        # Add new overrides
        for k, v in config_overrides.items():
            kwargs[k] = v
            
        return original_generate(**kwargs)
        
    runner.model.generate = patched_generate
    logger = setup_logging()
    
    # Disable cache to force generation
    runner.cache = {}
    runner.save_cache = lambda: None
    
    # Hook to collect stats dynamically to see unsafe rejections
    import copy
    
    # Run processing
    for msg in process_document(input_path, output_path, config, runner, logger):
        if "❌ Bỏ qua sửa đổi nguy hiểm" in msg:
            print("  [Reject]", msg)
            
    runner.model.generate = original_generate # restore
    
    # Evaluate
    in_paras = get_paragraphs_from_docx(input_path)
    exp_paras = get_paragraphs_from_docx(expected_path)
    act_paras = get_paragraphs_from_docx(output_path)
    
    groups = evaluate_groups(in_paras, exp_paras, act_paras)
    
    tp = groups['diacritics_spelling']['TP']
    fp = groups['diacritics_spelling']['FP']
    fn = groups['diacritics_spelling']['FN']
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    
    print(f"Results for {label}:")
    print(f"  TP: {tp}, FP: {fp}, FN: {fn}")
    print(f"  Precision: {precision:.2f}, Recall: {recall:.2f}")
    print(f"  Entity Failures: {groups['entity_preservation']['Failures']}")
    print(f"  Format Failures: {groups['format_preservation']['Failures']}")
    return tp, fp, fn, precision, recall

if __name__ == "__main__":
    configs = [
        {"label": "baseline_beam1", "params": {"num_beams": 1}},
        {"label": "beam2_rep1.05", "params": {"num_beams": 2, "repetition_penalty": 1.05}},
        {"label": "beam2_rep1.2", "params": {"num_beams": 2, "repetition_penalty": 1.2}},
        {"label": "beam4_rep1.1", "params": {"num_beams": 4, "repetition_penalty": 1.1}},
        {"label": "sample_temp0.7", "params": {"do_sample": True, "temperature": 0.7, "top_p": 0.9}}
    ]
    
    for conf in configs:
        test_config(conf['params'], conf['label'])
