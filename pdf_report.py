"""Styled PDF itinerary generator for the Travel Planner Agent.

Turns the agent's markdown answer (plus optional structured data captured from
the agent's tool calls) into a clean, print-ready A4 PDF with embedded fonts
(Poppins + Playfair Display, both SIL OFL), a title banner, summary tiles,
a budget chart and day-by-day cards.

Public API:
    build_itinerary_pdf(markdown_text, meta=None) -> bytes
    suggest_filename(markdown_text, meta=None) -> str
    looks_like_itinerary(markdown_text) -> bool
"""

from __future__ import annotations

import datetime
import io
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

_FONT_FILES = {
    "Poppins": "Poppins-Regular.ttf",
    "Poppins-Light": "Poppins-Light.ttf",
    "Poppins-Medium": "Poppins-Medium.ttf",
    "Poppins-SemiBold": "Poppins-SemiBold.ttf",
    "Poppins-Bold": "Poppins-Bold.ttf",
    "Poppins-Italic": "Poppins-Italic.ttf",
    "Playfair": "PlayfairDisplay-Regular.ttf",
    "Playfair-Bold": "PlayfairDisplay-Bold.ttf",
}
_fonts_ready = False
_SUPPORTED_CODEPOINTS: set[int] = set()


def _register_fonts() -> None:
    global _fonts_ready, _SUPPORTED_CODEPOINTS
    if _fonts_ready:
        return
    for name, fname in _FONT_FILES.items():
        path = os.path.join(FONT_DIR, fname)
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        "Poppins",
        normal="Poppins",
        bold="Poppins-SemiBold",
        italic="Poppins-Italic",
        boldItalic="Poppins-Italic",
    )
    _SUPPORTED_CODEPOINTS = set(pdfmetrics.getFont("Poppins").face.charToGlyph.keys())
    _fonts_ready = True


# --------------------------------------------------------------------------
# Palette and layout
# --------------------------------------------------------------------------
TEAL = colors.HexColor("#0B3C49")
TEAL_MID = colors.HexColor("#3A7D8C")
TEAL_LIGHT = colors.HexColor("#8FB8C0")
AMBER = colors.HexColor("#D98324")
AMBER_LIGHT = colors.HexColor("#E9B872")
SAND = colors.HexColor("#F7F2EA")
SAND_DARK = colors.HexColor("#EDE4D6")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#6B7280")
RULE = colors.HexColor("#E4DCCF")
BRICK = colors.HexColor("#B23A48")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
HERO_H = 62 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

SEGMENT_COLORS = [TEAL, TEAL_MID, TEAL_LIGHT, AMBER, AMBER_LIGHT]

SLOT_KEYWORDS = {
    "morning", "afternoon", "evening", "night", "breakfast", "lunch", "dinner",
    "brunch", "snack", "snacks", "midday", "noon", "sunset", "sunrise", "late",
    "early", "stay", "transport", "travel", "check", "accommodation", "food",
    "eat", "note", "tip", "optional", "arrival", "departure", "overnight",
}
SLOT_COLORS = {
    "morning": AMBER, "breakfast": AMBER, "brunch": AMBER, "sunrise": AMBER, "early": AMBER,
    "afternoon": TEAL_MID, "lunch": TEAL_MID, "midday": TEAL_MID, "noon": TEAL_MID,
    "evening": TEAL, "dinner": TEAL, "night": TEAL, "sunset": TEAL, "late": TEAL,
}

# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F\u200D]"
)
_REPLACEMENTS = {
    "→": " to ", "←": " from ", "➜": " to ", "✓": "", "✔": "", "✗": "", "✘": "",
    "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u2212": "-", "≈": "~", "★": "",
    "⭐": "", "☆": "",
}


def sanitize(text: str) -> str:
    """Remove emoji and any character the PDF font cannot draw."""
    _register_fonts()
    if not text:
        return ""
    for k, v in _REPLACEMENTS.items():
        text = text.replace(k, v)
    text = _EMOJI_RE.sub("", text)
    out = []
    for ch in text:
        if ch in "\n\t" or ord(ch) in _SUPPORTED_CODEPOINTS:
            out.append(ch)
    return re.sub(r"[ ]{2,}", " ", "".join(out))


