import json
import re
from pathlib import Path

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/schemes")

SCHEME_CODES = {
    "pmkisan": "pmkisan",
    "pmjay": "pmjay",
    "nsap_oldage": "nsap",
    "pmayg": "pmayg",
    "tn_oldage": "tnoap",
    "tn_cmchis": "cmchis",
}

SECTION_PATTERN = re.compile(
    r"\[SECTION\s+([A-Za-z0-9.]+)\]\s*(.*?)\n(.*?)(?=\n\[SECTION|\Z)",
    re.S,
)

TYPE_KEYWORDS = (
    ("exclusion", "exclusion"),
    ("benefit amount", "benefit_amount"),
    ("unit assistance", "benefit_amount"),
    ("eligib", "eligibility"),
    ("universe of eligible", "eligibility"),
)


def infer_clause_type(section_title: str) -> str:
    title_lower = section_title.lower()
    for keyword, clause_type in TYPE_KEYWORDS:
        if keyword in title_lower:
            return clause_type
    return "general"


def parse_header(text: str) -> dict:
    scheme_match = re.search(r"^SCHEME:\s*(.+)$", text, re.M)
    state_match = re.search(r"^STATE:\s*(.+)$", text, re.M)
    last_verified_match = re.search(r"^LAST_VERIFIED:\s*(.+)$", text, re.M)
    return {
        "scheme_name": scheme_match.group(1).strip() if scheme_match else "",
        "state": state_match.group(1).strip() if state_match else "",
        "last_verified": last_verified_match.group(1).strip() if last_verified_match else "",
    }


def chunk_file(raw_path: Path) -> dict:
    stem = raw_path.stem
    code = SCHEME_CODES[stem]
    content = raw_path.read_text(encoding="utf-8")
    header = parse_header(content)

    clauses = []
    for match in SECTION_PATTERN.finditer(content):
        section_number, title, body = match.groups()
        clause_id = f"{code}-{section_number}"
        clauses.append(
            {
                "clause_id": clause_id,
                "section_title": title.strip(),
                "clause_type": infer_clause_type(title.strip()),
                "text": " ".join(body.strip().split()),
            }
        )

    scheme = {
        "scheme_id": code,
        "scheme_name": header["scheme_name"],
        "state": header["state"],
        "clauses": clauses,
    }
    if header["last_verified"]:
        scheme["last_verified"] = header["last_verified"]
    return scheme


def chunk_all(raw_dir: Path = RAW_DIR, out_dir: Path = OUT_DIR) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for raw_path in sorted(raw_dir.glob("*.txt")):
        scheme = chunk_file(raw_path)
        out_path = out_dir / f"{scheme['scheme_id']}.json"
        out_path.write_text(
            json.dumps(scheme, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        total += len(scheme["clauses"])
    return total
