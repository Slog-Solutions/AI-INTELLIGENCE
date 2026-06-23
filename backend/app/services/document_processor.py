import os
import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4
import pandas as pd
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from ..config import UPLOAD_DIR

class DocumentProcessor:
    @staticmethod
    def save_upload(file_obj, filename: str) -> str:
        safe_name = Path(filename).name
        target_path = Path(UPLOAD_DIR) / safe_name
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            target_path = target_path.with_name(f"{stem}-{uuid4().hex[:8]}{suffix}")
        
        file_obj.seek(0)
        with open(target_path, "wb") as out_file:
            content = file_obj.read()
            out_file.write(content)
        return str(target_path)

    @staticmethod
    def extract_metadata(path: str, original_filename: str, category: str, source: str, page_count: int = 0, chunk_count: int = 0) -> Dict[str, Any]:
        file_path = Path(path)
        return {
            "original_filename": Path(original_filename).name,
            "saved_filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "category": category,
            "source": source,
            "size_bytes": file_path.stat().st_size,
            "page_count": page_count,
            "chunk_count": chunk_count,
        }

    @staticmethod
    def generate_preview(parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a lightweight preview of the document content."""
        if parsed["type"] == "excel":
            preview = {}
            for sheet, data in parsed["sheets"].items():
                preview[sheet] = data[:10]
            return {"type": "excel", "data": preview}
        elif parsed["type"] == "csv":
            return {"type": "csv", "data": parsed["rows"][:10]}
        elif parsed["type"] == "pdf":
            return {"type": "pdf", "data": parsed["full_text"][:1000]}
        elif parsed["type"] == "docx":
            return {"type": "docx", "data": "\n".join(parsed["paragraphs"][:10])}
        return {"type": "unknown", "data": ""}

    @staticmethod
    def parse_excel(path: str) -> Dict[str, Any]:
        workbook = pd.ExcelFile(path)
        sheets = {}
        for sheet in workbook.sheet_names:
            df = workbook.parse(sheet_name=sheet)
            sheets[sheet] = df.fillna("").to_dict(orient="records")
        return {"type": "excel", "sheets": sheets}

    @staticmethod
    def parse_csv(path: str) -> Dict[str, Any]:
        df = pd.read_csv(path)
        return {"type": "csv", "rows": df.fillna("").to_dict(orient="records")}

    @staticmethod
    def parse_pdf(path: str) -> Dict[str, Any]:
        full_text = []
        page_texts = []
        page_count = 0
        try:
            with fitz.open(path) as doc:
                page_count = doc.page_count
                for page_num in range(page_count):
                    page = doc.load_page(page_num)
                    text = page.get_text("text")
                    full_text.append(text)
                    page_texts.append(text)
            return {"type": "pdf", "full_text": "\n".join(full_text), "page_texts": page_texts, "page_count": page_count}
        except Exception as e:
            return {"type": "pdf", "full_text": "", "page_texts": [], "page_count": 0, "error": str(e)}

    @staticmethod
    def parse_docx(path: str) -> Dict[str, Any]:
        doc = DocxDocument(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        tables = []
        for table in doc.tables:
            rows = []
            for r in table.rows:
                rows.append([c.text for c in r.cells])
            tables.append(rows)
        return {"type": "docx", "paragraphs": paragraphs, "tables": tables}

    @staticmethod
    def to_chunks(parsed: Dict[str, Any], original_filename: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
        chunks_with_metadata = []

        if parsed["type"] in ["excel", "csv"]:
            rows = []
            if parsed["type"] == "excel":
                for sheet, records in parsed["sheets"].items():
                    for record in records:
                        rows.append(f"Sheet: {sheet} | Data: {json.dumps(record)}")
            else:
                for record in parsed["rows"]:
                    rows.append(f"Data: {json.dumps(record)}")
            
            current_chunk_text = []
            current_len = 0
            for i, row in enumerate(rows):
                row_len = len(row)
                if current_len + row_len > chunk_size and current_chunk_text:
                    chunks_with_metadata.append({
                        "content": "\n".join(current_chunk_text),
                        "metadata": {
                            "source": original_filename,
                            "chunk_index": len(chunks_with_metadata),
                            "document_type": parsed["type"],
                        }
                    })
                    overlap_rows = []
                    overlap_len = 0
                    for j in range(len(current_chunk_text) - 1, -1, -1):
                        if overlap_len + len(current_chunk_text[j]) <= chunk_overlap:
                            overlap_rows.insert(0, current_chunk_text[j])
                            overlap_len += len(current_chunk_text[j])
                        else:
                            break
                    current_chunk_text = overlap_rows + [row]
                    current_len = overlap_len + row_len
                else:
                    current_chunk_text.append(row)
                    current_len += row_len
            if current_chunk_text:
                chunks_with_metadata.append({
                    "content": "\n".join(current_chunk_text),
                    "metadata": {
                        "source": original_filename,
                        "chunk_index": len(chunks_with_metadata),
                        "document_type": parsed["type"],
                    }
                })

        elif parsed["type"] == "pdf":
            for page_num, page_text in enumerate(parsed["page_texts"]):
                paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                current_chunk_text = []
                current_len = 0
                for para in paragraphs:
                    para_len = len(para)
                    if current_len + para_len > chunk_size and current_chunk_text:
                        chunks_with_metadata.append({
                            "content": "\n".join(current_chunk_text),
                            "metadata": {
                                "source": original_filename,
                                "page_number": page_num + 1,
                                "chunk_index": len(chunks_with_metadata),
                                "document_type": parsed["type"],
                            }
                        })
                        overlap_text = current_chunk_text[-1][-chunk_overlap:] if current_chunk_text else ""
                        current_chunk_text = [overlap_text + para] if overlap_text else [para]
                        current_len = len(current_chunk_text[0])
                    else:
                        current_chunk_text.append(para)
                        current_len += para_len
                if current_chunk_text:
                    chunks_with_metadata.append({
                        "content": "\n".join(current_chunk_text),
                        "metadata": {
                            "source": original_filename,
                            "page_number": page_num + 1,
                            "chunk_index": len(chunks_with_metadata),
                            "document_type": parsed["type"],
                        }
                    })

        elif parsed["type"] == "docx":
            current_chunk_text = []
            current_len = 0
            for i, p in enumerate(parsed["paragraphs"]):
                p_len = len(p)
                if current_len + p_len > chunk_size and current_chunk_text:
                    chunks_with_metadata.append({
                        "content": "\n".join(current_chunk_text),
                        "metadata": {
                            "source": original_filename,
                            "chunk_index": len(chunks_with_metadata),
                            "document_type": parsed["type"],
                        }
                    })
                    overlap_paras = []
                    overlap_len = 0
                    for j in range(len(current_chunk_text) - 1, -1, -1):
                        if overlap_len + len(current_chunk_text[j]) <= chunk_overlap:
                            overlap_paras.insert(0, current_chunk_text[j])
                            overlap_len += len(current_chunk_text[j])
                        else:
                            break
                    current_chunk_text = overlap_paras + [p]
                    current_len = overlap_len + p_len
                else:
                    current_chunk_text.append(p)
                    current_len += p_len
            if current_chunk_text:
                chunks_with_metadata.append({
                    "content": "\n".join(current_chunk_text),
                    "metadata": {
                        "source": original_filename,
                        "chunk_index": len(chunks_with_metadata),
                        "document_type": parsed["type"],
                    }
                })
        
        return chunks_with_metadata
