from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import JobFilterForm, LoginForm, ProfileForm, RegisterForm
from .matching import calculate_match
from .models import Application, Job, Notification, Profile


def jobseeker_required(view):
    """Sadece iş arayan rolündeki kullanıcılar girebilir."""
    @wraps(view)
    @login_required(login_url="jobs:login")
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if profile is None or not profile.is_jobseeker:
            messages.error(request, "Bu alan sadece iş arayanlar içindir. Lütfen iş arayan hesabıyla giriş yapın.")
            return redirect("jobs:login")
        return view(request, *args, **kwargs)
    return wrapper


def register_view(request):
    if request.user.is_authenticated:
        return redirect("jobs:job_list")
    form = RegisterForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Kayıt tamamlandı, hoş geldiniz!")
        return redirect("jobs:job_list")
    return render(request, "jobs/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated and hasattr(request.user, "profile") \
            and request.user.profile.is_jobseeker:
        return redirect("jobs:job_list")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(request, username=form.cleaned_data["email"].lower(),
                            password=form.cleaned_data["password"])
        if user is None:
            form.add_error(None, "E-posta veya şifre hatalı.")
        else:
            profile = getattr(user, "profile", None)
            if profile is None or not profile.is_jobseeker:
                form.add_error(None, "Bu giriş sadece iş arayanlar içindir.")
            else:
                login(request, user)
                nxt = request.GET.get("next")
                if nxt and url_has_allowed_host_and_scheme(
                        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    return redirect(nxt)
                return redirect("jobs:job_list")
    return render(request, "jobs/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


@jobseeker_required
def job_list(request):
    profile = request.user.profile
    form = JobFilterForm(request.GET or None)
    jobs = Job.objects.filter(is_active=True).select_related("department") \
        .prefetch_related("required_languages")

    # Süresi dolmuş ilanları gizle
    from django.utils import timezone
    today = timezone.localdate()
    jobs = jobs.filter(Q(application_deadline__isnull=True) | Q(application_deadline__gte=today))

    sort = "new"
    if form.is_valid():
        c = form.cleaned_data
        if c["q"]:
            jobs = jobs.filter(Q(title__icontains=c["q"]) | Q(hotel_name__icontains=c["q"])
                               | Q(description__icontains=c["q"]))
        if c["department"]:
            jobs = jobs.filter(department=c["department"])
        if c["job_type"]:
            jobs = jobs.filter(job_type=c["job_type"])
        if c["language"]:
            jobs = jobs.filter(required_languages=c["language"])
        if c["location"]:
            jobs = jobs.filter(location__icontains=c["location"])
        if c["accommodation"]:
            jobs = jobs.filter(provides_accommodation=True)
        if c["meals"]:
            jobs = jobs.filter(provides_meals=True)
        if c["seasonal"]:
            jobs = jobs.filter(job_type="seasonal")
        if c["season_from"]:
            jobs = jobs.filter(season_start__gte=c["season_from"])
        if c["season_to"]:
            jobs = jobs.filter(season_end__lte=c["season_to"])
        if c["max_experience"] is not None:
            jobs = jobs.filter(min_experience__lte=c["max_experience"])
        sort = c["sort"] or "new"

    jobs = jobs.distinct()
    applied_ids = set(request.user.applications.values_list("job_id", flat=True))

    job_rows = []
    for job in jobs:
        job_rows.append({"job": job, "score": calculate_match(job, profile),
                         "applied": job.id in applied_ids})
    if sort == "match":
        job_rows.sort(key=lambda r: r["score"], reverse=True)

    return render(request, "jobs/job_list.html", {"form": form, "rows": job_rows})


@jobseeker_required
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.prefetch_related("required_languages"), pk=pk, is_active=True)
    application = Application.objects.filter(job=job, applicant=request.user).first()
    return render(request, "jobs/job_detail.html", {
        "job": job, "application": application,
        "score": calculate_match(job, request.user.profile),
    })


@jobseeker_required
@require_POST
def apply_job(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    if not job.is_open:
        messages.error(request, "Bu ilanın başvuru süresi dolmuş.")
        return redirect("jobs:job_detail", pk=pk)
    with transaction.atomic():
        application, created = Application.objects.get_or_create(
            job=job, applicant=request.user,
            defaults={
                "match_score": calculate_match(job, request.user.profile),
                "cover_note": request.POST.get("cover_note", "")[:2000],
            },
        )
    if created:
        messages.success(request, "Başvurunuz gönderildi. Durumunu 'Başvurularım' sayfasından takip edebilirsiniz.")
    else:
        messages.info(request, "Bu ilana zaten başvurdunuz.")
    return redirect("jobs:application_detail", pk=application.pk)


@jobseeker_required
def my_applications(request):
    apps = request.user.applications.select_related("job", "job__department")
    return render(request, "jobs/my_applications.html", {"applications": apps})


STEPS = [Application.Status.SENT, Application.Status.REVIEWED, Application.Status.INTERVIEW]


@jobseeker_required
def application_detail(request, pk):
    application = get_object_or_404(Application, pk=pk, applicant=request.user)
    reached = set(application.history.values_list("status", flat=True))
    timeline = []
    for s in STEPS:
        timeline.append({"label": s.label, "done": s.value in reached})
    final = None
    if application.status in (Application.Status.ACCEPTED, Application.Status.REJECTED):
        final = {"label": application.get_status_display(),
                 "accepted": application.status == Application.Status.ACCEPTED}
    return render(request, "jobs/application_detail.html", {
        "application": application, "timeline": timeline, "final": final,
        "history": application.history.all(),
    })


@jobseeker_required
def notifications_view(request):
    items = list(request.user.notifications.select_related("application"))
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "jobs/notifications.html", {"items": items})


@jobseeker_required
def profile_view(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile,
                       initial={"first_name": request.user.first_name,
                                "last_name": request.user.last_name})
    if request.method == "POST" and form.is_valid():
        form.save()
        request.user.first_name = form.cleaned_data["first_name"]
        request.user.last_name = form.cleaned_data["last_name"]
        request.user.save()
        messages.success(request, "Profil güncellendi.")
        return redirect("jobs:profile")
    return render(request, "jobs/profile.html", {"form": form})
