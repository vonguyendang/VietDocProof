from docx.shared import RGBColor

class RevisionWriter:
    def __init__(self, mode="safe", track_changes=False, highlight_fallback=True):
        self.mode = mode
        self.track_changes = track_changes
        self.highlight_fallback = highlight_fallback

    def apply_edits(self, paragraph, run_mapper, edits):
        """
        Applies changes safely at the Run level.
        NEVER clears the paragraph to preserve links, bookmarks, and exact formatting.
        """
        import copy
        import logging
        from docx.text.run import Run
        from docx.shared import RGBColor
        
        logger = logging.getLogger('VietDocProof')

        if not edits:
            return edits

        # Build a list of runs and their current texts
        runs = paragraph.runs
        if not runs:
            return edits
            
        # 1. Sort edits in reverse order so length changes don't affect earlier offsets
        edits = sorted(edits, key=lambda x: x['orig_start'], reverse=True)
        
        min_processed_start = float('inf')
            
        for edit in edits:
            # Metadata debug initialization
            edit['applied'] = False
            edit['skip_reason'] = None
            edit['run_index'] = None
            edit['is_single_run'] = None
            
            if edit['type'] == 'equal':
                edit['skip_reason'] = 'type_equal'
                continue
                
            orig_start = edit['orig_start']
            orig_end = edit['orig_end']
            corr_text = edit['corr_text']
            
            # 4. Overlap guard
            if orig_end > min_processed_start:
                edit['skip_reason'] = 'overlap'
                logger.warning(f"Overlap detected for edit '{edit['orig_text']}'. Skipping.")
                continue
            
            # Find which runs intersect this range
            offsets = run_mapper.get_run_offsets_for_range(orig_start, orig_end)
            if not offsets:
                edit['skip_reason'] = 'no_mapping_found'
                continue
                
            sorted_run_indices = sorted(offsets.keys())
            
            # 2. Single-run Guard
            if len(sorted_run_indices) > 1:
                edit['is_single_run'] = False
                edit['skip_reason'] = 'multi_run_edit_not_supported_yet'
                logger.warning(f"Skipping multi-run edit: '{edit['orig_text']}' spans {len(sorted_run_indices)} runs.")
                continue
                
            edit['is_single_run'] = True
            r_idx = sorted_run_indices[0]
            edit['run_index'] = r_idx
            
            run = runs[r_idx]
            start_off, end_off = offsets[r_idx]
            
            text_before = run.text[:start_off]
            text_after = run.text[end_off:]
            
            # 5. XML manipulation with Try/Except
            try:
                # Backup old text
                old_text = run.text
                
                run.text = text_before
                last_inserted_element = run._r
                
                if corr_text:
                    new_r_corr = copy.deepcopy(run._r)
                    last_inserted_element.addnext(new_r_corr)
                    new_run_corr = Run(new_r_corr, run._parent)
                    new_run_corr.text = corr_text
                    if self.highlight_fallback and corr_text.strip():
                        new_run_corr.font.color.rgb = RGBColor(255, 0, 0)
                    last_inserted_element = new_r_corr
                    
                if text_after:
                    new_r_after = copy.deepcopy(run._r)
                    last_inserted_element.addnext(new_r_after)
                    new_run_after = Run(new_r_after, run._parent)
                    new_run_after.text = text_after
                    
                # Update min_processed_start
                min_processed_start = orig_start
                edit['applied'] = True
                
            except Exception as e:
                run.text = old_text
                edit['skip_reason'] = 'xml_manipulation_failed'
                logger.error(f"XML manipulation failed for edit '{edit['orig_text']}': {e}")
                
        return edits
