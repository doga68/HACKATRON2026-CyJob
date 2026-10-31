"""Uyum skoru (0-100).

Bu dosya Django'dan bağımsızdır: sadece sade veri sınıfları alır, bu yüzden
tek başına test edilebilir. ORM nesnelerini bu sınıflara çeviren kısım
`matching.py` içindedir.

Puan dağılımı (toplam 100):
    Departman  30
    Dil        25
    Deneyim    20
    Uygunluk   15  (çalışma tipi 10 + tarih 5)
    Konaklama  10
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

WEIGHTS = {
    "department": 30,
    "language": 25,
    "experience": 20,
    "availability": 15,
    "accommodation": 10,
}

SEASONAL = "seasonal"


@dataclass(frozen=True)
class JobSpec:
    department: str
    employment_type: str
    min_experience: int
    languages: frozenset  # aranan dillerin adları
    provides_accommodation: bool
    season_start: Optional[date] = None


@dataclass(frozen=True)
class CandidateSpec:
    department: str
    experience_years: int
    languages: frozenset  # bildiği dillerin adları
    needs_accommodation: bool
    accepts_types: frozenset  # kabul ettiği çalışma tipleri
    available_from: Optional[date] = None


@dataclass(frozen=True)
class Part:
    key: str
    label: str
    points: int
    max_points: int
    note: str


@dataclass(frozen=True)
class MatchResult:
    score: int
    parts: tuple

    @property
    def level(self) -> str:
        if self.score >= 75:
            return "high"
        if self.score >= 50:
            return "medium"
        return "low"

    @property
    def level_label(self) -> str:
        return {"high": "Yüksek uyum", "medium": "Orta uyum", "low": "Düşük uyum"}[
            self.level
        ]


def _half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def _department(job: JobSpec, cand: CandidateSpec) -> Part:
    mx = WEIGHTS["department"]
    if job.department == cand.department:
        return Part("department", "Departman", mx, mx, "Departman uyuşuyor")
    return Part("department", "Departman", 0, mx, "Departman uyuşmuyor")


def _language(job: JobSpec, cand: CandidateSpec) -> Part:
    mx = WEIGHTS["language"]
    required = frozenset(job.languages)
    if not required:
        return Part("language", "Dil", mx, mx, "İlanda dil şartı yok")
    matched = required & frozenset(cand.languages)
    pts = _half_up(mx * len(matched) / len(required))
    missing = sorted(required - matched)
    note = "Tüm diller uyuşuyor" if not missing else "Eksik dil: " + ", ".join(missing)
    return Part("language", "Dil", pts, mx, note)


def _experience(job: JobSpec, cand: CandidateSpec) -> Part:
    mx = WEIGHTS["experience"]
    required = max(job.min_experience, 0)
    have = max(cand.experience_years, 0)
    if required == 0:
        return Part("experience", "Deneyim", mx, mx, "İlanda deneyim şartı yok")
    pts = _half_up(mx * min(have / required, 1))
    return Part(
        "experience", "Deneyim", pts, mx, f"Aday {have} yıl, ilan en az {required} yıl istiyor"
    )


def _availability(job: JobSpec, cand: CandidateSpec, today: date) -> Part:
    mx = WEIGHTS["availability"]
    type_max, date_max = 10, 5

    type_ok = job.employment_type in cand.accepts_types
    type_pts = type_max if type_ok else 0

    if job.employment_type == SEASONAL and job.season_start:
        deadline = max(job.season_start, today)
    else:
        deadline = today + timedelta(days=30)
    date_ok = cand.available_from is None or cand.available_from <= deadline
    date_pts = date_max if date_ok else 0

    notes = []
    notes.append("Çalışma tipi uygun" if type_ok else "Aday bu çalışma tipini kabul etmiyor")
    notes.append("Tarih uygun" if date_ok else "Aday daha geç müsait")
    return Part("availability", "Uygunluk", type_pts + date_pts, mx, "; ".join(notes))


def _accommodation(job: JobSpec, cand: CandidateSpec) -> Part:
    mx = WEIGHTS["accommodation"]
    if not cand.needs_accommodation:
        return Part("accommodation", "Konaklama", mx, mx, "Adayın konaklama ihtiyacı yok")
    if job.provides_accommodation:
        return Part("accommodation", "Konaklama", mx, mx, "Aday konaklama arıyor, ilan sağlıyor")
    return Part(
        "accommodation", "Konaklama", 0, mx, "Aday konaklama arıyor, ilan sağlamıyor"
    )


def compute_match(
    job: JobSpec, cand: CandidateSpec, today: Optional[date] = None
) -> MatchResult:
    today = today or date.today()
    parts = (
        _department(job, cand),
        _language(job, cand),
        _experience(job, cand),
        _availability(job, cand, today),
        _accommodation(job, cand),
    )
    score = max(0, min(100, sum(p.points for p in parts)))
    return MatchResult(score=score, parts=parts)
