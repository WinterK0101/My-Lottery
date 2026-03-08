"""
Tickets History API
Provides user-scoped ticket history with on-demand evaluation for pending tickets.
"""

from datetime import date, datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

try:
    from ..services.draw_results_manager import create_draw_results_manager
    from ..services.prize_matching import evaluate_ticket, get_prize_amount, get_toto_tier
    from ..services.supabase import get_supabase_client
except ImportError:
    from services.draw_results_manager import create_draw_results_manager
    from services.prize_matching import evaluate_ticket, get_prize_amount, get_toto_tier
    from services.supabase import get_supabase_client


router = APIRouter(prefix="/api/tickets", tags=["tickets"])
logger = logging.getLogger(__name__)


def _parse_draw_date(draw_date_value: Any) -> Optional[date]:
    """Normalize draw date values from Supabase payloads."""
    if draw_date_value is None:
        return None

    if isinstance(draw_date_value, date):
        return draw_date_value

    draw_date_str = str(draw_date_value)
    if not draw_date_str:
        return None

    # Supabase may return "YYYY-MM-DD" or ISO timestamps.
    candidate = draw_date_str.split("T")[0]
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convert numeric-like values safely to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _estimate_ticket_cost(ticket: Dict[str, Any]) -> float:
    """
    Estimate ticket spend in SGD using combination count.
    Assumes SGD 1 per combination.
    """
    combinations_count = ticket.get("combinations_count")
    try:
        count = int(combinations_count)
    except (TypeError, ValueError):
        count = 1

    return float(max(1, count))


def _extract_expanded_combinations(rows: List[Dict[str, Any]]) -> List[List[int]]:
    """Normalize combination rows from ticket_combinations table."""
    combinations: List[List[int]] = []

    for row in sorted(rows, key=lambda r: r.get("combination_index", 0)):
        raw_numbers = row.get("numbers")
        if not isinstance(raw_numbers, list):
            continue

        normalized: List[int] = []
        for value in raw_numbers:
            try:
                normalized.append(int(value))
            except (TypeError, ValueError):
                continue

        if normalized:
            combinations.append(normalized)

    return combinations


