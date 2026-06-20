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
            # We use text2text-generation for this model
            print(f"Initializing pipeline on device: {device} (batch_size: {self.batch_size})")
            self.pipeline = pipeline("text2text-generation", model=model_name, device=device)
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
                results[i] = self._restore_whitespace(texts[i], bullet_prefix + self.cache[stripped_text])
                continue
            else:
                to_process_indices.append(i)
                to_process_texts.append(stripped_text)
                
        if not to_process_texts:
            return results
            
        # Run inference in batches
        try:
            # HuggingFace pipeline handles batching internally if passed as a list
            # We also set max_new_tokens to prevent truncation issues
            # We enforce num_beams=1 (greedy decoding) which is 4-5x faster than default beam search
            predictions = self.pipeline(to_process_texts, max_new_tokens=self.max_length, batch_size=self.batch_size, num_beams=1)
            
            for idx, pred_dict in zip(to_process_indices, predictions):
                pred_text = pred_dict['generated_text']
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
        """Prevents the AI from lowercasing words that the user explicitly capitalized."""
        import difflib
        # Match ignoring case so we align correctly even if only case changed
        matcher = difflib.SequenceMatcher(None, original.lower(), corrected.lower())
        result = list(corrected)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for orig_idx, corr_idx in zip(range(i1, i2), range(j1, j2)):
                    if original[orig_idx].isupper():
                        result[corr_idx] = result[corr_idx].upper()
            elif tag == 'replace':
                if i1 < i2 and j1 < j2:
                    # If the first character of the replaced chunk was uppercase, make the new chunk uppercase
                    if original[i1].isupper():
                        result[j1] = result[j1].upper()
                        
        return "".join(result)

    def _restore_whitespace(self, original, generated):
        """Restores leading and trailing whitespace from the original text."""
        leading = original[:len(original) - len(original.lstrip())]
        trailing = original[len(original.rstrip()):]
        return leading + generated.strip() + trailing
