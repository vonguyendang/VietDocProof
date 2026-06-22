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
        if not edits:
            return

        # Build a list of runs and their current texts
        runs = paragraph.runs
        if not runs:
            return
            
        # 1. Sort edits in reverse order so length changes don't affect earlier offsets
        edits = sorted(edits, key=lambda x: x['orig_start'], reverse=True)
        
        import copy
        from docx.text.run import Run
            
        for edit in edits:
            if edit['type'] == 'equal':
                continue
                
            orig_start = edit['orig_start']
            orig_end = edit['orig_end']
            corr_text = edit['corr_text']
            
            # Find which runs intersect this range
            offsets = run_mapper.get_run_offsets_for_range(orig_start, orig_end)
            if not offsets:
                continue
                
            sorted_run_indices = sorted(offsets.keys())
            
            # Since we are modifying runs from right to left in a single edit that spans multiple runs,
            # we should also process the intersected runs in reverse order.
            sorted_run_indices.reverse()
            
            for i, r_idx in enumerate(sorted_run_indices):
                run = runs[r_idx]
                start_off, end_off = offsets[r_idx]
                
                text_before = run.text[:start_off]
                text_after = run.text[end_off:]
                
                # If this is the FIRST run in logical order, we insert corr_text here.
                # Since we reversed sorted_run_indices, the first logical run is the LAST in our loop.
                is_first_logical_run = (i == len(sorted_run_indices) - 1)
                
                # Update original run to text_before
                run.text = text_before
                
                last_inserted_element = run._r
                
                if is_first_logical_run and corr_text:
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
