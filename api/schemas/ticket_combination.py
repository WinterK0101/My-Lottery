"""
Pydantic schemas for ticket_combinations table
"""
from pydantic import BaseModel, Field, field_validator
from typing import List
from datetime import datetime


class TicketCombinationCreate(BaseModel):
    """Schema for creating a ticket combination"""
    ticket_id: str = Field(..., description="UUID of parent ticket")
    combination_index: int = Field(..., ge=0, description="0-based index of combination")
    numbers: List[int] = Field(..., description="6-number combination")
    sorted_numbers: List[int] = Field(..., description="Pre-sorted numbers for matching")

    @field_validator('numbers')
    @classmethod
    def validate_numbers_length(cls, v: List[int]) -> List[int]:
        """Validate that numbers list has exactly 6 elements"""
        if len(v) != 6:
            raise ValueError("numbers must contain exactly 6 elements")
        return v

    @field_validator('sorted_numbers')
    @classmethod
    def validate_sorted_numbers(cls, v: List[int], info) -> List[int]:
        """Validate that sorted_numbers is actually sorted"""
        if v != sorted(v):
            raise ValueError("sorted_numbers must be in ascending order")
        if len(v) != 6:
            raise ValueError("sorted_numbers must contain exactly 6 elements")
        return v

    @classmethod
    def from_numbers(
        cls,
        ticket_id: str,
        combination_index: int,
        numbers: List[int]
    ) -> "TicketCombinationCreate":
        """
        Factory method to create combination with auto-sorted numbers
        
        Args:
            ticket_id: Parent ticket UUID
            combination_index: Index in combination list
            numbers: 6-number combination
            
        Returns:
            TicketCombinationCreate instance
        """
        return cls(
            ticket_id=ticket_id,
            combination_index=combination_index,
            numbers=numbers,
            sorted_numbers=sorted(numbers)
        )

    def to_db_dict(self):
        """Convert to dictionary for database insertion"""
        return self.model_dump()


class TicketCombinationResponse(BaseModel):
    """Schema for ticket combination response from database"""
    id: int
    ticket_id: str
    combination_index: int
    numbers: List[int]
    sorted_numbers: List[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TicketCombinationBatch(BaseModel):
    """Schema for batch creating ticket combinations"""
    combinations: List[TicketCombinationCreate] = Field(..., min_length=1)

    @classmethod
    def from_ticket(
        cls,
        ticket_id: str,
        combinations: List[List[int]]
    ) -> "TicketCombinationBatch":
        """
        Factory method to create batch from ticket and combinations list
        
        Args:
            ticket_id: Parent ticket UUID
            combinations: List of 6-number combinations
            
        Returns:
            TicketCombinationBatch instance
        """
        combination_objects = [
            TicketCombinationCreate.from_numbers(
                ticket_id=ticket_id,
                combination_index=idx,
                numbers=combo
            )
            for idx, combo in enumerate(combinations)
        ]
        return cls(combinations=combination_objects)

    def to_db_list(self) -> List[dict]:
        """Convert all combinations to list of dicts for batch insertion"""
        return [combo.to_db_dict() for combo in self.combinations]
