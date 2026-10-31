from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("kayit/", views.register_view, name="register"),
    path("giris/", views.login_view, name="login"),
    path("cikis/", views.logout_view, name="logout"),
    path("ilan/<int:pk>/", views.job_detail, name="job_detail"),
    path("ilan/<int:pk>/basvur/", views.apply_job, name="apply_job"),
    path("basvurularim/", views.my_applications, name="my_applications"),
    path("basvuru/<int:pk>/", views.application_detail, name="application_detail"),
    path("bildirimler/", views.notifications_view, name="notifications"),
    path("profil/", views.profile_view, name="profile"),
]
