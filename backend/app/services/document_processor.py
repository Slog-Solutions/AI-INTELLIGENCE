import os
import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4
import pandas as pd
import pdfplumber
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
    def extract_metadata(path: str, original_filename: str, category: str, source: str) -> Dict[str, Any]:
        file_path = Path(path)
        return {
            "original_filename": Path(original_filename).name,
            "saved_filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "category": category,
            "source": source,
            "size_bytes": file_path.stat().st_size,
        }

    @staticmethod
    def generate_preview(parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a lightweight preview of the document content."""
        if parsed["type"] == "excel":
            preview = {}
            for sheet, data in parsed["sheets"].items():
                preview[sheet] = data[:10]  # First 10 rows
            return {"type": "excel", "data": preview}
        elif parsed["type"] == "csv":
            return {"type": "csv", "data": parsed["rows"][:10]}
        elif parsed["type"] == "pdf":
            return {"type": "pdf", "data": parsed["text"][:1000]}
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
        text = []
        tables = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
                page_tables = [table.extract() for table in page.find_tables()]
                tables.extend(page_tables)
        return {"type": "pdf", "text": "\n".join(text), "tables": tables}

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
    def to_chunks(parsed: Dict[str, Any], limit: int = 1000) -> List[str]:
        chunks = []
        if parsed["type"] in ["excel", "csv"]:
            rows = []
            if parsed["type"] == "excel":
                for sheet, records in parsed["sheets"].items():
                    for record in records:
                        rows.append(f"Sheet: {sheet} | Data: {json.dumps(record)}")
            else:
                for record in parsed["rows"]:
                    rows.append(f"Data: {json.dumps(record)}")
            
            # Group rows into larger chunks to provide context
            current_chunk = []
            current_len = 0
            for row in rows:
                if current_len + len(row) > 1500:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [row]
                    current_len = len(row)
                else:
                    current_chunk.append(row)
                    current_len += len(row)
            if current_chunk:
                chunks.append("\n".join(current_chunk))

        elif parsed["type"] == "pdf":
            text = parsed["text"]
            # Split by double newline for paragraphs
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                if len(p) > 1500:
                    # Sub-chunking long paragraphs
                    for i in range(0, len(p), 1200):
                        chunks.append(p[i:i+1500])
                else:
                    chunks.append(p)
        
        elif parsed["type"] == "docx":
            for p in parsed["paragraphs"]:
                if len(p) > 1500:
                    for i in range(0, len(p), 1200):
                        chunks.append(p[i:i+1500])
                else:
                    chunks.append(p)
        
        return chunks[:limit]
