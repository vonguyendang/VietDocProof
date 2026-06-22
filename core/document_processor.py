from pathlib import Path
from tqdm import tqdm

from core.docx_reader import DocxReader
from core.text_segmenter import TextSegmenter
from core.diff_engine import DiffEngine
from core.confidence import ConfidenceScorer
from core.revision_writer import RevisionWriter
from core.stats import StatsTracker
from core.reporter import Reporter
from core.normalizer import TextNormalizer
from core.entity_protector import EntityProtector
from core.paragraph_merger import ParagraphMerger
from utils.logging_utils import setup_logging

def process_document(input_path, output_path, config, runner, logger=None):
    if not logger:
        logger = setup_logging()
        
    logger.info(f"Processing {input_path}")
    
    reader = DocxReader(input_path)
    segmenter = TextSegmenter(max_length=config['model'].get('max_length', 256))
    diff_engine = DiffEngine(config.get('diff_engine', None))
    scorer = ConfidenceScorer(config['confidence'])
    revision_writer = RevisionWriter(
        mode=config['engine']['mode'], 
        track_changes=config['engine']['track_changes'],
        highlight_fallback=config['engine']['highlight_fallback']
    )
    stats = StatsTracker()
    reporter = Reporter(output_path.parent)
    protector = EntityProtector()
    
    mode = config['engine'].get('merge_mode', 'soft-merge')
    
    from core.review_tracker import ReviewTracker
    review_tracker = ReviewTracker(output_path.parent)
    document_id = input_path.name
    
    yield f"🚀 Bắt đầu quét và phân tích file: {input_path.name} (Mode: {mode})..."
    
    paragraphs_to_process = list(reader.extract_paragraphs())
    
    buffer_data = []
    
    for idx, section_name, para, mapper in tqdm(paragraphs_to_process, desc="Scanning Paragraphs"):
        buffer_data.append((idx, section_name, para, mapper))
        
        # Decide if we should merge with next
        should_merge = False
        if idx < len(paragraphs_to_process) - 1 and mode in ['soft-merge', 'hard-merge']:
            next_idx, next_section, next_para, next_mapper = paragraphs_to_process[idx + 1]
            prev_style = para.style.name if para.style else ""
            next_style = next_para.style.name if next_para.style else ""
            if ParagraphMerger.should_merge(para.text, next_para.text, prev_style, next_style):
                should_merge = True
                
        if not should_merge:
            # Process buffer
            if not buffer_data:
                continue
                
            # 1. Build Logical Text
            logical_text = "\n".join([d[2].text for d in buffer_data])
            
            if not logical_text.strip():
                buffer_data = []
                continue
                
            stats.add_paragraph() # Count as 1 logical block
            para_id = f"para_{buffer_data[0][0]}"
            
            # 2. Normalize
            norm_text = TextNormalizer.normalize_all(logical_text)
            
            # 3. Protect Entities
            protected_text, entity_map = protector.protect(norm_text)
            
            # 4. Segment and Correct
            chunks = segmenter.segment(protected_text)
            chunk_texts = [c[0] for c in chunks]
            
            if chunk_texts:
                corrected_chunks = runner.correct_batch(chunk_texts)
                
                # Reconstruct corrected protected text
                corr_protected_text = protected_text
                offset_shift = 0
                for chunk_idx, (orig_chunk, start_idx, end_idx) in enumerate(chunks):
                    stats.add_sentence(len(orig_chunk.split()))
                    corr_chunk = corrected_chunks[chunk_idx]
                    real_start = start_idx + offset_shift
                    real_end = end_idx + offset_shift
                    corr_protected_text = corr_protected_text[:real_start] + corr_chunk + corr_protected_text[real_end:]
                    offset_shift += len(corr_chunk) - len(orig_chunk)
                    
                # 5. Unprotect Entities
                corr_norm_text = protector.unprotect(corr_protected_text, entity_map)
                
                # 6. Diff & Apply
                import unicodedata
                logical_norm = unicodedata.normalize('NFC', logical_text)
                corr_norm = unicodedata.normalize('NFC', corr_norm_text)
                
                if logical_norm != corr_norm:
                    edits = diff_engine.diff(logical_norm, corr_norm)
                    
                    # Map edits to physical paragraphs
                    para_boundaries = []
                    curr_offset = 0
                    for d in buffer_data:
                        length = len(d[2].text)
                        para_boundaries.append((curr_offset, curr_offset + length, d))
                        curr_offset += length + 1 # +1 for \n
                        
                    for edit in edits:
                        if edit['type'] == 'equal':
                            continue
                            
                        orig_start = edit['orig_start']
                        orig_end = edit['orig_end']
                        
                        # Find which paragraph it belongs to
                        intersecting_paras = []
                        for start_bound, end_bound, d in para_boundaries:
                            if orig_start < end_bound and orig_end > start_bound:
                                intersecting_paras.append((start_bound, end_bound, d))
                                
                        if not intersecting_paras:
                            continue
                            
                        if len(intersecting_paras) > 1:
                            if mode == 'hard-merge':
                                # Allow cross-paragraph edits in hard-merge
                                pass
                            else:
                                # Soft-merge: Reject destructive cross-boundary edit
                                record = {
                                    "file_name": Path(input_path).name,
                                    "section_name": buffer_data[0][1],
                                    "paragraph_index": buffer_data[0][0],
                                    "original_text": edit['orig_text'],
                                    "corrected_text": edit['corr_text'],
                                    "error_type": "rejected_destructive_merge",
                                    "confidence": 0,
                                    "action_status": "reject",
                                    "changed_word_count": 0
                                }
                                reporter.add_record(record)
                                review_tracker.add_edit(document_id, para_id, edit['orig_text'], edit['corr_text'], "Rejected", "destructive_merge")
                                continue
                                
                        # It's safe to apply to the single intersecting paragraph
                        start_bound, end_bound, target_d = intersecting_paras[0]
                        local_edit = edit.copy()
                        local_edit['orig_start'] = max(0, orig_start - start_bound)
                        local_edit['orig_end'] = min(end_bound - start_bound, orig_end - start_bound)
                        
                        target_para = target_d[2]
                        target_mapper = target_d[3]
                        
                        # Apply edit
                        is_safe, reason, edit_ratio, length_delta = diff_engine.is_safe_edit_detailed(local_edit['orig_text'], local_edit['corr_text'])
                        
                        logger.debug(f"Edit Check: '{local_edit['orig_text']}' -> '{local_edit['corr_text']}' | Safe: {is_safe} | Reason: {reason} | Edit Ratio: {edit_ratio:.2f} | Length Delta: {length_delta:.2f}")
                        
                        if is_safe:
                            revision_writer.apply_edits(target_para, target_mapper, [local_edit])
                            
                            if local_edit.get('applied'):
                                categories = diff_engine.categorize_edits([local_edit])
                                stats.add_change('apply', len(local_edit['orig_text'].split()), categories)
                                review_tracker.add_edit(document_id, para_id, local_edit['orig_text'], local_edit['corr_text'], "Applied", "safe_edit", edit_ratio, length_delta)
                            else:
                                skip_reason = local_edit.get('skip_reason', 'unknown')
                                review_tracker.add_edit(document_id, para_id, local_edit['orig_text'], local_edit['corr_text'], "Skipped", f"writer_{skip_reason}", edit_ratio, length_delta)
                                logger.warning(f"Edit skipped during XML write: {skip_reason} ('{local_edit['orig_text']}')")
                                continue
                            
                            md_str = ""
                            if local_edit['type'] == 'replace':
                                md_str = f"~~{local_edit['orig_text']}~~ **{local_edit['corr_text']}**"
                            elif local_edit['type'] == 'insert':
                                md_str = f"**{local_edit['corr_text']}**"
                            elif local_edit['type'] == 'delete':
                                md_str = f"~~{local_edit['orig_text']}~~"
                                
                            yield f"🔄 Đã sửa: {md_str}"
                        else:
                            # Rejected unsafe edit
                            stats.add_change('reject_unsafe', len(local_edit['orig_text'].split()), ['unsafe_edit'])
                            review_tracker.add_edit(document_id, para_id, local_edit['orig_text'], local_edit['corr_text'], "Rejected", reason, edit_ratio, length_delta)
                            yield f"❌ Bỏ qua sửa đổi nguy hiểm ({reason}): ~~{local_edit['orig_text']}~~ -> **{local_edit['corr_text']}**"
                            
            buffer_data = []
            
            # Save cache periodically to allow resuming
            if idx > 0 and idx % 20 == 0:
                runner.save_cache()
                
    # Save cache at the end
    runner.save_cache()
            
    # Save the output
    reader.save(output_path)
    
    # Save reports and review data
    reporter.generate_reports(stats.get_summary())
    review_tracker.save()
    logger.info(f"Finished processing. Saved output to {output_path}")
