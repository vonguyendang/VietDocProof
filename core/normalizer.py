import re

class TextNormalizer:
    """
    Tầng 1 & 2: Chuẩn hóa khoảng trắng và dấu câu cơ bản.
    """
    
    @staticmethod
    def normalize_spaces(text: str) -> str:
        """
        Gộp các khoảng trắng thừa thành 1 khoảng trắng duy nhất.
        """
        # Giữ nguyên newline, chỉ gộp dấu cách và tab
        return re.sub(r'[ \t]+', ' ', text).strip()
        
    @staticmethod
    def normalize_punctuation_spacing(text: str) -> str:
        """
        Xóa khoảng trắng trước các dấu câu và đảm bảo có khoảng trắng sau dấu câu.
        Ví dụ: "chữ ," -> "chữ,"
               "chữ.Chữ" -> "chữ. Chữ"
        """
        # Xóa khoảng trắng trước dấu câu .,:;!?
        text = re.sub(r'\s+([.,:;!?])', r'\1', text)
        
        # Thêm khoảng trắng sau dấu câu nếu liền kề chữ cái (tránh trường hợp số thập phân như 3.14)
        # hoặc các URL
        # Để an toàn, chỉ fix cho chữ thường/chữ hoa tiếng Việt liền kề sau dấu câu
        vietnamese_chars = 'a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ'
        
        text = re.sub(r'([.,:;!?])([' + vietnamese_chars + r'])', r'\1 \2', text)
        
        return text

    @staticmethod
    def normalize_all(text: str) -> str:
        text = TextNormalizer.normalize_spaces(text)
        text = TextNormalizer.normalize_punctuation_spacing(text)
        return text
