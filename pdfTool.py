from typing import Dict, Union
import markdown2
from supabase import create_client, Client
from html.parser import HTMLParser
from dotenv import load_dotenv, find_dotenv
import os
from fpdf import FPDF
from agents.tool import function_tool


_:bool = load_dotenv(find_dotenv())


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL or Key is not set in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class PDFGenerator(FPDF):
    def __init__(self):
        super().__init__()
        # Use project-relative font paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fonts_dir = os.path.join(base_dir, "fonts")
        fira_code_regular = os.path.join(fonts_dir, "FiraCodeNerdFont-Regular.ttf")
        fira_code_bold = os.path.join(fonts_dir, "FiraCodeNerdFont-Bold.ttf")
        # print("Current Working Directory:", os.getcwd())
        # print("Checking if Fira Code Nerd Font files exist:")
        # print(f"Regular Font: {fira_code_regular} - Exists? {os.path.exists(fira_code_regular)}")
        # print(f"Bold Font: {fira_code_bold} - Exists? {os.path.exists(fira_code_bold)}")

        try:
            self.add_font("FiraCodeNerdFont", "", fira_code_regular, uni=True)
            self.add_font("FiraCodeNerdFont", "B", fira_code_bold, uni=True)
        except Exception as e:
            raise RuntimeError(f"Error loading Fira Code Nerd Font: {e}")

        # Basic PDF setup
        self.add_page()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_font("FiraCodeNerdFont", size=12)

    def add_html_content(self, html_content: str):
        class HTMLToPDFParser(HTMLParser):
            def __init__(self, pdf):
                super().__init__()
                self.pdf = pdf
                self.in_code_block = False

                # Track current font state
                self.current_font = {
                    "family": "FiraCodeNerdFont",
                    "style": "",
                    "size": 12
                }

            def set_font_from_tag(self, tag):
                """Apply an inline style change based on the HTML tag."""
                if tag in ("strong", "b"):
                    # Bold style
                    self.current_font["style"] += "B"
                elif tag in ("em", "i"):
                    # Use Times Italic for italics
                    self.current_font["family"] = "Times"
                    self.current_font["style"] = "I"
                    self.current_font["size"] = 12
                elif tag == "code":
                    # Inline code in Courier (no auto-bold to avoid 'BB' error)
                    self.current_font["family"] = "Courier"
                    self.current_font["style"] = ""
                    self.current_font["size"] = 12

                self.pdf.set_font(
                    self.current_font["family"],
                    self.current_font["style"],
                    self.current_font["size"]
                )

            def reset_font(self, tag):
                """Reset the style change when the tag ends."""
                if tag in ("strong", "b"):
                    self.current_font["style"] = self.current_font["style"].replace("B", "")
                elif tag in ("em", "i"):
                    # Return to normal Fira Code Nerd Font
                    self.current_font["family"] = "FiraCodeNerdFont"
                    self.current_font["style"] = ""
                    self.current_font["size"] = 12
                elif tag == "code":
                    # Return to normal Fira Code Nerd Font
                    self.current_font["family"] = "FiraCodeNerdFont"
                    self.current_font["size"] = 12

                # Re-apply the current font setting
                self.pdf.set_font(
                    self.current_font["family"],
                    self.current_font["style"],
                    self.current_font["size"]
                )

            def handle_starttag(self, tag, attrs):
                """Handle block/inline elements at the start."""
                # Headings
                if tag in ("h1", "h2", "h3"):
                    sizes = {"h1": 16, "h2": 14, "h3": 12}
                    self.pdf.ln(6)
                    self.pdf.set_font("FiraCodeNerdFont", "B", sizes[tag])

                # Block tags
                elif tag in ("p", "ul", "ol"):
                    self.pdf.ln(5)

                elif tag == "li":
                    self.pdf.ln(5)
                    self.pdf.write(5, u"\u2022 ")  # bullet

                # Inline style tags (bold, italic, code)
                elif tag in ("strong", "b", "em", "i", "code"):
                    self.set_font_from_tag(tag)

                # Multi-line code block: <pre>
                if tag == "pre":
                    self.pdf.ln(5)
                    # Courier (no bold) at smaller size
                    self.pdf.set_font("Courier", "", 11)
                    self.pdf.set_fill_color(240, 240, 240)
                    self.in_code_block = True

            def handle_endtag(self, tag):
                """When a tag ends, revert style if needed."""
                if tag in ("h1", "h2", "h3"):
                    self.pdf.ln(5)
                    # Return to normal Fira Code Nerd Font
                    self.pdf.set_font("FiraCodeNerdFont", "", 12)

                elif tag in ("strong", "b", "em", "i", "code"):
                    self.reset_font(tag)

                elif tag == "pre":
                    self.pdf.ln(5)
                    self.pdf.set_font("FiraCodeNerdFont", "", 12)
                    self.pdf.set_fill_color(255, 255, 255)
                    self.in_code_block = False

            def handle_data(self, data):
                """Handle the text data inside tags."""
                if self.in_code_block:
                    # Preserve newlines in code blocks
                    lines = data.splitlines()
                    for line in lines:
                        self.pdf.multi_cell(0, 5, line, fill=True)
                else:
                    # Inline text: collapse newlines to spaces
                    text = data.replace("\n", " ")
                    if text.strip():
                        self.pdf.write(5, text + " ")

        parser = HTMLToPDFParser(self)
        parser.feed(html_content)

    def add_markdown_content(self, markdown_content: str):
        """Convert Markdown to HTML, then parse it."""
        html_content = markdown2.markdown(
            markdown_content,
            extras=["fenced-code-blocks", "tables", "code-friendly"]
        )
        self.add_html_content(html_content)

@function_tool("pdf_creator_tool")
def pdf_creator_tool(
    markdown_content: str,
    filename:str
) -> Dict[str, Union[bool, str]]:
    """
    Convert the provided Markdown content into a PDF,
    upload it to Supabase Storage, and return a public link.
    """
    # filename="output.pdf"
    bucket_name="pdf_storage"
    try:
        if not markdown_content.strip():
            return {"success": False, "error": "Markdown content is empty."}

        pdf = PDFGenerator()
        pdf.add_markdown_content(markdown_content)
        pdf.output(filename)

        # Upload PDF to Supabase Storage
        with open(filename, "rb") as file_data:
            supabase.storage.from_(bucket_name).upload(
                filename,
                file_data,
                {"content-type": "application/pdf"}
            )

        public_url_response = supabase.storage.from_(bucket_name).get_public_url(filename)
        if not public_url_response:
            return {"success": False, "error": "Failed to retrieve public URL."}

        return {
            "success": True,
            "message": "PDF created and uploaded successfully.",
            "download_link": public_url_response,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}