"""Pilot run: ask Claude the survey-planning questions, with and without the Detectability tool, and score the answers.

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...
    python run_pilot.py --models claude-opus-5-5                 # the published pilot
    python run_pilot.py --models claude-haiku-5-5 --ids K01,F05  # a quick test
    python run_pilot.py --report                                 # scores of the stored results only

Conditions: A = no tools (the model answers from its own physics); B = the model may call ``check_detectability``,
which runs Detectability locally. Every answer is a JSON object (structured output) scored against the reference in
``data/scenarios.json``. Results are appended to ``results/pilot.jsonl``; re-running skips finished items.

The API key is read from ANTHROPIC_API_KEY; it is never printed or stored.
No refusal fallback is enabled: a benchmark must measure each model on its own, so a refusal is recorded as such.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent

import anthropic  # noqa: E402

from detectability import __version__ as DETECTABILITY_VERSION  # noqa: E402
from detectability import detect, evaluate, rocks  # noqa: E402
from detectability.survey import SHAPES, Survey, _main_field  # noqa: E402

OUT = HERE / "results" / "pilot.jsonl"
MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
# USD per million tokens (input, output): Claude API list prices, November 2026.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}
METHODS = ("gravity", "magnetic", "gradient")
VERDICTS = ("clearly detectable", "marginal", "not detectable")
MAX_TOOL_TURNS = 6

SYSTEM = f"""You are helping to plan a near-surface geophysical survey. Answer the question as a geophysicist would, \
using standard forward modelling.

Standard conditions unless the question says otherwise:
- Gravity: Scintrex CG-6 gravimeter, 5 µGal per reading, plus 10 µGal field noise (added in quadrature).
- Total-field magnetics: Overhauser magnetometer, 0.022 nT per reading, plus 2 nT field noise; sensor 0.5 m above ground.
- Magnetic vertical gradient: Bartington Grad601 fluxgate gradiometer, 0.1 nT, plus 0.5 nT field noise; lower sensor \
0.2 m above ground, 1 m baseline. The reading is the lower-sensor total-field anomaly minus the upper-sensor one, in nT.
- Induced magnetisation only; no remanence unless stated.
- Flat ground, homogeneous host, no regional trend. Use typical textbook densities and susceptibilities for the named \
materials unless a contrast is given.
- Verdict from the signal-to-noise ratio S/N = peak anomaly / effective noise: S/N >= {detect.CLEAR:g} clearly \
detectable, {detect.MARGINAL:g} to {detect.CLEAR:g} marginal, below {detect.MARGINAL:g} not detectable.
- Peak anomaly: the largest absolute value of the profile anomaly (for a step-like anomaly, its full step).
- Station spacing: allow at least {detect.STATIONS_ACROSS} stations across the anomaly width (full width at half \
maximum); give 0 when not detectable.

