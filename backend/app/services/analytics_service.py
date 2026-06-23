import pandas as pd
import json
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

class AnalyticsService:
    @staticmethod
    def generate_analytics(file_path: str, filename: str, parsed_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate analytics for different file types.
        """
        ext = Path(filename).suffix.lower()
        
        if ext in ['.csv', '.xlsx', '.xls']:
            return AnalyticsService._analyze_tabular(file_path, ext)
        elif ext in ['.pdf', '.docx']:
            return AnalyticsService._analyze_text(parsed_content)
        return {}

    @staticmethod
    def _analyze_tabular(file_path: str, ext: str) -> Dict[str, Any]:
        try:
            if ext == '.csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Basic stats
            summary = {
                "type": "tabular",
                "rows": len(df),
                "columns": list(df.columns),
                "column_summaries": {},
                "charts": []
            }
            
            # Column analysis
            for col in df.columns:
                col_data = df[col]
                if pd.api.types.is_numeric_dtype(col_data):
                    summary["column_summaries"][col] = {
                        "mean": float(col_data.mean()) if not col_data.empty else 0,
                        "min": float(col_data.min()) if not col_data.empty else 0,
                        "max": float(col_data.max()) if not col_data.empty else 0,
                    }
                    # Simple distribution for charts
                    counts, bins = pd.cut(col_data.dropna(), bins=5, retbins=True)
                    summary["charts"].append({
                        "id": f"dist_{col}",
                        "title": f"Distribution of {col}",
                        "type": "bar",
                        "data": [{"name": f"{bins[i]:.1f}-{bins[i+1]:.1f}", "value": int(count)} for i, count in enumerate(counts.value_counts().sort_index())]
                    })
                elif pd.api.types.is_object_dtype(col_data):
                    top_values = col_data.value_counts().head(5)
                    summary["column_summaries"][col] = {
                        "unique_count": int(col_data.nunique()),
                        "top_values": top_values.to_dict()
                    }
                    if col_data.nunique() < 10:
                        summary["charts"].append({
                            "id": f"breakdown_{col}",
                            "title": f"Breakdown of {col}",
                            "type": "pie",
                            "data": [{"name": str(k), "value": int(v)} for k, v in top_values.items()]
                        })

            return summary
        except Exception as e:
            logger.error(f"Tabular analysis error: {e}")
            return {"error": str(e)}

    @staticmethod
    def _analyze_text(parsed_content: Dict[str, Any]) -> Dict[str, Any]:
        # Placeholder for text analysis (entities, keywords, etc.)
        # In a real app, this would use NLP libraries
        text = parsed_content.get("text", "")
        
        # Mocking keyword extraction and topics
        keywords = ["analysis", "report", "intelligence", "operations", "strategic"]
        entities = ["ATIP", "Command", "HQ"]
        
        return {
            "type": "text",
            "keywords": keywords,
            "entities": entities,
            "topics": ["Operational Planning", "Resource Allocation"],
            "risks": ["Resource shortage in Q3", "Timeline slippage"],
            "summary": "This document outlines the strategic operational goals and current resource status.",
            "charts": [
                {
                    "id": "keyword_freq",
                    "title": "Keyword Frequency",
                    "type": "bar",
                    "data": [{"name": k, "value": len(k) * 2} for k in keywords]
                }
            ]
        }
