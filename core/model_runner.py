import torch
from transformers import pipeline

class ModelRunner:
    def __init__(self, model_name="bmd1905/vietnamese-correction-v2", max_length=512, batch_size=4, cache_file="correction_cache.json"):
        import json
        from pathlib import Path
        
        self.model_name = model_name
        self.max_length = max_length
        self.batch_size = batch_size
        self.cache_file = Path(cache_file)
        self.cache = {}
        
        # Load cache if exists
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"Loaded {len(self.cache)} cached corrections.")
            except Exception as e:
                print(f"Could not load cache: {e}")
        
        # Determine device
        if torch.cuda.is_available():
            device = "cuda:0"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            print(f"Loading tokenizer and model: {model_name} on {device} (batch_size: {self.batch_size})")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)
            self.device = device
        except Exception as e:
            raise RuntimeError(f"Failed to load model {model_name}: {e}")

    def correct_batch(self, texts):
        """
        Takes a list of string chunks, runs correction on them, and returns a list of corrected texts.
        Uses a simple exact-match cache to avoid redundant inference.
        """
        import re
        results = [""] * len(texts)
        to_process_indices = []
        to_process_texts = []
        
        # Regex to detect if there is at least one Vietnamese/English letter
        has_letter = re.compile(r'[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]')
        
        bullets_map = {}
        
        import unicodedata
        
        for i, text in enumerate(texts):
            # Enforce NFC to prevent HuggingFace tokenizer from dropping decomposed unicode words!
            text = unicodedata.normalize('NFC', text)
            stripped_text = text.strip()
            
            # Extract bullet points like *, +, -, >, • to protect them
            bullet_match = re.match(r'^([*+\-•>]+)\s*', stripped_text)
            bullet_prefix = ""
            if bullet_match:
                bullet_prefix = bullet_match.group(0)
                stripped_text = stripped_text[bullet_match.end():]
                
            bullets_map[i] = bullet_prefix
            
            # If text is empty or just numbers/symbols, skip heavy processing
            if not stripped_text or not has_letter.search(stripped_text):
                results[i] = text
                continue
                
            if stripped_text in self.cache:
                # Restore bullet and cache
                import logging
                logging.getLogger('VietDocProof').debug(f"[ModelRunner] Cache HIT: '{stripped_text}' -> '{self.cache[stripped_text]}'")
                results[i] = self._restore_whitespace(texts[i], bullet_prefix + self.cache[stripped_text])
                continue
            else:
                to_process_indices.append(i)
                to_process_texts.append(stripped_text)
                
        if not to_process_texts:
            return results
            
        # Run inference in batches
        try:
            # Process in explicit batches since we bypassed pipeline
            import logging
            logger = logging.getLogger('VietDocProof')
            import time
            start_time = time.time()
            
            for i in range(0, len(to_process_texts), self.batch_size):
                batch = to_process_texts[i:i + self.batch_size]
                inputs = self.tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=self.max_length).to(self.device)
                outputs = self.model.generate(
                    **inputs, 
                    max_new_tokens=self.max_length, 
                    num_beams=2,
                    repetition_penalty=1.05
                )
                decoded = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
                predictions.extend(decoded)
                
            logger.debug(f"[ModelRunner] Inference completed for {len(to_process_texts)} chunks in {time.time() - start_time:.2f}s")
            
            for idx, pred_text in zip(to_process_indices, predictions):
                orig_text = to_process_texts[to_process_indices.index(idx)]
                
                # Fix hallucinated periods on headings/short phrases
                pred_text = self._align_trailing_punctuation(orig_text, pred_text)
                
                # Restore user's capitalization
                pred_text = self._restore_capitalization(orig_text, pred_text)
                
                # Cache the plain string
                self.cache[orig_text] = pred_text
                
                # Restore original leading/trailing whitespace and bullet prefix
                bullet = bullets_map[idx]
                results[idx] = self._restore_whitespace(texts[idx], bullet + pred_text)
                
        except Exception as e:
            print(f"Warning: Model inference failed for batch: {e}")
            # Fallback to original text on failure
            for idx in to_process_indices:
                results[idx] = texts[idx]
                
        return results

    def save_cache(self):
        """Saves the cache to disk to allow resuming later."""
        import json
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save cache: {e}")

    def _align_trailing_punctuation(self, original, corrected):
        """Ensures the AI doesn't arbitrarily add or remove trailing periods/semicolons."""
        orig_s = original.strip()
        corr_s = corrected.strip()
        if not orig_s or not corr_s:
            return corrected
            
        import re
        # Extract trailing punctuation from original text
        orig_punct = re.search(r'([.;:!?]+)$', orig_s)
        orig_tail = orig_punct.group(1) if orig_punct else ""
        
        # Strip all trailing punctuation from corrected text
        corr_s_stripped = re.sub(r'([.;:!?]+)$', '', corr_s)
        
        # Enforce the original punctuation
        return corr_s_stripped + orig_tail

    def _restore_capitalization(self, original, corrected):
        """Forces the first letter of each word in the corrected text to strictly match the case of the original text's first letters,
           and forces the entire word to be ALL CAPS if the original word was ALL CAPS."""
        if original.isupper():
            return corrected.upper()
        if original.islower():
            return corrected.lower()
            
        import difflib
        
        def get_word_info(text):
            firsts = set()
            bounds = []
            is_in_word = False
            start = 0
            for i, c in enumerate(text):
                if c.isalpha():
                    if not is_in_word:
                        firsts.add(i)
                        start = i
                        is_in_word = True
                else:
                    if is_in_word:
                        bounds.append((start, i))
                        is_in_word = False
            if is_in_word:
                bounds.append((start, len(text)))
            return firsts, bounds
            
        orig_firsts, orig_bounds = get_word_info(original)
        corr_firsts, corr_bounds = get_word_info(corrected)
        
        char_in_upper_word = [False] * len(original)
        for start, end in orig_bounds:
            word = original[start:end]
            if word.isupper() and (len(word) > 1 or original.isupper()):
                for i in range(start, end):
                    char_in_upper_word[i] = True
                    
        corr_to_orig = [-1] * len(corrected)
        matcher = difflib.SequenceMatcher(None, original.lower(), corrected.lower())
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ('equal', 'replace'):
                if i2 - i1 == j2 - j1:
                    for o, c in zip(range(i1, i2), range(j1, j2)):
                        corr_to_orig[c] = o
                else:
                    for c in range(j1, j2):
                        ratio = (c - j1) / max(1, (j2 - j1))
                        o = i1 + int(ratio * (i2 - i1))
                        if o >= i2: o = i2 - 1
                        corr_to_orig[c] = o
            elif tag == 'insert':
                o = i1 - 1 if i1 > 0 else 0
                for c in range(j1, j2):
                    corr_to_orig[c] = o
                    
        result = list(corrected)
        
        for start, end in corr_bounds:
            upper_count = 0
            alpha_count = 0
            first_orig_idx = -1
            
            for c in range(start, end):
                if result[c].isalpha():
                    alpha_count += 1
                    o = corr_to_orig[c]
                    if first_orig_idx == -1 and o != -1:
                        first_orig_idx = o
                    if o != -1 and char_in_upper_word[o]:
                        upper_count += 1
                        
            if alpha_count > 0 and upper_count >= alpha_count / 2.0:
                # Make the entire word ALL CAPS
                for c in range(start, end):
                    if result[c].isalpha():
                        result[c] = result[c].upper()
            else:
                # Fallback to first-letter capitalization logic
                orig_first = -1
                for c in range(start, end):
                    o = corr_to_orig[c]
                    if o != -1 and o in orig_firsts:
                        orig_first = o
                        break
                
                if orig_first == -1:
                    orig_first = first_orig_idx
                    
                if orig_first != -1:
                    c_first = -1
                    for c in range(start, end):
                        if result[c].isalpha():
                            c_first = c
                            break
                    
                    if c_first != -1:
                        if original[orig_first].isupper():
                            result[c_first] = result[c_first].upper()
                        elif original[orig_first].islower():
                            result[c_first] = result[c_first].lower()
                            
        return "".join(result)

    def _restore_whitespace(self, original, generated):
        """Restores leading and trailing whitespace from the original text."""
        leading = original[:len(original) - len(original.lstrip())]
        trailing = original[len(original.rstrip()):]
        return leading + generated.strip() + trailing
