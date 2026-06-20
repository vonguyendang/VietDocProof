from docx.shared import RGBColor
from core.run_preserver import RunPreserver

class RevisionWriter:
    def __init__(self, mode="safe", track_changes=False, highlight_fallback=True):
        self.mode = mode
        self.track_changes = track_changes
        self.highlight_fallback = highlight_fallback

    def apply_edits(self, paragraph, run_mapper, edits):
        """
        Applies changes to the paragraph while attempting to preserve formatting.
        In Phase 1, we use red text highlighting as a fallback for track changes.
        """
        original_runs_data = []
        for r in paragraph.runs:
            original_runs_data.append({
                'run': r,
                'text': r.text
            })
            
        new_run_specs = [] 
        
        for edit in edits:
            op = edit['type']
            orig_start = edit['orig_start']
            orig_end = edit['orig_end']
            
            offsets = run_mapper.get_run_offsets_for_range(orig_start, orig_end)
            
            if op == 'equal':
                for run_idx, (start_off, end_off) in offsets.items():
                    sub_text = original_runs_data[run_idx]['text'][start_off:end_off]
                    new_run_specs.append({'text': sub_text, 'source_run_idx': run_idx, 'is_change': False})
            elif op == 'replace' or op == 'insert':
                if offsets:
                    source_run_idx = sorted(offsets.keys())[0]
                else:
                    if orig_start == 0 and original_runs_data:
                        source_run_idx = 0
                    elif original_runs_data:
                        source_run_idx = len(original_runs_data) - 1
                    else:
                        source_run_idx = -1
                
                new_run_specs.append({'text': edit['corr_text'], 'source_run_idx': source_run_idx, 'is_change': True})
            elif op == 'delete':
                pass
                
        # Store original run references
        original_runs_cache = [r for r in paragraph.runs]
            
        # Clear paragraph
        paragraph.clear()
        
        # Append new runs
        for spec in new_run_specs:
            if not spec['text']: continue
            
            run = paragraph.add_run(spec['text'])
            if spec['source_run_idx'] != -1 and spec['source_run_idx'] < len(original_runs_cache):
                source_r = original_runs_cache[spec['source_run_idx']]
                RunPreserver.clone_run_format(source_r, run)
                
            if spec['is_change'] and self.highlight_fallback:
                run.font.color.rgb = RGBColor(255, 0, 0)
