from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import employer_required
from .forms import (
    ApplicationFilterForm,
    ApplicationUpdateForm,
    CandidateForm,
    EmployerRegisterForm,
    JobPostingForm,
    MarketFilterForm,
)
from .matching import (
    attach_matches,
    fold_text,
    listed_jobs,
)
from .models import (
    Application,
    ApplicationStatus,
    ApplicationStatusLog,
    Candidate,
    EmploymentType,
    JobPosting,
    JobStatus,
)


# ----------------------------------------------------------------------------
# Yardımcılar (hepsi sadece GİRİŞ YAPAN işverenin işletmesine ait verilerle çalışır)
# ----------------------------------------------------------------------------
def _own_jobs(request):
    return JobPosting.objects.filter(company=request.company)


def _own_applications(request):
    """İşletmeye ait başvurular; skor hesabı için gerekli ilişkiler önceden yüklenir."""
    return (
        Application.objects.filter(job__company=request.company)
        .select_related("job", "candidate")
        .prefetch_related("job__required_languages", "candidate__languages")
    )


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# İşveren kaydı (herkese açık; giriş gerektirmez)
# ----------------------------------------------------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect("employer:dashboard")
    form = EmployerRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Kaydınız tamamlandı. Şimdi giriş yapabilirsiniz.")
            return redirect("employer:login")
    return render(request, "core/register.html", {"form": form})


# ----------------------------------------------------------------------------
# Panel
# ----------------------------------------------------------------------------
@employer_required
def dashboard(request):
    jobs = _own_jobs(request)
    apps = Application.objects.filter(job__company=request.company)

    counts = {
        row["status"]: row["n"]
        for row in apps.order_by().values("status").annotate(n=Count("id"))
    }
    status_rows = [
        {"value": value, "label": label, "n": counts.get(value, 0)}
        for value, label in ApplicationStatus.choices
    ]

    pending = attach_matches(
        list(_own_applications(request).filter(status=ApplicationStatus.SENT))
    )
    pending.sort(key=lambda a: (-a.match.score, -a.applied_at.timestamp()))

    recent = attach_matches(list(_own_applications(request)[:8]))

    return render(
        request,
        "core/dashboard.html",
        {
            "open_jobs": jobs.filter(status=JobStatus.OPEN).count(),
            "total_jobs": jobs.count(),
            "total_apps": apps.count(),
            "status_rows": status_rows,
            "pending": pending[:5],
            "pending_total": len(pending),
            "recent": recent,
        },
    )


# ----------------------------------------------------------------------------
# İlanlarım
# ----------------------------------------------------------------------------
@employer_required
def job_list(request):
    jobs = _own_jobs(request).annotate(app_count=Count("applications"))
    return render(request, "core/job_list.html", {"jobs": jobs})


@employer_required
def job_create(request):
    form = JobPostingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.company = request.company
        job.save()
        form.save_m2m()
        messages.success(request, "İlan oluşturuldu.")
        return redirect("employer:job_detail", pk=job.pk)
    return render(request, "core/job_form.html", {"form": form, "title": "Yeni ilan"})


@employer_required
def job_edit(request, pk):
    job = get_object_or_404(_own_jobs(request), pk=pk)
    form = JobPostingForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "İlan güncellendi.")
        return redirect("employer:job_detail", pk=job.pk)
    return render(
        request,
        "core/job_form.html",
        {"form": form, "title": f"İlanı düzenle: {job.title}", "job": job},
    )


@employer_required
@require_POST
def job_toggle(request, pk):
    job = get_object_or_404(_own_jobs(request), pk=pk)
    if job.status == JobStatus.OPEN:
        job.status = JobStatus.CLOSED
        messages.success(request, "İlan kapatıldı (piyasada artık görünmez).")
    else:
        job.status = JobStatus.OPEN
        messages.success(request, "İlan yeniden açıldı.")
    job.save(update_fields=["status", "updated_at"])
    return redirect("employer:job_detail", pk=job.pk)


