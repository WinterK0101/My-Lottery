"""
Pydantic schemas for database models and API requests/responses
"""
from .ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketMetadata,
    GameType,
    TicketStatus,
)
from .ticket_combination import (
    TicketCombinationCreate,
    TicketCombinationResponse,
    TicketCombinationBatch,
)
from .lottery_result import (
    LotteryResultCreate,
    LotteryResultResponse,
    FourDWinningNumbers,
    TotoWinningNumbers,
)
from .notification import (
    NotificationRequest,
    UserSubscriptionCreate,
    UserSubscriptionUpdate,
    UserSubscriptionResponse,
)
from .prediction import (
    FourDPrediction,
    TotoPrediction,
    ModelPrediction,
    PredictionResponse,
    PredictionGenerateRequest,
)

__all__ = [
    # Ticket schemas
    "TicketCreate",
    "TicketUpdate",
    "TicketResponse",
    "TicketMetadata",
    "GameType",
    "TicketStatus",
    # Ticket combination schemas
    "TicketCombinationCreate",
    "TicketCombinationResponse",
    "TicketCombinationBatch",
    # Lottery result schemas
    "LotteryResultCreate",
    "LotteryResultResponse",
    "FourDWinningNumbers",
    "TotoWinningNumbers",
    # Notification schemas
    "NotificationRequest",
    "UserSubscriptionCreate",
    "UserSubscriptionUpdate",
    "UserSubscriptionResponse",
    # Prediction schemas
    "FourDPrediction",
    "TotoPrediction",
    "ModelPrediction",
    "PredictionResponse",
    "PredictionGenerateRequest",
]
