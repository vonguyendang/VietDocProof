from pathlib import Path
from tqdm import tqdm
from core.docx_reader import DocxReader
from core.text_segmenter import TextSegmenter
from core.diff_engine import DiffEngine
from core.confidence import ConfidenceScorer
from core.revision_writer import RevisionWriter
from core.stats import StatsTracker
from core.reporter import Reporter
from utils.logging_utils import setup_logging

def process_document(input_path, output_path, config, runner, logger=None):
    if not logger:
        logger = setup_logging()
        
    logger.info(f"Processing {input_path}")
    
    reader = DocxReader(input_path)
    segmenter = TextSegmenter(max_length=config['model'].get('max_length', 256))
    diff_engine = DiffEngine()
    scorer = ConfidenceScorer(config['confidence'])
    revision_writer = RevisionWriter(
        mode=config['engine']['mode'], 
        track_changes=config['engine']['track_changes'],
        highlight_fallback=config['engine']['highlight_fallback']
    )
    stats = StatsTracker()
    reporter = Reporter(output_path.parent)
    
    yield f"🚀 Bắt đầu quét và phân tích file: {input_path.name}..."
    
    paragraphs_to_process = list(reader.extract_paragraphs())
    
    for idx, section_name, para, mapper in tqdm(paragraphs_to_process, desc="Scanning Paragraphs"):
        stats.add_paragraph()
        text = mapper.text
        if not text.strip(): continue
        
        chunks = segmenter.segment(text)
        chunk_texts = [c[0] for c in chunks]
        
        if not chunk_texts: continue
            
        corrected_chunks = runner.correct_batch(chunk_texts)
        
        corr_para_text = text
        offset_shift = 0
        for chunk_idx, (orig_chunk, start_idx, end_idx) in enumerate(chunks):
            stats.add_sentence(len(orig_chunk.split()))
            corr_chunk = corrected_chunks[chunk_idx]
            
            # Normalize unicode to avoid flagging identical-looking text (e.g. decomposed vs precomposed)
            import unicodedata
            orig_norm = unicodedata.normalize('NFC', orig_chunk)
            corr_norm = unicodedata.normalize('NFC', corr_chunk)
            
            if orig_norm != corr_norm:
                edits = diff_engine.diff(orig_norm, corr_norm)
                categories = diff_engine.categorize_edits(edits)
                score = scorer.score(orig_chunk, corr_chunk, edits, categories)
                action = scorer.get_action_status(score, mode=config['engine']['mode'])
                
                stats.add_change(action, len(orig_chunk.split()), categories)
                record = {
                        "file_name": Path(input_path).name,
                        "section_name": section_name,
                        "paragraph_index": idx,
                        "original_text": orig_chunk,
                        "corrected_text": corr_chunk,
                        "error_type": ", ".join(categories),
                        "confidence": score,
                        "action_status": action,
                        "changed_word_count": len(orig_chunk.split()) if action == 'apply' else 0
                }
                reporter.add_record(record)
                
                if action == 'apply':
                    ansi_str = ""
                    md_str = ""
                    for e in edits:
                        if e['type'] == 'equal':
                            ansi_str += e['corr_text']
                            md_str += e['corr_text']
                        elif e['type'] == 'replace':
                            ansi_str += f"\033[91m{e['corr_text']}\033[0m"
                            md_str += f"~~{e['orig_text']}~~ **{e['corr_text']}**"
                        elif e['type'] == 'delete':
                            # Don't show deletions in the terminal corrected string to avoid clutter
                            md_str += f"~~{e['orig_text']}~~"
                        elif e['type'] == 'insert':
                            ansi_str += f"\033[91m{e['corr_text']}\033[0m"
                            md_str += f"**{e['corr_text']}**"
                            
                    import sys
                    tqdm.write(f"🔄 Đã sửa: {orig_chunk}  -->  {ansi_str}")
                    sys.stdout.flush()
                    yield f"🔄 Đã sửa: {md_str}"
                    
                    real_start = start_idx + offset_shift
                    real_end = end_idx + offset_shift
                    corr_para_text = corr_para_text[:real_start] + corr_chunk + corr_para_text[real_end:]
                    offset_shift += len(corr_chunk) - len(orig_chunk)
                    
        if corr_para_text != text:
            para_edits = diff_engine.diff(text, corr_para_text)
            revision_writer.apply_edits(para, mapper, para_edits)
            
        # Save cache periodically to allow resuming
        if idx > 0 and idx % 20 == 0:
            runner.save_cache()
            
    # Save cache at the end
    runner.save_cache()
            
    # Save the output
    reader.save(output_path)
    
    # Save reports
    reporter.generate_reports(stats.get_summary())
    logger.info(f"Finished processing. Saved output to {output_path}")
