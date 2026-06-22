import os
import re
import math
from pathlib import Path
from rapidfuzz import process, fuzz
import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM

from core.entity_protector import EntityProtector
from core.diff_engine import DiffEngine

class HybridRunner:
    def __init__(self, config=None, dict_path=None):
        if config is None:
            config = {}
        self.confidence_threshold = config.get('confidence_threshold', 0.85)
        self.user_lexicon = config.get('user_lexicon', [])
        
        # 1. Tải Dictionary
        base_dir = Path(__file__).parent.parent
        if dict_path is None:
            dict_path = base_dir / "resources/vietnamese_dict.txt"
        
        self.vocab = set()
        if os.path.exists(dict_path):
            with open(dict_path, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip().lower()
                    if word:
                        # Split multi-syllable words into single syllables for a basic syllable vocab
                        # because spell checking is usually at the syllable level
                        for syl in word.split('_'):
                            for s in syl.split():
                                self.vocab.add(s)
                                
        # Add basic punctuation and numbers to vocab so they aren't flagged
        for p in ".,!?;:()[]{}\"'<>_-%/\\":
            self.vocab.add(p)
            
        # 2. Tải mô hình PhoBERT MLM
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
        self.model = AutoModelForMaskedLM.from_pretrained("vinai/phobert-base").to(self.device)
        self.model.eval()
        
        self.protector = EntityProtector()
        
    def _is_suspicious(self, token: str) -> bool:
        """
        Bước 1: Suspicion Scoring
        """
        t_lower = token.lower()
        if t_lower in self.vocab:
            return False
            
        # Bỏ qua các định dạng đặc biệt
        if re.match(r'^[0-9]+([.,][0-9]+)*$', token): return False # Số
        if re.match(r'^https?://', token): return False # URL
        if re.match(r'^\S+@\S+\.\S+$', token): return False # Email
        if token.isupper() and len(token) > 1: return False # ALL-CAPS
        
        # Bỏ qua Entity và User Lexicon
        for k, v in self.protector.WHITELIST.items():
            if t_lower == v.lower():
                return False
                
        for w in self.user_lexicon:
            if t_lower == w.lower():
                return False
                
        return True
        
    def _generate_candidates(self, token: str, top_k=5):
        """
        Bước 2: Candidate Generator bằng RapidFuzz
        """
        token_lower = token.lower()
        # Tìm các từ gần giống nhất trong từ điển
        matches = process.extract(token_lower, list(self.vocab), limit=top_k, scorer=fuzz.ratio)
        # matches: list of tuples (match_string, score, index)
        # Chỉ lấy những từ có score > 70 (gần giống)
        candidates = [m[0] for m in matches if m[1] > 70]
        return candidates
        
    def _score_candidates_with_phobert(self, context_tokens, token_index, candidates):
        """
        Bước 3: Context Reranker
        """
        if not candidates:
            return []
            
        # Create masked sentence
        masked_tokens = list(context_tokens)
        masked_tokens[token_index] = self.tokenizer.mask_token
        # PhoBERT expects words joined by underscores, but for basic MLM we can just join with spaces
        masked_sentence = " ".join(masked_tokens)
        
        inputs = self.tokenizer(masked_sentence, return_tensors="pt").to(self.device)
        
        # Find mask index
        mask_token_index = (inputs.input_ids == self.tokenizer.mask_token_id)[0].nonzero(as_tuple=True)[0]
        if len(mask_token_index) == 0:
            return [] # No mask token found, probably tokenized strangely
        mask_token_index = mask_token_index[0].item()
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = outputs.logits[0, mask_token_index].softmax(dim=0)
            
        scored_candidates = []
        for cand in candidates:
            # Tokenize candidate to get its ID in PhoBERT vocab
            # phoBERT tokenizer often handles syllables directly
            cand_id = self.tokenizer.convert_tokens_to_ids(cand)
            if cand_id == self.tokenizer.unk_token_id:
                score = 0.0
            else:
                score = predictions[cand_id].item()
            scored_candidates.append((cand, score))
            
        # Sắp xếp theo score giảm dần
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates

    def correct_batch(self, texts):
        """
        Hàm chính được gọi từ DocumentProcessor.
        Xử lý từng text một cách an toàn.
        """
        corrected_texts = []
        
        for text in texts:
            # Tokenize đơn giản bằng dấu cách
            # (Thực tế nên dùng Regex để tách dấu câu cho chính xác hơn, 
            # nhưng để đảm bảo Format Preservation, ta sẽ xử lý cẩn thận)
            
            # Tạm thời dùng split() để giữ logic đơn giản,
            # hoặc dùng regex để bắt các từ:
            tokens = re.findall(r"[\w']+|[.,!?;:]", text)
            
            corrected_tokens = list(tokens)
            
            for i, token in enumerate(tokens):
                # Bỏ qua dấu câu
                if not token.isalnum():
                    continue
                    
                if self._is_suspicious(token):
                    candidates = self._generate_candidates(token)
                    if candidates:
                        scored = self._score_candidates_with_phobert(tokens, i, candidates)
                        if scored:
                            best_cand, best_score = scored[0]
                            # Bước 4: Safe Applier
                            if best_score >= self.confidence_threshold:
                                # Preserve case
                                if token.istitle():
                                    best_cand = best_cand.capitalize()
                                elif token.isupper():
                                    best_cand = best_cand.upper()
                                    
                                import logging
                                logger = logging.getLogger('VietDocProof')
                                logger.debug(f"[HybridCorrector] Replaced '{token}' -> '{best_cand}' (Score: {best_score:.3f})")
                                    
                                corrected_tokens[i] = best_cand
                                
            # Reconstruct text (rất cơ bản, có thể làm thay đổi khoảng trắng)
            # Tuy nhiên diff_engine.is_safe_edit sẽ chặn mọi thứ nếu vỡ khoảng trắng nghiêm trọng
            reconstructed = ""
            for tok in corrected_tokens:
                if re.match(r'[.,!?;:]', tok):
                    reconstructed += tok
                else:
                    if reconstructed and not reconstructed.endswith(' '):
                        reconstructed += " "
                    reconstructed += tok
                    
            corrected_texts.append(reconstructed.strip())
            
        return corrected_texts

    def load_cache(self):
        pass

    def save_cache(self):
        pass
