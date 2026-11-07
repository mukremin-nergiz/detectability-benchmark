# Detectability benchmark

Can a language model tell, before fieldwork, whether a gravity or magnetic survey will see a buried target? This
repository holds realistic survey-planning questions, reference answers computed with the validated forward models of
[Detectability](https://github.com/mukremin-nergiz/detectability) (DOI
[10.5281/zenodo.23931815](https://doi.org/10.5281/zenodo.23931815)), and a first pilot run with Claude Opus 5.5.

## What is inside

| Path | Content |
|---|---|
| `data/scenarios.json` | 50 scenarios: the question, the Detectability inputs, sources, assumptions and the reference answer |
| `data/reference.csv` | The reference answers in one table |
| `scenarios.py` | Defines the scenarios and recomputes the reference answers (`--check` compares with the stored file) |
| `run_pilot.py` | Asks Claude the questions with and without the Detectability tool and scores the answers |
| `results/pilot.jsonl` | The pilot run: every answer, tool call, token count and cost |

## The scenarios

Each scenario is a common survey situation taken from a published case study or from survey guidance; the links are
in `sources`. Where a source does not give a value (a cavity's size, a host rock, a density), the value used is written
in `assumptions`. Nothing else is invented.

| Group | Scenarios | Examples |
|---|---|---|
| Karst and sinkholes (K) | 11 | Dissolution cavities in the Sivas gypsum, a covered cavity at 40 m on the Konya plain, an infilled collapse doline |
| Mine workings (M) | 6 | Open and capped shafts, a partially filled coal-mine shaft, galleries |
| Tunnels (T) | 5 | A known test tunnel, a qanat-type water tunnel, a lined tunnel in stiff clay |
| Archaeology (A) | 7 | A crypt, coffin niches, an empty and a water-filled cistern, a room cut in tuff |
| Geology and ore (G) | 12 | Basalt dykes, a kimberlite pipe, a chromite pod, a magnetite ore body, faults, a salt diapir, buried valleys |
| Ferrous objects and UXO (F) | 9 | Steel drums, a fuel tank, a pipeline, aerial bombs and a shell under a drone and on foot |

Thirteen scenarios are from Türkiye. The reference answers are balanced: 23 clearly detectable, 10 marginal and 17 not
detectable, so a model cannot score well by calling everything visible.

Archaeological magnetic targets such as kilns, hearths and ditches are left out on purpose: the sources report their
anomalies but not their susceptibility or remanence, and those values would have had to be invented.

**Comparison with published measurements.** Where a source reports an anomaly, the reference agrees in some cases
(copper-mine shaft: 31 µGal modelled, 20-50 µGal measured; small shell under a drone at 2 m: 2.3 nT modelled, 2-18 nT
reported) and overestimates in others (steel drum as a solid sphere of equal volume: 853 nT against about 290 nT; old
iron-mine shaft: 90 µGal against 30 µGal). The reference is what the stated model and assumptions give, not a claim
about the real sites.

## The pilot

Claude Opus 5.5 (`claude-opus-5-5`, effort `medium`, one run per question, 7 November 2026) answered every question
twice:

- **A, no tools:** the model works out the physics itself.
- **B, with the tool:** the model may call `check_detectability`, which runs Detectability locally.

The questions do not contain the published anomaly values (they would hint at the answer). They do contain the
materials, contrasts and main magnetic field the reference used, so differences come from reasoning rather than from
different inputs. Answers are JSON (structured output) and are scored against the reference.

| Condition | Valid answers | Verdict | Recommended method | Amplitude within 2x (S/N >= 1, n = 69) | Station spacing within 2x | Cost USD |
|---|---|---|---|---|---|---|
| A, no tools | 50/50 | 97 % | 94 % | 86 % | 91 % | 2.27 |
| B, with the tool | 50/50 | 99 % | 98 % | 100 % | 100 % | 2.24 |

Verdicts are counted per method (gravity, total-field magnetic, gradiometer; 146 assessable results).

Without the tool, errors were rare but large: a unit slip made a steel drum's anomaly 1,000 times too large, and two
dyke anomalies were off by factors of 3.5 and 13. With the tool, the only miss came from the question itself: a burial
chamber "about 6 m across and 6 m high" was entered as a cube, while the reference is a sphere. The model also noticed
that the material tables have no susceptibility for soil.

## Reproduce

```bash
pip install -r requirements.txt
python scenarios.py --check          # the reference answers, from detectability 0.3.0
python run_pilot.py --report         # the scores of the stored pilot
export ANTHROPIC_API_KEY=...
python run_pilot.py --models claude-opus-5-5   # a new run (about USD 4.50 for both conditions)
```

## Limitations

- The targets are simple shapes on flat ground, with no terrain, regional field or remanence.
- Ferrous objects are modelled as solid permeable bodies of equal volume, which overestimates hollow drums and tanks.
- The pilot is one model, one effort level and one run per question.

## Licence and citation

Code: BSD 3-Clause (`LICENSE`). Data (`data/`, `results/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
To cite, use `CITATION.cff`.

Author: Mükremin Nergiz, independent researcher, ORCID [0009-0001-6789-2774](https://orcid.org/0009-0001-6789-2774).
