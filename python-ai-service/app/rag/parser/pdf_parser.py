"""PDF 解析器 - 双后端: PyMuPDF (fitz) 主用, pypdf 回退。"""

try:
    import fitz
    _HAS_FITZ = True
except ImportError:
    fitz = None
    _HAS_FITZ = False

from app.rag.parser.parser_factory import BaseParser, ParsedDocument, PageInfo, ParagraphInfo, HeadingInfo
from app.core.logger import get_logger

logger = get_logger(__name__)


class PdfParser(BaseParser):
    MIN_TEXT_PER_PAGE = 10

    @property
    def supported_types(self) -> list[str]:
        return [".pdf"]

    def parse(self, file_path: str, file_name: str, content: bytes) -> ParsedDocument:
        if _HAS_FITZ:
            return self._parse_fitz(content, file_name)
        else:
            return self._parse_pypdf(content, file_name)

    def _parse_fitz(self, content: bytes, file_name: str) -> ParsedDocument:
        doc = fitz.open(stream=content, filetype="pdf")
        total_pages = doc.page_count
        if total_pages == 0:
            return ParsedDocument(file_name=file_name, file_type="pdf", total_chars=0, total_pages=0, full_text="")

        pages, paragraphs, headings, errors, all_text_parts, global_offset = [], [], [], [], [], 0
        for page_idx in range(total_pages):
            try:
                page_text = doc[page_idx].get_text("text") or ""
            except Exception as e:
                errors.append(f"page {page_idx+1} read error: {e}")
                page_text = ""

            if len(page_text.strip()) < self.MIN_TEXT_PER_PAGE:
                images = doc[page_idx].get_images(full=True)
                if images:
                    page_text = f"[page {page_idx+1}: image/scanned, {len(images)} images]"

            pages.append(PageInfo(page_number=page_idx+1, text=page_text, char_count=len(page_text)))
            for para_text in page_text.split("\n"):
                stripped = para_text.strip()
                if not stripped:
                    continue
                is_heading = _detect_heading(stripped)
                paragraphs.append(ParagraphInfo(text=stripped, page_number=page_idx+1, char_offset=global_offset, char_count=len(stripped), is_heading=is_heading, heading_level=_guess_heading_level(stripped) if is_heading else 0))
                if is_heading:
                    headings.append(HeadingInfo(level=_guess_heading_level(stripped), text=stripped, page_number=page_idx+1, char_offset=global_offset))
                global_offset += len(stripped) + 1
            all_text_parts.append(f"[page {page_idx+1}]\n{page_text}")

        doc.close()
        full_text = "\n\n".join(all_text_parts)
        title_path = [h.text for h in headings if h.level <= 2]
        logger.info(f"[PdfParser:fitz] {file_name}: {total_pages}p, {len(full_text)}chars, {len(headings)}headings")
        return ParsedDocument(file_name=file_name, file_type="pdf", total_chars=len(full_text), total_pages=total_pages, full_text=full_text, pages=pages, paragraphs=paragraphs, headings=headings, title_path=title_path, metadata={"parser": "PyMuPDF", "page_count": total_pages}, parse_errors=errors)

    def _parse_pypdf(self, content: bytes, file_name: str) -> ParsedDocument:
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        total_pages = len(reader.pages)
        if total_pages == 0:
            return ParsedDocument(file_name=file_name, file_type="pdf", total_chars=0, total_pages=0, full_text="")

        pages, paragraphs, headings, errors, all_text_parts, global_offset = [], [], [], [], [], 0
        for page_idx in range(total_pages):
            try:
                page_text = reader.pages[page_idx].extract_text() or ""
            except Exception as e:
                errors.append(f"page {page_idx+1} error: {e}")
                page_text = ""

            pages.append(PageInfo(page_number=page_idx+1, text=page_text, char_count=len(page_text)))
            for para_text in page_text.split("\n"):
                stripped = para_text.strip()
                if not stripped:
                    continue
                is_heading = _detect_heading(stripped)
                paragraphs.append(ParagraphInfo(text=stripped, page_number=page_idx+1, char_offset=global_offset, char_count=len(stripped), is_heading=is_heading, heading_level=_guess_heading_level(stripped) if is_heading else 0))
                if is_heading:
                    headings.append(HeadingInfo(level=_guess_heading_level(stripped), text=stripped, page_number=page_idx+1, char_offset=global_offset))
                global_offset += len(stripped) + 1
            all_text_parts.append(f"[page {page_idx+1}]\n{page_text}")

        full_text = "\n\n".join(all_text_parts)
        title_path = [h.text for h in headings if h.level <= 2]
        logger.info(f"[PdfParser:pypdf] {file_name}: {total_pages}p, {len(full_text)}chars")
        return ParsedDocument(file_name=file_name, file_type="pdf", total_chars=len(full_text), total_pages=total_pages, full_text=full_text, pages=pages, paragraphs=paragraphs, headings=headings, title_path=title_path, metadata={"parser": "pypdf", "page_count": total_pages}, parse_errors=errors)


def _detect_heading(text: str) -> bool:
    if len(text) > 100:
        return False
    import re
    patterns = [r"^第[一二三四五六七八九十百千万\d]+[章节条款]", r"^[\d]+[\.\、\．][\d]*", r"^[一二三四五六七八九十]+[、\．\s]", r"^[（\(][一二三四五六七八九十\d]+[）\)]"]
    return any(re.match(p, text) for p in patterns)

def _guess_heading_level(text: str) -> int:
    import re
    if re.match(r"^第[一二三四五六七八九十百千万\d]+章", text): return 1
    if re.match(r"^第[一二三四五六七八九十百千万\d]+节", text): return 2
    if re.match(r"^[\d]+\.$", text): return 1
    if re.match(r"^[\d]+\.[\d]+", text): return 2
    if re.match(r"^[\d]+\.[\d]+\.[\d]+", text): return 3
    if re.match(r"^[一二三四五六七八九十]+[、\．]", text): return 1
    if re.match(r"^[（\(][一二三四五六七八九十\d]+[）\)]", text): return 2
    return 3
