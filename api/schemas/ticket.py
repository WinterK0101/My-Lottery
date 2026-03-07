"""
Pydantic schemas for tickets table
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class GameType(str, Enum):
    """Valid game types"""
    FOUR_D = "4D"
    TOTO = "TOTO"


class TicketStatus(str, Enum):
    """Valid ticket status values"""
    PENDING = "pending"
    CHECKED = "checked"
    WON = "won"
    LOST = "lost"


class TicketMetadata(BaseModel):
    """Metadata stored in tickets.metadata JSONB field"""
    ocr_confidence: Optional[float] = None
    is_system_bet: bool = False
    is_system_roll: bool = False
    
    class Config:
        extra = "allow"  # Allow additional fields


class TicketCreate(BaseModel):
    """Schema for creating a new ticket"""
    user_id: str = Field(
        default="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
        description="User ID (defaults to fixed UUID)"
    )
    game_type: GameType = Field(..., description="Game type: 4D or TOTO")
    ticket_type: str = Field(..., description="Ticket type (e.g., 'Ordinary', 'System 7')")
    draw_date: date = Field(..., description="Draw date")
    draw_id: Optional[str] = Field(None, description="Official draw ID from Singapore Pools")
    ticket_serial_number: Optional[str] = Field(None, description="Physical ticket serial number")
    selected_numbers: List[int] = Field(..., description="Selected numbers on the ticket")
    combinations_count: int = Field(default=0, description="Number of expanded combinations")
    ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="OCR confidence score")
    image_url: Optional[str] = Field(None, description="URL of uploaded ticket image")
    metadata: Optional[TicketMetadata] = Field(default_factory=dict, description="Additional metadata")
    status: TicketStatus = Field(default=TicketStatus.PENDING, description="Ticket status")
    prize_tier: Optional[str] = Field(None, description="Prize tier if won")
    winning_amount: float = Field(default=0.0, ge=0, description="Winning amount in SGD")

    @field_validator('selected_numbers')
    @classmethod
    def validate_numbers(cls, v: List[int]) -> List[int]:
        """Validate selected numbers are not empty"""
        if not v:
            raise ValueError("selected_numbers cannot be empty")
        return v

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        data = self.model_dump(exclude_none=False)
        # Convert enums to string values
        data['game_type'] = self.game_type.value
        data['status'] = self.status.value
        # Convert date to string
        if isinstance(data['draw_date'], date):
            data['draw_date'] = data['draw_date'].isoformat()
        # Ensure metadata is a dict
        if isinstance(data.get('metadata'), TicketMetadata):
            data['metadata'] = data['metadata'].model_dump()
        return data


class TicketUpdate(BaseModel):
    """Schema for updating a ticket"""
    status: Optional[TicketStatus] = None
    prize_tier: Optional[str] = None
    winning_amount: Optional[float] = Field(None, ge=0)
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database update"""
        data = self.model_dump(exclude_none=True)
        # Convert enums to string values
        if 'status' in data:
            data['status'] = self.status.value
        return data


class TicketResponse(BaseModel):
    """Schema for ticket response from database"""
    id: str
    created_at: datetime
    user_id: str
    game_type: str
    ticket_type: str
    draw_date: date
    draw_id: Optional[str] = None
    ticket_serial_number: Optional[str] = None
    selected_numbers: List[int]
    combinations_count: int
    ocr_confidence: Optional[float] = None
    image_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    status: str
    prize_tier: Optional[str] = None
    winning_amount: Optional[float] = None
    
    class Config:
        from_attributes = True
