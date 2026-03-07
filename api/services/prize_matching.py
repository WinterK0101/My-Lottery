"""
Prize Matching Engine for Singapore 4D and TOTO Lottery
Evaluates tickets against official results and determines prize tier.

Implements official Singapore Pools prize rules for accurate matching.
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


def _normalize_4d_number(value: any) -> Optional[str]:
    """Normalize a value into a 4-digit string, preserving leading zeros where possible."""
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 4:
        return digits
    return None


def _normalize_4d_number_list(value: any) -> List[str]:
    """Normalize starter/consolation values into a list of 4-digit strings."""
    if value is None:
        return []

    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = [value]

    normalized = []
    for item in raw_values:
        normalized_item = _normalize_4d_number(item)
        if normalized_item:
            normalized.append(normalized_item)

    return normalized


class PrizeTier(Enum):
    """TOTO prize tiers based on Singapore Pools rules."""
    GROUP_1 = "Group 1"
    GROUP_2 = "Group 2"
    GROUP_3 = "Group 3"
    GROUP_4 = "Group 4"
    GROUP_5 = "Group 5"
    GROUP_6 = "Group 6"
    GROUP_7 = "Group 7"
    NO_PRIZE = "No Prize"


class FourDPrizeTier(Enum):
    """4D prize categories."""
    FIRST = "1st Prize"
    SECOND = "2nd Prize"
    THIRD = "3rd Prize"
    STARTER = "Starter Prize"
    CONSOLATION = "Consolation Prize"
    NO_PRIZE = "No Prize"


# ============================================================================
# Prize Amount Lookup (Singapore Pools Official Rates)
# ============================================================================

def get_toto_prize_amount(prize_tier: str) -> int:
    """
    Get prize amount in SGD for TOTO prize tier.
    Based on Singapore Pools official prize tables.
    
    Args:
        prize_tier: Prize tier name (e.g., "Group 1", "No Prize")
    
    Returns:
        Prize amount in SGD (integer). Returns 0 for "No Prize".
    """
    toto_prizes = {
        "Group 1": 2400000,  # ~$2.4M for Group 1
        "Group 2": 480000,   # ~$480K for Group 2
        "Group 3": 60000,    # ~$60K for Group 3
        "Group 4": 18000,    # ~$18K for Group 4
        "Group 5": 7200,     # ~$7.2K for Group 5
        "Group 6": 2400,     # ~$2.4K for Group 6
        "Group 7": 1800,     # ~$1.8K for Group 7
        "No Prize": 0,
    }
    return toto_prizes.get(prize_tier, 0)


def get_4d_prize_amount(prize_tier: str) -> int:
    """
    Get prize amount in SGD for 4D prize tier.
    Based on Singapore Pools official prize tables.
    
    Args:
        prize_tier: Prize tier name (e.g., "1st Prize", "Starter Prize")
    
    Returns:
        Prize amount in SGD (integer). Returns 0 for "No Prize".
    """
    four_d_prizes = {
        "1st Prize": 10000,
        "2nd Prize": 3500,
        "3rd Prize": 1500,
        "Starter Prize": 500,
        "Consolation Prize": 100,
        "No Prize": 0,
    }
    return four_d_prizes.get(prize_tier, 0)


def get_prize_amount(game_type: str, prize_tier: str) -> int:
    """
    Get prize amount for any game type and prize tier.
    
    Args:
        game_type: "4D" or "TOTO"
        prize_tier: Prize tier name
    
    Returns:
        Prize amount in SGD (0 if no prize)
    """
    if game_type == "TOTO":
        return get_toto_prize_amount(prize_tier)
    elif game_type == "4D":
        return get_4d_prize_amount(prize_tier)
    else:
        return 0


def evaluate_ticket(
    user_ticket: Dict[str, any],
    official_results: Dict[str, any],
) -> Dict[str, any]:
    """
    Main evaluation function that routes to appropriate game-specific handler.
    
    Args:
        user_ticket: User's ticket data with structure:
            {
                "game_type": "4D" or "TOTO",
                "numbers": [...],
                "expanded_combinations": [...] # for TOTO system bets
            }
        official_results: Official results from scraper with structure:
            For 4D:
            {
                "game_type": "4D",
                "results": {
                    "first_prize": "1234",
                    "second_prize": "5678",
                    ...
                }
            }
            For TOTO:
            {
                "game_type": "TOTO",
                "results": {
                    "winning_numbers": [1, 2, 3, 4, 5, 6],
                    "additional_number": 7
                }
            }
    
    Returns:
        Dict with evaluation results:
        {
            "ticket_id": str,
            "game_type": "4D" or "TOTO",
            "prize_tier": str,
            "is_winner": bool,
            "matched_numbers": [...],
            "details": {...}
        }
    """
    game_type = user_ticket.get("game_type")
    
    try:
        if game_type == "4D":
            return evaluate_4d_ticket(user_ticket, official_results)
        elif game_type == "TOTO":
            return evaluate_toto_ticket(user_ticket, official_results)
        else:
            return {
                "status": "error",
                "message": f"Unknown game type: {game_type}",
                "is_winner": False,
            }
    
    except Exception as e:
        logger.error(f"Error evaluating ticket: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "is_winner": False,
        }


def evaluate_4d_ticket(
    user_ticket: Dict[str, any],
    official_results: Dict[str, any],
) -> Dict[str, any]:
    """
    Evaluate 4D ticket against official results.
    
    Checks if the user's 4-digit number matches any prize category:
    - 1st, 2nd, 3rd: Exact position match
    - Starter: Last 3 digits match
    - Consolation: Last 2 digits match
    
    Args:
        user_ticket: 4D ticket with "numbers" field (e.g., ["1234"])
        official_results: Official 4D results from scraper
    
    Returns:
        Dict with prize tier and match details
    """
    user_numbers = user_ticket.get("numbers", [])
    results = official_results.get("results", {})
    
    if not user_numbers or not results:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.NO_PRIZE.value,
            "is_winner": False,
            "reason": "Invalid ticket or results data",
        }
    
    # Get the user's 4D number (should be single string)
    user_number = str(user_numbers[0]) if user_numbers else None
    
    if not user_number or len(user_number) != 4:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.NO_PRIZE.value,
            "is_winner": False,
            "reason": "Invalid user number format",
        }
    
    # Extract official results
    first_prize = _normalize_4d_number(results.get("first_prize")) or ""
    second_prize = _normalize_4d_number(results.get("second_prize")) or ""
    third_prize = _normalize_4d_number(results.get("third_prize")) or ""
    starter_numbers = _normalize_4d_number_list(results.get("starter"))
    consolation_numbers = _normalize_4d_number_list(results.get("consolation"))
    
    # Check exact matches first (highest priority)
    if user_number == first_prize:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.FIRST.value,
            "is_winner": True,
            "matched_number": user_number,
            "details": {"match_type": "exact", "position": "first"},
        }
    
    if user_number == second_prize:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.SECOND.value,
            "is_winner": True,
            "matched_number": user_number,
            "details": {"match_type": "exact", "position": "second"},
        }
    
    if user_number == third_prize:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.THIRD.value,
            "is_winner": True,
            "matched_number": user_number,
            "details": {"match_type": "exact", "position": "third"},
        }
    
    # Check starter and consolation pools (official 4-digit exact-match lists)
    if user_number in starter_numbers:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.STARTER.value,
            "is_winner": True,
            "matched_number": user_number,
            "details": {"match_type": "starter_exact"},
        }

    if user_number in consolation_numbers:
        return {
            "game_type": "4D",
            "prize_tier": FourDPrizeTier.CONSOLATION.value,
            "is_winner": True,
            "matched_number": user_number,
            "details": {"match_type": "consolation_exact"},
        }
    
    # No prize
    return {
        "game_type": "4D",
        "prize_tier": FourDPrizeTier.NO_PRIZE.value,
        "is_winner": False,
        "reason": "No matching numbers",
    }


def evaluate_toto_ticket(
    user_ticket: Dict[str, any],
    official_results: Dict[str, any],
) -> Dict[str, any]:
    """
    Evaluate TOTO ticket against official results.
    
    For regular tickets: Check direct 6-number match
    For system bets: Iterate through expanded_combinations and find best match
    
    Args:
        user_ticket: TOTO ticket with:
            - "numbers": original selected numbers
            - "expanded_combinations": list of 6-number combinations (if system bet)
        official_results: Official TOTO results from scraper with:
            - "winning_numbers": list of 6 winning numbers
            - "additional_number": the additional number
    
    Returns:
        Dict with prize tier and match details
    """
    winning_numbers = official_results.get("results", {}).get("winning_numbers", [])
    additional_number = official_results.get("results", {}).get("additional_number")
    
    if not winning_numbers or additional_number is None:
        return {
            "game_type": "TOTO",
            "prize_tier": PrizeTier.NO_PRIZE.value,
            "is_winner": False,
            "reason": "Invalid or incomplete results",
        }
    
    # Convert winning numbers to set for faster lookup
    winning_set = set(winning_numbers)
    
    # Get combinations to check
    expanded_combinations = user_ticket.get("expanded_combinations")
    
    if expanded_combinations:
        # System bet: check all combinations
        best_tier = PrizeTier.NO_PRIZE
        best_match = None
        all_matches = []
        
        for combo_idx, combination in enumerate(expanded_combinations):
            tier, match_info = _check_toto_combination(
                combination, winning_numbers, additional_number
            )
            all_matches.append({
                "combination_index": combo_idx,
                "tier": tier.value,
                "match_info": match_info,
            })
            
            # Keep track of best prize found
            if tier.value != PrizeTier.NO_PRIZE.value:
                if best_tier.value == PrizeTier.NO_PRIZE.value or _prize_rank(tier) < _prize_rank(best_tier):
                    best_tier = tier
                    best_match = match_info
        
        return {
            "game_type": "TOTO",
            "prize_tier": best_tier.value,
            "is_winner": best_tier.value != PrizeTier.NO_PRIZE.value,
            "matched_numbers": best_match["matched_numbers"] if best_match else [],
            "has_additional": best_match["has_additional"] if best_match else False,
            "details": {
                "ticket_type": "system_bet",
                "combinations_checked": len(expanded_combinations),
                "winning_combinations": len([
                    m for m in all_matches if m["tier"] != PrizeTier.NO_PRIZE.value
                ]),
                "all_matches": all_matches[:5],  # Show top 5 matches
            },
        }
    else:
        # Regular single ticket: check direct numbers
        user_numbers = user_ticket.get("numbers", [])
        
        if not user_numbers:
            return {
                "game_type": "TOTO",
                "prize_tier": PrizeTier.NO_PRIZE.value,
                "is_winner": False,
                "reason": "No user numbers provided",
            }
        
        # For regular tickets, use first 6 numbers
        ticket_numbers = user_numbers[:6]
        
        tier, match_info = _check_toto_combination(
            ticket_numbers, winning_numbers, additional_number
        )
        
        return {
            "game_type": "TOTO",
            "prize_tier": tier.value,
            "is_winner": tier.value != PrizeTier.NO_PRIZE.value,
            "matched_numbers": match_info["matched_numbers"],
            "has_additional": match_info["has_additional"],
            "details": {
                "ticket_type": "regular",
                "matched_count": len(match_info["matched_numbers"]),
            },
        }


def _check_toto_combination(
    combination: List[int],
    winning_numbers: List[int],
    additional_number: int,
) -> Tuple[PrizeTier, Dict[str, any]]:
    """
    Check a single 6-number combination against winning numbers.
    
    Args:
        combination: List of 6 numbers from ticket
        winning_numbers: List of 6 official winning numbers
        additional_number: Official additional number
    
    Returns:
        Tuple of (PrizeTier, match_info_dict)
    """
    # Find matches
    combo_set = set(combination)
    winning_set = set(winning_numbers)
    matched = combo_set & winning_set
    matched_count = len(matched)
    has_additional = additional_number in combo_set
    
    # Determine prize tier based on official TOTO rules
    tier = get_toto_tier(matched_count, has_additional)
    
    return tier, {
        "matched_numbers": sorted(list(matched)),
        "has_additional": has_additional,
        "matched_count": matched_count,
    }


def get_toto_tier(matches: int, has_additional: bool) -> PrizeTier:
    """
    Determine TOTO prize tier based on official Singapore Pools rules.
    
    Prize Structure:
    - Group 1: 6 matches (all winning numbers)
    - Group 2: 5 matches + additional number
    - Group 3: 5 matches
    - Group 4: 4 matches + additional number
    - Group 5: 4 matches
    - Group 6: 3 matches + additional number
    - Group 7: 3 matches
    - No Prize: Anything else
    
    Args:
        matches: Number of matched winning numbers (0-6)
        has_additional: Whether the ticket has the additional number
    
    Returns:
        PrizeTier enum value
    """
    if matches == 6:
        return PrizeTier.GROUP_1
    elif matches == 5:
        if has_additional:
            return PrizeTier.GROUP_2
        else:
            return PrizeTier.GROUP_3
    elif matches == 4:
        if has_additional:
            return PrizeTier.GROUP_4
        else:
            return PrizeTier.GROUP_5
    elif matches == 3:
        if has_additional:
            return PrizeTier.GROUP_6
        else:
            return PrizeTier.GROUP_7
    else:
        return PrizeTier.NO_PRIZE


def _prize_rank(tier: PrizeTier) -> int:
    """
    Return ranking of prize tier (lower = better).
    Used for determining best prize in system bets.
    """
    ranking = {
        PrizeTier.GROUP_1: 1,
        PrizeTier.GROUP_2: 2,
        PrizeTier.GROUP_3: 3,
        PrizeTier.GROUP_4: 4,
        PrizeTier.GROUP_5: 5,
        PrizeTier.GROUP_6: 6,
        PrizeTier.GROUP_7: 7,
        PrizeTier.NO_PRIZE: 999,
    }
    return ranking.get(tier, 999)


def should_evaluate_ticket(draw_date: str) -> bool:
    """
    Determine if a ticket should be evaluated based on draw date.
    
    Args:
        draw_date: Draw date in ISO format (YYYY-MM-DD)
    
    Returns:
        True if draw date is today or in the past
    """
    from datetime import datetime, date
    
    try:
        draw_datetime = datetime.fromisoformat(draw_date).date()
        today = date.today()
        return draw_datetime <= today
    except (ValueError, AttributeError):
        return False
