"""
Predictive Analysis Router for 4D/TOTO
=====================================
Three distinct predictive models:
1. Frequency Analysis (Statistical)
2. Markov Chain (Sequential Pattern)
3. Gap / Due Number Analysis (Positional)

DISCLAIMER: All predictions are purely for educational/entertainment purposes only.
They are NOT intended for gambling or financial decisions. Lottery draws are
random events and no model can reliably predict outcomes.
"""

import asyncio
from collections import Counter, defaultdict
import random
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

try:
    from ..schemas import (
        FourDPrediction,
        ModelPrediction,
        PredictionGenerateRequest,
        PredictionResponse,
        TotoPrediction,
    )
    from .results import get_draw_history
except ImportError:
    from schemas import (
        FourDPrediction,
        ModelPrediction,
        PredictionGenerateRequest,
        PredictionResponse,
        TotoPrediction,
    )
    from results import get_draw_history

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _first_available(payload: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    """Return the first non-empty value found for the provided key aliases."""
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _extract_nested_results(result_row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize both legacy and draw-history payload shapes."""
    nested_results = result_row.get("results")
    if isinstance(nested_results, dict):
        return nested_results
    return result_row


def _get_4d_numbers_from_results(past_results: List[Dict[str, Any]]) -> List[str]:
    """Flatten 4D winning numbers from draw-history or legacy payloads."""
    numbers: List[str] = []
    for row in past_results:
        if str(row.get("game_type", "")).upper() != "4D":
            continue

        payload = _extract_nested_results(row)

        # Support both schema variants: first_prize/second_prize/third_prize and first/second/third.
        for key_aliases in (("first_prize", "first"), ("second_prize", "second"), ("third_prize", "third")):
            prize_value = _first_available(payload, key_aliases)
            if prize_value is None:
                continue

            if isinstance(prize_value, list):
                for entry in prize_value:
                    if entry is not None:
                        numbers.append(str(entry).zfill(4))
            else:
                numbers.append(str(prize_value).zfill(4))

        starter_values = _first_available(payload, ("starter", "special")) or []
        if not isinstance(starter_values, list):
            starter_values = [starter_values]
        for entry in starter_values:
            if entry is not None:
                numbers.append(str(entry).zfill(4))

        consolation_values = payload.get("consolation", [])
        if not isinstance(consolation_values, list):
            consolation_values = [consolation_values]
        for entry in consolation_values:
            if entry is not None:
                numbers.append(str(entry).zfill(4))

    return numbers


def _get_toto_numbers_from_results(past_results: List[Dict[str, Any]]) -> List[List[int]]:
    """Return winning TOTO number sets from draw-history or legacy payloads."""
    sets: List[List[int]] = []
    for row in past_results:
        if str(row.get("game_type", "")).upper() != "TOTO":
            continue

        payload = _extract_nested_results(row)
        raw_numbers = payload.get("winning_numbers", row.get("winning_numbers", []))

        if not isinstance(raw_numbers, list):
            continue

        normalized_numbers: List[int] = []
        for value in raw_numbers:
            try:
                normalized_numbers.append(int(value))
            except (TypeError, ValueError):
                continue

        if normalized_numbers:
            sets.append(normalized_numbers)

    return sets


async def _load_results_from_supabase_history(limit: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load 4D and TOTO history via existing Supabase-backed draw-history endpoint logic."""
    four_d_history, toto_history = await asyncio.gather(
        get_draw_history(
            game_type="4D",
            start_date=None,
            end_date=None,
            limit=limit,
        ),
        get_draw_history(
            game_type="TOTO",
            start_date=None,
            end_date=None,
            limit=limit,
        ),
    )

    if not isinstance(four_d_history, list) or not isinstance(toto_history, list):
        raise HTTPException(status_code=500, detail="Unexpected draw-history response format.")

    return four_d_history, toto_history


# ---------------------------------------------------------------------------
# Model 1 — Frequency Analysis
# ---------------------------------------------------------------------------

def model_frequency(four_d_numbers: List[str], toto_sets: List[List[int]]) -> ModelPrediction:
    """
    Hot-number frequency model: picks digits / numbers that appeared most often.
    For 4D: ranks each digit position's most frequent digit independently.
    For TOTO: picks the 12 most frequently drawn individual numbers.
    """
    # --- 4D ---
    if four_d_numbers:
        pos_counters = [Counter(), Counter(), Counter(), Counter()]
        for num in four_d_numbers:
            for i, d in enumerate(num):
                pos_counters[i][d] += 1
        predicted_4d = ""
        for pos in pos_counters:
            predicted_4d += pos.most_common(1)[0][0] if pos else str(random.randint(0, 9))
        freq_counts = [pos_counters[i].most_common(1)[0][1] if pos_counters[i] else 0 for i in range(4)]
        avg_freq = sum(freq_counts) / 4 if freq_counts else 0
        max_possible = len(four_d_numbers) if four_d_numbers else 1
        conf_4d = min(0.55, round(avg_freq / max_possible + 0.2, 3))
        reason_4d = f"Each digit position was analysed across {len(four_d_numbers)} past results. The most frequent digit per position was selected."
    else:
        predicted_4d = "".join([str(random.randint(0, 9)) for _ in range(4)])
        conf_4d = 0.1
        reason_4d = "Insufficient data — random baseline used."

    # --- TOTO ---
    if toto_sets:
        flat = [n for s in toto_sets for n in s]
        counter = Counter(flat)
        top12 = [num for num, _ in counter.most_common(12)]
        # pad if needed
        while len(top12) < 12:
            candidate = random.randint(1, 49)
            if candidate not in top12:
                top12.append(candidate)
        top12 = sorted(top12[:12])
        primary = top12[:6]
        supplementary = top12[6:]
        conf_toto = round(min(0.5, counter.most_common(1)[0][1] / len(toto_sets) * 1.5), 3)
        reason_toto = f"The 12 most frequently drawn TOTO numbers across {len(toto_sets)} draws were selected as System 12."
    else:
        top12 = sorted(random.sample(range(1, 50), 12))
        primary = top12[:6]
        supplementary = top12[6:]
        conf_toto = 0.1
        reason_toto = "Insufficient data — random baseline used."

    return ModelPrediction(
        model_name="Frequency Analysis",
        model_key="frequency",
        description="Identifies 'hot' numbers based on historical draw frequency. Most-drawn digits and numbers are selected.",
        four_d=FourDPrediction(number=predicted_4d, confidence=conf_4d, reasoning=reason_4d),
        toto=TotoPrediction(
            numbers=top12, primary=primary, supplementary=supplementary,
            confidence=conf_toto, reasoning=reason_toto
        ),
        methodology=(
            "For 4D: Each digit position (thousands, hundreds, tens, units) is treated independently. "
            "A frequency counter tallies each digit (0–9) per position across all historical results. "
            "The most common digit at each position forms the predicted number.\n\n"
            "For TOTO: All individual numbers from historical draws are pooled into a single frequency table. "
            "The top 12 most-drawn numbers are selected to form a System 12 entry."
        ),
        assumptions=(
            "• Lottery draws exhibit a non-uniform distribution over finite samples.\n"
            "• Hot numbers continue to appear at above-average rates in the near term.\n"
            "• Draw results are independent but digit/number biases may persist short-term."
        ),
        validation=(
            "Back-testing on held-out draws (last 10%) measures how often predicted digits match "
            "any prize-winning entry. Expected random baseline for 4D: ~10% per position. "
            "Model aims to exceed baseline by ≥5% in back-tests."
        ),
        confidence_note=(
            "Confidence is capped at 0.55 to reflect inherent randomness. "
            "Higher data volume improves digit-frequency stability."
        ),
    )


# ---------------------------------------------------------------------------
# Model 2 — Markov Chain (Sequential Pattern)
# ---------------------------------------------------------------------------

def model_markov(four_d_numbers: List[str], toto_sets: List[List[int]]) -> ModelPrediction:
    """
    First-order Markov Chain: given the last observed value, predict the next
    most likely value based on historical transition probabilities.
    """
    # --- 4D ---
    if len(four_d_numbers) >= 4:
        # Build per-position transition matrices
        transitions = [defaultdict(Counter) for _ in range(4)]
        for i in range(len(four_d_numbers) - 1):
            curr = four_d_numbers[i]
            nxt = four_d_numbers[i + 1]
            for pos in range(4):
                transitions[pos][curr[pos]][nxt[pos]] += 1

        last = four_d_numbers[-1]
        predicted_4d = ""
        conf_parts = []
        for pos in range(4):
            trans = transitions[pos][last[pos]]
            if trans:
                best_digit, best_count = trans.most_common(1)[0]
                total = sum(trans.values())
                conf_parts.append(best_count / total)
                predicted_4d += best_digit
            else:
                predicted_4d += str(random.randint(0, 9))
                conf_parts.append(0.1)
        conf_4d = round(sum(conf_parts) / 4, 3)
        reason_4d = (
            f"Markov transitions from last drawn number '{last}' used. "
            f"Each digit position follows its most probable next digit."
        )
    else:
        predicted_4d = "".join([str(random.randint(0, 9)) for _ in range(4)])
        conf_4d = 0.1
        reason_4d = "Insufficient sequential data for Markov chain."

    # --- TOTO ---
    if len(toto_sets) >= 3:
        # Build transition counts between consecutive draws per ball position
        pos_transitions = [defaultdict(Counter) for _ in range(6)]
        for i in range(len(toto_sets) - 1):
            curr_sorted = sorted(toto_sets[i])
            next_sorted = sorted(toto_sets[i + 1])
            for pos in range(min(6, len(curr_sorted), len(next_sorted))):
                pos_transitions[pos][curr_sorted[pos]][next_sorted[pos]] += 1

        last_sorted = sorted(toto_sets[-1])
        primary = []
        for pos in range(6):
            if pos < len(last_sorted):
                trans = pos_transitions[pos][last_sorted[pos]]
                if trans:
                    primary.append(trans.most_common(1)[0][0])
                else:
                    primary.append(last_sorted[pos])
            else:
                primary.append(random.randint(1, 49))

        # Remove duplicates and ensure valid range
        primary = list(dict.fromkeys(primary))
        while len(primary) < 6:
            candidate = random.randint(1, 49)
            if candidate not in primary:
                primary.append(candidate)
        primary = sorted(primary[:6])

        # Supplementary: next 6 from transition or random
        supplementary = []
        for n in primary:
            candidate = n + random.choice([-1, 1, 2, -2, 3])
            candidate = max(1, min(49, candidate))
            if candidate not in primary and candidate not in supplementary:
                supplementary.append(candidate)
        while len(supplementary) < 6:
            candidate = random.randint(1, 49)
            if candidate not in primary and candidate not in supplementary:
                supplementary.append(candidate)
        supplementary = sorted(supplementary[:6])
        all12 = sorted(primary + supplementary)

        conf_toto = 0.3
        reason_toto = (
            f"Position-wise Markov transitions from last draw {last_sorted} applied. "
            "Each ball position follows its historically most likely next value."
        )
    else:
        all12 = sorted(random.sample(range(1, 50), 12))
        primary = all12[:6]
        supplementary = all12[6:]
        conf_toto = 0.1
        reason_toto = "Insufficient sequential data for Markov chain."

    return ModelPrediction(
        model_name="Markov Chain",
        model_key="markov",
        description="Models draw sequences as states in a Markov chain, predicting the next draw from the most probable transition.",
        four_d=FourDPrediction(number=predicted_4d, confidence=conf_4d, reasoning=reason_4d),
        toto=TotoPrediction(
            numbers=all12, primary=primary, supplementary=supplementary,
            confidence=conf_toto, reasoning=reason_toto
        ),
        methodology=(
            "A first-order Markov chain is built where each state is a digit (4D) or ball value (TOTO). "
            "Transition probabilities P(next | current) are estimated from consecutive draw pairs.\n\n"
            "For 4D: Four separate per-position transition matrices are built (digit 0–9). "
            "Given the last drawn number, the most probable next digit per position is selected.\n\n"
            "For TOTO: Six per-position transition matrices track how each sorted ball position changes "
            "between consecutive draws. The most probable successor at each position is predicted."
        ),
        assumptions=(
            "• Sequential dependence exists between consecutive draws (first-order Markov property).\n"
            "• The transition matrix is stationary — probabilities do not drift over time.\n"
            "• Sorted ball positions are comparable across draws."
        ),
        validation=(
            "Walk-forward validation: train on draws 1..N-k, predict draw N-k+1 to N. "
            "Measure mean absolute error per ball position vs. random baseline (±~16 for TOTO range 1-49)."
        ),
        confidence_note=(
            "Confidence reflects average transition probability strength. "
            "Sparse transitions (rare digit pairs) reduce confidence significantly."
        ),
    )


# ---------------------------------------------------------------------------
# Model 3 — Gap / Due-Number Analysis
# ---------------------------------------------------------------------------

def model_gap(four_d_numbers: List[str], toto_sets: List[List[int]]) -> ModelPrediction:
    """
    Gap analysis (Due-number theory): numbers that haven't appeared for a long time
    are considered 'overdue' and predicted to appear soon.
    """
    # --- 4D ---
    if len(four_d_numbers) >= 5:
        # For each digit position, find the digit with the longest absence
        last_seen = [defaultdict(lambda: -1) for _ in range(4)]
        for idx, num in enumerate(four_d_numbers):
            for pos, d in enumerate(num):
                last_seen[pos][d] = idx

        n = len(four_d_numbers)
        predicted_4d = ""
        gaps = []
        for pos in range(4):
            overdue = max(range(10), key=lambda d: n - 1 - last_seen[pos][str(d)])
            gap = n - 1 - last_seen[pos][str(overdue)]
            predicted_4d += str(overdue)
            gaps.append(gap)

        avg_gap = sum(gaps) / 4
        conf_4d = round(min(0.5, avg_gap / n * 2), 3)
        reason_4d = (
            f"Each digit position analysed for absence streaks across {n} draws. "
            f"Most overdue digit per position selected (avg gap: {avg_gap:.1f} draws)."
        )
    else:
        predicted_4d = "".join([str(random.randint(0, 9)) for _ in range(4)])
        conf_4d = 0.1
        reason_4d = "Insufficient data for gap analysis."

    # --- TOTO ---
    if len(toto_sets) >= 5:
        last_seen_toto = defaultdict(lambda: -1)
        for idx, s in enumerate(toto_sets):
            for num in s:
                last_seen_toto[num] = idx

        n = len(toto_sets)
        all_numbers = list(range(1, 50))
        overdue_scores = {num: n - 1 - last_seen_toto[num] for num in all_numbers}
        sorted_by_gap = sorted(all_numbers, key=lambda x: overdue_scores[x], reverse=True)
        top12 = sorted(sorted_by_gap[:12])
        primary = top12[:6]
        supplementary = top12[6:]

        max_gap = max(overdue_scores.values())
        conf_toto = round(min(0.45, max_gap / n * 1.5), 3)
        reason_toto = (
            f"The 12 most overdue TOTO numbers (not drawn for longest) selected across {n} draws. "
            f"Max absence streak: {max_gap} draws."
        )
    else:
        top12 = sorted(random.sample(range(1, 50), 12))
        primary = top12[:6]
        supplementary = top12[6:]
        conf_toto = 0.1
        reason_toto = "Insufficient data for gap analysis."

    return ModelPrediction(
        model_name="Gap / Due-Number Analysis",
        model_key="gap",
        description="Identifies 'cold' or overdue numbers that have not appeared for the longest time, based on the gambler's fallacy theory studied academically.",
        four_d=FourDPrediction(number=predicted_4d, confidence=conf_4d, reasoning=reason_4d),
        toto=TotoPrediction(
            numbers=top12, primary=primary, supplementary=supplementary,
            confidence=conf_toto, reasoning=reason_toto
        ),
        methodology=(
            "A 'last seen' index is tracked for every digit (4D) and ball (TOTO) across all historical draws. "
            "The gap score for each digit/number is calculated as: current_draw_index − last_seen_index.\n\n"
            "For 4D: Per position, the digit with the largest gap (longest absence) is selected.\n\n"
            "For TOTO: All 49 numbers are ranked by their gap score. The top 12 'most overdue' "
            "numbers are selected to form a System 12 entry."
        ),
        assumptions=(
            "• The law of large numbers suggests rarely drawn numbers will eventually regress to mean frequency.\n"
            "• Absence streaks provide a statistically meaningful signal within a finite sample.\n"
            "• The method is studied academically as a behavioural benchmark (gambler's fallacy)."
        ),
        validation=(
            "Empirical validation: measure the average gap at which overdue numbers eventually appear. "
            "Compare hit rate of top-12 overdue selections vs. random 12 over back-test periods."
        ),
        confidence_note=(
            "Confidence scales with gap length relative to draw history size. "
            "Longer histories produce more reliable gap signals. Note: due-number theory has weak empirical support in true RNG draws."
        ),
    )


@router.post("/generate", response_model=PredictionResponse)
async def generate_predictions(payload: Optional[PredictionGenerateRequest] = None):
    """
    Generate predictions from three models using historical draw results.
    If payload.results is omitted, history is loaded from Supabase-backed draw-history endpoints.
    """
    request = payload or PredictionGenerateRequest()

    if request.results is not None:
        if not request.results:
            raise HTTPException(status_code=400, detail="No past results provided.")

        source_results = request.results
        four_d_numbers = _get_4d_numbers_from_results(source_results)
        toto_sets = _get_toto_numbers_from_results(source_results)
        data_points_used = len(source_results)
    else:
        four_d_history, toto_history = await _load_results_from_supabase_history(request.limit)

        if not four_d_history and not toto_history:
            raise HTTPException(status_code=404, detail="No draw history available in Supabase.")

        four_d_numbers = _get_4d_numbers_from_results(four_d_history)
        toto_sets = _get_toto_numbers_from_results(toto_history)
        data_points_used = len(four_d_history) + len(toto_history)

    if not four_d_numbers and not toto_sets:
        raise HTTPException(status_code=404, detail="No usable 4D/TOTO result data found.")

    models = [
        model_frequency(four_d_numbers, toto_sets),
        model_markov(four_d_numbers, toto_sets),
        model_gap(four_d_numbers, toto_sets),
    ]

    return PredictionResponse(
        disclaimer=(
            "⚠️ DISCLAIMER: All predictions are generated purely for educational and entertainment purposes. "
            "They are NOT financial or gambling advice. Lottery draws are random events — "
            "no algorithm can reliably predict outcomes. Please gamble responsibly."
        ),
        models=models,
        data_points_used=data_points_used,
    )


@router.get("/models-info")
async def get_models_info():
    """Return static documentation for all three models."""
    return {
        "models": [
            {
                "key": "frequency",
                "name": "Frequency Analysis",
                "tagline": "Hot numbers keep appearing",
                "icon": "🔥",
            },
            {
                "key": "markov",
                "name": "Markov Chain",
                "tagline": "Next draw follows the last",
                "icon": "⛓️",
            },
            {
                "key": "gap",
                "name": "Gap / Due-Number",
                "tagline": "Overdue numbers are coming",
                "icon": "⏳",
            },
        ]
    }