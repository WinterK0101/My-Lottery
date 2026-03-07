"""
Pydantic schemas for lottery_results table
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from enum import Enum


class GameType(str, Enum):
    """Valid game types"""
    FOUR_D = "4D"
    TOTO = "TOTO"


class FourDWinningNumbers(BaseModel):
    """Structure for 4D winning numbers"""
    first_prize: List[str] = Field(..., description="1st prize numbers")
    second_prize: List[str] = Field(..., description="2nd prize numbers")
    third_prize: List[str] = Field(..., description="3rd prize numbers")
    starter: List[str] = Field(..., description="Starter prize numbers")
    consolation: List[str] = Field(..., description="Consolation prize numbers")


class TotoWinningNumbers(BaseModel):
    """Structure for TOTO winning numbers"""
    winning_numbers: List[int] = Field(..., description="6 main winning numbers")

    @field_validator('winning_numbers')
    @classmethod
    def validate_winning_numbers(cls, v: List[int]) -> List[int]:
        """Validate that we have exactly 6 winning numbers"""
        if len(v) != 6:
            raise ValueError("TOTO must have exactly 6 winning numbers")
        return v


class LotteryResultCreate(BaseModel):
    """Schema for creating lottery results"""
    game_type: GameType = Field(..., description="Game type: 4D or TOTO")
    draw_date: date = Field(..., description="Draw date")
    draw_id: str = Field(..., description="Official draw ID from Singapore Pools")
    winning_numbers: Dict[str, Any] = Field(..., description="Winning numbers (structure varies by game type)")
    additional_number: Optional[int] = Field(None, description="Additional number for TOTO")

    @field_validator('winning_numbers')
    @classmethod
    def validate_winning_numbers_structure(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """Validate winning numbers structure based on game type"""
        # Get game_type from context if available
        game_type = info.data.get('game_type')
        
        if game_type == GameType.FOUR_D:
            # Validate 4D structure
            required_keys = ['first_prize', 'second_prize', 'third_prize', 'starter', 'consolation']
            for key in required_keys:
                if key not in v:
                    raise ValueError(f"4D winning_numbers must contain '{key}'")
        elif game_type == GameType.TOTO:
            # Validate TOTO structure
            if 'winning_numbers' not in v:
                raise ValueError("TOTO winning_numbers must contain 'winning_numbers' key")
            if not isinstance(v['winning_numbers'], list) or len(v['winning_numbers']) != 6:
                raise ValueError("TOTO must have exactly 6 winning numbers")
        
        return v

    @field_validator('additional_number')
    @classmethod
    def validate_additional_number(cls, v: Optional[int], info) -> Optional[int]:
        """Validate additional number is only for TOTO"""
        game_type = info.data.get('game_type')
        
        if game_type == GameType.FOUR_D and v is not None:
            raise ValueError("4D should not have an additional_number")
        elif game_type == GameType.TOTO and v is None:
            raise ValueError("TOTO must have an additional_number")
        
        return v

    @classmethod
    def create_4d_result(
        cls,
        draw_date: date,
        draw_id: str,
        first_prize: List[str],
        second_prize: List[str],
        third_prize: List[str],
        starter: List[str],
        consolation: List[str],
    ) -> "LotteryResultCreate":
        """
        Factory method for creating 4D results
        
        Args:
            draw_date: Draw date
            draw_id: Official draw ID
            first_prize: List of 1st prize numbers
            second_prize: List of 2nd prize numbers
            third_prize: List of 3rd prize numbers
            starter: List of starter numbers
            consolation: List of consolation numbers
            
        Returns:
            LotteryResultCreate instance
        """
        return cls(
            game_type=GameType.FOUR_D,
            draw_date=draw_date,
            draw_id=draw_id,
            winning_numbers={
                "first_prize": first_prize,
                "second_prize": second_prize,
                "third_prize": third_prize,
                "starter": starter,
                "consolation": consolation,
            },
            additional_number=None
        )

    @classmethod
    def create_toto_result(
        cls,
        draw_date: date,
        draw_id: str,
        winning_numbers: List[int],
        additional_number: int,
    ) -> "LotteryResultCreate":
        """
        Factory method for creating TOTO results
        
        Args:
            draw_date: Draw date
            draw_id: Official draw ID
            winning_numbers: List of 6 winning numbers
            additional_number: Additional number
            
        Returns:
            LotteryResultCreate instance
        """
        return cls(
            game_type=GameType.TOTO,
            draw_date=draw_date,
            draw_id=draw_id,
            winning_numbers={
                "winning_numbers": winning_numbers,
            },
            additional_number=additional_number
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        data = self.model_dump(exclude_none=False)
        # Convert enums to string values
        data['game_type'] = self.game_type.value
        # Convert date to string
        if isinstance(data['draw_date'], date):
            data['draw_date'] = data['draw_date'].isoformat()
        return data


class LotteryResultResponse(BaseModel):
    """Schema for lottery result response from database"""
    id: str
    game_type: str
    draw_date: date
    draw_id: str
    winning_numbers: Dict[str, Any]
    additional_number: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
