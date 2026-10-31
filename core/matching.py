"""ORM nesnelerini skor hesaplayıcıya bağlar + piyasadaki ilanları listeler."""
from django.db.models import Q
from django.utils import timezone

from .models import JobPosting, JobStatus
from .scoring import CandidateSpec, JobSpec, compute_match


def job_spec(job):
    return JobSpec(
        department=job.department,
        employment_type=job.employment_type,
        min_experience=job.min_experience_years,
        languages=frozenset(lang.name for lang in job.required_languages.all()),
        provides_accommodation=job.provides_accommodation,
        season_start=job.season_start,
    )


def candidate_spec(candidate):
    return CandidateSpec(
        department=candidate.department,
        experience_years=candidate.experience_years,
        languages=frozenset(lang.name for lang in candidate.languages.all()),
        needs_accommodation=candidate.needs_accommodation,
        accepts_types=candidate.accepted_types(),
        available_from=candidate.available_from,
    )


def attach_matches(applications, today=None):
    """Her başvuruya `.match` (MatchResult) ekler ve aynı listeyi döndürür.

    Performans için çağıran taraf şunları yapmalı:
        select_related("job", "candidate")
        prefetch_related("job__required_languages", "candidate__languages")
    """
    today = today or timezone.localdate()
    job_specs = {}
    for app in applications:
        spec = job_specs.get(app.job_id)
        if spec is None:
            spec = job_specs[app.job_id] = job_spec(app.job)
        app.match = compute_match(spec, candidate_spec(app.candidate), today)
    return applications


_TR_FOLD = str.maketrans(
    {
        "İ": "i", "I": "i", "ı": "i",
        "Ç": "c", "ç": "c", "Ğ": "g", "ğ": "g",
        "Ö": "o", "ö": "o", "Ş": "s", "ş": "s",
        "Ü": "u", "ü": "u",
    }
)


def fold_text(text):
    """Arama için: Türkçe büyük/küçük harf ve aksan farkını yok sayar.

    SQLite'ın icontains'i Ü/ü, İ/i gibi harfleri eşleştirmez; bu yüzden metin
    araması Python tarafında bu fonksiyonla yapılır. 'ucuncu' → 'Üçüncü' bulur.
    """
    return (text or "").translate(_TR_FOLD).lower()


# ----------------------------------------------------------------------------
# Piyasadaki (listelenen) ilanlar
# ----------------------------------------------------------------------------
def listed_jobs(today=None):
    """Piyasada görünen (açık ve süresi geçmemiş) tüm ilanlar."""
    today = today or timezone.localdate()
    return JobPosting.objects.filter(status=JobStatus.OPEN).filter(
        Q(season_end__isnull=True) | Q(season_end__gte=today)
    )
