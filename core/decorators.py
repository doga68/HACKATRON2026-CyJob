from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.urls import reverse

from .models import EmployerProfile


def employer_required(view_func):
    """Sadece giriş yapmış işveren hesaplarının geçmesine izin verir.

    - Giriş yapmamış → giriş sayfası
    - Giriş yapmış ama işveren profili yok (ör. sadece admin) → 403 sayfası
    - işveren hesabı → request.employer ve request.company doldurulur
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=reverse("employer:login"))
        profile = (
            EmployerProfile.objects.select_related("company")
            .filter(user=request.user)
            .first()
        )
        if profile is None:
            return render(request, "core/not_employer.html", status=403)
        request.employer = profile
        request.company = profile.company
        return view_func(request, *args, **kwargs)

    return _wrapped
