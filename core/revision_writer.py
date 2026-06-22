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
                
            # To apply a replacement across potentially multiple runs without breaking formatting:
            # We put the entirely new corrected text into the FIRST intersecting run,
            # and delete the corresponding text segments from all other intersecting runs.
            
            sorted_run_indices = sorted(offsets.keys())
            first_run_idx = sorted_run_indices[0]
            
            for i, r_idx in enumerate(sorted_run_indices):
                run = runs[r_idx]
                start_off, end_off = offsets[r_idx]
                
                # Extract parts of the run text that are OUTSIDE the replaced range
                text_before = run.text[:start_off]
                text_after = run.text[end_off:]
                
                if i == 0:
                    # The first run takes the new text
                    run.text = text_before + corr_text + text_after
                    if self.highlight_fallback and corr_text.strip():
                        run.font.color.rgb = RGBColor(255, 0, 0)
                else:
                    # Subsequent runs just get their replaced portion removed
                    run.text = text_before + text_after