Give your final answer only in the required JSON format."""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        **{m: {"type": "object",
               "properties": {"peak": {"type": "number"},
                              "verdict": {"type": "string", "enum": list(VERDICTS)},
                              "station_spacing_m": {"type": "number"}},
               "required": ["peak", "verdict", "station_spacing_m"], "additionalProperties": False}
           for m in METHODS},
        "recommended_method": {"type": "string", "enum": [*METHODS, "none"]},
        "caveats": {"type": "string"},
    },
    "required": [*METHODS, "recommended_method", "caveats"],
    "additionalProperties": False,
}

MATERIALS = sorted(set(rocks.DENSITY_G_CM3) | set(rocks.SUSCEPTIBILITY_SI))
TOOL = {
    "name": "check_detectability",
    "description": (
        "Runs Detectability, a validated forward-modelling library, for one buried target and returns the modelled "
        "gravity, total-field magnetic and magnetic-gradient anomalies, the effective noise, S/N, verdict, station "
        "spacing and the recommended method. Shapes: " + "; ".join(f"{k}: {v}" for k, v in SHAPES.items())
        + ". Materials (for material and host): " + ", ".join(MATERIALS) + ". density_contrast (kg/m³) and "
        "susceptibility_contrast (SI) override the material tables. Give latitude, longitude and date for the main "
        "magnetic field. Instrument settings default to the standard conditions."),
    "input_schema": {
        "type": "object",
        "properties": {
            "target": {"type": "object", "description": "shape, depth_top (m), size (m), depth_bottom (m), length "
                       "(m, prism), dip (deg, dyke), material, host, density_contrast, susceptibility_contrast"},
            "survey": {"type": "object", "description": "latitude, longitude, date (YYYY-MM-DD), optional "
                       "sensor_height and gradiometer_height (m)"},
        },
        "required": ["target", "survey"],
    },
}


def api_key() -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY to run the pilot (not needed for --report).")
    return os.environ["ANTHROPIC_API_KEY"]


def run_tool(inp: dict) -> tuple[str, bool]:
    try:
        r = evaluate(inp.get("target") or {}, inp.get("survey") or {}, methods=METHODS)
    except Exception as e:  # the model's input was invalid: tell it, let it correct itself
        return f"Error: {e}", True
    out = {"recommended": r.recommended, "methods": {}}
    for m in r.results:
        if not m.available:
            out["methods"][m.method] = {"available": False, "reason": m.reason}
            continue
        a = m.assessment
        out["methods"][m.method] = {"peak": round(a.peak, 4), "units": a.units, "noise": round(a.noise, 4),
                                    "snr": round(a.snr, 3), "verdict": a.verdict, "station_spacing_m": a.station_spacing,
                                    "contrast": m.contrast, "contrast_units": m.contrast_units}
    return json.dumps(out), False


def question(s: dict) -> str:
    """The stored question without published anomaly values (they would hint at the answer), plus the properties and
    main field the reference used, so differences come from reasoning rather than from different inputs."""
    q = s["question"]
    for sentence in re.split(r"(?<=[.;])\s+", s["setting"]):
        if re.search(r"nT|µGal|mGal|gamma|anomal", sentence):
            q = q.replace(sentence, "").replace("  ", " ")
    t = s["target"]
    props = [f"target material: {t['material']}", f"host: {t['host']}"]
    if "density_contrast" in t:
        props.append(f"density contrast {t['density_contrast']:g} kg/m³")
    if "susceptibility_contrast" in t:
        props.append(f"apparent susceptibility contrast {t['susceptibility_contrast']:g} SI")
    sv = Survey(**s["survey"])
    _, info = _main_field(sv)
    field = (f"Main magnetic field at the site: {info['total']:.0f} nT, inclination {info['inclination']:.1f}°, "
             f"declination {info['declination']:.1f}°.")
    notes = " ".join(s["assumptions"])
    return f"{q}\n\nProperties to use: {'; '.join(props)}. {field}\nNotes: {notes}"


def ask(client: anthropic.Anthropic, model: str, condition: str, s: dict, effort: str) -> dict:
    messages = [{"role": "user", "content": question(s)}]
    kwargs = dict(model=model, max_tokens=16000, system=SYSTEM, output_config={
        "effort": effort, "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}})
    if condition == "B":
        kwargs["tools"] = [TOOL]
        messages[0]["content"] += "\n\nYou can run the check_detectability tool; use it."
    usage = {"input_tokens": 0, "output_tokens": 0}
    tool_calls = []
    for _ in range(MAX_TOOL_TURNS + 1):
        r = client.messages.create(messages=messages, **kwargs)
        usage["input_tokens"] += r.usage.input_tokens
        usage["output_tokens"] += r.usage.output_tokens
        if r.stop_reason == "refusal":
            return {"status": "refusal", "usage": usage, "tool_calls": tool_calls,
                    "refusal": getattr(r.stop_details, "category", None) if r.stop_details else None}
        if r.stop_reason == "max_tokens":
            return {"status": "max_tokens", "usage": usage, "tool_calls": tool_calls}
        uses = [b for b in r.content if b.type == "tool_use"]
        if r.stop_reason == "tool_use" and uses:
            messages.append({"role": "assistant", "content": r.content})
            results = []
            for b in uses:
                text, err = run_tool(b.input if isinstance(b.input, dict) else {})
                tool_calls.append({"input": b.input, "error": err})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": err})
            messages.append({"role": "user", "content": results})
            continue
        text = next((b.text for b in r.content if b.type == "text"), "")
        try:
            answer = json.loads(text)
        except json.JSONDecodeError:
            return {"status": "bad_json", "usage": usage, "tool_calls": tool_calls, "text": text[:2000]}
        return {"status": "ok", "answer": answer, "usage": usage, "tool_calls": tool_calls}
    return {"status": "too_many_tool_turns", "usage": usage, "tool_calls": tool_calls}


def cost(model: str, usage: dict) -> float:
    pin, pout = PRICES[model]
    return usage["input_tokens"] / 1e6 * pin + usage["output_tokens"] / 1e6 * pout


def score(s: dict, rec: dict) -> dict:
    ref = s["reference"]["methods"]
    ans = rec.get("answer") or {}
    out = {"verdict_hits": 0, "verdict_n": 0, "log_errors": [], "relevant_errors": [], "spacing_hits": 0, "spacing_n": 0}
    for m in METHODS:
        r = ref.get(m, {})
        a = ans.get(m)
        if not r.get("available") or not a:
            continue
        out["verdict_n"] += 1
        out["verdict_hits"] += int(a["verdict"] == r["verdict"])
        peak = abs(a["peak"])  # some answers give the signed extreme; the reference peak is an absolute value
        if r["peak"] > 0 and peak > 0:
            e = abs(math.log10(peak / r["peak"]))
            out["log_errors"].append(e)
            if r["snr"] >= 1:  # anomalies at or above the noise: the ones a survey decision depends on
                out["relevant_errors"].append(e)
        if r["verdict"] != "not detectable":
            out["spacing_n"] += 1
            out["spacing_hits"] += int(a["station_spacing_m"] > 0 and 0.5 <= a["station_spacing_m"] / r["station_spacing"] <= 2)
    out["method_hit"] = int(ans.get("recommended_method") == (s["reference"]["recommended"] or "none")) if ans else 0
    return out


def report(records: list[dict], scenarios: dict) -> str:
    rows = []
    for model in MODELS:
        for cond in ("A", "B"):
            rs = [r for r in records if r["model"] == model and r["condition"] == cond]
            if not rs:
                continue
            sc = [score(scenarios[r["id"]], r) for r in rs]
            vn = sum(x["verdict_n"] for x in sc)
            le = sorted(e for x in sc for e in x["log_errors"])
            rel = [e for x in sc for e in x["relevant_errors"]]
            sn = sum(x["spacing_n"] for x in sc)
            ok = sum(r["status"] == "ok" for r in rs)
            within = math.log10(2)
            rows.append(
                f"| {model} | {cond} | {len(rs)} | {ok} | "
                f"{sum(x['verdict_hits'] for x in sc) / vn:.0%} | "
                f"{sum(x['method_hit'] for x in sc) / len(rs):.0%} | "
                f"{(le[len(le) // 2] if le else float('nan')):.2f} | "
                f"{sum(1 for e in le if e <= within) / len(le) if le else 0:.0%} | "
                f"{sum(1 for e in rel if e <= within) / len(rel) if rel else 0:.0%} ({len(rel)}) | "
                f"{(sum(x['spacing_hits'] for x in sc) / sn if sn else 0):.0%} | "
                f"{sum(r['cost_usd'] for r in rs):.2f} |")
    head = ("| Model | Condition | Items | Valid JSON | Verdict accuracy | Recommended method | Median log10 amplitude "
            "error | Amplitude within 2x | Amplitude within 2x where S/N >= 1 (n) | Spacing within 2x | Cost USD |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|")
    return head + "\n" + "\n".join(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--models", default=",".join(MODELS))
    p.add_argument("--conditions", default="A,B")
    p.add_argument("--ids", default="", help="comma-separated scenario ids; default all")
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--report", action="store_true", help="only print the scores of the stored results")
    a = p.parse_args()

    scenarios = {s["id"]: s for s in json.loads((HERE / "data" / "scenarios.json").read_text("utf-8"))}
    OUT.parent.mkdir(exist_ok=True)
    done = [json.loads(line) for line in OUT.read_text("utf-8").splitlines()] if OUT.exists() else []
    if a.report:
        print(report(done, scenarios))
        return 0

    ids = [i for i in a.ids.split(",") if i] or list(scenarios)
    finished = {(r["model"], r["condition"], r["id"], r["effort"]) for r in done if r["status"] == "ok"}
    jobs = [(m, c, i) for m in a.models.split(",") for c in a.conditions.split(",") for i in ids
            if (m, c, i, a.effort) not in finished]
    client = anthropic.Anthropic(api_key=api_key(), max_retries=4)
    lock = threading.Lock()
    total = 0.0

    def work(job):
        model, cond, sid = job
        try:
            res = ask(client, model, cond, scenarios[sid], a.effort)
        except anthropic.APIStatusError as e:
            res = {"status": f"api_error_{e.status_code}", "usage": {"input_tokens": 0, "output_tokens": 0},
                   "tool_calls": [], "error": str(e.message)[:500]}
        rec = {"id": sid, "model": model, "condition": cond, "effort": a.effort, "detectability": DETECTABILITY_VERSION,
               "date": dt.date.today().isoformat(), **res, "cost_usd": round(cost(model, res["usage"]), 5)}
        with lock:
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for rec in ex.map(work, jobs):
            total += rec["cost_usd"]
            print(f"{rec['model']:18s} {rec['condition']} {rec['id']} {rec['status']:10s} "
                  f"tools={len(rec['tool_calls'])} in={rec['usage']['input_tokens']} out={rec['usage']['output_tokens']} "
                  f"${rec['cost_usd']:.4f}", flush=True)
    print(f"spent this run: ${total:.4f}")
    done = [json.loads(line) for line in OUT.read_text("utf-8").splitlines()]
    print(report(done, scenarios))
    return 0


if __name__ == "__main__":
    sys.exit(main())