def inr(value) -> str:
    """Format a number as rupees with Indian digit grouping."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return "-"
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = head + "," + tail
    return ("-" if n < 0 else "") + "\u20b9" + s


def inline(text: str) -> str:
    """Convert a small markdown subset to ReportLab paragraph markup."""
    text = sanitize(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                  r'<a href="\2" color="#0B3C49"><u>\1</u></a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Poppins-Medium">\1</font>', text)
    return text.replace("\n", "<br/>")


def plain(text: str) -> str:
    """Strip markdown markers for places where only plain text is wanted."""
    text = sanitize(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`]+", "", text)
    return text.strip()


# --------------------------------------------------------------------------
# Markdown parsing
# --------------------------------------------------------------------------
_SEP_CELL = re.compile(r"^:?-{1,}:?$")


def parse_markdown(md: str) -> list[tuple]:
    lines = md.replace("\r\n", "\n").split("\n")
    blocks: list[tuple] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            blocks.append(("hr",))
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", stripped)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2)))
            i += 1
            continue
        if stripped.startswith("|"):
            raw = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw.append(lines[i].strip())
                i += 1
            rows = [[c.strip() for c in r.strip("|").split("|")] for r in raw]
            rows = [r for r in rows if not (r and all(_SEP_CELL.match(c.replace(" ", "")) for c in r))]
            if rows:
                blocks.append(("table", rows))
            continue
        if re.match(r"^\s*[-*\u2022+]\s+", line) and not re.match(r"^\s*\*\*[^*]+\*\*\s*$", stripped):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*\u2022+]\s+", lines[i]):
                indent = len(lines[i]) - len(lines[i].lstrip())
                txt = re.sub(r"^\s*[-*\u2022+]\s+", "", lines[i]).strip()
                items.append((1 if indent >= 2 else 0, txt))
                i += 1
            blocks.append(("ul", items))
            continue
        if re.match(r"^\s*\d+[.)]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                items.append((0, re.sub(r"^\s*\d+[.)]\s+", "", lines[i]).strip()))
                i += 1
            blocks.append(("ol", items))
            continue
        if stripped.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(("quote", " ".join(quote)))
            continue
        blocks.append(("p", stripped))
        i += 1
    return blocks


_DAY_RE = re.compile(r"^day\s*(\d+)\s*(?:[:\-\u2013\u2014|.,]\s*|\s+)?(.*)$", re.I)


def match_day(text: str):
    t = plain(text).strip()
    m = _DAY_RE.match(t)
    if not m:
        return None
    title = m.group(2).strip(" :-\u2013\u2014|")
    return int(m.group(1)), title


def match_slot(raw: str):
    """Return (label, text) if the line looks like 'Morning: ...'."""
    raw = raw.strip()
    m = re.match(r"^\*\*([^*:]{2,34}):?\*\*\s*:?\s*(.*)$", raw)
    if not m:
        m = re.match(r"^([A-Za-z][A-Za-z0-9 /&().,'\u2019-]{1,32}):\s+(.*)$", raw)
    if not m:
        m = re.match(r"^([A-Za-z][A-Za-z ]{1,24})\s+[\u2013\u2014-]\s+(.*)$", raw)
    if not m:
        return None
    label, rest = m.group(1).strip(), m.group(2).strip()
    first = re.split(r"[\s(/&-]", label.lower())[0]
    if first not in SLOT_KEYWORDS:
        return None
    return label, rest


# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------
def _styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="Poppins", fontSize=9.3, leading=14.2, textColor=INK, alignment=TA_LEFT)
    s = {
        "body": ParagraphStyle("body", spaceAfter=5, **base),
        "muted": ParagraphStyle("muted", **{**base, "fontName": "Poppins-Italic", "fontSize": 8,
                                            "leading": 12, "textColor": MUTED}, spaceAfter=4),
        "h3": ParagraphStyle("h3", **{**base, "fontName": "Poppins-SemiBold", "fontSize": 10.5,
                                      "leading": 14, "textColor": TEAL}, spaceBefore=8, spaceAfter=4,
                             keepWithNext=1),
        "bullet": ParagraphStyle("bullet", **base, leftIndent=5 * mm, bulletIndent=0.5 * mm,
                                 bulletFontName="Poppins-Bold", bulletFontSize=10,
                                 bulletColor=AMBER, spaceAfter=3.2),
        "bullet2": ParagraphStyle("bullet2", **base, leftIndent=10 * mm, bulletIndent=5.5 * mm,
                                  bulletFontName="Poppins-Bold", bulletFontSize=9,
                                  bulletColor=TEAL_LIGHT, spaceAfter=2.4),
        "slot_text": ParagraphStyle("slot_text", **{**base, "fontSize": 9.2, "leading": 13.6}),
        "slot_label": ParagraphStyle("slot_label", **{**base, "fontName": "Poppins-SemiBold",
                                                     "fontSize": 7.3, "leading": 10.5,
                                                     "textColor": TEAL_MID}),
        "th": ParagraphStyle("th", **{**base, "fontName": "Poppins-SemiBold", "fontSize": 7.8,
                                      "leading": 10.5, "textColor": WHITE}),
        "td": ParagraphStyle("td", **{**base, "fontSize": 8.8, "leading": 12.4}),
        "td_r": ParagraphStyle("td_r", **{**base, "fontSize": 8.8, "leading": 12.4, "alignment": TA_RIGHT}),
        "th_r": ParagraphStyle("th_r", **{**base, "fontName": "Poppins-SemiBold", "fontSize": 7.8,
                                          "leading": 10.5, "textColor": WHITE, "alignment": TA_RIGHT}),
        "callout": ParagraphStyle("callout", **{**base, "fontSize": 9.6, "leading": 15}, spaceAfter=3),
        "tile_label": ParagraphStyle("tile_label", **{**base, "fontName": "Poppins-SemiBold", "fontSize": 6.8,
                                                      "leading": 9, "textColor": MUTED}),
        "tile_value": ParagraphStyle("tile_value", fontName="Playfair-Bold", fontSize=15.5, leading=19,
                                     textColor=TEAL),
        "tile_sub": ParagraphStyle("tile_sub", **{**base, "fontSize": 7.2, "leading": 9.5, "textColor": MUTED}),
    }
    return s


# --------------------------------------------------------------------------
# Custom flowables
# --------------------------------------------------------------------------
class SectionHeader(Flowable):
    """Numbered section title with a hairline rule and amber accent."""

    def __init__(self, number: int, title: str, width: float = CONTENT_W):
        super().__init__()
        self.number, self.title, self.width = number, plain(title), width
        self.height = 15 * mm
        self.keepWithNext = True

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(AMBER)
        c.setFont("Poppins-SemiBold", 8)
        c.drawString(0, 6.6 * mm, f"{self.number:02d}")
        c.setFillColor(TEAL)
        size = 17
        while pdfmetrics.stringWidth(self.title, "Playfair-Bold", size) > self.width - 12 * mm and size > 11:
            size -= 0.5
        c.setFont("Playfair-Bold", size)
        c.drawString(9 * mm, 6 * mm, self.title)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.7)
        c.line(0, 1.6 * mm, self.width, 1.6 * mm)
        c.setStrokeColor(AMBER)
        c.setLineWidth(1.6)
        c.line(0, 1.6 * mm, 16 * mm, 1.6 * mm)
        c.restoreState()


class DayHeader(Flowable):
    """Pill with the day number plus the day title."""

    def __init__(self, number: int, title: str, width: float = CONTENT_W):
        super().__init__()
        self.number, self.title, self.width = number, plain(title), width
        self.height = 12 * mm
        self.keepWithNext = True

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        label = f"DAY {self.number}"
        c.setFont("Poppins-SemiBold", 8)
        pill_w = pdfmetrics.stringWidth(label, "Poppins-SemiBold", 8) + 7 * mm
        c.setFillColor(TEAL)
        c.roundRect(0, 2.2 * mm, pill_w, 6.6 * mm, 3.3 * mm, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.drawCentredString(pill_w / 2, 4.4 * mm, label)
        if self.title:
            c.setFillColor(TEAL)
            size = 13.5
            maxw = self.width - pill_w - 6 * mm
            while pdfmetrics.stringWidth(self.title, "Playfair-Bold", size) > maxw and size > 9:
                size -= 0.5
            c.setFont("Playfair-Bold", size)
            c.drawString(pill_w + 4 * mm, 4.2 * mm, self.title)
        c.restoreState()


class BudgetVisual(Flowable):
    """Stacked spend bar, legend and an estimate-vs-budget gauge.

    mode "single": one tier breakdown (+ gauge against the budget when known).
    mode "tiers": budget / mid / comfort bars compared side by side.
    """

    def __init__(self, data: dict, width: float = CONTENT_W):
        super().__init__()
        self.data, self.width = data, width
        self.mode = data["mode"]
        if self.mode == "single":
            n_items = len(data["items"])
            legend_rows = (n_items + 2) // 3
            self.height = ((41.5 if data.get("budget") else 21.5) + legend_rows * 6.2) * mm
        else:
            n_items = len(data["items"])
            legend_rows = (n_items + 2) // 3
            self.height = (8 + 3 * 11.5 + 5 + legend_rows * 6.2 + 3) * mm

    def wrap(self, aw, ah):
        return self.width, self.height

    # -- drawing helpers
    def _stack(self, c, x, y, w, h, items, total, gap=0.5 * mm):
        cx = x
        usable = w - gap * (len(items) - 1)
        for idx, (_, val) in enumerate(items):
            if total <= 0 or val <= 0:
                continue
            sw = usable * (val / total)
            c.setFillColor(SEGMENT_COLORS[idx % len(SEGMENT_COLORS)])
            c.rect(cx, y, sw, h, stroke=0, fill=1)
            cx += sw + gap

    def _legend(self, c, top, items, total, show_values=True):
        col_w = self.width / 3
        for idx, (label, val) in enumerate(items):
            row, col = divmod(idx, 3)
            x = col * col_w
            y = top - row * 6.2 * mm
            c.setFillColor(SEGMENT_COLORS[idx % len(SEGMENT_COLORS)])
            c.roundRect(x, y - 2.6 * mm, 2.6 * mm, 2.6 * mm, 0.6 * mm, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont("Poppins-Medium", 7.6)
            c.drawString(x + 4 * mm, y - 2.2 * mm, label)
            if show_values:
                c.setFillColor(MUTED)
                c.setFont("Poppins", 7.6)
                pct = f"  {val / total * 100:.0f}%" if total else ""
                c.drawString(x + 4 * mm + pdfmetrics.stringWidth(label, "Poppins-Medium", 7.6) + 1.6 * mm,
                             y - 2.2 * mm, inr(val) + pct)

    def draw(self):
        c = self.canv
        c.saveState()
        d = self.data
        top = self.height
        c.setFillColor(MUTED)
        c.setFont("Poppins-SemiBold", 6.8)
        title = d.get("title", "SPEND BREAKDOWN")
        c.saveState()
        t = c.beginText(0, top - 3.2 * mm)
        t.setFont("Poppins-SemiBold", 6.8)
        t.setCharSpace(1.1)
        t.textOut(title.upper())
        c.drawText(t)
        c.restoreState()

        if self.mode == "single":
            items = d["items"]
            total = sum(v for _, v in items)
            bar_y = top - 6.5 * mm - 9 * mm
            self._stack(c, 0, bar_y, self.width, 9 * mm, items, total)
            self._legend(c, bar_y - 3.6 * mm, items, total)
            rows = (len(items) + 2) // 3
            if d.get("budget"):
                budget = d["budget"]
                gy = bar_y - 3.6 * mm - rows * 6.2 * mm - 15 * mm
                c.saveState()
                t = c.beginText(0, gy + 10.4 * mm)
                t.setFont("Poppins-SemiBold", 6.8)
                t.setFillColor(MUTED)
                t.setCharSpace(1.1)
                t.textOut("ESTIMATE VS YOUR BUDGET")
                c.drawText(t)
                c.restoreState()
                c.setFillColor(SAND_DARK)
                c.roundRect(0, gy, self.width, 4.6 * mm, 2.3 * mm, stroke=0, fill=1)
                ratio = min(total / budget, 1) if budget else 0
                over = total > budget
                c.setFillColor(BRICK if over else TEAL)
                if ratio > 0:
                    c.roundRect(0, gy, max(self.width * ratio, 4.6 * mm), 4.6 * mm, 2.3 * mm, stroke=0, fill=1)
                c.setFillColor(INK)
                c.setFont("Poppins-SemiBold", 8)
                c.drawString(0, gy - 4.2 * mm, f"Estimated {inr(total)}  ({total / budget * 100:.0f}% of {inr(budget)})")
                c.setFont("Poppins", 7.6)
                c.setFillColor(BRICK if over else TEAL_MID)
                if over:
                    msg = f"Over budget by {inr(total - budget)}"
                else:
                    extra = d.get("not_included") or "flights and extras"
                    msg = f"{inr(budget - total)} left for {extra}"
                c.drawRightString(self.width, gy - 4.2 * mm, msg)
        else:
            tiers = d["tiers"]
            max_total = max(t["total"] for t in tiers) or 1
            label_w, total_w = 22 * mm, 24 * mm
            bar_w = self.width - label_w - total_w
            y = top - 6.5 * mm - 7.5 * mm
            for tier in tiers:
                c.setFillColor(INK)
                c.setFont("Poppins-SemiBold", 8)
                c.drawString(0, y + 2.2 * mm, tier["name"])
                seg_total = tier["total"]
                self._stack(c, label_w, y, bar_w * (seg_total / max_total), 7.5 * mm, tier["items"], seg_total,
                            gap=0.4 * mm)
                c.setFillColor(TEAL)
                c.setFont("Poppins-SemiBold", 8.4)
                c.drawRightString(self.width, y + 2.2 * mm, inr(seg_total))
                y -= 11.5 * mm
            self._legend(c, y + 4.2 * mm, d["items"], 0, show_values=False)
        c.restoreState()


# --------------------------------------------------------------------------
# Table / callout builders
# --------------------------------------------------------------------------
_NUMERIC_RE = re.compile(r"^[\s~\u2248+\-]*[\u20b9$\u20ac\u00a3]?\s*[\d.,]+\s*(%|/-)?\s*$")


def _is_numeric(cell: str) -> bool:
    c = plain(cell)
    return bool(c) and bool(_NUMERIC_RE.match(c.replace("Rs", "").replace("INR", "").strip()))


def build_table(rows: list[list[str]], st: dict) -> Table:
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    header, body = rows[0], rows[1:]
    numeric_cols = set()
    for ci in range(1, ncols):
        vals = [r[ci] for r in body if r[ci].strip()]
        if vals and all(_is_numeric(v) for v in vals):
            numeric_cols.add(ci)

    data = [[Paragraph(inline(h).upper() if len(plain(h)) < 24 else inline(h),
                       st["th_r"] if ci in numeric_cols else st["th"])
             for ci, h in enumerate(header)]]
    total_rows, remaining_rows = [], []
    for ri, r in enumerate(body, start=1):
        first = plain(r[0]).lower()
        is_total = first.startswith("total") or first.startswith("**total") or "total" == first.strip(" :")
        is_rem = first.startswith("remaining") or first.startswith("left")
        if is_total:
            total_rows.append(ri)
        if is_rem:
            remaining_rows.append(ri)
        row = []
        for ci, cell in enumerate(r):
            txt = inline(cell)
            if (is_total or is_rem) and "<b>" not in txt:
                txt = f"<b>{txt}</b>"
            row.append(Paragraph(txt, st["td_r"] if ci in numeric_cols else st["td"]))
        data.append(row)

    # column widths: proportional to content, first column gets the extra room
    lens = []
    for ci in range(ncols):
        longest = max(len(plain(r[ci])) for r in rows)
        lens.append(min(max(longest, 6), 46))
    if ncols == 2:
        widths = [CONTENT_W * 0.62, CONTENT_W * 0.38]
    else:
        total_len = sum(lens)
        widths = [max(CONTENT_W * l / total_len, 18 * mm) for l in lens]
        scale = CONTENT_W / sum(widths)
        widths = [w * scale for w in widths]

    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
    ]
    for ri in range(1, len(data)):
        if ri % 2 == 0:
            style.append(("BACKGROUND", (0, ri), (-1, ri), SAND))
    for ri in total_rows:
        style += [("LINEABOVE", (0, ri), (-1, ri), 1, TEAL), ("BACKGROUND", (0, ri), (-1, ri), SAND_DARK)]
    for ri in remaining_rows:
        style += [("BACKGROUND", (0, ri), (-1, ri), colors.HexColor("#FBEBD3"))]
    t.setStyle(TableStyle(style))
    return t


def callout(flowables: list, accent=AMBER, bg=SAND) -> Table:
    inner = Table([[flowables]], colWidths=[CONTENT_W - 6 * mm])
    inner.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    outer = Table([[inner]], colWidths=[CONTENT_W])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
    ]))
    return outer


def slots_table(slots: list[tuple[str, str]], st: dict) -> Table:
    rows, styles = [], []
    for ri, (label, text) in enumerate(slots):
        key = re.split(r"[\s(/&-]", label.lower())[0]
        color = SLOT_COLORS.get(key, MUTED if key in ("note", "tip", "optional") else TEAL_MID)
        lab_style = ParagraphStyle(f"lab{ri}", parent=st["slot_label"], textColor=color)
        rows.append([Paragraph(inline(label).upper(), lab_style), Paragraph(inline(text), st["slot_text"])])
    t = Table(rows, colWidths=[27 * mm, CONTENT_W - 27 * mm])
    styles = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 4 * mm),
        ("LEFTPADDING", (1, 0), (1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.1 * mm),
        ("LINEBEFORE", (0, 0), (0, -1), 1.4, TEAL_LIGHT),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
    ]
    t.setStyle(TableStyle(styles))
    return t


def stat_tiles(tiles: list[tuple[str, str, str]], st: dict) -> Table:
    cells = []
    for label, value, sub in tiles:
        cell = [Paragraph(label.upper(), st["tile_label"]), Spacer(1, 1.2 * mm),
                Paragraph(sanitize(value).replace("&", "&amp;"), st["tile_value"])]
        if sub:
            cell.append(Paragraph(sanitize(sub).replace("&", "&amp;"), st["tile_sub"]))
        cells.append(cell)
    gap = 3 * mm
    n = len(cells)
    w = (CONTENT_W - gap * (n - 1)) / n
    data, widths = [[]], []
    for i, cell in enumerate(cells):
        data[0].append(cell)
        widths.append(w)
        if i < n - 1:
            data[0].append("")
            widths.append(gap)
    t = Table(data, colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3.2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
             ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm)]
    for i in range(0, len(widths), 2):
        style += [("BACKGROUND", (i, 0), (i, 0), SAND), ("LINEABOVE", (i, 0), (i, 0), 1.6, AMBER)]
    for i in range(1, len(widths), 2):
        style += [("LEFTPADDING", (i, 0), (i, 0), 0), ("RIGHTPADDING", (i, 0), (i, 0), 0)]
    t.setStyle(TableStyle(style))
    return t


# --------------------------------------------------------------------------
# Budget data extraction
# --------------------------------------------------------------------------
_BREAKDOWN_LABELS = {
    "stay": "Stay", "food": "Food", "local_transport": "Local transport",
    "entry_fees": "Entry fees", "misc_and_tips": "Misc and tips",
}


def _number(text: str):
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", plain(text).replace("\u20b9", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _items_from_breakdown(b: dict) -> list[tuple[str, float]]:
    return [(_BREAKDOWN_LABELS.get(k, k.replace("_", " ").title()), float(v)) for k, v in b.items() if v]


def budget_data_from_meta(meta: dict | None):
    est = (meta or {}).get("estimate") or {}
    if est.get("breakdown_inr"):
        return {
            "mode": "single",
            "title": f"Spend breakdown - {str(est.get('tier_used', '')).title()} tier".replace(" -  ", " "),
            "items": _items_from_breakdown(est["breakdown_inr"]),
            "budget": est.get("budget_inr") or 0,
            "not_included": est.get("not_included") or "",
        }
    if est.get("tier_options_inr"):
        tiers = []
        for name in ("budget", "mid", "comfort"):
            t = est["tier_options_inr"].get(name)
            if t:
                tiers.append({"name": name.title(), "items": _items_from_breakdown(t["breakdown"]),
                              "total": float(t["total"])})
        if tiers:
            return {"mode": "tiers", "title": "Compare the three comfort levels", "tiers": tiers,
                    "items": tiers[0]["items"]}
    return None


def budget_data_from_table(rows: list[list[str]]):
    """Fallback: pull a breakdown out of the markdown budget table."""
    if not rows or len(rows[0]) != 2:
        return None
    keys = {"stay": "Stay", "hotel": "Stay", "accommodation": "Stay", "food": "Food", "transport": "Local transport",
            "entry": "Entry fees", "ticket": "Entry fees", "misc": "Misc and tips", "tips": "Misc and tips"}
    items, total, remaining = {}, None, None
    for r in rows[1:]:
        if len(r) < 2:
            continue
        label = plain(r[0]).lower()
        val = _number(r[1])
        if val is None:
            continue
        if label.startswith("total"):
            total = val
        elif label.startswith("remaining") or label.startswith("left"):
            remaining = val
        else:
            for k, name in keys.items():
                if k in label:
                    items[name] = items.get(name, 0) + val
                    break
    if len(items) >= 3:
        data = {"mode": "single", "title": "Spend breakdown", "items": list(items.items()), "budget": 0,
                "not_included": ""}
        if total and remaining is not None:
            data["budget"] = total + remaining
        return data
    return None


# --------------------------------------------------------------------------
# Page furniture
# --------------------------------------------------------------------------
def _make_canvas_class(ctx: dict):
    class FurnishedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                self._furniture(total)
                super().showPage()
            super().save()

        # -- drawing
        def _furniture(self, total):
            n = self._pageNumber
            if n == 1:
                self._hero()
            else:
                self._running_header()
            self._footer(n, total)

        def _hero(self):
            c = self
            c.saveState()
            c.setFillColor(TEAL)
            c.rect(0, PAGE_H - HERO_H, PAGE_W, HERO_H, stroke=0, fill=1)
            # restrained concentric arcs, top right
            c.setStrokeColor(WHITE)
            c.setLineWidth(0.8)
            c.setStrokeAlpha(0.10)
            for r in (30, 46, 62, 78):
                c.circle(PAGE_W - 12 * mm, PAGE_H - 6 * mm, r * mm, stroke=1, fill=0)
            c.setStrokeAlpha(1)
            # accent bar
            c.setFillColor(AMBER)
            c.rect(MARGIN_X, PAGE_H - HERO_H, 22 * mm, 1.6 * mm, stroke=0, fill=1)
            # kicker
            c.saveState()
            t = c.beginText(MARGIN_X, PAGE_H - 17 * mm)
            t.setFont("Poppins-SemiBold", 7.6)
            t.setFillColor(AMBER_LIGHT)
            t.setCharSpace(2.2)
            t.textOut(ctx["kicker"].upper())
            c.drawText(t)
            c.restoreState()
            # title
            title = ctx["title"]
            size = 36
            maxw = PAGE_W - 2 * MARGIN_X - 10 * mm
            while pdfmetrics.stringWidth(title, "Playfair-Bold", size) > maxw and size > 20:
                size -= 1
            c.setFillColor(WHITE)
            c.setFont("Playfair-Bold", size)
            c.drawString(MARGIN_X, PAGE_H - 33 * mm, title)
            # subtitle (wrap to two lines)
            c.setFillColor(colors.HexColor("#CFE3E7"))
            lines = _wrap(ctx["subtitle"], "Poppins-Light", 9.6, PAGE_W - 2 * MARGIN_X - 30 * mm, max_lines=2)
            y = PAGE_H - 42 * mm
            c.setFont("Poppins-Light", 9.6)
            for ln in lines:
                c.drawString(MARGIN_X, y, ln)
                y -= 5.2 * mm
            # date
            c.setFont("Poppins", 7.2)
            c.setFillColor(TEAL_LIGHT)
            c.drawString(MARGIN_X, PAGE_H - HERO_H + 6 * mm, f"Prepared {ctx['date']}")
            c.restoreState()

        def _running_header(self):
            c = self
            c.saveState()
            t = c.beginText(MARGIN_X, PAGE_H - 13 * mm)
            t.setFont("Poppins-SemiBold", 7)
            t.setFillColor(AMBER)
            t.setCharSpace(1.6)
            t.textOut(("Travel plan  /  " + ctx["title"]).upper())
            c.drawText(t)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.6)
            c.line(MARGIN_X, PAGE_H - 16 * mm, PAGE_W - MARGIN_X, PAGE_H - 16 * mm)
            c.restoreState()

        def _footer(self, n, total):
            c = self
            c.saveState()
            c.setStrokeColor(RULE)
            c.setLineWidth(0.6)
            c.line(MARGIN_X, 14 * mm, PAGE_W - MARGIN_X, 14 * mm)
            c.setFont("Poppins", 6.6)
            c.setFillColor(MUTED)
            c.drawString(MARGIN_X, 9.6 * mm,
                         "Prepared by Travel Planner Agent. Prices are estimates; confirm fares, fees and opening hours before booking.")
            c.setFont("Poppins-SemiBold", 7)
            c.setFillColor(TEAL)
            c.drawRightString(PAGE_W - MARGIN_X, 9.6 * mm, f"{n} / {total}")
            c.restoreState()

    return FurnishedCanvas


def _wrap(text: str, font: str, size: float, width: float, max_lines: int = 2) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while pdfmetrics.stringWidth(last + "...", font, size) > width and len(last) > 4:
            last = last[:-1]
        lines[-1] = last.rstrip(" ,.;:") + "..."
    return lines


# --------------------------------------------------------------------------
# Main builder
# --------------------------------------------------------------------------
def looks_like_itinerary(md: str) -> bool:
    if not md or len(md) < 300:
        return False
    low = md.lower()
    return bool(re.search(r"\bday\s*1\b", low)) or "itinerary" in low


def _title_case_city(city: str) -> str:
    return " ".join(w.capitalize() if w.islower() else w for w in (city or "").split())


def _derive_header(md_blocks, meta: dict | None):
    meta = meta or {}
    city = _title_case_city(str(meta.get("city") or "")).strip()
    if not city:
        for b in md_blocks:
            if b[0] == "h" and b[1] == 1:
                city = plain(b[2])
                break
    days = meta.get("days") or 0
    if not city:
        city = "Your Trip Plan"
    kicker = f"{int(days)}-day itinerary" if days else "Travel itinerary"

    parts = []
    if days:
        parts.append(f"{int(days)} day{'s' if int(days) != 1 else ''}")
    tr = meta.get("travelers")
    if tr:
        parts.append(f"{int(tr)} traveller{'s' if int(tr) != 1 else ''}")
    if meta.get("budget_inr"):
        parts.append(f"Budget {inr(meta['budget_inr'])}")
    interests = meta.get("interests")
    if interests:
        parts.append("Interests: " + (interests if isinstance(interests, str) else ", ".join(interests)))
    subtitle = "  \u00b7  ".join(parts)
    if not subtitle:
        for idx, b in enumerate(md_blocks):
            if b[0] == "h" and "summary" in plain(b[2]).lower():
                for nb in md_blocks[idx + 1:]:
                    if nb[0] == "p":
                        subtitle = plain(nb[1])
                        break
                    if nb[0] == "h":
                        break
                break
    return city, kicker, subtitle or "A personalised day-by-day plan with budget estimate"


def _derive_tiles(meta: dict | None, st):
    meta = meta or {}
    est = meta.get("estimate") or {}
    tiles = []
    if meta.get("days"):
        d = int(meta["days"])
        tiles.append(("Duration", f"{d} day{'s' if d != 1 else ''}", f"{max(d - 1, 1)} night{'s' if d - 1 != 1 else ''}"))
    if meta.get("travelers"):
        n = int(meta["travelers"])
        tiles.append(("Travellers", str(n), "sharing rooms" if n > 1 else "solo trip"))
    if meta.get("budget_inr"):
        tiles.append(("Your budget", inr(meta["budget_inr"]), "total, whole trip"))
    if est.get("estimated_total_inr"):
        tiles.append(("Estimated spend", inr(est["estimated_total_inr"]),
                      f"{str(est.get('tier_used', '')).title()} tier, excl. flights" if est.get("international")
                      else f"{str(est.get('tier_used', '')).title()} tier"))
    elif est.get("tier_options_inr", {}).get("mid"):
        tiles.append(("Estimate (mid)", inr(est["tier_options_inr"]["mid"]["total"]),
                      "excl. flights and visa" if est.get("international") else "no budget set"))
    return stat_tiles(tiles, st) if len(tiles) >= 2 else None


def _collect_until_heading(blocks, start):
    out, i = [], start
    while i < len(blocks) and blocks[i][0] != "h":
        out.append(blocks[i])
        i += 1
    return out, i


def _bullets(items, st, numbered=False):
    flow = []
    for n, (level, txt) in enumerate(items, start=1):
        style = st["bullet2" if level else "bullet"]
        bullet = f"{n}." if numbered else ("\u2013" if level else "\u2022")
        flow.append(Paragraph(inline(txt), style, bulletText=bullet))
    return flow


def _render_day_body(blocks, st):
    """Turn the blocks under a day heading into slot rows and bullets."""
    flow, slots = [], []

    def flush():
        nonlocal slots
        if slots:
            flow.append(slots_table(slots, st))
            flow.append(Spacer(1, 3 * mm))
            slots = []

    for b in blocks:
        if b[0] in ("ul", "ol"):
            for level, txt in b[1]:
                m = match_slot(txt) if level == 0 else None
                if m:
                    slots.append(m)
                else:
                    flush()
                    flow += _bullets([(level, txt)], st)
        elif b[0] == "p":
            m = match_slot(b[1])
            if m:
                slots.append(m)
            else:
                flush()
                flow.append(Paragraph(inline(b[1]), st["body"]))
        elif b[0] == "quote":
            flush()
            flow.append(Paragraph(inline(b[1]), st["muted"]))
        elif b[0] == "table":
            flush()
            flow.append(build_table(b[1], st))
            flow.append(Spacer(1, 3 * mm))
    flush()
    return flow


def build_itinerary_pdf(markdown_text: str, meta: dict | None = None) -> bytes:
    """Render the agent's markdown answer as a styled A4 PDF and return bytes."""
    _register_fonts()
    st = _styles()
    blocks = parse_markdown(markdown_text or "")
    city, kicker, subtitle = _derive_header(blocks, meta)
    ctx = {"title": sanitize(city), "kicker": kicker, "subtitle": sanitize(subtitle),
           "date": datetime.date.today().strftime("%d %B %Y").lstrip("0")}

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=22 * mm, bottomMargin=18 * mm,
        title=f"{ctx['title']} - Travel Itinerary", author="Travel Planner Agent",
        subject="Personalised travel itinerary", creator="Travel Planner Agent",
    )
    first = Frame(MARGIN_X, 18 * mm, CONTENT_W, PAGE_H - HERO_H - 8 * mm - 18 * mm, id="first",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    later = Frame(MARGIN_X, 18 * mm, CONTENT_W, PAGE_H - 22 * mm - 18 * mm, id="later",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="first", frames=[first]), PageTemplate(id="later", frames=[later])])

    story: list = [NextPageTemplate("later")]
    tiles = _derive_tiles(meta, st)
    if tiles is not None:
        story += [tiles, Spacer(1, 7 * mm)]
    else:
        story.append(Spacer(1, 2 * mm))

    budget_visual_data = budget_data_from_meta(meta)
    budget_visual_added = False
    section_no = 0
    i = 0
    while i < len(blocks):
        b = blocks[i]
        kind = b[0]

        if kind == "h":
            level, text = b[1], b[2]
            day = match_day(text)
            low = plain(text).lower()
            if day:
                body, nxt = _collect_until_day(blocks, i + 1)
                story.append(CondPageBreak(45 * mm))
                story.append(DayHeader(day[0], day[1]))
                story += _render_day_body(body, st)
                i = nxt
                continue
            if level == 1:
                i += 1
                continue
            if level >= 3:
                story.append(Paragraph(inline(text), st["h3"]))
                i += 1
                continue
            body, nxt = _collect_until_heading(blocks, i + 1)
            section_no += 1
            story.append(CondPageBreak(55 * mm))
            story.append(SectionHeader(section_no, text))
            if "summary" in low:
                paras = [Paragraph(inline(x[1]), st["callout"]) for x in body if x[0] == "p"]
                paras += [p for x in body if x[0] in ("ul", "ol") for p in _bullets(x[1], st)]
                if paras:
                    story += [callout(paras), Spacer(1, 5 * mm)]
            elif "tip" in low:
                paras = []
                for x in body:
                    if x[0] in ("ul", "ol"):
                        paras += _bullets(x[1], st, numbered=(x[0] == "ol"))
                    elif x[0] == "p":
                        paras.append(Paragraph(inline(x[1]), st["body"]))
                if paras:
                    story += [callout(paras, accent=TEAL), Spacer(1, 4 * mm)]
            elif "itinerary" in low or "day-wise" in low or "day wise" in low:
                # days appear as sub-blocks (bold lines or h3); handled by the day matcher below
                story += _render_section_with_days(body, st)
            else:
                is_budget = "budget" in low or "cost" in low
                flow, added = _render_generic(body, st, is_budget, budget_visual_data, budget_visual_added)
                story += flow
                budget_visual_added = budget_visual_added or added
            i = nxt
            continue

        # blocks outside any heading
        if kind == "p":
            day = match_day(b[1])
            if day:
                body, nxt = _collect_until_day(blocks, i + 1)
                story += [CondPageBreak(45 * mm), DayHeader(day[0], day[1])] + _render_day_body(body, st)
                i = nxt
                continue
            story.append(Paragraph(inline(b[1]), st["body"]))
        elif kind in ("ul", "ol"):
            story += _bullets(b[1], st, numbered=(kind == "ol"))
        elif kind == "table":
            story += [build_table(b[1], st), Spacer(1, 4 * mm)]
        elif kind == "quote":
            story.append(callout([Paragraph(inline(b[1]), st["callout"])]))
        i += 1

    doc.build(story, canvasmaker=_make_canvas_class(ctx))
    return buf.getvalue()


