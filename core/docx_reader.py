import docx
from core.run_mapper import RunMapper

class DocxReader:
    def __init__(self, doc_path):
        self.doc_path = doc_path
        self.doc = docx.Document(doc_path)
        
    def extract_paragraphs(self):
        """
        Yields (paragraph_index, paragraph_obj, run_mapper)
        Includes paragraphs from body and tables.
        """
        index = 0
        
        # Extract from main document body
        for para in self.doc.paragraphs:
            if not para.text.strip():
                index += 1
                continue
            yield index, "body", para, RunMapper(para)
            index += 1
            
        # Extract from tables
        for table in self.doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if not para.text.strip():
                            index += 1
                            continue
                        yield index, "table", para, RunMapper(para)
                        index += 1

    def save(self, output_path):
        self.doc.save(output_path)