def _build_toto_combination_analysis(
    expanded_combinations: List[List[int]],
    draw_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Annotate each expanded TOTO combination with its matching outcome."""
    results = draw_results.get("results", {}) if isinstance(draw_results, dict) else {}

    winning_numbers = results.get("winning_numbers", [])
    additional_number = results.get("additional_number")

    if not isinstance(winning_numbers, list) or additional_number is None:
        return []

    try:
        normalized_winning = [int(num) for num in winning_numbers]
        normalized_additional = int(additional_number)
    except (TypeError, ValueError):
        return []

    winning_set = set(normalized_winning)
    analysis: List[Dict[str, Any]] = []

    for combo_index, combination in enumerate(expanded_combinations):
        combo_set = set(combination)
        matched_numbers = sorted(combo_set & winning_set)
        has_additional = normalized_additional in combo_set
        tier = get_toto_tier(len(matched_numbers), has_additional).value

        analysis.append(
            {
                "combination_index": combo_index,
                "numbers": combination,
                "matched_numbers": matched_numbers,
                "matched_count": len(matched_numbers),
                "has_additional": has_additional,
                "tier": tier,
                "is_winning": tier != "No Prize",
            }
        )

    return analysis


def _fetch_ticket_combinations(
    supabase: Any,
    ticket_ids: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Load ticket combinations in a single query when possible."""
    if not ticket_ids:
        return {}

    grouped: Dict[str, List[Dict[str, Any]]] = {ticket_id: [] for ticket_id in ticket_ids}

    try:
        response = (
            supabase.table("ticket_combinations")
            .select("ticket_id, combination_index, numbers")
            .in_("ticket_id", ticket_ids)
            .order("combination_index")
            .execute()
        )

        for row in response.data or []:
            ticket_id = row.get("ticket_id")
            if ticket_id in grouped:
                grouped[ticket_id].append(row)

    except Exception as combo_error:
        # Keep endpoint resilient on old schemas where table may not exist.
        logger.warning(f"Unable to fetch ticket_combinations: {combo_error}")

    return grouped


@router.get("/{user_id}")
async def get_user_ticket_history(user_id: str):
    """
    Return ticket history for one user and evaluate stale pending tickets.

    Security:
    - Reads and updates are always scoped by user_id to prevent cross-user leaks.
    """
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        supabase = get_supabase_client()
        draw_manager = create_draw_results_manager()

        ticket_response = (
            supabase.table("tickets")
            .select("*")
            .eq("user_id", user_id)
            .order("draw_date", desc=True)
            .order("created_at", desc=True)
            .execute()
        )

        tickets: List[Dict[str, Any]] = list(ticket_response.data or [])

        if not tickets:
            return {
                "user_id": user_id,
                "summary": {
                    "total_tickets": 0,
                    "total_spent": 0.0,
                    "total_winnings": 0.0,
                    "active_tickets": 0,
                    "status_counts": {"won": 0, "lost": 0, "pending": 0},
                    "game_type_counts": {"4D": 0, "TOTO": 0},
                    "match_counts": {
                        "winning_tickets": 0,
                        "winning_combinations": 0,
                        "evaluated_now": 0,
                        "unresolved_pending": 0,
                    },
                },
                "tickets": [],
            }

        ticket_ids = [str(ticket.get("id")) for ticket in tickets if ticket.get("id")]
        combinations_by_ticket = _fetch_ticket_combinations(supabase, ticket_ids)

        today = date.today()
        draw_results_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        evaluated_now = 0
        unresolved_pending = 0

        for ticket in tickets:
            ticket_id = str(ticket.get("id") or "")
            game_type = ticket.get("game_type")
            status = ticket.get("status")
            draw_date_obj = _parse_draw_date(ticket.get("draw_date"))

            combination_rows = combinations_by_ticket.get(ticket_id, [])
            expanded_combinations = _extract_expanded_combinations(combination_rows)
            ticket["expanded_combinations"] = expanded_combinations

            # Evaluate pending tickets only when draw date has passed.
            if status == "pending" and draw_date_obj and draw_date_obj <= today:
                cache_key = (str(game_type), draw_date_obj.isoformat())

                if cache_key not in draw_results_cache:
                    draw_results_cache[cache_key] = draw_manager.get_draw_results(
                        game_type=str(game_type),
                        draw_date=draw_date_obj.isoformat(),
                        fetch_if_missing=True,
                    )

                draw_results = draw_results_cache[cache_key]

                if draw_results.get("status") == "success":
                    ticket_payload: Dict[str, Any] = {
                        "ticket_id": ticket_id,
                        "game_type": game_type,
                        "numbers": ticket.get("selected_numbers") or [],
                        "ticket_type": ticket.get("ticket_type"),
                        "draw_date": draw_date_obj.isoformat(),
                    }

                    if expanded_combinations:
                        ticket_payload["expanded_combinations"] = expanded_combinations

                    evaluation = evaluate_ticket(ticket_payload, draw_results)

                    if evaluation.get("status") != "error":
                        is_winner = bool(evaluation.get("is_winner", False))
                        prize_tier = str(evaluation.get("prize_tier", "No Prize"))
                        winning_amount = (
                            float(get_prize_amount(str(game_type), prize_tier))
                            if is_winner
                            else 0.0
                        )

                        evaluation["winning_amount"] = winning_amount

                        update_data: Dict[str, Any] = {
                            "status": "won" if is_winner else "lost",
                            "prize_tier": prize_tier,
                            "winning_amount": winning_amount,
                            "evaluation_result": evaluation,
                            "evaluated_at": datetime.now(timezone.utc).isoformat(),
                        }

                        optional_fields = [
                            "evaluated_at",
                            "evaluation_result",
                            "winning_amount",
                            "prize_tier",
                        ]

                        while True:
                            try:
                                (
                                    supabase.table("tickets")
                                    .update(update_data)
                                    .eq("id", ticket_id)
                                    .eq("user_id", user_id)
                                    .execute()
                                )
                                break
                            except Exception as update_error:
                                error_text = str(update_error)
                                removed_field = None

                                for field in optional_fields:
                                    if field in error_text and field in update_data:
                                        removed_field = field
                                        update_data.pop(field, None)
                                        logger.warning(
                                            "Column '%s' not found while updating ticket %s; retrying",
                                            field,
                                            ticket_id,
                                        )
                                        break

                                if not removed_field:
                                    raise

                        ticket["status"] = update_data.get("status", ticket.get("status"))
                        ticket["prize_tier"] = update_data.get("prize_tier", ticket.get("prize_tier"))
                        ticket["winning_amount"] = update_data.get("winning_amount", ticket.get("winning_amount"))
                        ticket["evaluation_result"] = evaluation
                        ticket["evaluated_at"] = update_data.get("evaluated_at")

                        evaluated_now += 1
                    else:
                        unresolved_pending += 1
                        ticket["evaluation_error"] = evaluation.get("message")
                else:
                    unresolved_pending += 1
                    ticket["results_lookup_error"] = draw_results.get(
                        "message",
                        "Draw results not available yet",
                    )

            # Enrich TOTO system bets with full combination outcome for frontend expansion.
            if (
                str(game_type) == "TOTO"
                and expanded_combinations
                and draw_date_obj
                and draw_date_obj <= today
            ):
                cache_key = ("TOTO", draw_date_obj.isoformat())
                if cache_key not in draw_results_cache:
                    draw_results_cache[cache_key] = draw_manager.get_draw_results(
                        game_type="TOTO",
                        draw_date=draw_date_obj.isoformat(),
                        fetch_if_missing=True,
                    )

                draw_results = draw_results_cache.get(cache_key, {})
                combination_analysis = _build_toto_combination_analysis(
                    expanded_combinations,
                    draw_results,
                )

                winning_combinations = [
                    entry for entry in combination_analysis if entry.get("is_winning")
                ]

                ticket["combination_analysis"] = combination_analysis
                ticket["winning_combinations"] = winning_combinations
                ticket["winning_combination_indexes"] = [
                    entry.get("combination_index") for entry in winning_combinations
                ]
                if draw_results.get("status") == "success":
                    ticket["draw_result"] = draw_results.get("results")

        status_counts = {"won": 0, "lost": 0, "pending": 0}
        game_type_counts = {"4D": 0, "TOTO": 0}
        total_spent = 0.0
        total_winnings = 0.0
        winning_combination_count = 0

        for ticket in tickets:
            ticket_status = str(ticket.get("status") or "pending")
            if ticket_status in status_counts:
                status_counts[ticket_status] += 1
            else:
                status_counts["pending"] += 1

            game_type = str(ticket.get("game_type") or "")
            if game_type in game_type_counts:
                game_type_counts[game_type] += 1

            total_spent += _estimate_ticket_cost(ticket)
            total_winnings += _to_float(ticket.get("winning_amount"), 0.0)

            winning_combinations = ticket.get("winning_combinations")
            if isinstance(winning_combinations, list):
                winning_combination_count += len(winning_combinations)

        summary = {
            "total_tickets": len(tickets),
            "total_spent": round(total_spent, 2),
            "total_winnings": round(total_winnings, 2),
            "active_tickets": status_counts["pending"],
            "status_counts": status_counts,
            "game_type_counts": game_type_counts,
            "match_counts": {
                "winning_tickets": status_counts["won"],
                "winning_combinations": winning_combination_count,
                "evaluated_now": evaluated_now,
                "unresolved_pending": unresolved_pending,
            },
        }

        return {
            "user_id": user_id,
            "summary": summary,
            "tickets": tickets,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching ticket history for {user_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch ticket history")

