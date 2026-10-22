from __future__ import annotations

import json

import pytest


def make_pdf(pages: list[str]) -> bytes:
    """Build a minimal text PDF by hand so tests need no PDF-writing dependency."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        lines = [l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for l in text.split("\n")]
        ops = "BT /F1 10 Tf 13 TL 40 800 Td " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
        objects.append(f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream")
        content_ref = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents {content_ref} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


FILLER = "\n".join(["This page is part of the offer document and contains standard disclosure text."] * 12)


def filing_pages(company: str, auditor_resigned: bool = True) -> list[str]:
    """A 14-page offer document: cover, contents, then sections with printed page numbers at the top."""
    toc = "\n".join([
        "TABLE OF CONTENTS",
        "DEFINITIONS AND ABBREVIATIONS ........ 1",
        "RISK FACTORS ........ 2",
        "SUMMARY OF FINANCIAL INFORMATION ........ 3",
        "SUMMARY OF RELATED PARTY TRANSACTIONS ........ 4",
        "GENERAL INFORMATION ........ 5",
        "OBJECTS OF THE ISSUE ........ 6",
        "OUR MANAGEMENT ........ 7",
        "OUR PROMOTERS AND PROMOTER GROUP ........ 8",
        "GROUP COMPANIES ........ 9",
        "RESTATED FINANCIAL INFORMATION ........ 10",
        "OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS ........ 11",
        "DECLARATION ........ 12",
    ])
    body = {
        1: "DEFINITIONS AND ABBREVIATIONS\n" + FILLER,
        2: "RISK FACTORS\n" + FILLER,
        3: "SUMMARY OF FINANCIAL INFORMATION\nRevenue from operations 2,400.00 1,800.00\nNet cash from operating activities (120.50) 80.00\nProfit after tax 210.00 150.00",
        4: f"SUMMARY OF RELATED PARTY TRANSACTIONS\nSale of product\nRiver Pipes Private Limited Entity under common control 240.00 10.00\nPurchase of the product\nHill Machines Private Limited Entity under common control 120.00 5.00\nSalary\nAsha Rao Director 12.00 0.50",
        5: "GENERAL INFORMATION\nBoard of Directors\nAsha Rao Managing Director 01174144\nBook Running Lead Manager\nNorthgate Capital Markets Limited\nSEBI registration number: INM000000016\nStatutory Auditors\nKumar and Associates\n"
           + ("Kumar and Associates May 30, 2024 Appointment due to casual vacancy\nOld Audit LLP May 23, 2024 Resignation due to pre-occupation in other assignments" if auditor_resigned else "There has been no change in the statutory auditors."),
        6: "OBJECTS OF THE ISSUE\nFunding working capital requirements of our Company 1,150.00\nNone of the Net Proceeds will be paid to our Promoters, Directors or Group Companies.",
        7: "OUR MANAGEMENT\nAsha Rao is the Managing Director. DIN 01174144. Other directorships: River Pipes Private Limited",
        8: f"OUR PROMOTERS AND PROMOTER GROUP\nAsha Rao is the Promoter of our Company and holds 72.50% of the paid-up equity share capital.\nThe permanent account number of Asha Rao is AAJPS3762N.",
        9: "GROUP COMPANIES\n1. River Pipes Private Limited;\n2. Hill Machines Private Limited.",
        10: "RESTATED FINANCIAL INFORMATION\n" + FILLER,
        11: "OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS\nOne criminal proceeding has been filed against our Promoter Asha Rao under Section 138.",
        12: "DECLARATION\n" + FILLER,
    }
    return [f"{company.upper()} LIMITED\nRED HERRING PROSPECTUS", toc] + [f"{n}\n{body[n]}" for n in range(1, 13)]


def responses(company: str, auditor_resigned: bool = True) -> dict:
    """Canned model output per section, as the real extractor would return it (pages are PDF pages = printed + 2)."""
    return {
        "general_information": {
            "issuer": {"name": f"{company} Limited", "cin": None, "page": 7, "quote": "GENERAL INFORMATION"},
            "directors": [{"name": "Asha Rao", "din": "01174144", "designation": "Managing Director", "page": 7, "quote": "Asha Rao Managing Director 01174144"}],
            "intermediaries": [
                {"role": "lead_manager", "name": "Northgate Capital Markets Limited", "sebi_registration": "INM000000016", "page": 7,
                 "quote": "SEBI registration number: INM000000016"},
                {"role": "statutory_auditor", "name": "Kumar and Associates", "page": 7, "quote": "Statutory Auditors Kumar and Associates"},
            ],
            "auditor_changes": [{"auditor": "Old Audit LLP", "date": "May 23, 2024", "reason": "Resignation due to pre-occupation in other assignments",
                                 "page": 7, "quote": "Old Audit LLP May 23, 2024 Resignation due to pre-occupation"}] if auditor_resigned else [],
        },
        "management": {"directors": [{"name": "Asha Rao", "din": "01174144", "designation": "Managing Director",
                                      "other_directorships": ["River Pipes Private Limited"], "page": 9,
                                      "quote": "Other directorships: River Pipes Private Limited"}]},
        "promoters": {"promoters": [{"name": "Asha Rao", "type": "individual", "din": None, "shareholding_pct": 72.5, "page": 10,
                                     "quote": "holds 72.50% of the paid-up equity share capital"}],
                      "combined_shareholding_pct": {"value": 72.5, "page": 10, "quote": "holds 72.50% of the paid-up equity share capital"},
                      "promoter_group_entities": []},
        "group_companies": {"group_companies": [
            {"name": "River Pipes Private Limited", "page": 11, "quote": "1. River Pipes Private Limited;"},
            {"name": "Hill Machines Pvt. Ltd.", "page": 11, "quote": "2. Hill Machines Private Limited."}]},
        "rpt_summary": {"unit": "million", "fiscal": "Fiscal 2026", "transactions": [
            {"party": "River Pipes Private Limited", "relationship": "Entity under common control", "nature": "Sale of product",
             "amount": 240.0, "pct_of_revenue": 10.0, "page": 6, "quote": "River Pipes Private Limited Entity under common control 240.00 10.00"},
            {"party": "Hill Machines Private Limited", "relationship": "Entity under common control", "nature": "Purchase of the product",
             "amount": 120.0, "pct_of_revenue": 5.0, "page": 6, "quote": "Hill Machines Private Limited Entity under common control 120.00 5.00"},
            {"party": "Asha Rao", "relationship": "Director", "nature": "Salary", "amount": 12.0, "pct_of_revenue": 0.5, "page": 6,
             "quote": "Asha Rao Director 12.00 0.50"}]},
        "litigation": {"items": [{"party_type": "promoter", "direction": "against", "category": "criminal", "count": 1, "amount": None,
                                  "unit": None, "summary": "Section 138 complaint", "page": 13,
                                  "quote": "One criminal proceeding has been filed against our Promoter Asha Rao"}]},
        "objects": {"unit": "million", "objects": [{"purpose": "Funding working capital requirements", "amount": 1150.0, "page": 8,
                                                    "quote": "Funding working capital requirements of our Company 1,150.00"}],
                    "related_party_payments": [],
                    "no_related_party_statement": {"page": 8, "quote": "None of the Net Proceeds will be paid to our Promoters"}},
        "financial_summary": {"unit": "million", "metrics": [
            {"metric": "revenue_from_operations", "fiscal": "Fiscal 2026", "value": 2400.0, "page": 5, "quote": "Revenue from operations 2,400.00"},
            {"metric": "profit_after_tax", "fiscal": "Fiscal 2026", "value": 210.0, "page": 5, "quote": "Profit after tax 210.00"},
            {"metric": "net_cash_from_operating_activities", "fiscal": "Fiscal 2026", "value": -120.5, "page": 5,
             "quote": "Net cash from operating activities (120.50)"}]},
    }


MARKERS = {
    '"intermediaries"': "general_information", '"other_directorships"': "management", '"promoter_group_entities"': "promoters",
    '"group_companies": [{"name"': "group_companies", '"transactions"': "rpt_summary", '"party_type"': "litigation",
    '"related_party_payments"': "objects", '"metrics"': "financial_summary",
}


class FakeLLM:
    """Answers extraction prompts with canned JSON for one filing; chat prompts cite the first source."""

    def __init__(self, canned: dict):
        self.canned = canned
        self.calls = 0

    def complete(self, system, user, *, temperature=0.2, max_tokens=1024, **_):
        self.calls += 1
        if user.startswith("Company:"):
            return "The filing lists a lead manager [S1]. Also [S99]."
        section = next(v for k, v in MARKERS.items() if k in system)
        return json.dumps(self.canned[section])


@pytest.fixture
def acme_pdf(tmp_path):
    path = tmp_path / "acme-agro-rhp.pdf"
    path.write_bytes(make_pdf(filing_pages("Acme Agro")))
    return path
