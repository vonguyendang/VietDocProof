import argparse
import yaml
import os
from pathlib import Path
from utils.logging_utils import setup_logging
from core.model_runner import ModelRunner
from core.document_processor import process_document

def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="VietDocProof: Vietnamese Spelling and Grammar Correction for Word Documents")
    parser.add_argument("--input", type=str, default="./input", help="Input .docx file or directory (default: ./input)")
    parser.add_argument("--output", type=str, default="./output", help="Output directory or file path (default: ./output)")
    parser.add_argument("--report", type=str, default="./report", help="Report output directory (default: ./report)")
    parser.add_argument("--mode", type=str, choices=["safe", "review", "aggressive"], help="Confidence mode (overrides config)")
    parser.add_argument("--track-changes", type=bool, help="Enable Microsoft Word Track Changes (overrides config)")
    parser.add_argument("--highlight-fallback", type=bool, help="Enable red text highlighting fallback (overrides config)")
    parser.add_argument("--model", type=str, help="HuggingFace model name (overrides config)")
    parser.add_argument("--experimental", action="store_true", help="Enable experimental Hybrid Corrector")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", type=str, default="config/default.yaml", help="Path to config file")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    
    # Override with CLI arguments if provided
    if args.mode:
        config['engine']['mode'] = args.mode
    if args.track_changes is not None:
        config['engine']['track_changes'] = args.track_changes
    if args.highlight_fallback is not None:
        config['engine']['highlight_fallback'] = args.highlight_fallback
    if args.model:
        config['model']['name'] = args.model

    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)
    
    # Setup directories
    if not input_path.exists():
        print(f"Error: Input path {input_path} does not exist.")
        return
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.mkdir(parents=True, exist_ok=True)

    import logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(report_path / "run.log", level=log_level)
    logger.info(f"Starting VietDocProof with config: {config}")
    
    if args.experimental:
        from core.hybrid_runner import HybridRunner
        runner = HybridRunner(config=config.get('hybrid', {}))
        logger.info("Using Experimental Hybrid Runner")
    else:
        from core.model_runner import ModelRunner
        runner = ModelRunner(model_name=config['model']['name'], max_length=config['model']['max_length'], batch_size=config['model']['batch_size'])
        logger.info("Using Seq2Seq Model Runner")
    
    if input_path.is_file():
        if output_path.is_dir():
            actual_output_path = output_path / input_path.name
        else:
            actual_output_path = output_path
        for _ in process_document(input_path, actual_output_path, config, runner, logger): pass
    else:
        # Batch processing
        for doc_file in input_path.glob("*.docx"):
            out_file = output_path / doc_file.name
            for _ in process_document(doc_file, out_file, config, runner, logger): pass

if __name__ == "__main__":
    main()
