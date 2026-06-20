from docx.shared import RGBColor

class RunPreserver:
    @staticmethod
    def clone_run_format(src_run, dest_run):
        """
        Copies formatting from src_run to dest_run.
        """
        dest_run.bold = src_run.bold
        dest_run.italic = src_run.italic
        dest_run.underline = src_run.underline
        
        if src_run.font.name:
            dest_run.font.name = src_run.font.name
        if src_run.font.size:
            dest_run.font.size = src_run.font.size
        if src_run.font.color and src_run.font.color.rgb:
            dest_run.font.color.rgb = src_run.font.color.rgb
        if src_run.font.highlight_color:
            dest_run.font.highlight_color = src_run.font.highlight_color
        
        dest_run.style = src_run.style
