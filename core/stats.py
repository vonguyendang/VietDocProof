class StatsTracker:
    def __init__(self):
        self.total_paragraphs = 0
        self.total_sentences = 0
        self.total_words = 0
        self.total_changed_sentences = 0
        self.total_changed_words = 0
        self.total_changes_applied = 0
        self.total_changes_skipped = 0
        self.breakdown_by_error_type = {}
        
    def add_paragraph(self):
        self.total_paragraphs += 1
        
    def add_sentence(self, word_count):
        self.total_sentences += 1
        self.total_words += word_count
        
    def add_change(self, status, words_changed, error_categories):
        if status == 'apply':
            self.total_changes_applied += 1
            self.total_changed_words += words_changed
            self.total_changed_sentences += 1
            for cat in error_categories:
                self.breakdown_by_error_type[cat] = self.breakdown_by_error_type.get(cat, 0) + 1
        elif status == 'skip':
            self.total_changes_skipped += 1
            
    def get_summary(self):
        return {
            "total_paragraphs": self.total_paragraphs,
            "total_sentences": self.total_sentences,
            "total_words": self.total_words,
            "total_changed_sentences": self.total_changed_sentences,
            "total_changed_words": self.total_changed_words,
            "total_changes_applied": self.total_changes_applied,
            "total_changes_skipped": self.total_changes_skipped,
            "changed_word_ratio_percent": round((self.total_changed_words / max(1, self.total_words)) * 100, 2),
            "changed_sentence_ratio_percent": round((self.total_changed_sentences / max(1, self.total_sentences)) * 100, 2),
            "breakdown_by_error_type": self.breakdown_by_error_type
        }
