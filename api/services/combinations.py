"""
TOTO System Combination Expansion Utility
Handles expansion of System Bets (7-12 numbers) into all 6-number combinations
and System Roll expansion logic.
"""

from itertools import combinations
import logging

logger = logging.getLogger(__name__)


def expand_toto_combinations(numbers: list[int], system_type: int) -> list[list[int]]:
    """
    Expand TOTO system bet numbers into all possible 6-number combinations.
    
    Args:
        numbers: List of selected numbers (7-12 numbers for system bets)
        system_type: The system type (7, 8, 9, 10, 11, or 12)
    
    Returns:
        List of all possible 6-number combinations, sorted numerically
    
    Raises:
        ValueError: If the number of numbers doesn't match the system_type
        ValueError: If any number is outside the valid TOTO range (1-49)
    
    Examples:
        >>> expand_toto_combinations([1, 2, 3, 4, 5, 6, 7], 7)
        [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 7], ..., [2, 3, 4, 5, 6, 7]]  # 7 combinations
        
        >>> expand_toto_combinations([1, 2, 3, 4, 5, 6, 7, 8], 8)
        # Returns 28 combinations
    """
    
    # Validate system_type
    if system_type not in (7, 8, 9, 10, 11, 12):
        raise ValueError(f"Invalid system type: {system_type}. Must be 7-12.")
    
    # Validate number count matches system_type
    if len(numbers) != system_type:
        raise ValueError(
            f"System {system_type} requires {system_type} numbers, "
            f"but {len(numbers)} numbers were provided."
        )
    
    # Validate all numbers are in valid TOTO range (1-49)
    for num in numbers:
        if not isinstance(num, int) or num < 1 or num > 49:
            raise ValueError(
                f"Invalid number: {num}. All numbers must be integers between 1 and 49."
            )
    
    # Check for duplicates
    if len(numbers) != len(set(numbers)):
        raise ValueError("Duplicate numbers detected. All numbers must be unique.")
    
    # Generate all 6-number combinations from the provided numbers
    all_combinations = list(combinations(numbers, 6))
    
    # Convert tuples to sorted lists
    result = [sorted(list(combo)) for combo in all_combinations]
    
    # Sort the entire result for consistency
    result.sort()
    
    logger.info(f"System {system_type} expanded into {len(result)} combinations")
    return result


def expand_toto_system_roll(numbers: list[int]) -> list[list[int]]:
    """
    Expand TOTO System Roll using 5 selected numbers + all remaining numbers.
    
    System Roll format: Takes 5 numbers and fills the 6th slot with each of the
    remaining 44 numbers (49 total - 5 selected = 44 remaining).
    
    Args:
        numbers: List of 5 selected numbers for system roll
    
    Returns:
        List of 44 combinations (5 fixed numbers + each remaining number)
    
    Raises:
        ValueError: If not exactly 5 numbers provided
        ValueError: If any number is outside the valid TOTO range (1-49)
    
    Example:
        >>> expand_toto_system_roll([1, 2, 3, 4, 5])
        # Returns 44 combinations: [1,2,3,4,5,6], [1,2,3,4,5,7], ..., [1,2,3,4,5,49]
    """
    
    # Validate exactly 5 numbers
    if len(numbers) != 5:
        raise ValueError(
            f"System Roll requires exactly 5 numbers, "
            f"but {len(numbers)} numbers were provided."
        )
    
    # Validate all numbers are in valid TOTO range
    for num in numbers:
        if not isinstance(num, int) or num < 1 or num > 49:
            raise ValueError(
                f"Invalid number: {num}. All numbers must be integers between 1 and 49."
            )
    
    # Check for duplicates
    if len(numbers) != len(set(numbers)):
        raise ValueError("Duplicate numbers detected. All numbers must be unique.")
    
    # Create set of provided numbers for quick lookup
    selected_set = set(numbers)
    
    # Generate all combinations: 5 fixed + 1 from remaining 44
    result = []
    for filler_num in range(1, 50):
        if filler_num not in selected_set:
            combination = sorted(numbers + [filler_num])
            result.append(combination)
    
    logger.info(f"System Roll expanded into {len(result)} combinations")
    return result


def validate_system_type(ticket_type: str) -> int | None:
    """
    Extract system type from ticket type string.
    
    Args:
        ticket_type: String like "System 7", "System 8", "System Roll", etc.
    
    Returns:
        System type as int (7-12), None for System Roll, or None if not a system bet
    """
    if not ticket_type:
        return None
    
    if "System Roll" in ticket_type:
        return None  # Special case: use expand_toto_system_roll instead
    
    if "System" in ticket_type:
        import re
        match = re.search(r"System\D*(\d+)", ticket_type)
        if match:
            system_num = int(match.group(1))
            if 7 <= system_num <= 12:
                return system_num
    
    return None
