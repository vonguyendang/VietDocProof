import re

class ParagraphMerger:
    """
    Xác định điểm số gộp đoạn (merge score) theo heuristic.
    """
    
    @staticmethod
    def calculate_merge_score(prev_text: str, next_text: str, prev_style: str, next_style: str) -> int:
        score = 0
        prev_text = prev_text.strip()
        next_text = next_text.strip()
        
        if not prev_text or not next_text:
            return -10 # Không gộp với đoạn rỗng
            
        # 1. Paragraph trước không kết thúc bằng dấu câu ngắt câu
        if not re.search(r'[.?!]\s*$', prev_text):
            score += 2
            
        # 2. Paragraph sau bắt đầu bằng chữ thường
        if next_text and next_text[0].islower():
            score += 2
            
        # 3. Paragraph sau có style đặc biệt
        special_styles = ['Heading', 'List', 'Caption', 'Title', 'Subtitle']
        if next_style and any(s in next_style for s in special_styles):
            score -= 5
            
        # 4. Khác style gốc
        if prev_style != next_style:
            score -= 2
            
        return score
        
    @staticmethod
    def should_merge(prev_text: str, next_text: str, prev_style: str, next_style: str, threshold: int = 2) -> bool:
        score = ParagraphMerger.calculate_merge_score(prev_text, next_text, prev_style, next_style)
        return score >= threshold
