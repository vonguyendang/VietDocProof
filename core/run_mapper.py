class RunMapper:
    def __init__(self, paragraph):
        self.paragraph = paragraph
        self.runs = paragraph.runs
        self.mapping = [] # List of tuples: (run_index, offset_in_run)
        self.text = ""
        self._build_mapping()

    def _build_mapping(self):
        self.text = ""
        self.mapping = []
        for i, run in enumerate(self.runs):
            run_text = run.text
            for j in range(len(run_text)):
                self.mapping.append((i, j))
            self.text += run_text

    def get_run_indices_for_range(self, start_idx, end_idx):
        """
        Returns a list of unique run indices that cover the text from start_idx to end_idx.
        """
        if start_idx >= len(self.mapping) or start_idx >= end_idx:
            return []
            
        # end_idx is exclusive
        end_idx = min(end_idx, len(self.mapping))
        
        run_indices = set()
        for i in range(start_idx, end_idx):
            run_indices.add(self.mapping[i][0])
            
        return sorted(list(run_indices))
        
    def get_run_offsets_for_range(self, start_idx, end_idx):
        """
        Returns a dict mapping run_index -> (start_offset_in_run, end_offset_in_run_exclusive).
        """
        if start_idx >= len(self.mapping) or start_idx >= end_idx:
            return {}
            
        end_idx = min(end_idx, len(self.mapping))
        offsets = {}
        
        for i in range(start_idx, end_idx):
            run_idx, offset_in_run = self.mapping[i]
            if run_idx not in offsets:
                offsets[run_idx] = [offset_in_run, offset_in_run + 1]
            else:
                offsets[run_idx][1] = offset_in_run + 1
                
        return offsets
