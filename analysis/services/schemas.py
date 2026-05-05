from pydantic import BaseModel, Field
from typing import List, Optional

class ActionItem(BaseModel):
    id: str = Field(..., description="Unique ID for tracking the PR status")
    title: str = Field(..., description="Clear, non-technical title (e.g., 'Fix Missing Image Tags on Homepage')")
    impact_score: int = Field(..., description="1-10 scale of how this affects traffic/ranking")
    effort_level: str = Field(..., description="'Low', 'Medium', 'High' - Quick Wins are always 'Low'")
    explanation: str = Field(..., description="The 'So What?' explanation for a non-expert")
    technical_details: str = Field(..., description="The specific code change proposed")
    code_fix: Optional[str] = Field(None, description="The exact literal code string to push via PR")
    target_file: Optional[str] = Field(None, description="File path in the repo (e.g., 'src/app/page.tsx')")
    status: str = Field(default="pending", description="'pending', 'approved', 'pr_created'")

class TrafficDecayAlert(BaseModel):
    url: str
    drop_percentage: float = Field(..., description="Percentage drop over 30 days")
    recommended_action: str

class CannibalizationWarning(BaseModel):
    keyword: str
    competing_urls: List[str]
    recommended_action: str

class MissedClicksMetric(BaseModel):
    keyword: str
    url: str
    current_position: float
    current_ctr: float
    potential_traffic_gain: int = Field(..., description="Estimated extra clicks if CTR hit industry average")

class MobilePenaltyIndex(BaseModel):
    desktop_score: int
    mobile_score: int
    penalty_gap: int = Field(..., description="Difference between desktop and mobile scores")
    critical_issues: List[str]

class CompetitorBlindSpot(BaseModel):
    target_keyword: str
    missing_topics: List[str]
    competitor_urls: List[str]

class EnrichedStatistics(BaseModel):
    traffic_decay: List[TrafficDecayAlert]
    cannibalization: List[CannibalizationWarning]
    missed_clicks: List[MissedClicksMetric]
    mobile_penalty: MobilePenaltyIndex
    competitor_blind_spots: List[CompetitorBlindSpot]

class DashboardIntelligencePayload(BaseModel):
    global_health_score: int = Field(..., description="0-100 consolidated grade")
    technical_health: int = Field(default=85, description="Technical health score from PageSpeed")
    content_score: int = Field(default=70, description="Neural analysis of content quality")
    backlink_strength: int = Field(default=40, description="Graph-based evaluation of backlink profile")
    traffic_velocity: str = Field(..., description="'trending_up', 'trending_down', 'flat'")
    enriched_statistics: EnrichedStatistics
    critical_action_items: List[ActionItem]
    traffic: Optional[List[dict]] = Field(default=None, description="Mock traffic array for the chart")
