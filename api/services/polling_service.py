"""
Polling Service for Future Draw Results
Handles checking and evaluating tickets when draw results become available.
Supports both single ticket polling and batch polling for all pending tickets.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from .draw_results_manager import create_draw_results_manager
    from .prize_matching import evaluate_ticket, get_prize_amount
    from .supabase import get_supabase_client
    from .notification_service import create_notification_service
except ImportError:
    from services.draw_results_manager import create_draw_results_manager
    from services.prize_matching import evaluate_ticket, get_prize_amount
    from services.supabase import get_supabase_client
    from services.notification_service import create_notification_service

logger = logging.getLogger(__name__)


class PollingService:
    """
    Service for polling and evaluating lottery tickets against draw results.
    Handles both past draws (immediate evaluation) and future draws (scheduled polling).
    """

    def __init__(self):
        """Initialize the polling service with necessary clients."""
        self.draw_manager = create_draw_results_manager()
        self.supabase = get_supabase_client()
        self.notification_service = create_notification_service()

    def is_draw_in_past(self, draw_date: str) -> bool:
        """
        Check if a draw date is in the past (results should be available).
        
        Args:
            draw_date: Date in YYYY-MM-DD format
        
        Returns:
            True if draw date is today or earlier, False otherwise
        """
        try:
            draw_dt = datetime.strptime(draw_date, "%Y-%m-%d").date()
            today = date.today()
            return draw_dt <= today
        except ValueError:
            logger.error(f"Invalid date format: {draw_date}")
            return False

    def get_pending_tickets_for_date(
        self,
        game_type: str,
        draw_date: str,
    ) -> List[Dict[str, any]]:
        """
        Get all pending tickets for a specific game type and draw date.
        
        Args:
            game_type: "4D" or "TOTO"
            draw_date: Date in YYYY-MM-DD format
        
        Returns:
            List of ticket records
        """
        try:
            response = (
                self.supabase.table("tickets")
                .select("*")
                .eq("game_type", game_type)
                .eq("draw_date", draw_date)
                .eq("status", "pending")
                .execute()
            )

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Error fetching pending tickets: {str(e)}")
            return []

    def get_all_pending_tickets(self) -> List[Dict[str, any]]:
        """
        Get all pending tickets across all game types and dates.
        
        Returns:
            List of ticket records
        """
        try:
            response = (
                self.supabase.table("tickets")
                .select("*")
                .eq("status", "pending")
                .execute()
            )

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Error fetching all pending tickets: {str(e)}")
            return []

    def evaluate_ticket_against_results(
        self,
        ticket: Dict[str, any],
        draw_results: Dict[str, any],
    ) -> Dict[str, any]:
        """
        Evaluate a single ticket against draw results.
        
        Args:
            ticket: Ticket record from database
            draw_results: Draw results from draw_results_manager
        
        Returns:
            Evaluation result
        """
        try:
            # Prepare ticket data for prize matching
            ticket_data = {
                "ticket_id": ticket.get("id"),
                "game_type": ticket.get("game_type"),
                "numbers": ticket.get("selected_numbers"),
                "ticket_type": ticket.get("ticket_type"),
                "draw_date": ticket.get("draw_date"),
            }

            # Get expanded combinations if they exist
            combinations_response = (
                self.supabase.table("ticket_combinations")
                .select("numbers")
                .eq("ticket_id", ticket.get("id"))
                .order("combination_index")
                .execute()
            )

            if combinations_response.data:
                ticket_data["expanded_combinations"] = [
                    combo["numbers"] for combo in combinations_response.data
                ]

            # Evaluate ticket
            evaluation = evaluate_ticket(ticket_data, draw_results)

            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating ticket {ticket.get('id')}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
            }

    def update_ticket_with_results(
        self,
        ticket_id: str,
        evaluation: Dict[str, any],
        ticket_data: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """
        Update ticket record with evaluation results and send notification to user.
        
        Args:
            ticket_id: UUID of the ticket
            evaluation: Evaluation result from prize_matching
            ticket_data: Optional ticket data (if not provided, will be fetched)
        
        Returns:
            Dict with update status
        """
        try:
            # Fetch ticket data if not provided (needed for user_id and game info)
            if not ticket_data:
                ticket_result = self.supabase.table("tickets").select("*").eq("id", ticket_id).execute()
                if ticket_result.data and len(ticket_result.data) > 0:
                    ticket_data = ticket_result.data[0]
                else:
                    ticket_data = {}
            
            # Determine status and prize tier
            is_winner = evaluation.get("is_winner", False)
            prize_tier = evaluation.get("prize_tier", "No Prize")
            
            update_data = {
                "status": "won" if is_winner else "lost",
                "prize_tier": prize_tier,
                "evaluation_result": evaluation,
                "evaluated_at": datetime.utcnow().isoformat(),
            }

            # Update winning amount if available
            if "winning_amount" in evaluation:
                update_data["winning_amount"] = evaluation["winning_amount"]

            # Backward-compatible updates for older schemas missing optional columns.
            optional_fields = ["evaluated_at", "evaluation_result", "winning_amount", "prize_tier"]
            response = None
            while True:
                try:
                    response = (
                        self.supabase.table("tickets")
                        .update(update_data)
                        .eq("id", ticket_id)
                        .execute()
                    )
                    break
                except Exception as update_err:
                    err_text = str(update_err)
                    removed_field = None
                    for field in optional_fields:
                        if field in err_text and field in update_data:
                            removed_field = field
                            update_data.pop(field, None)
                            logger.warning(
                                f"Column '{field}' not found in tickets table; retrying update without it"
                            )
                            break

                    if not removed_field:
                        raise

            if response.data:
                logger.info(f"Updated ticket {ticket_id} with evaluation results")
                
                # Send notification to user if user_id exists
                user_id = ticket_data.get("user_id")
                if user_id:
                    try:
                        prize_amount = evaluation.get("winning_amount", 0)
                        self.notification_service.notify_ticket_result(
                            user_id=user_id,
                            ticket_id=ticket_id,
                            is_winner=is_winner,
                            prize_tier=prize_tier,
                            prize_amount=prize_amount,
                            game_type=ticket_data.get("game_type", "Unknown"),
                            draw_date=ticket_data.get("draw_date", "Unknown"),
                            draw_id=ticket_data.get("draw_id")
                        )
                        logger.info(f"Notification sent for ticket {ticket_id} to user {user_id}")
                    except Exception as notify_err:
                        logger.error(f"Failed to send notification for ticket {ticket_id}: {str(notify_err)}")
                
                return {
                    "status": "success",
                    "ticket_id": ticket_id,
                    "is_winner": is_winner,
                    "prize_tier": prize_tier,
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to update ticket",
                    "ticket_id": ticket_id,
                }

        except Exception as e:
            logger.error(f"Error updating ticket {ticket_id}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "ticket_id": ticket_id,
            }

    def process_ticket(
        self,
        ticket_id: str,
        force_check: bool = False,
    ) -> Dict[str, any]:
        """
        Process a single ticket: check for results and evaluate if available.
        
        Args:
            ticket_id: UUID of the ticket
            force_check: If True, check even if draw date is in future
        
        Returns:
            Dict with processing status including winning information
        """
        try:
            # Fetch ticket from database
            response = (
                self.supabase.table("tickets")
                .select("*")
                .eq("id", ticket_id)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                return {
                    "status": "error",
                    "message": f"Ticket not found: {ticket_id}",
                }

            ticket = response.data[0]
            game_type = ticket.get("game_type")
            draw_date = ticket.get("draw_date")

            # Check if already evaluated
            if ticket.get("status") in ["won", "lost"]:
                existing_eval = ticket.get("evaluation_result", {})
                prize_tier = existing_eval.get("prize_tier", "No Prize")
                is_winner = existing_eval.get("is_winner", False)
                prize_amount = get_prize_amount(game_type, prize_tier)

                draw_information = {
                    "game_type": game_type,
                    "draw_date": draw_date,
                }

                # Include draw metadata when available for better frontend rendering.
                existing_draw_results = self.draw_manager.get_draw_results(
                    game_type=game_type,
                    draw_date=draw_date,
                    fetch_if_missing=False,
                )

                if existing_draw_results.get("status") == "success":
                    draw_information["draw_id"] = existing_draw_results.get("draw_id")
                    draw_information["winning_numbers"] = existing_draw_results.get(
                        "results", {}
                    )
                
                return {
                    "status": "already_evaluated",
                    "ticket_id": ticket_id,
                    "result": {
                        "is_winner": is_winner,
                        "prize_tier": prize_tier,
                        "prize_amount_sgd": prize_amount,
                        "message": f"You {'won' if is_winner else 'did not win'}! Prize Tier: {prize_tier}" if is_winner else "Ticket did not win.",
                    },
                    "draw_information": draw_information,
                    "evaluation_details": existing_eval,
                }

            # Check if draw is in the past
            if not force_check and not self.is_draw_in_past(draw_date):
                return {
                    "status": "pending",
                    "message": f"Draw has not occurred yet. Expected on {draw_date}.",
                    "ticket_id": ticket_id,
                    "draw_date": draw_date,
                }

            # Try to get results (from database or web)
            draw_results = self.draw_manager.get_draw_results(
                game_type=game_type,
                draw_date=draw_date,
                fetch_if_missing=True,
            )

            if draw_results.get("status") == "error":
                return {
                    "status": "no_results",
                    "message": draw_results.get(
                        "message", "Draw results not yet available"
                    ),
                    "ticket_id": ticket_id,
                    "draw_date": draw_date,
                }

            # Evaluate ticket
            evaluation = self.evaluate_ticket_against_results(ticket, draw_results)

            if evaluation.get("status") == "error":
                return {
                    "status": "evaluation_error",
                    "message": evaluation.get("message"),
                    "ticket_id": ticket_id,
                }

            # Update ticket with results
            update_result = self.update_ticket_with_results(ticket_id, evaluation, ticket)

            # Calculate prize amount
            prize_tier = evaluation.get("prize_tier", "No Prize")
            is_winner = evaluation.get("is_winner", False)
            prize_amount = get_prize_amount(game_type, prize_tier)

            return {
                "status": "success",
                "ticket_id": ticket_id,
                "result": {
                    "is_winner": is_winner,
                    "prize_tier": prize_tier,
                    "prize_amount_sgd": prize_amount,
                    "message": f"Congratulations! You won {prize_tier}! Prize: SGD ${prize_amount:,}" if is_winner else "Ticket did not win.",
                },
                "draw_information": {
                    "game_type": game_type,
                    "draw_date": draw_date,
                    "draw_id": draw_results.get("draw_id"),
                    "winning_numbers": draw_results.get("results", {}),
                },
                "evaluation_details": evaluation,
            }

        except Exception as e:
            logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "ticket_id": ticket_id,
            }

    def process_pending_tickets_for_draw(
        self,
        game_type: str,
        draw_date: str,
    ) -> Dict[str, any]:
        """
        Process all pending tickets for a specific draw.
        
        Args:
            game_type: "4D" or "TOTO"
            draw_date: Date in YYYY-MM-DD format
        
        Returns:
            Dict with batch processing results
        """
        try:
            # Get draw results first (fail fast if not available)
            draw_results = self.draw_manager.get_draw_results(
                game_type=game_type,
                draw_date=draw_date,
                fetch_if_missing=True,
            )

            if draw_results.get("status") == "error":
                return {
                    "status": "no_results",
                    "message": draw_results.get("message", "Draw results not available"),
                    "game_type": game_type,
                    "draw_date": draw_date,
                }

            # Get all pending tickets for this draw
            tickets = self.get_pending_tickets_for_date(game_type, draw_date)

            if not tickets:
                return {
                    "status": "no_tickets",
                    "message": "No pending tickets for this draw",
                    "game_type": game_type,
                    "draw_date": draw_date,
                }

            # Process each ticket
            results = {
                "total": len(tickets),
                "evaluated": 0,
                "winners": 0,
                "errors": 0,
                "tickets": [],
            }

            for ticket in tickets:
                evaluation = self.evaluate_ticket_against_results(ticket, draw_results)
                
                if evaluation.get("status") == "error":
                    results["errors"] += 1
                    continue

                update_result = self.update_ticket_with_results(
                    ticket.get("id"),
                    evaluation,
                    ticket,
                )

                if update_result.get("status") == "success":
                    results["evaluated"] += 1
                    if update_result.get("is_winner"):
                        results["winners"] += 1
                    
                    results["tickets"].append({
                        "ticket_id": ticket.get("id"),
                        "is_winner": update_result.get("is_winner"),
                        "prize_tier": update_result.get("prize_tier"),
                    })
                else:
                    results["errors"] += 1

            return {
                "status": "success",
                "game_type": game_type,
                "draw_date": draw_date,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error processing batch for {game_type} {draw_date}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "game_type": game_type,
                "draw_date": draw_date,
            }

    def poll_all_pending_tickets(self) -> Dict[str, any]:
        """
        Poll all pending tickets and evaluate those with available results.
        Useful for scheduled tasks to check multiple draws at once.
        
        Returns:
            Dict with summary of polling results
        """
        try:
            tickets = self.get_all_pending_tickets()

            if not tickets:
                return {
                    "status": "no_tickets",
                    "message": "No pending tickets to process",
                }

            # Group tickets by game type and draw date
            grouped_tickets = {}
            for ticket in tickets:
                game_type = ticket.get("game_type")
                draw_date = ticket.get("draw_date")
                key = f"{game_type}_{draw_date}"
                
                if key not in grouped_tickets:
                    grouped_tickets[key] = {
                        "game_type": game_type,
                        "draw_date": draw_date,
                        "tickets": [],
                    }
                
                grouped_tickets[key]["tickets"].append(ticket)

            # Process each unique draw
            summary = {
                "total_draws": len(grouped_tickets),
                "draws_processed": 0,
                "total_tickets": len(tickets),
                "tickets_evaluated": 0,
                "winners": 0,
                "errors": 0,
                "draws": [],
            }

            for key, group in grouped_tickets.items():
                result = self.process_pending_tickets_for_draw(
                    group["game_type"],
                    group["draw_date"],
                )

                if result.get("status") == "success":
                    summary["draws_processed"] += 1
                    results_data = result.get("results", {})
                    summary["tickets_evaluated"] += results_data.get("evaluated", 0)
                    summary["winners"] += results_data.get("winners", 0)
                    summary["errors"] += results_data.get("errors", 0)

                summary["draws"].append({
                    "game_type": group["game_type"],
                    "draw_date": group["draw_date"],
                    "status": result.get("status"),
                    "message": result.get("message"),
                })

            return {
                "status": "success",
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error polling all pending tickets: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
            }


def create_polling_service() -> PollingService:
    """Factory function to create a PollingService instance."""
    return PollingService()
