from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmployerAuthenticationForm

app_name = "employer"

urlpatterns = [
    path(
        "giris/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
            authentication_form=EmployerAuthenticationForm,
        ),
        name="login",
    ),
    path("kayit/", views.register, name="register"),
    path("cikis/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    # İlanlar
    path("ilanlar/", views.job_list, name="job_list"),
    path("ilanlar/yeni/", views.job_create, name="job_create"),
    path("ilanlar/<int:pk>/", views.job_detail, name="job_detail"),
    path("ilanlar/<int:pk>/duzenle/", views.job_edit, name="job_edit"),
    path("ilanlar/<int:pk>/durum/", views.job_toggle, name="job_toggle"),
    path("ilanlar/<int:pk>/basvuru-ekle/", views.application_add, name="application_add"),
    # Başvurular
    path("basvurular/", views.application_list, name="application_list"),
    path("basvurular/<int:pk>/", views.application_detail, name="application_detail"),
    # Piyasa
    path("piyasa/", views.market, name="market"),
]
