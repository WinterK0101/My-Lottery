#!/usr/bin/env python3
"""
Load historical lottery results from Singapore Pools into Supabase.
Fetches multiple past draws for both 4D and TOTO games.
"""

import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from api.services.scraper import create_scraper
    from api.services.supabase import get_supabase_client
except ImportError:
    from services.scraper import create_scraper
    from services.supabase import get_supabase_client


def fetch_available_draws(game_type: str, scraper) -> List[str]:
    """
    Fetch list of available draw dates from draw list archive.
    Returns list of ISO date strings.
    """
    try:
        from bs4 import BeautifulSoup
        
        list_url = (
            scraper.TOTO_DRAW_LIST_URL if game_type == "TOTO" 
            else scraper.FOURD_DRAW_LIST_URL
        )
        
        response = scraper.session.get(
            list_url,
            headers=scraper.HEADERS,
            timeout=scraper.timeout
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        options = soup.select("option")
        
        dates = []
        for option in options[:30]:  # Get top 30 most recent draws
            label = scraper._normalize_whitespace(option.get_text(strip=True))
            iso_date = scraper._parse_draw_label_to_iso(label)
            query_string = option.get("querystring") or option.get("queryString")
            
            if iso_date and query_string:
                dates.append((iso_date, label))
        
        return dates
    except Exception as e:
        logger.error(f"Error fetching {game_type} draw list: {str(e)}")
        return []


def store_result(supabase, game_type: str, result: Dict[str, Any]) -> bool:
    """Store a single result in Supabase. Returns True if stored."""
    try:
        if result.get("status") != "success":
            logger.warning(f"Skipping {game_type} {result.get('draw_date')}: {result.get('message')}")
            return False
        
        draw_date = result.get("draw_date")
        draw_id = result.get("draw_number") or result.get("draw_id") or ""
        game_results = result.get("results", {})
        additional_number = result.get("additional_number")
        
        # Check if already exists
        existing = supabase.table("lottery_results").select("id").eq(
            "game_type", game_type
        ).eq("draw_date", draw_date).execute()
        
        if existing.data:
            logger.info(f"  ✓ {game_type} {draw_date} already exists, skipping")
            return False
        
        # Insert new result
        payload = {
            "game_type": game_type,
            "draw_date": draw_date,
            "draw_id": draw_id,
            "winning_numbers": game_results,
        }
        
        if additional_number is not None and game_type == "TOTO":
            payload["additional_number"] = additional_number
        
        supabase.table("lottery_results").insert(payload).execute()
        logger.info(f"  ✓ Stored {game_type} {draw_date}")
        return True
    except Exception as e:
        logger.error(f"  ✗ Error storing {game_type} {draw_date}: {str(e)}")
        return False


def load_historical_results(
    game_type: str = "4D",
    num_draws: int = 20,
    delay_seconds: float = 1.0
) -> int:
    """
    Load historical results for a game type.
    
    Args:
        game_type: "4D" or "TOTO"
        num_draws: Number of past draws to fetch
        delay_seconds: Delay between requests (be respectful to server)
    
    Returns:
        Number of new results stored
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Loading historical {game_type} results...")
    logger.info(f"{'='*60}")
    
    scraper = create_scraper()
    supabase = get_supabase_client()
    
    # Fetch available draw dates
    logger.info(f"Fetching available {game_type} draw dates...")
    available_dates = fetch_available_draws(game_type, scraper)
    
    if not available_dates:
        logger.error(f"Could not fetch draw list for {game_type}")
        return 0
    
    logger.info(f"Found {len(available_dates)} available draws, fetching {min(num_draws, len(available_dates))}")
    
    stored_count = 0
    for idx, (iso_date, label) in enumerate(available_dates[:num_draws]):
        logger.info(f"\n[{idx+1}/{min(num_draws, len(available_dates))}] Fetching {game_type} {iso_date}...")
        
        try:
            result = scraper.get_past_results(game_type, iso_date)
            if store_result(supabase, game_type, result):
                stored_count += 1
        except Exception as e:
            logger.error(f"  ✗ Exception: {str(e)}")
        
        # Respectful delay
        if idx < len(available_dates) - 1:
            time.sleep(delay_seconds)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✓ Stored {stored_count} new {game_type} results")
    logger.info(f"{'='*60}")
    
    return stored_count


def main():
    """Load historical results for both 4D and TOTO."""
    logger.info("Starting historical results loader...")
    
    total_4d = load_historical_results("4D", num_draws=25, delay_seconds=1.5)
    total_toto = load_historical_results("TOTO", num_draws=25, delay_seconds=1.5)
    
    total = total_4d + total_toto
    logger.info(f"\n{'='*60}")
    logger.info(f"✓ COMPLETED: Loaded {total} new results total")
    logger.info(f"  - 4D: {total_4d}")
    logger.info(f"  - TOTO: {total_toto}")
    logger.info(f"{'='*60}\n")
    
    return total


if __name__ == "__main__":
    try:
        count = main()
        sys.exit(0 if count > 0 else 1)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(2)
