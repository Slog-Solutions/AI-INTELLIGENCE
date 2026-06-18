import os
from pathlib import Path
from typing import Any
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
        
        # Ensure we're at the start of the file
        file_obj.seek(0)
        with open(target_path, "wb") as out_file:
            content = file_obj.read()
            out_file.write(content)
        return str(target_path)

    @staticmethod
    def extract_metadata(path: str, original_filename: str, category: str, source: str) -> dict[str, Any]:
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
    def parse_excel(path: str) -> dict[str, Any]:
        workbook = pd.ExcelFile(path)
        sheets = {}
        for sheet in workbook.sheet_names:
            df = workbook.parse(sheet_name=sheet)
            sheets[sheet] = df.fillna("").to_dict(orient="records")
        return {"type": "excel", "sheets": sheets}

    @staticmethod
    def parse_csv(path: str) -> dict[str, Any]:
        df = pd.read_csv(path)
        return {"type": "csv", "rows": df.fillna("").to_dict(orient="records")}

    @staticmethod
    def parse_pdf(path: str) -> dict[str, Any]:
        text = []
        tables = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
                page_tables = [table.extract() for table in page.find_tables()]
                tables.extend(page_tables)
        return {"type": "pdf", "text": "\n".join(text), "tables": tables}

    @staticmethod
    def parse_docx(path: str) -> dict[str, Any]:
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
    def to_chunks(parsed: dict[str, Any], limit: int = 500) -> list[str]:
        chunks = []
        if parsed["type"] in ["excel", "csv"]:
            rows = []
            if parsed["type"] == "excel":
                for sheet, records in parsed["sheets"].items():
                    rows.extend([f"Sheet: {sheet} | Data: {record}" for record in records])
            else:
                rows = [f"Data: {record}" for record in parsed["rows"]]
            chunks = [row for row in rows if row.strip()]
        elif parsed["type"] == "pdf":
            # Better PDF chunking: split by paragraphs and limit chunk size
            raw_chunks = [chunk.strip() for chunk in parsed["text"].split("\n\n") if chunk.strip()]
            for rc in raw_chunks:
                if len(rc) > 1000:
                    # Simple split for very long paragraphs
                    chunks.extend([rc[i:i+1000] for i in range(0, len(rc), 1000)])
                else:
                    chunks.append(rc)
        elif parsed["type"] == "docx":
            chunks = [paragraph.strip() for paragraph in parsed["paragraphs"] if paragraph.strip()]
        
        return chunks[:limit]
