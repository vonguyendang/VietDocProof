class ConfidenceScorer:
    def __init__(self, config=None):
        if config is None:
            self.safe_threshold = 0.90
            self.review_threshold = 0.70
            self.aggressive_threshold = 0.50
        else:
            self.safe_threshold = config.get('safe_threshold', 0.90)
            self.review_threshold = config.get('review_threshold', 0.70)
            self.aggressive_threshold = config.get('aggressive_threshold', 0.50)

    def score(self, original, corrected, edits, categories):
        """
        Scores the confidence of the correction from 0.0 to 1.0.
        """
        if original == corrected:
            return 1.0
            
        if 'rewrite_large' in categories:
            return 0.4  # Low confidence for large rewrites
            
        score = 1.0
        
        # Penalize based on number of changes
        num_changes = sum(1 for e in edits if e['type'] != 'equal')
        score -= (num_changes * 0.05)
        
        # Penalize if string length changed drastically
        len_diff = abs(len(original) - len(corrected))
        if len_diff > 5:
            score -= min(0.3, len_diff * 0.02)
            
        # Heavily penalize if the model DELETED words (hallucinated missing words)
        if len(corrected.split()) < len(original.split()):
            score -= 0.5
            
        # Penalize heavily for hallucinating or dropping quotes/brackets
        paired_chars = ['"', "'", '(', ')', '[', ']', '{', '}', '“', '”', '‘', '’']
        for char in paired_chars:
            if original.count(char) != corrected.count(char):
                score -= 0.5
                break
                
        return max(0.0, score)

    def get_action_status(self, score, mode="safe"):
        """
        Returns 'apply', 'review', or 'skip' based on score and mode.
        """
        if mode == "safe":
            if score >= self.safe_threshold:
                return "apply"
            else:
                return "skip"
        elif mode == "review":
            if score >= self.review_threshold:
                return "apply"
            elif score >= self.aggressive_threshold:
                return "review"
            else:
                return "skip"
        elif mode == "aggressive":
            if score >= self.aggressive_threshold:
                return "apply"
            else:
                return "review"
        
        return "skip"
