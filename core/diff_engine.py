import difflib
import string

class DiffEngine:
    def __init__(self):
        pass

    def diff(self, original, corrected):
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

    def categorize_edits(self, edits):
        """
        Categorizes the overall diff to determine what kind of fixes were made.
        Returns a list of edit categories.
        """
        categories = set()
        
        for edit in edits:
            if edit['type'] == 'equal':
                continue
                
            orig = edit['orig_text']
            corr = edit['corr_text']
            
            # Check for whitespace fix
            if orig.strip() == corr.strip() and orig != corr:
                categories.add('whitespace_fix')
                continue
                
            # Check for punctuation fix
            if self._is_punctuation_only(orig) and self._is_punctuation_only(corr):
                categories.add('punctuation_fix')
                continue
            elif self._is_punctuation_only(orig) and not corr:
                categories.add('punctuation_fix')
                continue
            elif not orig and self._is_punctuation_only(corr):
                categories.add('punctuation_fix')
                continue
                
            # If length differs a lot, or many words changed, might be rewrite_large
            if len(orig.split()) > 3 or len(corr.split()) > 3:
                categories.add('rewrite_large')
            else:
                categories.add('spelling_or_diacritics_fix')
                
        return list(categories)

    def _is_punctuation_only(self, text):
        return all(c in string.punctuation or c.isspace() for c in text)
