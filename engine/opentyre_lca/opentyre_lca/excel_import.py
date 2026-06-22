from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .tyre_model import TyreLCAParams, workbook_base_case, update_params


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "Excel import requires pandas and openpyxl. Install with: pip install -r requirements.txt"
        ) from exc
    return pd


def _rewind(file_obj: Any) -> None:
    try:
        file_obj.seek(0)
    except Exception:
        pass


def _normalise(text: Any) -> str:
    if text is None:
        return ""
    return str(text).strip().lower().replace("₂", "2").replace("₃", "3")


def _to_float(value: Any) -> float | None:
    pd = _require_pandas()

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", ".")
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def detect_workbook_structure(file_obj: Any) -> dict:
    """Return sheet names and simple classification."""
    pd = _require_pandas()
    _rewind(file_obj)

    xls = pd.ExcelFile(file_obj)
    sheets = xls.sheet_names

    classification = {}
    for sheet in sheets:
        s = _normalise(sheet)
        if "summary" in s:
            classification[sheet] = "summary"
        elif "elt" in s or "tyre" in s or "tire" in s:
            classification[sheet] = "elt_inventory"
        elif "lci" in s or "inventory" in s:
            classification[sheet] = "lci_inventory"
        elif "deash" in s or "demin" in s or "acid" in s:
            classification[sheet] = "deashing"
        else:
            classification[sheet] = "unknown"

    return {
        "sheet_count": len(sheets),
        "sheets": sheets,
        "classification": classification,
    }


def preview_sheet(file_obj: Any, sheet_name: str, nrows: int = 50):
    """Preview one workbook sheet."""
    pd = _require_pandas()
    _rewind(file_obj)
    return pd.read_excel(file_obj, sheet_name=sheet_name, nrows=nrows)


def extract_candidate_values(
    file_obj: Any,
    sheet_names: Iterable[str] | None = None,
    max_rows: int = 100,
    max_cols: int = 30,
) -> list[dict]:
    """
    Extract label-value candidates from workbook.

    Method:
    - Read sheets without headers.
    - For every text cell, search nearby cells to the right and below for a numeric value.
    - Return a transparent candidate table for user review.
    """
    pd = _require_pandas()
    _rewind(file_obj)

    structure = detect_workbook_structure(file_obj)
    sheets = list(sheet_names) if sheet_names else structure["sheets"]

    records: list[dict] = []

    for sheet in sheets:
        _rewind(file_obj)
        try:
            df = pd.read_excel(file_obj, sheet_name=sheet, header=None, nrows=max_rows)
        except Exception:
            continue

        if df.empty:
            continue

        df = df.iloc[:, :max_cols]

        for r in range(df.shape[0]):
            for c in range(df.shape[1]):
                raw_label = df.iat[r, c]
                label = _normalise(raw_label)

                if not label or len(label) < 3:
                    continue

                if _to_float(raw_label) is not None:
                    continue

                nearby = []

                # Search same row, next 1-4 cells.
                for dc in range(1, 5):
                    if c + dc < df.shape[1]:
                        nearby.append((r, c + dc, df.iat[r, c + dc], f"R{r+1}C{c+dc+1}"))

                # Search one row below, same and next columns.
                if r + 1 < df.shape[0]:
                    for dc in range(0, 3):
                        if c + dc < df.shape[1]:
                            nearby.append((r + 1, c + dc, df.iat[r + 1, c + dc], f"R{r+2}C{c+dc+1}"))

                for rr, cc, value_raw, value_cell in nearby:
                    value = _to_float(value_raw)
                    if value is None:
                        continue

                    records.append(
                        {
                            "sheet": sheet,
                            "label": str(raw_label).strip(),
                            "label_normalised": label,
                            "label_cell": f"R{r+1}C{c+1}",
                            "value": value,
                            "value_raw": value_raw,
                            "value_cell": value_cell,
                        }
                    )
                    break

    return records


@dataclass(frozen=True)
class MappingRule:
    output_name: str
    field: str
    patterns: tuple[str, ...]
    sheet_keywords: tuple[str, ...] = ()
    percent_to_fraction: bool = False


