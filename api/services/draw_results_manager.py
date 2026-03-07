"""
Draw Results Manager
Handles storage and retrieval of lottery draw results from Supabase.
Provides a caching layer between scraper and database.
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, List
import json

try:
    from .supabase import get_supabase_client
    from .scraper import create_scraper
except ImportError:
    from services.supabase import get_supabase_client
    from services.scraper import create_scraper

logger = logging.getLogger(__name__)


class DrawResultsManager:
    """
    Manages lottery draw results storage and retrieval.
    Acts as a bridge between the scraper and Supabase database.
    """

    def __init__(self):
        """Initialize the manager with Supabase client."""
        self.supabase = get_supabase_client()
        self.scraper = create_scraper()

    def store_draw_results(
        self,
        game_type: str,
        draw_date: str,
        draw_id: str,
        results_data: dict,
    ) -> Dict[str, any]:
        """
        Store draw results in the database.
        
        Args:
            game_type: "4D" or "TOTO"
            draw_date: Date in format YYYY-MM-DD
            draw_id: Official draw number from Singapore Pools
            results_data: Dict containing winning numbers
        
        Returns:
            Dict with status and stored result ID
        """
        try:
            # Prepare data for database
            if game_type == "4D":
                winning_numbers = {
                    "first_prize": results_data.get("first_prize"),
                    "second_prize": results_data.get("second_prize"),
                    "third_prize": results_data.get("third_prize"),
                    "starter": results_data.get("starter"),
                    "consolation": results_data.get("consolation"),
                }
                additional_number = None
            elif game_type == "TOTO":
                winning_numbers = {
                    "winning_numbers": results_data.get("winning_numbers"),
                }
                additional_number = results_data.get("additional_number")
            else:
                return {
                    "status": "error",
                    "message": f"Invalid game_type: {game_type}",
                }

            # Insert into lottery_results table
            insert_data = {
                "game_type": game_type,
                "draw_date": draw_date,
                "draw_id": draw_id,
                "winning_numbers": winning_numbers,
                "additional_number": additional_number,
            }

            # Use upsert to avoid duplicates
            response = (
                self.supabase.table("lottery_results")
                .upsert(insert_data, on_conflict="game_type,draw_date")
                .execute()
            )

            if response.data:
                logger.info(
                    f"Stored {game_type} results for draw {draw_id} on {draw_date}"
                )
                return {
                    "status": "success",
                    "message": "Results stored successfully",
                    "result_id": response.data[0].get("id"),
                }
            else:
                logger.warning(f"No data returned when storing results for {draw_date}")
                return {
                    "status": "error",
                    "message": "Failed to store results",
                }

        except Exception as e:
            logger.error(f"Error storing draw results: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
            }

    def get_draw_results(
        self,
        game_type: str,
        draw_date: str,
        fetch_if_missing: bool = True,
    ) -> Dict[str, any]:
        """
        Retrieve draw results from database, optionally fetching from web if missing.
        
        Args:
            game_type: "4D" or "TOTO"
            draw_date: Date in format YYYY-MM-DD
            fetch_if_missing: If True, scrape from web when not in database
        
        Returns:
            Dict with draw results or error message
        """
        try:
            # Query database first
            response = (
                self.supabase.table("lottery_results")
                .select("*")
                .eq("game_type", game_type)
                .eq("draw_date", draw_date)
                .execute()
            )

            if response.data and len(response.data) > 0:
                # Results found in database
                result = response.data[0]
                logger.info(f"Retrieved {game_type} results from database for {draw_date}")
                
                # Parse winning numbers from JSONB/string payloads
                raw_winning_numbers = result.get("winning_numbers")
                if isinstance(raw_winning_numbers, dict):
                    winning_numbers = raw_winning_numbers
                elif isinstance(raw_winning_numbers, str):
                    try:
                        winning_numbers = json.loads(raw_winning_numbers)
                    except json.JSONDecodeError:
                        winning_numbers = {}
                else:
                    winning_numbers = {}

                # Keep evaluator-compatible shape for TOTO.
                # evaluate_toto_ticket expects additional_number inside results.
                if game_type == "TOTO" and "additional_number" not in winning_numbers:
                    db_additional = result.get("additional_number")
                    if db_additional is not None:
                        winning_numbers["additional_number"] = db_additional
                
                return {
                    "status": "success",
                    "source": "database",
                    "game_type": game_type,
                    "draw_date": result["draw_date"],
                    "draw_id": result["draw_id"],
                    "results": winning_numbers,
                    "additional_number": result.get("additional_number"),
                }

            # Results not in database
            if not fetch_if_missing:
                return {
                    "status": "error",
                    "message": f"No results found in database for {draw_date}",
                    "game_type": game_type,
                    "draw_date": draw_date,
                }

            # Fetch from web and store
            logger.info(f"Results not in database, fetching from web for {draw_date}")
            scraped_results = self.scraper.get_past_results(game_type, draw_date)

            if scraped_results.get("status") == "error":
                return scraped_results

            # Store the scraped results
            self.store_draw_results(
                game_type=game_type,
                draw_date=draw_date,
                draw_id=scraped_results.get("draw_id") or scraped_results.get("draw_number"),
                results_data=scraped_results.get("results", {}),
            )

            return {
                **scraped_results,
                "source": "web",
            }

        except Exception as e:
            logger.error(f"Error retrieving draw results: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "game_type": game_type,
                "draw_date": draw_date,
            }

    def check_results_exist(self, game_type: str, draw_date: str) -> bool:
        """
        Check if results exist in database for a specific draw date.
        
        Args:
            game_type: "4D" or "TOTO"
            draw_date: Date in format YYYY-MM-DD
        
        Returns:
            True if results exist, False otherwise
        """
        try:
            response = (
                self.supabase.table("lottery_results")
                .select("id")
                .eq("game_type", game_type)
                .eq("draw_date", draw_date)
                .execute()
            )

            return response.data and len(response.data) > 0

        except Exception as e:
            logger.error(f"Error checking results existence: {str(e)}")
            return False

    def get_latest_draw_date(self, game_type: str) -> Optional[str]:
        """
        Get the most recent draw date stored in database.
        
        Args:
            game_type: "4D" or "TOTO"
        
        Returns:
            Date string in YYYY-MM-DD format, or None if no results exist
        """
        try:
            response = (
                self.supabase.table("lottery_results")
                .select("draw_date")
                .eq("game_type", game_type)
                .order("draw_date", desc=True)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]["draw_date"]
            
            return None

        except Exception as e:
            logger.error(f"Error getting latest draw date: {str(e)}")
            return None

    def fetch_and_store_latest_results(self, game_type: str) -> Dict[str, any]:
        """
        Fetch latest results from web and store in database.
        Useful for scheduled polling tasks.
        
        Args:
            game_type: "4D" or "TOTO"
        
        Returns:
            Dict with status and results
        """
        try:
            # Fetch from scraper
            scraped_results = self.scraper.get_latest_results(game_type)

            if scraped_results.get("status") == "error":
                return scraped_results

            # Check if already stored
            draw_date = scraped_results.get("draw_date")
            if self.check_results_exist(game_type, draw_date):
                logger.info(f"Results already stored for {game_type} on {draw_date}")
                return {
                    "status": "already_exists",
                    "message": "Results already stored in database",
                    "game_type": game_type,
                    "draw_date": draw_date,
                }

            # Store new results
            store_result = self.store_draw_results(
                game_type=game_type,
                draw_date=draw_date,
                draw_id=scraped_results.get("draw_id") or scraped_results.get("draw_number"),
                results_data=scraped_results.get("results", {}),
            )

            return {
                **store_result,
                "draw_date": draw_date,
                "game_type": game_type,
                "results": scraped_results.get("results"),
            }

        except Exception as e:
            logger.error(f"Error fetching and storing latest results: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "game_type": game_type,
            }

    def get_results_for_date_range(
        self,
        game_type: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, any]]:
        """
        Retrieve all draw results within a date range.
        
        Args:
            game_type: "4D" or "TOTO"
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            List of draw results
        """
        try:
            response = (
                self.supabase.table("lottery_results")
                .select("*")
                .eq("game_type", game_type)
                .gte("draw_date", start_date)
                .lte("draw_date", end_date)
                .order("draw_date", desc=True)
                .execute()
            )

            if not response.data:
                return []

            # Parse results
            results = []
            for result in response.data:
                winning_numbers = json.loads(result["winning_numbers"])
                results.append({
                    "game_type": result["game_type"],
                    "draw_date": result["draw_date"],
                    "draw_id": result["draw_id"],
                    "results": winning_numbers,
                    "additional_number": result.get("additional_number"),
                })

            return results

        except Exception as e:
            logger.error(f"Error retrieving date range results: {str(e)}")
            return []


def create_draw_results_manager() -> DrawResultsManager:
    """Factory function to create a DrawResultsManager instance."""
    return DrawResultsManager()
