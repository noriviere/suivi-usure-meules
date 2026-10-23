"""Routes de la page de consultation (lecture seule)."""
from fastapi import APIRouter

from ..services.controle import anomalies
from ..services.donnees import tableau

router = APIRouter()


@router.get("/api/donnees")
def donnees_completes():
    return tableau()


@router.get("/api/anomalies")
def api_anomalies():
    return anomalies()
