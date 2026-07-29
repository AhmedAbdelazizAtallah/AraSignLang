"""
Export & report generation.

Produces TXT, CSV, JSON and a polished PDF report for a recognition session.
PDF uses reportlab with Arabic reshaping + bidi so text renders RTL.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from backend.config.settings import settings
from backend.utils.logging import get_logger

logger = get_logger(__name__)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _reshape(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def export_txt(stats: Dict) -> Path:
    path = settings.REPORT_DIR / f"session_{stats['session_id']}_{_stamp()}.txt"
    path.write_text(stats.get("generated_text", ""), encoding="utf-8")
    return path


def export_json(stats: Dict) -> Path:
    path = settings.REPORT_DIR / f"session_{stats['session_id']}_{_stamp()}.json"
    path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_csv(stats: Dict) -> Path:
    path = settings.REPORT_DIR / f"session_{stats['session_id']}_{_stamp()}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in stats.items():
            if isinstance(v, list):
                v = " ".join(map(str, v))
            writer.writerow([k, v])
    return path


def export_pdf(stats: Dict) -> Path:
    path = settings.REPORT_DIR / f"report_{stats['session_id']}_{_stamp()}.pdf"
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(path), pagesize=A4)
        width, height = A4

        c.setFillColor(colors.HexColor("#6d5efc"))
        c.rect(0, height - 1.5 * cm, width, 1.5 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2 * cm, height - 1.05 * cm, "Arabic Sign Language - Prediction Report")

        y = height - 3 * cm
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 11)

        rows = [
            ("Session ID", stats["session_id"]),
            ("Date / Time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("Device used", stats.get("device", "cpu").upper()),
            ("Frames analysed", stats.get("frames_processed", 0)),
            ("Average FPS", stats.get("avg_fps", 0)),
            ("Processing time (s)", stats.get("duration_s", 0)),
            ("Average latency (ms)", stats.get("avg_latency_ms", 0)),
            ("Average confidence", f"{stats.get('avg_confidence', 0) * 100:.1f}%"),
            ("Highest confidence", f"{stats.get('max_confidence', 0) * 100:.1f}%"),
            ("Lowest confidence", f"{stats.get('min_confidence', 0) * 100:.1f}%"),
            ("Detected letters", len(stats.get("detected_letters", []))),
            ("Accepted letters", len(stats.get("accepted_letters", []))),
        ]
        for label, value in rows:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(2 * cm, y, f"{label}:")
            c.setFont("Helvetica", 11)
            c.drawString(8 * cm, y, str(value))
            y -= 0.7 * cm

        y -= 0.5 * cm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Generated Text:")
        y -= 0.8 * cm
        c.setFont("Helvetica", 13)
        text = _reshape(stats.get("generated_text", "")) or "(empty)"
        for line in _wrap(text, 60):
            c.drawRightString(width - 2 * cm, y, line)
            y -= 0.7 * cm

        c.showPage()
        c.save()
    except Exception as exc:  # pragma: no cover
        logger.warning("PDF generation failed (%s); writing text fallback.", exc)
        path = path.with_suffix(".txt")
        path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _wrap(text: str, width: int):
    words = text.split(" ")
    line, out = "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out or [""]


EXPORTERS = {"txt": export_txt, "json": export_json, "csv": export_csv, "pdf": export_pdf}


def export(stats: Dict, fmt: str) -> Path:
    fmt = fmt.lower()
    if fmt not in EXPORTERS:
        raise ValueError(f"Unsupported export format: {fmt}")
    return EXPORTERS[fmt](stats)
