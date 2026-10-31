"""Deneme için örnek veri: demo işveren hesabı, diğer işletmelerin ilanları ve başvurular.

Kullanım:  python manage.py seed_isveren_demo
Giriş:     kullanıcı adı  isveren_demo   şifre  demo12345   (SADECE deneme için!)
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    Application,
    ApplicationStatus,
    ApplicationStatusLog,
    Candidate,
    Company,
    EmployerProfile,
    JobPosting,
    Language,
)

DEMO_COMPANY = "Demo Otel"


def _lang(*names):
    return list(Language.objects.filter(name__in=names))


class Command(BaseCommand):
    help = "Deneme amaçlı örnek işletme, ilan ve başvuru verisi ekler."

    @transaction.atomic
    def handle(self, *args, **options):
        if Company.objects.filter(name=DEMO_COMPANY).exists():
            self.stdout.write("Demo veri zaten var, bir şey eklenmedi.")
            return

        today = timezone.localdate()
        year = today.year if today <= date(today.year, 5, 15) else today.year + 1
        s_start, s_end = date(year, 5, 15), date(year, 9, 30)

        me = Company.objects.create(name=DEMO_COMPANY, city="girne", business_type="hotel")
        User = get_user_model()
        user = User.objects.create_user(
            username="isveren_demo", password="demo12345", first_name="Demo", last_name="İşveren"
        )
        EmployerProfile.objects.create(user=user, company=me)

        others = {
            name: Company.objects.create(name=name, city=city, business_type=btype)
            for name, city, btype in [
                ("Mavi Koy Otel", "girne", "hotel"),
                ("Palmiye Resort", "gazimagusa", "hotel"),
                ("Zeytin Bistro", "lefkosa", "restaurant"),
                ("Akdeniz Marina Club", "iskele", "bar"),
                ("Güzelyurt Portakal Bahçesi", "guzelyurt", "farm"),
                ("Sahil Kafe", "girne", "cafe"),
            ]
        }

        def job(company, title, dept, city, etype, **kw):
            langs = kw.pop("langs", [])
            j = JobPosting.objects.create(
                company=company, title=title, department=dept, city=city,
                employment_type=etype, **kw,
            )
            j.required_languages.set(_lang(*langs))
            return j

        # --- Bizim ilanlar ---
        j1 = job(me, "Resepsiyon Görevlisi (Yaz Sezonu)", "reception", "girne", "seasonal",
                 positions=2, min_experience_years=2, langs=["Türkçe", "İngilizce", "Rusça"],
                 provides_accommodation=True, provides_meals=True,
                 salary_min=45000, salary_max=55000, season_start=s_start, season_end=s_end,
                 description="Ön büro, check-in/out ve misafir ilişkileri.")
        j2 = job(me, "Aşçı Yardımcısı", "kitchen", "girne", "full_time",
                 positions=3, min_experience_years=1, langs=["Türkçe"],
                 provides_meals=True, salary_min=38000, salary_max=46000)
        job(me, "Garson", "service", "girne", "part_time",
            positions=4, min_experience_years=0, langs=["Türkçe", "İngilizce"],
            salary_min=30000, salary_max=36000)

        # --- Rakip ilanlar (piyasa) ---
        job(others["Mavi Koy Otel"], "Resepsiyonist", "reception", "girne", "seasonal",
            min_experience_years=3, langs=["Türkçe", "İngilizce"],
            provides_accommodation=True, provides_meals=True,
            salary_min=52000, salary_max=62000, season_start=s_start, season_end=s_end)
        job(others["Palmiye Resort"], "Ön Büro Görevlisi", "reception", "gazimagusa", "full_time",
            min_experience_years=1, langs=["Türkçe", "İngilizce", "Almanca"],
            provides_accommodation=True, salary_min=48000, salary_max=58000)
        job(others["Zeytin Bistro"], "Aşçı Yardımcısı", "kitchen", "lefkosa", "full_time",
            min_experience_years=2, langs=["Türkçe"], provides_meals=True,
            salary_min=40000, salary_max=47000)
        job(others["Akdeniz Marina Club"], "Garson / Barmen", "service", "iskele", "seasonal",
            min_experience_years=1, langs=["Türkçe", "İngilizce"],
            provides_accommodation=True, provides_meals=True,
            salary_min=35000, salary_max=42000, season_start=s_start, season_end=s_end)
        job(others["Akdeniz Marina Club"], "Kat Görevlisi", "housekeeping", "iskele", "seasonal",
            min_experience_years=0, langs=["Türkçe"], provides_accommodation=True,
            salary_min=32000, salary_max=36000, season_start=s_start, season_end=s_end)

        # --- Bahçe / kafe ilanları (farklı işveren türleri) ---
        job(others["Güzelyurt Portakal Bahçesi"], "Portakal Toplama Elemanı", "agriculture",
            "guzelyurt", "seasonal", positions=10, min_experience_years=0, langs=["Türkçe"],
            provides_accommodation=True, provides_meals=True,
            salary_min=28000, salary_max=34000,
            season_start=date(year, 11, 15), season_end=date(year + 1, 3, 31),
            description="Hasat sezonu boyunca bahçede portakal toplama ve sandıklama.")
        job(others["Sahil Kafe"], "Barista", "service", "girne", "full_time",
            min_experience_years=1, langs=["Türkçe", "İngilizce"], provides_meals=True,
            salary_min=34000, salary_max=40000)

        # --- Adaylar ve başvurular ---
        def candidate(name, dept, years, langs, **kw):
            c = Candidate.objects.create(
                full_name=name, email=f"{name.split()[0].lower()}@ornek.test",
                department=dept, experience_years=years, added_by_company=me, **kw,
            )
            c.languages.set(_lang(*langs))
            return c

        def apply(job_, cand, status=ApplicationStatus.SENT, days_ago=0):
            a = Application.objects.create(
                job=job_, candidate=cand, status=ApplicationStatus.SENT,
                applied_at=timezone.now() - timedelta(days=days_ago),
            )
            ApplicationStatusLog.objects.create(
                application=a, old_status="", new_status=ApplicationStatus.SENT,
                changed_by=user, changed_at=a.applied_at,
            )
            if status != ApplicationStatus.SENT:
                a.status = status
                a.save()
                ApplicationStatusLog.objects.create(
                    application=a, old_status=ApplicationStatus.SENT,
                    new_status=status, changed_by=user,
                )
            return a

        apply(j1, candidate("Ayşe Demir", "reception", 4, ["Türkçe", "İngilizce", "Rusça"],
                            needs_accommodation=True), ApplicationStatus.INTERVIEW, 3)
        apply(j1, candidate("Mehmet Kaya", "reception", 2, ["Türkçe", "İngilizce"]),
              ApplicationStatus.REVIEWED, 5)
        apply(j1, candidate("Elena Petrova", "reception", 1, ["Rusça", "İngilizce"],
                            needs_accommodation=True), ApplicationStatus.SENT, 1)
        apply(j1, candidate("Can Yıldız", "kitchen", 6, ["Türkçe"],
                            accepts_seasonal=False), ApplicationStatus.REJECTED, 7)
        apply(j2, candidate("Hasan Çelik", "kitchen", 3, ["Türkçe"]), ApplicationStatus.SENT, 2)
        apply(j2, candidate("Zeynep Arslan", "kitchen", 0, ["Türkçe", "İngilizce"],
                            needs_accommodation=True), ApplicationStatus.SENT, 0)
        apply(j2, candidate("Burak Şahin", "service", 5, ["Türkçe", "İngilizce"]),
              ApplicationStatus.ACCEPTED, 10)

        self.stdout.write(self.style.SUCCESS(
            "Demo veri eklendi. Giriş: kullanıcı 'isveren_demo', şifre 'demo12345' "
            "(sadece deneme için, gerçek kullanımda silin)."
        ))
