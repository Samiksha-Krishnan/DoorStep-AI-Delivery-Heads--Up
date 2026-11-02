"""Message parser (regex baseline). Replace parse_message() with spaCy NER / DistilBERT and compare F1."""
import re
from datetime import datetime, timedelta
from ml import COURIERS

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _t(h, m, ap):
    h, m = int(h), int(m or 0)
    if ap:
        ap = ap.lower()
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
    return f"{h:02d}:{m:02d}"


def parse_message(text, today=None):
    today = today or datetime.now()
    low, out = text.lower(), {}
    for c in COURIERS + ["myntra", "meesho", "dtdc", "swiggy", "zomato"]:
        if c in low or c.replace(" ", "") in low:
            out["courier"] = c.title(); break
    m = re.search(r"(?:otp|code|pin)\D{0,15}(\d{4,6})", text, re.I)
    if m: out["otp"] = m.group(1)
    m = re.search(r"(?:package|parcel|order|shipment|item)(?:\s+(?:for|of|containing))?[:\s]+[\"“']?"
                  r"([A-Za-z0-9][^.,\"”\n]{2,40}?)(?:\s+(?:will|is|has|was|arrives|arriving|out)\b|[.,\"”\n]|$)", text, re.I)
    if m: out["item"] = m.group(1).strip()
    d = None
    if re.search(r"\btoday\b", low): d = today
    elif re.search(r"\btomorrow\b", low): d = today + timedelta(days=1)
    else:
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s-]+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", low)
        if m:
            d = datetime(today.year, MONTHS.index(m.group(2)) + 1, int(m.group(1)))
            if d.date() < today.date(): d = d.replace(year=today.year + 1)
        else:
            m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-]\d{2,4})?\b", low)
            if m: d = datetime(today.year, int(m.group(2)), int(m.group(1)))
    if d: out["date"] = d.strftime("%Y-%m-%d")
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|–|to|and)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text, re.I)
    if m:
        out["from"] = _t(m.group(1), m.group(2), m.group(3) or m.group(6))
        out["to"] = _t(m.group(4), m.group(5), m.group(6))
    else:
        m = re.search(r"by\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", low)
        if m:
            to = _t(m.group(1), m.group(2), m.group(3))
            out["to"], out["from"] = to, f"{max(int(to[:2]) - 4, 0):02d}{to[2:]}"
    out["status"] = "trouble" if re.search(r"delay|resched|attempt|unable|failed|postpone", low) \
        else "ofd" if "out for delivery" in low else "ok"
    return out
