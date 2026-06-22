import re

class EntityProtector:
    """
    Tầng 3: Phát hiện và bảo vệ các danh từ riêng, từ tiếng Anh, email, URL, ...
    """
    
    WHITELIST = {
        "google": "Google",
        "microsoft": "Microsoft",
        "apple": "Apple",
        "facebook": "Facebook",
        "openai": "OpenAI",
        "vietinbank": "VietinBank",
        "lpbank": "LPBank",
        "infinityfree": "InfinityFree",
        "android": "Android",
        "paypal": "PayPal"
    }

    def __init__(self):
        # Biểu thức chính quy cho URL, Email, và File path đơn giản
        self.url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*')
        self.email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
        self.path_pattern = re.compile(r'(?:/[a-zA-Z0-9_.-]+)+/?|[a-zA-Z]:\\(?:[a-zA-Z0-9_.-]+\\?)*')
        
        # Biểu thức cho All-Caps tokens (từ viết tắt, ít nhất 2 chữ cái)
        self.all_caps_pattern = re.compile(r'\b[A-Z]{2,}\b')
        
        # Tiền tố tên tiếng Anh: Mr., Ms., Mrs., Dr., Prof. (tiếp theo là 1 từ viết hoa)
        self.mr_ms_pattern = re.compile(r'\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+[A-Z][a-zA-Z]*\b')

    def protect(self, text: str):
        """
        Quét và mask các entities.
        Trả về text đã mask và dictionary để unmask.
        """
        masked_text = text
        entity_map = {}
        counter = 0

        def add_entity(match_str):
            nonlocal counter, masked_text
            placeholder = f"[[ENT_{counter}]]"
            entity_map[placeholder] = match_str
            counter += 1
            return placeholder

        # 1. Bảo vệ URL
        masked_text = self.url_pattern.sub(lambda m: add_entity(m.group(0)), masked_text)
        
        # 2. Bảo vệ Email
        masked_text = self.email_pattern.sub(lambda m: add_entity(m.group(0)), masked_text)
        
        # 3. Bảo vệ File paths
        masked_text = self.path_pattern.sub(lambda m: add_entity(m.group(0)), masked_text)
        
        # 4. Bảo vệ tên riêng theo sau Mr., Ms., etc.
        masked_text = self.mr_ms_pattern.sub(lambda m: add_entity(m.group(0)), masked_text)
        
        # 5. Phân tích các từ đơn lẻ để bảo vệ whitelist và all-caps
        def process_word(match):
            word = match.group(0)
            
            # Nếu là từ viết hoa toàn bộ (VD: HTML, CSS)
            if self.all_caps_pattern.fullmatch(word):
                return add_entity(word)
                
            # Canonicalization & Whitelist check
            lower_word = word.lower()
            if lower_word in self.WHITELIST:
                canonical_word = self.WHITELIST[lower_word]
                # Nếu từ hiện tại chỉ sai khác in hoa/in thường so với whitelist (không tính trường hợp đã chuẩn)
                # Ta cứ mask bằng canonical_word để sau này nhả ra từ chuẩn
                return add_entity(canonical_word)
                
            return word

        # Tách từ dựa trên ranh giới từ tiếng Anh, cẩn thận không cắt nhầm dấu câu
        masked_text = re.sub(r'\b[a-zA-Z0-9]+\b', process_word, masked_text)

        return masked_text, entity_map

    def unprotect(self, text: str, entity_map: dict) -> str:
        """
        Khôi phục lại các entities từ placeholders.
        """
        for placeholder, original in entity_map.items():
            # Mẫu regex để bắt placeholder kể cả khi bị model thêm khoảng trắng: [ [ ENT _ 0 ] ]
            # placeholder có dạng [[ENT_0]]
            m = re.match(r'\[\[ENT_(\d+)\]\]', placeholder)
            if m:
                ent_id = m.group(1)
                pattern = r'\[\s*\[\s*ENT\s*_\s*' + ent_id + r'\s*\]\s*\]'
                text = re.sub(pattern, original, text, flags=re.IGNORECASE)
            else:
                text = text.replace(placeholder, original)
        return text
