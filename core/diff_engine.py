import difflib
import string
import re

class DiffEngine:
    def __init__(self, config=None):
        if config is None:
            self.edit_ratio_thresh = 0.20
            self.length_delta_ratio_thresh = 0.30
            self.user_lexicon = []
        else:
            self.edit_ratio_thresh = config.get('edit_ratio', 0.20)
            self.length_delta_ratio_thresh = config.get('length_delta_ratio', 0.30)
            self.user_lexicon = config.get('user_lexicon', [])
            
        # Default whitelist (can be expanded)
        self.whitelist = []

    def diff(self, original: str, corrected: str):
        """
        Compare original and corrected string and return a list of edits.
        Returns a list of dicts.
        """
        matcher = difflib.SequenceMatcher(None, original, corrected)
        opcodes = matcher.get_opcodes()
        
        edits = []
        for tag, i1, i2, j1, j2 in opcodes:
            edits.append({
                'type': tag,
                'orig_start': i1,
                'orig_end': i2,
                'corr_start': j1,
                'corr_end': j2,
                'orig_text': original[i1:i2],
                'corr_text': corrected[j1:j2]
            })
            
        return edits

    def is_safe_edit_detailed(self, original: str, corrected: str) -> tuple:
        """
        Check if the edit is safe and returns detailed reasons and metrics.
        Returns (is_safe, reason, edit_ratio, length_delta)
        """
        if original == corrected:
            return True, "equal", 0.0, 0.0
            
        # 1. Entity and Lexicon protection
        for w in self.whitelist + self.user_lexicon:
            if w.lower() in original.lower() and w.lower() not in corrected.lower():
                return False, "whitelist_violation", 0.0, 0.0
                
        # 2. Length Delta Check
        orig_len = len(original)
        corr_len = len(corrected)
        
        if orig_len == 0 and corr_len > 0:
            return False, "insertion_burst", 0.0, 1.0
            
        length_delta = abs(corr_len - orig_len) / max(1, orig_len)
        if length_delta > self.length_delta_ratio_thresh:
            return False, "length_delta_exceeded", 0.0, length_delta
            
        # 3. Word-level Levenshtein check
        orig_words = original.split()
        corr_words = corrected.split()
        
        if len(orig_words) == 0:
            return False, "insertion_burst", 0.0, 1.0
            
        import Levenshtein
        distance = Levenshtein.distance(orig_words, corr_words)
        edit_ratio = distance / max(1, len(orig_words))
        
        if edit_ratio > self.edit_ratio_thresh and len(orig_words) > 3:
            return False, "edit_ratio_exceeded", edit_ratio, length_delta
        
        # 4. Regex kiểm tra lỗi lặp đặc trưng của seq2seq (vd: "se ẽ", "kho ó")
        for i in range(len(corr_words) - 1):
            w1 = corr_words[i].lower()
            w2 = corr_words[i+1].lower()
            if len(w1) >= 2 and len(w2) >= 1:
                # Nếu w1 là "se" và w2 là "ẽ", w1 chứa các ký tự tương tự w2
                if w1[-1] in w2 or w2 in w1:
                    if len(w2) <= 2 and (w2.startswith(w1[-1]) or w2.endswith(w1[-1])):
                        return False, "repetition_hallucination", edit_ratio, length_delta
                        
        return True, "safe", edit_ratio, length_delta

    def is_safe_edit(self, original: str, corrected: str) -> bool:
        """Backward compatibility"""
        is_safe, _, _, _ = self.is_safe_edit_detailed(original, corrected)
        return is_safe

    def categorize_edits(self, edits):
        categories = set()
        for edit in edits:
            if edit['type'] == 'equal':
                continue
                
            orig = edit['orig_text']
            corr = edit['corr_text']
            
            if orig.strip() == corr.strip() and orig != corr:
                categories.add('spacing_fix')
                continue
                
            if self._is_punctuation_only(orig) and self._is_punctuation_only(corr):
                categories.add('punctuation_fix')
                continue
            elif self._is_punctuation_only(orig) and not corr:
                categories.add('punctuation_fix')
                continue
            elif not orig and self._is_punctuation_only(corr):
                categories.add('punctuation_fix')
                continue
                
            if orig.lower() == corr.lower() and orig != corr:
                categories.add('capitalization_fix')
                continue
                
            if len(orig.split()) > 3 or len(corr.split()) > 3:
                categories.add('rewrite_large')
            else:
                # Kiểm tra xem có lỗi diacritics không
                categories.add('spelling_or_diacritics_fix')
                
        return list(categories)

    def _is_punctuation_only(self, text):
        return all(c in string.punctuation or c.isspace() for c in text)
