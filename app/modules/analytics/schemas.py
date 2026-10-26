from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_consultations: int
    scheduled_consultations: int
    in_progress_consultations: int
    completed_consultations: int
    cancelled_consultations: int
    total_patients: int
    total_doctors: int
    verified_doctors: int
    total_prescriptions: int
    total_revenue: float
