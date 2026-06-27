"""
ATIP Analytics Service
========================
Generates document-level analytics used by the dashboard.
For text documents (PDF/DOCX), uses entities extracted by DocumentProcessor
instead of the placeholder mock data in the original implementation.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class AnalyticsService:

    @staticmethod
    def generate_analytics(
        file_path: str,
        filename: str,
        parsed_content: Dict[str, Any],
    ) -> Dict[str, Any]:
        ext = Path(filename).suffix.lower()
        if ext in (".csv", ".xlsx", ".xls"):
            return AnalyticsService._analyze_tabular(file_path, ext)
        elif ext in (".pdf", ".docx"):
            return AnalyticsService._analyze_text(parsed_content)
        return {}

    # ── Tabular Analysis ─────────────────────────────────────────────────────
    @staticmethod
    def _analyze_tabular(file_path: str, ext: str) -> Dict[str, Any]:
        try:
            df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)

            summary: Dict[str, Any] = {
                "type": "tabular",
                "rows": len(df),
                "columns": list(df.columns),
                "column_summaries": {},
                "charts": [],
            }

            for col in df.columns:
                col_data = df[col]
                if pd.api.types.is_numeric_dtype(col_data):
                    summary["column_summaries"][col] = {
                        "mean": float(col_data.mean()) if not col_data.empty else 0,
                        "min": float(col_data.min()) if not col_data.empty else 0,
                        "max": float(col_data.max()) if not col_data.empty else 0,
                    }
                    try:
                        counts, bins = pd.cut(
                            col_data.dropna(), bins=5, retbins=True
                        )
                        summary["charts"].append({
                            "id": f"dist_{col}",
                            "title": f"Distribution of {col}",
                            "type": "bar",
                            "data": [
                                {
                                    "name": f"{bins[i]:.1f}-{bins[i+1]:.1f}",
                                    "value": int(cnt),
                                }
                                for i, cnt in enumerate(
                                    counts.value_counts().sort_index()
                                )
                            ],
                        })
                    except Exception:
                        pass
                elif pd.api.types.is_object_dtype(col_data):
                    top_values = col_data.value_counts().head(5)
                    summary["column_summaries"][col] = {
                        "unique_count": int(col_data.nunique()),
                        "top_values": top_values.to_dict(),
                    }
                    if col_data.nunique() < 10:
                        summary["charts"].append({
                            "id": f"breakdown_{col}",
                            "title": f"Breakdown of {col}",
                            "type": "pie",
                            "data": [
                                {"name": str(k), "value": int(v)}
                                for k, v in top_values.items()
                            ],
                        })

            return summary

        except Exception as e:
            logger.error(f"Tabular analysis error: {e}")
            return {"error": str(e)}

    # ── Text / Document Analysis ─────────────────────────────────────────────
    @staticmethod
    def _analyze_text(parsed_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract real analytics from the parsed document's text.
        Entities are extracted by DocumentProcessor and passed in via
        the parsed_content dict (via the chunks' metadata). Here we do
        a lightweight keyword frequency pass over the full text.
        """
        full_text = parsed_content.get("full_text", "")
        page_count = parsed_content.get("page_count", 0)

        # ── Keyword frequency (military domain vocabulary) ─────────────────
        domain_keywords = [
            "operation", "mission", "battalion", "regiment", "company", "platoon",
            "attack", "defence", "defense", "casualty", "objective", "manoeuvre",
            "logistics", "intelligence", "reconnaissance", "communication",
            "training", "exercise", "ammunition", "artillery", "infantry",
            "armoured", "command", "control", "strategy", "tactical",
        ]
        keyword_counts: Dict[str, int] = {}
        lower_text = full_text.lower()
        for kw in domain_keywords:
            cnt = lower_text.count(kw)
            if cnt > 0:
                keyword_counts[kw] = cnt

        keyword_list = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

        # ── Risk keywords ──────────────────────────────────────────────────
        risk_terms = [
            "shortage", "delay", "failure", "breach", "alert", "threat",
            "vulnerable", "risk", "critical", "emergency", "loss", "damage",
        ]
        detected_risks: List[str] = []
        for term in risk_terms:
            if term in lower_text:
                # Find a short excerpt around the term for context
                idx = lower_text.find(term)
                excerpt = full_text[max(0, idx - 40): idx + 80].replace("\n", " ").strip()
                detected_risks.append(excerpt)
                if len(detected_risks) >= 5:
                    break

        # ── Build charts ───────────────────────────────────────────────────
        charts: List[Dict[str, Any]] = []
        if keyword_list:
            charts.append({
                "id": "keyword_freq",
                "title": "Domain Keyword Frequency",
                "type": "bar",
                "data": [
                    {"name": kw, "value": cnt}
                    for kw, cnt in keyword_list[:12]
                ],
            })

        return {
            "type": "text",
            "page_count": page_count,
            "keywords": [kw for kw, _ in keyword_list[:15]],
            "keyword_frequency": dict(keyword_list[:15]),
            "risks": detected_risks,
            "charts": charts,
            "summary": (
                f"Document has {page_count} pages. "
                f"Top domain terms: {', '.join(kw for kw, _ in keyword_list[:5])}."
                if keyword_list
                else "Document analysed."
            ),
        }