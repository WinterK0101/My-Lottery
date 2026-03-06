"""
Supabase Integration Example for TOTO Ticket Data with Expanded Combinations

This module demonstrates how to insert TOTO lottery ticket data (with expanded
combinations) into Supabase using the extracted data from the FastAPI endpoint.

Prerequisites:
- Supabase project initialized
- Tables created: tickets, ticket_combinations
- Python Supabase client installed: pip install supabase
"""

import json
import logging
from typing import Optional
from datetime import datetime

# Example Supabase client setup (replace with your actual credentials)
"""
from supabase import create_client, Client

SUPABASE_URL = "your_supabase_url"
SUPABASE_KEY = "your_supabase_anon_key"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
"""

logger = logging.getLogger(__name__)


def insert_toto_ticket_with_combinations(
    supabase_client,
    extracted_data: dict,
    user_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
) -> dict:
    """
    Insert TOTO ticket data and expanded combinations into Supabase.
    
    This function:
    1. Inserts the main ticket record into 'tickets' table
    2. Inserts each combination into 'ticket_combinations' table (for efficient querying)
    
    Args:
        supabase_client: Supabase client instance
        extracted_data: The response data from /api/extract endpoint
        user_id: Optional user ID to associate with the ticket
        ticket_id: Optional override for ticket ID (uses UUID if not provided)
    
    Returns:
        Dict with status, ticket_id, and combinations_count
    
    Raises:
        Exception: If database insertion fails
    """
    
    try:
        # Extract relevant data from the API response
        game_type = extracted_data.get("game_type")
        ticket_type = extracted_data.get("ticket_type")
        draw_date = extracted_data.get("draw_date")
        numbers = extracted_data.get("numbers", [])
        expanded_combinations = extracted_data.get("expanded_combinations", [])
        confidence = extracted_data.get("confidence", 0.0)
        combinations_count = extracted_data.get("combinations_count")
        
        # Validate data before insertion
        if not numbers or game_type != "TOTO":
            raise ValueError("Invalid extracted data: missing numbers or not TOTO game")
        
        # Step 1: Insert main ticket record
        ticket_data = {
            "id": ticket_id,  # Supabase will auto-generate UUID if None
            "user_id": user_id,
            "game_type": game_type,
            "ticket_type": ticket_type,
            "draw_date": draw_date,
            "selected_numbers": numbers,  # Store original selected numbers (array)
            "combinations_count": combinations_count or len(expanded_combinations or []),
            "confidence": confidence,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": {
                "ocr_confidence": confidence,
                "is_system_bet": "System" in (ticket_type or ""),
                "is_system_roll": "System Roll" in (ticket_type or ""),
            }
        }
        
        # Insert ticket record
        ticket_response = supabase_client.table("tickets").insert(ticket_data).execute()
        
        if not ticket_response.data:
            raise Exception(f"Failed to insert ticket: {ticket_response}")
        
        inserted_ticket_id = ticket_response.data[0]["id"]
        logger.info(f"Ticket inserted with ID: {inserted_ticket_id}")
        
        combinations_inserted = 0
        
        # Step 2: Insert expanded combinations (if available)
        if expanded_combinations:
            # Batch insert combinations for better performance
            # Split into chunks of 100 to handle Supabase batch limits
            combinations_batch = []
            
            for idx, combination in enumerate(expanded_combinations):
                combination_record = {
                    "ticket_id": inserted_ticket_id,
                    "combination_index": idx,  # Position in the list (0-indexed)
                    "numbers": combination,  # Array of 6 numbers
                    "sorted_numbers": sorted(combination),  # Pre-sorted for matching
                    "created_at": datetime.utcnow().isoformat(),
                }
                combinations_batch.append(combination_record)
                
                # Batch insert in chunks of 100
                if len(combinations_batch) >= 100:
                    insert_response = (
                        supabase_client.table("ticket_combinations")
                        .insert(combinations_batch)
                        .execute()
                    )
                    combinations_inserted += len(combinations_batch)
                    combinations_batch = []
                    logger.debug(f"Inserted {combinations_inserted} combinations so far")
            
            # Insert remaining combinations
            if combinations_batch:
                insert_response = (
                    supabase_client.table("ticket_combinations")
                    .insert(combinations_batch)
                    .execute()
                )
                combinations_inserted += len(combinations_batch)
            
            logger.info(f"All {combinations_inserted} combinations inserted")
        
        return {
            "status": "success",
            "ticket_id": inserted_ticket_id,
            "combinations_count": combinations_inserted,
            "message": f"Ticket and {combinations_inserted} combinations inserted successfully",
        }
    
    except Exception as e:
        logger.error(f"Error inserting ticket data: {str(e)}", exc_info=True)
        raise