MAPPING_RULES = [
    MappingRule(
        "Annual ELT feed",
        "annual_elt_t",
        (r"annual.*elt", r"elt.*feed", r"tyre.*feed", r"tire.*feed", r"annual.*feed"),
        ("summary", "elt", "tyre", "tire"),
    ),
    MappingRule(
        "Raw rCB yield",
        "rcb_yield_t_per_t_elt",
        (r"raw.*rcb.*yield", r"rcb.*yield", r"carbon.*black.*yield"),
        ("summary", "elt", "tyre", "tire"),
        percent_to_fraction=True,
    ),
    MappingRule(
        "Virgin carbon black EF",
        "virgin_cb_ef_tco2e_per_t",
        (r"virgin.*carbon.*black.*ef", r"virgin.*cb.*ef", r"virgin.*carbon.*black.*emission"),
        ("summary", "lci", "inventory"),
    ),
    MappingRule(
        "Raw rCB pyrolysis EF",
        "raw_rcb_pyrolysis_ef_tco2e_per_t",
        (r"raw.*rcb.*ef", r"rcb.*production.*emission", r"pyrolysis.*rcb.*ef"),
        ("summary", "lci", "inventory"),
    ),
    MappingRule(
        "Avoided shipping credit",
        "avoided_shipping_tco2e_per_year",
        (r"avoided.*shipping", r"shipping.*credit", r"transport.*credit"),
        ("summary", "transport", "route"),
    ),
    MappingRule(
        "Oil substitution credit",
        "oil_credit_tco2e_per_year",
        (r"oil.*credit", r"pyrolysis.*oil.*substitution", r"avoided.*fuel"),
        ("summary", "oil"),
    ),
    MappingRule(
        "Purified rCB yield",
        "deashing__purified_yield_t_per_t_feed",
        (r"purified.*yield", r"purification.*yield", r"deash.*yield"),
        ("deash", "demin"),
        percent_to_fraction=True,
    ),
    MappingRule(
        "HNO3 use",
        "deashing__hno3_kg_per_t_feed",
        (r"hno3", r"nitric.*acid"),
        ("deash", "demin", "acid"),
    ),
    MappingRule(
        "NaOH use",
        "deashing__naoh_kg_per_t_feed",
        (r"naoh", r"sodium.*hydroxide"),
        ("deash", "demin", "acid"),
    ),
    MappingRule(
        "Deashing electricity",
        "deashing__electricity_kwh_per_t_feed",
        (r"electricity", r"power"),
        ("deash", "demin"),
    ),
    MappingRule(
        "Fresh water",
        "deashing__fresh_water_m3_per_t_feed",
        (r"fresh.*water", r"water.*input"),
        ("deash", "demin"),
    ),
    MappingRule(
        "Wastewater",
        "deashing__wastewater_m3_per_t_feed",
        (r"wastewater", r"waste.*water"),
        ("deash", "demin"),
    ),
]


def _score_candidate(rule: MappingRule, candidate: dict) -> int:
    label = candidate["label_normalised"]
    sheet = _normalise(candidate["sheet"])

    pattern_hit = any(re.search(pattern, label) for pattern in rule.patterns)
    if not pattern_hit:
        return -1

    score = 10

    if rule.sheet_keywords and any(k in sheet for k in rule.sheet_keywords):
        score += 10

    # Prefer labels that are not very long.
    if len(label) < 60:
        score += 2

    return score


def map_workbook_to_params(
    file_obj: Any,
    base_params: TyreLCAParams | None = None,
) -> tuple[TyreLCAParams, list[dict]]:
    """
    Map detected workbook values into TyreLCAParams.

    Returns:
    - params with mapped values
    - mapping records for transparent review
    """
    base = base_params or workbook_base_case()

    candidates = extract_candidate_values(file_obj)
    changes: dict[str, float | bool] = {}
    mapping_records: list[dict] = []

    for rule in MAPPING_RULES:
        scored = []
        for candidate in candidates:
            score = _score_candidate(rule, candidate)
            if score >= 0:
                scored.append((score, candidate))

        if not scored:
            continue

        scored.sort(key=lambda x: x[0], reverse=True)
        score, chosen = scored[0]

        value = float(chosen["value"])

        if rule.percent_to_fraction and value > 1.0 and value <= 100.0:
            value = value / 100.0

        # Guardrails to avoid absurd accidental mappings.
        if rule.field.endswith("yield_t_per_t_elt") or rule.field.endswith("yield_t_per_t_feed"):
            if not 0 <= value <= 1:
                continue

        changes[rule.field] = value

        mapping_records.append(
            {
                "mapped_output": rule.output_name,
                "field": rule.field,
                "value": value,
                "source_sheet": chosen["sheet"],
                "source_label": chosen["label"],
                "source_cell": chosen["label_cell"],
                "value_cell": chosen["value_cell"],
                "score": score,
            }
        )

    if any(key.startswith("deashing__") for key in changes):
        changes["deashing__enabled"] = True

    mapped_params = update_params(base, **changes)
    return mapped_params, mapping_records
