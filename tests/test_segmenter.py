from core.text_segmenter import TextSegmenter

def test_basic_segmentation():
    segmenter = TextSegmenter(max_length=50)
    text = "Xin chào các bạn. Hôm nay trời rất đẹp! Bạn thấy sao?"
    chunks = segmenter.segment(text)
    
    # Check that it splits correctly
    assert len(chunks) == 3
    assert chunks[0][0] == "Xin chào các bạn."
    assert chunks[1][0] == " Hôm nay trời rất đẹp!"
    assert chunks[2][0] == " Bạn thấy sao?"

def test_long_sentence_force_split():
    segmenter = TextSegmenter(max_length=5)
    text = "Đây là một câu rất dài và không có dấu chấm phẩy gì cả để xem nó cắt ra sao."
    chunks = segmenter.segment(text)
    
    # It should force split by words
    assert len(chunks) > 1
    
def test_no_split_needed():
    segmenter = TextSegmenter(max_length=256)
    text = "Chỉ một câu ngắn."
    chunks = segmenter.segment(text)
    assert len(chunks) == 1
    assert chunks[0][0] == "Chỉ một câu ngắn."