# ============================================================================
# SUPABASE TABLE SCHEMA (SQL)
# ============================================================================
"""
Create these tables in your Supabase project:

-- Main tickets table
CREATE TABLE public.tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE DEFAULT NULL,
  game_type TEXT NOT NULL CHECK (game_type IN ('TOTO', '4D')),
  ticket_type TEXT NOT NULL,  -- e.g., "Ordinary", "System 7", "System Roll"
  draw_date DATE NOT NULL,
  selected_numbers INTEGER[] NOT NULL,  -- e.g., [1, 2, 3, 4, 5, 6, 7]
  combinations_count INT NOT NULL DEFAULT 0,
  confidence DECIMAL(4, 2),  -- OCR confidence (0.00 to 1.00)
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  metadata JSONB,
  
  CONSTRAINT valid_combinations CHECK (
    (game_type = '4D') OR
    ((ticket_type LIKE 'System%' AND combinations_count > 0) OR
     (ticket_type = 'Ordinary' AND combinations_count = 0))
  )
);

CREATE INDEX idx_tickets_user_id ON public.tickets(user_id);
CREATE INDEX idx_tickets_draw_date ON public.tickets(draw_date);
CREATE INDEX idx_tickets_created_at ON public.tickets(created_at DESC);

-- Ticket combinations table (for efficient querying)
CREATE TABLE public.ticket_combinations (
  id BIGSERIAL PRIMARY KEY,
  ticket_id UUID NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
  combination_index INT NOT NULL,  -- 0-based index in the combinations list
  numbers INTEGER[] NOT NULL,  -- The 6 drawn numbers for this combination
  sorted_numbers INTEGER[] NOT NULL,  -- Pre-sorted for matching efficiency
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT valid_combination_length CHECK (array_length(numbers, 1) = 6),
  UNIQUE(ticket_id, combination_index)
);

CREATE INDEX idx_combinations_ticket_id ON public.ticket_combinations(ticket_id);
CREATE INDEX idx_combinations_sorted ON public.ticket_combinations USING GIN(sorted_numbers);

-- View for quick stats
CREATE VIEW ticket_statistics AS
SELECT 
  t.game_type,
  t.ticket_type,
  COUNT(*) as total_tickets,
  COALESCE(AVG(t.combinations_count), 0) as avg_combinations,
  MAX(t.created_at) as latest_ticket
FROM tickets t
GROUP BY t.game_type, t.ticket_type;
"""


# ============================================================================
# USAGE EXAMPLE IN FASTAPI
# ============================================================================
"""
from fastapi import FastAPI
from supabase import create_client, Client

app = FastAPI()

# Initialize Supabase client (use environment variables in production)
import os
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

@app.post("/api/extract-and-save")
async def extract_and_save(file: UploadFile = File(...), user_id: str = None):
    # Extract lottery data (this calls the existing /api/extract logic)
    extraction_result = await extract_lottery_data(file)
    
    if extraction_result.get("status") == "success":
        # Insert into Supabase with expanded combinations
        result = insert_toto_ticket_with_combinations(
            supabase,
            extraction_result["extracted_data"],
            user_id=user_id
        )
        return {
            "extraction": extraction_result,
            "database": result,
        }
    else:
        return extraction_result
"""


# ============================================================================
# QUERY EXAMPLES FOR SUPABASE
# ============================================================================
"""
-- 1. Get all tickets for a user with combination count
SELECT 
  id,
  ticket_type,
  draw_date,
  selected_numbers,
  combinations_count
FROM tickets
WHERE user_id = 'user-123'
ORDER BY created_at DESC;

-- 2. Check if a winning number combination exists in any ticket
SELECT 
  t.id,
  t.ticket_type,
  t.draw_date,
  tc.combination_index
FROM ticket_combinations tc
JOIN tickets t ON tc.ticket_id = t.id
WHERE tc.sorted_numbers = ARRAY[1,2,3,4,5,6]
  AND t.draw_date = '2025-03-08';

-- 3. Get statistics by ticket type
SELECT 
  ticket_type,
  COUNT(*) as total,
  SUM(combinations_count) as total_combinations,
  AVG(combinations_count) as avg_combinations
FROM tickets
GROUP BY ticket_type;

-- 4. System 12 tickets (largest combinations)
SELECT 
  id,
  selected_numbers,
  combinations_count,
  created_at
FROM tickets
WHERE ticket_type = 'System 12'
ORDER BY created_at DESC;
"""


if __name__ == "__main__":
    print("Supabase Integration Module")
    print("See docstrings and comments for implementation details.")
