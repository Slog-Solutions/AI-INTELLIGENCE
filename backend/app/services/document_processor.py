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
        with open(target_path, "wb") as out_file:
            out_file.write(file_obj.read())
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
    def to_chunks(parsed: dict[str, Any], limit: int = 100) -> list[str]:
        if parsed["type"] in ["excel", "csv"]:
            rows = []
            if parsed["type"] == "excel":
                for sheet, records in parsed["sheets"].items():
                    rows.extend([f"sheet={sheet} row={record}" for record in records])
            else:
                rows = [str(record) for record in parsed["rows"]]
            return [row for row in rows if row.strip()][:limit]
        if parsed["type"] == "pdf":
            chunks = [chunk.strip() for chunk in parsed["text"].split("\n\n") if chunk.strip()]
            if not chunks and parsed["text"].strip():
                chunks = [parsed["text"].strip()]
            return chunks[:limit]
        if parsed["type"] == "docx":
            return [paragraph.strip() for paragraph in parsed["paragraphs"] if paragraph.strip()][:limit]
        return []
