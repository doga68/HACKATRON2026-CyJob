from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from jobs.models import Department, Job, Language, Profile, Application

# Sıra önemli: seçim listesinde bu sırayla görünür ("Diğer" en sonda).
DEPARTMENTS = ["Otel", "Restoran", "Kafe/Pastane", "Bar/Eğlence Mekanı",
               "Tarım/Bahçe/Çiftlik", "Market/Mağaza", "Diğer"]

# Eski departmanları yenilerine taşır (ilan ve profil bilgisi kaybolmaz).
OLD_TO_NEW = {
    "Resepsiyon": "Otel", "Kat Hizmetleri": "Otel", "Animasyon": "Otel",
    "Teknik Servis": "Otel", "Mutfak": "Restoran", "Restoran & Bar": "Restoran",
    "Satış & Pazarlama": "Market/Mağaza",
}
LANGUAGES = ["Türkçe", "İngilizce", "Rusça", "Almanca", "Yunanca", "Arapça"]


class Command(BaseCommand):
    help = "Departman/dil listesini günceller ve test için örnek ilan ekler."

    def handle(self, *args, **options):
        D = {n: Department.objects.get_or_create(name=n)[0] for n in DEPARTMENTS}
        L = {n: Language.objects.get_or_create(name=n)[0] for n in LANGUAGES}

        # Eski departmanları taşı ve sil
        for old_name, new_name in OLD_TO_NEW.items():
            old = Department.objects.filter(name=old_name).first()
            if old:
                Job.objects.filter(department=old).update(department=D[new_name])
                Profile.objects.filter(department=old).update(department=D[new_name])
                old.delete()

        hr, created = User.objects.get_or_create(
            username="ik@demo.com", defaults={"email": "ik@demo.com", "is_staff": True})
        if created:
            hr.set_password("demo12345")
            hr.save()
        Profile.objects.get_or_create(user=hr, defaults={"role": Profile.Role.HR})

        if not Job.objects.exists():
            y = date.today().year
            samples = [
                ("Resepsiyon Görevlisi", "Grand Kyrenia Hotel", "Girne", "Otel", "full_time",
                 ["İngilizce", "Rusça"], 2, True, True, None, None),
                ("Aşçı Yardımcısı", "Bellapais Restaurant", "Girne", "Restoran", "seasonal",
                 ["Türkçe"], 1, True, True, date(y + 1, 5, 15), date(y + 1, 9, 30)),
                ("Garson", "Salamis Beach Bar", "Gazimağusa", "Bar/Eğlence Mekanı", "seasonal",
                 ["İngilizce"], 0, False, True, date(y + 1, 6, 1), date(y + 1, 9, 15)),
                ("Barista", "Kyrenia Harbour Cafe", "Girne", "Kafe/Pastane", "part_time",
                 ["İngilizce"], 0, False, False, None, None),
                ("Kasiyer", "Lefkoşa Market", "Lefkoşa", "Market/Mağaza", "full_time",
                 [], 0, False, False, None, None),
                ("Bahçıvan", "Karpaz Farm", "İskele", "Tarım/Bahçe/Çiftlik", "seasonal",
                 [], 0, True, True, date(y + 1, 4, 1), date(y + 1, 10, 31)),
            ]
            for (t, h, loc, d, jt, lg, exp, acc, meal, s, e) in samples:
                job = Job.objects.create(
                    title=t, hotel_name=h, location=loc, department=D[d], job_type=jt,
                    description=f"{h} bünyesinde {t} aranıyor.", min_experience=exp,
                    provides_accommodation=acc, provides_meals=meal,
                    season_start=s, season_end=e, created_by=hr,
                    application_deadline=date.today() + timedelta(days=60),
                )
                job.required_languages.set([L[x] for x in lg])
        self.stdout.write(self.style.SUCCESS(
            "Departmanlar güncellendi. İK demo: ik@demo.com / demo12345"))