def _collect_until_day(blocks, start):
    """Collect blocks up to the next heading or day-marker paragraph."""
    out, i = [], start
    while i < len(blocks):
        b = blocks[i]
        if b[0] == "h":
            break
        if b[0] == "p" and match_day(b[1]) and len(plain(b[1])) < 90:
            break
        out.append(b)
        i += 1
    return out, i


def _render_section_with_days(body, st):
    flow, i = [], 0
    while i < len(body):
        b = body[i]
        if b[0] == "p" and match_day(b[1]) and len(plain(b[1])) < 90:
            day = match_day(b[1])
            sub, nxt = _collect_until_day(body, i + 1)
            flow += [CondPageBreak(45 * mm), DayHeader(day[0], day[1])] + _render_day_body(sub, st)
            i = nxt
            continue
        if b[0] == "h" and b[1] >= 3 and match_day(b[2]):
            day = match_day(b[2])
            sub, nxt = _collect_until_day(body, i + 1)
            flow += [CondPageBreak(45 * mm), DayHeader(day[0], day[1])] + _render_day_body(sub, st)
            i = nxt
            continue
        flow += _render_day_body([b], st)
        i += 1
    return flow


def _render_generic(body, st, is_budget, visual_data, visual_added):
    flow, added = [], False
    for b in body:
        k = b[0]
        if k == "p":
            txt = b[1]
            if re.fullmatch(r"\*[^*].*[^*]\*", txt) or re.fullmatch(r"_[^_].*[^_]_", txt):
                flow.append(Paragraph(inline(txt), st["muted"]))
            else:
                flow.append(Paragraph(inline(txt), st["body"]))
        elif k in ("ul", "ol"):
            flow += _bullets(b[1], st, numbered=(k == "ol"))
            flow.append(Spacer(1, 2 * mm))
        elif k == "table":
            flow += [build_table(b[1], st), Spacer(1, 5 * mm)]
            if is_budget and not (visual_added or added):
                data = visual_data or budget_data_from_table(b[1])
                if data:
                    flow += [BudgetVisual(data), Spacer(1, 5 * mm)]
                    added = True
        elif k == "quote":
            flow += [callout([Paragraph(inline(b[1]), st["callout"])]), Spacer(1, 3 * mm)]
        elif k == "h":
            flow.append(Paragraph(inline(b[2]), st["h3"]))
    return flow, added


def suggest_filename(markdown_text: str = "", meta: dict | None = None) -> str:
    meta = meta or {}
    city = str(meta.get("city") or "").strip()
    if not city:
        m = re.search(r"^#\s+(.+)$", markdown_text or "", re.M)
        city = plain(m.group(1)) if m else "trip"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", city).strip("-") or "trip"
    days = meta.get("days")
    return f"{slug}-{int(days)}-day-itinerary.pdf" if days else f"{slug}-itinerary.pdf"