@employer_required
def job_detail(request, pk):
    job = get_object_or_404(
        _own_jobs(request).prefetch_related("required_languages"), pk=pk
    )
    status_filter = request.GET.get("status", "")
    if status_filter not in ApplicationStatus.values:
        status_filter = ""

    qs = (
        job.applications.select_related("candidate")
        .prefetch_related("candidate__languages")
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    applicants = attach_matches(list(qs))
    applicants.sort(key=lambda a: (-a.match.score, -a.applied_at.timestamp()))

    accepted = job.applications.filter(status=ApplicationStatus.ACCEPTED).count()

    return render(
        request,
        "core/job_detail.html",
        {
            "job": job,
            "applicants": applicants,
            "status_filter": status_filter,
            "status_choices": ApplicationStatus.choices,
            "total_applicants": job.applications.count(),
            "accepted": accepted,
        },
    )


# ----------------------------------------------------------------------------
# Başvurular
# ----------------------------------------------------------------------------
@employer_required
def application_list(request):
    form = ApplicationFilterForm(request.GET or None, company=request.company)
    qs = _own_applications(request)
    sort = "score"
    min_score = None

    if form.is_valid():
        cd = form.cleaned_data
        if cd.get("job"):
            qs = qs.filter(job=cd["job"])
        if cd.get("status"):
            qs = qs.filter(status=cd["status"])
        sort = cd.get("sort") or "score"
        min_score = cd.get("min_score")

    applications = attach_matches(list(qs))
    if min_score is not None:
        applications = [a for a in applications if a.match.score >= min_score]
    if sort == "date":
        applications.sort(key=lambda a: a.applied_at, reverse=True)
    else:
        applications.sort(key=lambda a: (-a.match.score, -a.applied_at.timestamp()))

    return render(
        request,
        "core/application_list.html",
        {"form": form, "applications": applications},
    )


@employer_required
def application_detail(request, pk):
    application = get_object_or_404(_own_applications(request), pk=pk)
    old_status = application.status

    if request.method == "POST":
        form = ApplicationUpdateForm(request.POST, instance=application)
        if form.is_valid():
            with transaction.atomic():
                application = form.save()
                if application.status != old_status:
                    ApplicationStatusLog.objects.create(
                        application=application,
                        old_status=old_status,
                        new_status=application.status,
                        changed_by=request.user,
                    )
            messages.success(request, "Başvuru güncellendi.")
            return redirect("employer:application_detail", pk=application.pk)
    else:
        form = ApplicationUpdateForm(instance=application)

    attach_matches([application])
    return render(
        request,
        "core/application_detail.html",
        {
            "application": application,
            "candidate": application.candidate,
            "job": application.job,
            "match": application.match,
            "form": form,
            "logs": application.logs.select_related("changed_by"),
        },
    )


@employer_required
def application_add(request, pk):
    """İşverenin bir ilana elle başvuru (aday) eklemesi: telefon/yüz yüze başvurular için."""
    job = get_object_or_404(_own_jobs(request), pk=pk)
    form = CandidateForm(request.POST or None, job=job)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            candidate = form.save(commit=False)
            candidate.added_by_company = request.company
            candidate.save()
            form.save_m2m()
            application = Application.objects.create(job=job, candidate=candidate)
            ApplicationStatusLog.objects.create(
                application=application,
                old_status="",
                new_status=application.status,
                changed_by=request.user,
            )
        messages.success(request, "Başvuru eklendi.")
        return redirect("employer:application_detail", pk=application.pk)
    return render(request, "core/application_form.html", {"form": form, "job": job})


# ----------------------------------------------------------------------------
# Piyasa (diğer işletmelerin ilanları)
# ----------------------------------------------------------------------------
@employer_required
def market(request):
    form = MarketFilterForm(request.GET or None)
    qs = (
        listed_jobs()
        .exclude(company=request.company)
        .select_related("company")
        .prefetch_related("required_languages")
    )

    needle = ""
    if form.is_valid():
        cd = form.cleaned_data
        needle = fold_text(cd.get("q", "").strip())
        if cd.get("department"):
            qs = qs.filter(department=cd["department"])
        if cd.get("city"):
            qs = qs.filter(city=cd["city"])
        if cd.get("business_type"):
            qs = qs.filter(company__business_type=cd["business_type"])
        if cd.get("language"):
            qs = qs.filter(required_languages=cd["language"])
        if cd.get("accommodation"):
            qs = qs.filter(provides_accommodation=True)
        if cd.get("meals"):
            qs = qs.filter(provides_meals=True)
        season_from, season_to = cd.get("season_from"), cd.get("season_to")
        if cd.get("seasonal") or season_from or season_to:
            qs = qs.filter(employment_type=EmploymentType.SEASONAL)
        # Sezon aralığı verilen aralıkla çakışan ilanlar
        if season_from:
            qs = qs.filter(season_end__gte=season_from)
        if season_to:
            qs = qs.filter(season_start__lte=season_to)

    jobs = qs.distinct()
    if needle:
        # Metin araması Türkçe harfe duyarsız olsun diye Python'da yapılır.
        jobs = [
            j
            for j in jobs
            if needle in fold_text(j.title) or needle in fold_text(j.company.name)
        ]

    page = Paginator(jobs, 20).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)

    return render(
        request,
        "core/market.html",
        {"form": form, "page": page, "query": query.urlencode()},
    )
