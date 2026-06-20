import re

class TextSegmenter:
    def __init__(self, max_length=256):
        # We use a slightly smaller chunk length to account for tokenization expansion
        self.max_length = max_length

    def segment(self, text):
        """
        Segments a large paragraph text into smaller chunks (sentences) 
        that fit within the model's max token length.
        
        Returns a list of tuples: (chunk_text, start_char_idx, end_char_idx)
        """
        if not text.strip():
            return []

        # Simple sentence boundary regex for Vietnamese
        # Matches punctuation followed by space and a capital letter, or just punctuation.
        boundaries = re.finditer(r'([.?!;]+)(?=\s|$)', text)
        
        chunks = []
        current_start = 0
        
        for match in boundaries:
            end_idx = match.end()
            chunk_text = text[current_start:end_idx]
            
            # If the chunk is still too large, we might need to split by commas or words
            if len(chunk_text.split()) > self.max_length:
                # Force split by spaces if it's exceptionally long
                sub_chunks = self._force_split(chunk_text, current_start)
                chunks.extend(sub_chunks)
            else:
                chunks.append((chunk_text, current_start, end_idx))
            
            current_start = end_idx
            
        # Add remaining text
        if current_start < len(text):
            chunk_text = text[current_start:]
            if chunk_text.strip():
                if len(chunk_text.split()) > self.max_length:
                    chunks.extend(self._force_split(chunk_text, current_start))
                else:
                    chunks.append((chunk_text, current_start, len(text)))
                
        return chunks

    def _force_split(self, text, start_offset):
        """Force splits extremely long sentences by comma or space."""
        # Try splitting by comma first
        comma_boundaries = list(re.finditer(r'(,)(?=\s|$)', text))
        chunks = []
        
        if comma_boundaries:
            curr = 0
            for match in comma_boundaries:
                end = match.end()
                chunk_str = text[curr:end]
                if len(chunk_str.split()) > self.max_length:
                    # Still too long, split by spaces
                    chunks.extend(self._split_by_words(chunk_str, start_offset + curr))
                else:
                    chunks.append((chunk_str, start_offset + curr, start_offset + end))
                curr = end
            if curr < len(text):
                rem = text[curr:]
                if rem.strip():
                    if len(rem.split()) > self.max_length:
                        chunks.extend(self._split_by_words(rem, start_offset + curr))
                    else:
                        chunks.append((rem, start_offset + curr, start_offset + len(text)))
        else:
            chunks.extend(self._split_by_words(text, start_offset))
            
        return chunks

    def _split_by_words(self, text, start_offset):
        """Splits by words when punctuation fails."""
        words = text.split(' ')
        chunks = []
        current_chunk = []
        current_len = 0
        curr_start = 0
        
        for i, word in enumerate(words):
            current_chunk.append(word)
            current_len += 1
            if current_len >= self.max_length:
                chunk_str = ' '.join(current_chunk)
                # Need to find actual exact string to preserve spaces
                # We can do this by regex or index
                # This is a bit complex, let's keep it simple and just use index
                pass
                
        # A simpler word splitter that preserves indices:
        chunks = []
        curr_start = 0
        word_iter = re.finditer(r'\S+(\s+|$)', text)
        count = 0
        for match in word_iter:
            count += 1
            if count >= self.max_length:
                end = match.end()
                chunk_str = text[curr_start:end]
                chunks.append((chunk_str, start_offset + curr_start, start_offset + end))
                curr_start = end
                count = 0
                
        if curr_start < len(text):
            chunk_str = text[curr_start:]
            chunks.append((chunk_str, start_offset + curr_start, start_offset + len(text)))
            
        return chunks
