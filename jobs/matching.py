"""Uyum skoru hesabı. Ağırlıklar toplam 100 puandır.
İK paneli ile aynı fonksiyon kullanılabilir: calculate_match(job, profile)."""

W_LANG = 35
W_EXP = 30
W_DEPT = 25
W_AVAIL = 10


def calculate_match(job, profile):
    # Diller
    required = set(job.required_languages.values_list("id", flat=True))
    if required:
        known = set(profile.languages.values_list("id", flat=True))
        lang_score = W_LANG * len(required & known) / len(required)
    else:
        lang_score = W_LANG

    # Deneyim
    if job.min_experience > 0:
        exp_score = W_EXP * min(profile.experience_years / job.min_experience, 1)
    else:
        exp_score = W_EXP

    # Departman
    dept_score = W_DEPT if profile.department_id == job.department_id else 0

    # Uygunluk (çalışma türü)
    avail_score = W_AVAIL if profile.availability in ("any", job.job_type) else 0

    return round(lang_score + exp_score + dept_score + avail_score)
