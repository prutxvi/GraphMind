"""Turn a filing's facts into what the UI shows: headline, red flags, connection map and fact lists.

Flags are fixed rules over cited facts. Nothing here asks a model for an opinion."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .config import Settings
from .store import Store, norm_org

TRADE = re.compile(r"sale|purchase|service|rent|lease|job ?work|contract|commission|consult|royalt|freight|supply", re.I)
PAY = re.compile(r"salary|remuneration|sitting fee|commission to director|bonus|perquisite|gratuity|reimbursement", re.I)
LOAN_GIVEN = re.compile(r"loan[s]? (given|granted|advanced)|advance[s]? (given|paid)(?! back)|inter[- ]?corporate deposit given|loan to", re.I)
SEVERITY_ORDER = {"high": 0, "medium": 1, "info": 2, "ok": 3}
ROLE_LABEL = {
    "lead_manager": "Lead manager", "registrar": "Registrar", "statutory_auditor": "Statutory auditor",
    "legal_counsel": "Legal counsel", "banker_to_issue": "Banker to the issue", "syndicate_member": "Syndicate member",
    "monitoring_agency": "Monitoring agency", "market_maker": "Market maker", "underwriter": "Underwriter",
    "peer_reviewed_auditor": "Peer-reviewed auditor",
}


def money(rupees: float | None) -> str:
    if rupees is None:
        return "—"
    if rupees < 0:
        return f"−{money(-rupees)}"
    if abs(rupees) >= 1e7:
        return f"₹{rupees / 1e7:,.2f} Cr"
    if abs(rupees) >= 1e5:
        return f"₹{rupees / 1e5:,.1f} lakh"
    return f"₹{rupees:,.0f}"


def short_name(name: str) -> str:
    return re.sub(r"\s+(private limited|pvt\.? ltd\.?|limited|ltd\.?)$", "", name, flags=re.I).strip()


def load_sebi_orders(cfg: Settings) -> list[dict]:
    path = Path(cfg.data_dir) / "sebi_orders.json"
    if not path.exists():
        return []
    return [o for o in json.loads(path.read_text()) if isinstance(o, dict) and o.get("entity")]


def _cite(f: dict) -> dict:
    return {"fact_id": f["id"], "page": f["page"], "quote": f["quote"], "verified": f["verified"]}


class FilingReport:
    def __init__(self, store: Store, filing: dict, cfg: Settings):
        self.store, self.filing, self.cfg = store, filing, cfg
        self.facts = store.facts(filing["id"])
        ids = {f["subject_id"] for f in self.facts} | {f["object_id"] for f in self.facts} | {filing["issuer_id"]}
        self.entities = store.entities(ids)
        self.issuer_id = filing["issuer_id"]
        self.company = short_name(filing["company"] or "This company")
        self.by_kind: dict[str, list[dict]] = defaultdict(list)
        for f in self.facts:
            self.by_kind[f["kind"]].append(f)

    def name(self, entity_id) -> str:
        e = self.entities.get(entity_id)
        return e["name"] if e else "Unknown"

    # -- numbers ---------------------------------------------------------------
    def metric(self, metric: str) -> dict | None:
        rows = [f for f in self.by_kind["financial"] if f["attrs"].get("metric") == metric and f["amount"] is not None]
        # The extractor returns two fiscals; the larger fiscal label is the latest ("Fiscal 2026" > "Fiscal 2025").
        return max(rows, key=lambda f: str(f["attrs"].get("fiscal", ""))) if rows else None

    def related_business(self) -> dict | None:
        rows = [f for f in self.by_kind["rpt"]
                if TRADE.search(f["attrs"].get("nature") or "") and self.entities.get(f["subject_id"], {}).get("kind") == "org"]
        if not rows:
            return None
        revenue = self.metric("revenue_from_operations")
        pct = sum(f["attrs"].get("pct_of_revenue") or 0 for f in rows)
        if not pct and revenue and revenue["amount"]:
            pct = 100 * sum(f["amount"] or 0 for f in rows) / revenue["amount"]
        per_party: dict[int, float] = defaultdict(float)
        for f in rows:
            per_party[f["subject_id"]] += f["amount"] or 0
        top = max(per_party, key=per_party.get)
        return {"rows": rows, "pct": round(pct, 2), "total": sum(per_party.values()), "parties": len(per_party),
                "top": top, "top_amount": per_party[top], "fiscal": rows[0]["attrs"].get("fiscal") or "the latest year"}

    # -- flags -----------------------------------------------------------------
    def flags(self) -> list[dict]:
        out: list[dict] = []
        c = self.company

        if rb := self.related_business():
            sev = "high" if rb["pct"] >= self.cfg.rpt_high_pct else "medium" if rb["pct"] >= self.cfg.rpt_medium_pct else "info"
            out.append({
                "id": "related_business", "severity": sev, "label": "Business with related companies",
                "value": f"{rb['pct']:g}% of revenue" if rb["pct"] else money(rb["total"]),
                "detail": f"{money(rb['total'])} of sales, purchases and services with {rb['parties']} related "
                          f"compan{'y' if rb['parties'] == 1 else 'ies'} in {rb['fiscal']}. Largest: "
                          f"{short_name(self.name(rb['top']))}, {money(rb['top_amount'])}.",
                "headline": f"{c} did {money(rb['total'])} of business with its own related companies in "
                            f"{rb['fiscal']}" + (f", {rb['pct']:g}% of its revenue." if rb["pct"] else "."),
                "citations": [_cite(f) for f in sorted(rb["rows"], key=lambda f: -(f["amount"] or 0))[:6]],
                "entities": [rb["top"]],
            })

        loans = [f for f in self.by_kind["rpt"] if LOAN_GIVEN.search(f["attrs"].get("nature") or "")]
        if loans:
            total = sum(f["amount"] or 0 for f in loans)
            out.append({
                "id": "loans_to_related", "severity": "medium", "label": "Money lent to related parties",
                "value": money(total), "detail": f"Loans or advances given to {len({f['subject_id'] for f in loans})} related parties.",
                "headline": f"{c} lent {money(total)} to related parties.",
                "citations": [_cite(f) for f in loans[:6]], "entities": list({f["subject_id"] for f in loans}),
            })

        proceeds = self.by_kind["proceeds_to_related"]
        if proceeds:
            total = sum(f["amount"] or 0 for f in proceeds)
            out.append({
                "id": "proceeds_to_related", "severity": "high", "label": "IPO money to related parties",
                "value": money(total) if total else f"{len(proceeds)} payments",
                "detail": "Part of the money raised is planned to go to promoters, directors or their companies.",
                "headline": f"Part of {c}'s IPO money is planned to go to its own related parties.",
                "citations": [_cite(f) for f in proceeds], "entities": [f["subject_id"] for f in proceeds],
            })
        elif self.by_kind["no_related_proceeds"]:
            f = self.by_kind["no_related_proceeds"][0]
            out.append({
                "id": "no_proceeds_to_related", "severity": "ok", "label": "IPO money to related parties",
                "value": "None stated", "detail": "The filing states no proceeds will be paid to promoters, directors or group companies.",
                "citations": [_cite(f)], "entities": [],
            })

        changes = self.by_kind["auditor_change"]
        resigned = [f for f in changes if re.search(r"resign", f["attrs"].get("reason") or "", re.I)]
        if resigned:
            f = resigned[0]
            reason = re.sub(r"^resignation( of auditors?)?( of our company)?\s*", "", f["attrs"].get("reason") or "", flags=re.I)
            out.append({
                "id": "auditor_resigned", "severity": "medium", "label": "Auditor resigned",
                "value": f"{len(resigned)} in 3 years",
                "detail": f"{short_name(self.name(f['subject_id']))} resigned on {f['attrs'].get('date', 'an undisclosed date')}"
                          + (f": {reason.strip()}." if reason.strip() else "."),
                "headline": f"{c}'s statutory auditor resigned on {f['attrs'].get('date', 'an undisclosed date')}.",
                "citations": [_cite(x) for x in changes], "entities": [x["subject_id"] for x in resigned],
            })

        lit = self.by_kind["litigation"]
        against = [f for f in lit if f["attrs"].get("direction") == "against"]
        insiders = [f for f in against if f["attrs"].get("party_type") in ("promoter", "director")
                    and f["attrs"].get("category") in ("criminal", "regulatory", "disciplinary")]
        if against:
            n = sum(f["attrs"].get("count", 1) for f in against)
            n_ins = sum(f["attrs"].get("count", 1) for f in insiders)
            sev = "high" if any(f["attrs"].get("category") == "criminal" for f in insiders) else "medium" if insiders else "info"
            amount = sum(f["amount"] or 0 for f in against)
            out.append({
                "id": "litigation", "severity": sev, "label": "Pending cases against",
                "value": f"{n} case{'s' if n != 1 else ''}",
                "detail": (f"{n_ins} involve{'s' if n_ins == 1 else ''} promoters or directors (criminal or regulatory). " if n_ins else "")
                          + (f"Amount at stake where stated: {money(amount)}." if amount else "Mostly unquantified."),
                "headline": f"{n_ins} criminal or regulatory case{'s are' if n_ins != 1 else ' is'} pending against "
                            f"{c}'s promoters or directors." if n_ins else None,
                "citations": [_cite(f) for f in against[:8]], "entities": [],
            })

        out.extend(self.lead_manager_flags())

        # A profitable year whose operations used a meaningful amount of cash (at least 10% of that profit).
        years = []
        for cfo in self.by_kind["financial"]:
            if cfo["attrs"].get("metric") != "net_cash_from_operating_activities" or (cfo["amount"] or 0) >= 0:
                continue
            pat = next((p for p in self.by_kind["financial"] if p["attrs"].get("metric") == "profit_after_tax"
                        and p["attrs"].get("fiscal") == cfo["attrs"].get("fiscal")), None)
            if pat and (pat["amount"] or 0) > 0 and -cfo["amount"] >= 0.1 * pat["amount"]:
                years.append((pat, cfo))
        if years:
            pat, cfo = max(years, key=lambda y: -y[1]["amount"])
            fy = cfo["attrs"].get("fiscal", "a recent year")
            out.append({
                "id": "cash_vs_profit", "severity": "medium", "label": "Profit without cash",
                "value": money(cfo["amount"]),
                "detail": f"Reported a profit of {money(pat['amount'])} in {fy} while operations used {money(-cfo['amount'])} "
                          f"of cash." + (f" Happened in {len(years)} of the years shown." if len(years) > 1 else ""),
                "headline": f"{c} reported a {money(pat['amount'])} profit in {fy}, but its operations used {money(-cfo['amount'])} of cash.",
                "citations": [_cite(x) for y in years for x in y], "entities": [],
            })

        return sorted(out, key=lambda f: SEVERITY_ORDER[f["severity"]])

    def lead_manager_flags(self) -> list[dict]:
        orders = load_sebi_orders(self.cfg)
        out = []
        for f in self.by_kind["intermediary"]:
            if f["attrs"].get("role") != "lead_manager":
                continue
            lm = self.entities.get(f["subject_id"])
            if not lm:
                continue
            others = {x["filing_id"] for x in self.store.facts_about(lm["id"])
                      if x["kind"] == "intermediary" and x["attrs"].get("role") == "lead_manager"} - {self.filing["id"]}
            hits = [o for o in orders if norm_org(o["entity"]) == norm_org(lm["name"])
                    or (lm.get("reg") and o.get("registration") and o["registration"].replace(" ", "").upper() == lm["reg"])]
            if hits:
                out.append({
                    "id": f"lead_manager_orders_{lm['id']}", "severity": "high", "label": "Lead manager's record",
                    "value": f"{len(hits)} SEBI order{'s' if len(hits) != 1 else ''}",
                    "detail": f"{short_name(lm['name'])} is named in {len(hits)} SEBI order(s). "
                              + (f"It is also lead manager on {len(others)} other filing{'s' if len(others) != 1 else ''} here." if others else ""),
                    "headline": f"{self.company}'s lead manager, {short_name(lm['name'])}, is named in "
                                f"{len(hits)} SEBI order{'s' if len(hits) != 1 else ''}.",
                    "citations": [_cite(f)], "orders": hits, "entities": [lm["id"]],
                })
            elif others:
                out.append({
                    "id": f"lead_manager_{lm['id']}", "severity": "info", "label": "Lead manager",
                    "value": f"{len(others) + 1} IPOs here",
                    "detail": f"{short_name(lm['name'])} also managed {len(others)} other filing{'s' if len(others) != 1 else ''} in Footnote.",
                    "citations": [_cite(f)], "entities": [lm["id"]],
                })
        return out

    # -- map -------------------------------------------------------------------
    def graph(self) -> dict:
        nodes: dict[int, dict] = {}
        edges: dict[tuple, dict] = {}

        def node(eid, role, column):
            if eid is None or eid not in self.entities:
                return None
            e = self.entities[eid]
            n = nodes.setdefault(eid, {"id": eid, "name": e["name"], "kind": e["kind"], "roles": [], "column": column,
                                       "din": e["din"], "reg": e["reg"], "cin": e["cin"]})
            if role and role not in n["roles"]:
                n["roles"].append(role)
            # A promoter or adviser placement wins over a generic one.
            if column in ("top", "left") and n["column"] == "right" and e["kind"] == "person":
                n["column"] = column
            return n

        def edge(src, dst, kind, label, f, amount=None):
            key = (src, dst, kind)
            e = edges.setdefault(key, {"id": f"{kind}-{src}-{dst}", "source": src, "target": dst, "kind": kind,
                                       "label": label, "amount": 0.0, "natures": [], "citations": []})
            if amount:
                e["amount"] += amount
            nature = f["attrs"].get("nature")
            if nature and nature not in e["natures"]:
                e["natures"].append(nature)
            if len(e["citations"]) < 8:
                e["citations"].append(_cite(f))
            return e

        node(self.issuer_id, "Company going public", "center")
        for f in self.facts:
            s, o, a = f["subject_id"], f["object_id"], f["attrs"]
            k = f["kind"]
            if k == "promoter":
                node(s, "Promoter", "left")
                pct = a.get("shareholding_pct")
                edge(s, o, k, f"promoter · {pct:g}%" if pct else "promoter", f)
            elif k == "director":
                independent = "independent" in (a.get("designation") or "").lower()
                node(s, "Independent director" if independent else "Director", "left")
                edge(s, o, k, "independent director" if independent else "director", f)
            elif k == "directorship":
                node(s, None, "left")
                node(o, "Other company of a director", "right")
                edge(s, o, k, "director of", f)
            elif k in ("group_company", "promoter_group"):
                node(s, "Group company" if k == "group_company" else "Promoter group", "right")
                edge(s, o, k, "group company" if k == "group_company" else "promoter group", f)
            elif k == "rpt":
                kind = self.entities.get(s, {}).get("kind")
                node(s, "Related party", "right" if kind == "org" else "left")
                # Salaries and sitting fees are ordinary pay; red lines are kept for business money.
                edge(s, o, "pay" if PAY.search(a.get("nature") or "") else "money", "", f, f["amount"])
            elif k == "proceeds_to_related":
                node(s, "Receives IPO money", "right")
                edge(o, s, "proceeds", "IPO money", f, f["amount"])
            elif k == "intermediary":
                role = ROLE_LABEL.get(a.get("role"), "Adviser")
                node(s, role, "top")
                edge(s, o, k, role.lower(), f)
            elif k == "auditor_change" and re.search(r"resign", a.get("reason") or "", re.I):
                node(s, "Former auditor (resigned)", "top")
                edge(s, o, k, "resigned as auditor", f)

        for e in edges.values():
            if e["kind"] == "money":
                e["label"] = money(e["amount"])
            elif e["kind"] == "pay":
                e["label"] = f"paid {money(e['amount'])}"
        return {"nodes": list(nodes.values()), "edges": list(edges.values()), "issuer": self.issuer_id}

    # -- lists -----------------------------------------------------------------
    def lists(self) -> dict:
        people = {}
        for f in self.by_kind["promoter"] + self.by_kind["director"]:
            e = self.entities.get(f["subject_id"])
            if not e:
                continue
            p = people.setdefault(e["id"], {"id": e["id"], "name": e["name"], "kind": e["kind"], "din": e["din"],
                                            "roles": [], "citations": []})
            role = "Promoter" if f["kind"] == "promoter" else (f["attrs"].get("designation") or "Director")
            if f["kind"] == "promoter" and f["attrs"].get("shareholding_pct"):
                role += f" · {f['attrs']['shareholding_pct']:g}%"
            # Committee tables list "Member"/"Chairperson"; those are not positions in the company.
            if re.fullmatch(r"(member|chair(man|person|woman)?)", role.strip(), re.I):
                continue
            if role.casefold() not in {r.casefold() for r in p["roles"]}:
                p["roles"].append(role)
            p["citations"].append(_cite(f))
        money_rows = [{
            "party": self.name(f["subject_id"]), "party_id": f["subject_id"], "nature": f["attrs"].get("nature"),
            "relationship": f["attrs"].get("relationship"), "amount": f["amount"], "amount_label": money(f["amount"]),
            "pct_of_revenue": f["attrs"].get("pct_of_revenue"), "fiscal": f["attrs"].get("fiscal"), **_cite(f),
        } for f in sorted(self.by_kind["rpt"], key=lambda f: -(f["amount"] or 0))]
        advisers: dict[tuple, dict] = {}
        for f in self.by_kind["intermediary"]:
            key = (f["subject_id"], f["attrs"].get("role"))
            row = advisers.get(key)
            # Keep one row per firm and role, preferring the mention that carries a registration number.
            if row is None or (not row["registration"] and f["attrs"].get("registration")):
                advisers[key] = {"id": f["subject_id"], "name": self.name(f["subject_id"]),
                                 "role": ROLE_LABEL.get(f["attrs"].get("role"), "Adviser"),
                                 "registration": f["attrs"].get("registration"), **_cite(f)}
        advisers = list(advisers.values())
        litigation = [{**f["attrs"], "amount_label": money(f["amount"]) if f["amount"] else None, **_cite(f)}
                      for f in self.by_kind["litigation"]]
        objects = [{"purpose": f["attrs"].get("purpose"), "amount_label": money(f["amount"]) if f["amount"] else "To be decided",
                    **_cite(f)} for f in self.by_kind["object"]]
        financials = [{"metric": f["attrs"].get("metric"), "fiscal": f["attrs"].get("fiscal"), "amount_label": money(f["amount"]),
                       **_cite(f)} for f in self.by_kind["financial"]]
        companies = {}
        for f in self.by_kind["group_company"] + self.by_kind["promoter_group"]:
            e = self.entities.get(f["subject_id"])
            if e:
                companies.setdefault(e["id"], {"id": e["id"], "name": e["name"], "roles": set(), **_cite(f)})["roles"].add(
                    "Group company" if f["kind"] == "group_company" else "Promoter group")
        return {
            "people": list(people.values()), "money": money_rows, "advisers": advisers, "litigation": litigation,
            "objects": objects, "financials": financials,
            "companies": [{**c, "roles": sorted(c["roles"])} for c in companies.values()],
        }

    def summary(self) -> dict:
        flags = self.flags()
        headline = next((f["headline"] for f in flags if f.get("headline") and f["severity"] in ("high", "medium")), None)
        holding = next((f["attrs"].get("pct") for f in self.by_kind["promoter_holding"]), None)
        return {
            "id": self.filing["id"], "company": self.filing["company"], "status": self.filing["status"],
            "meta": self.filing["meta"], "headline": headline, "promoter_holding_pct": holding,
            "flags": flags, "issuer_id": self.issuer_id,
            "counts": {"people": len({f["subject_id"] for f in self.by_kind["promoter"] + self.by_kind["director"]}),
                       "related_parties": len({f["subject_id"] for f in self.by_kind["rpt"]}),
                       "facts": len(self.facts), "verified": sum(f["verified"] for f in self.facts)},
        }

    def full(self) -> dict:
        return {**self.summary(), "graph": self.graph(), "lists": self.lists()}


def entity_report(store: Store, entity_id: int) -> dict | None:
    entity = store.entity(entity_id)
    if not entity:
        return None
    facts = store.facts_about(entity_id)
    filings = {f["id"]: f for f in store.filings() if f["status"] == "ready"}
    others = store.entities({f["subject_id"] for f in facts} | {f["object_id"] for f in facts})
    appearances: dict[str, dict] = {}
    for f in facts:
        filing = filings.get(f["filing_id"])
        if not filing:
            continue
        a = appearances.setdefault(f["filing_id"], {"filing_id": f["filing_id"], "company": filing["company"],
                                                     "roles": [], "facts": []})
        other = f["object_id"] if f["subject_id"] == entity_id else f["subject_id"]
        label = {
            "promoter": "Promoter", "director": f["attrs"].get("designation") or "Director",
            "directorship": f"Director of {others.get(f['object_id'], {}).get('name', '')}",
            "group_company": "Group company", "promoter_group": "Promoter group",
            "intermediary": ROLE_LABEL.get(f["attrs"].get("role"), "Adviser"),
            "rpt": f"Related party · {f['attrs'].get('nature') or 'transaction'} · {money(f['amount'])}",
            "auditor_change": "Auditor change", "proceeds_to_related": "Receives IPO money",
        }.get(f["kind"], f["kind"])
        if f["subject_id"] != entity_id and f["kind"] == "directorship":
            label = f"Company of director {others.get(other, {}).get('name', '')}"
        if filing.get("issuer_id") == entity_id:
            label = "Company going public"
        if label not in a["roles"]:
            a["roles"].append(label)
        a["facts"].append({"kind": f["kind"], "label": label, **_cite(f)})
    if any(f.get("issuer_id") == entity_id for f in filings.values()):
        for fid, filing in filings.items():
            if filing.get("issuer_id") == entity_id:
                appearances.setdefault(fid, {"filing_id": fid, "company": filing["company"], "roles": ["Company going public"], "facts": []})
    return {"entity": entity, "appearances": list(appearances.values())}
