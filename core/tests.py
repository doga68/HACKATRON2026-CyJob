from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Application,
    ApplicationStatus,
    ApplicationStatusLog,
    Candidate,
    Company,
    EmployerProfile,
    JobPosting,
    Language,
)
from .scoring import CandidateSpec, JobSpec, compute_match

TODAY = date(2026, 10, 31)


# ----------------------------------------------------------------------------
# Uyum skoru (Django'suz saf mantık)
# ----------------------------------------------------------------------------
class ScoringTests(SimpleTestCase):
    def job(self, **kw):
        base = dict(
            department="reception",
            employment_type="seasonal",
            min_experience=2,
            languages=frozenset({"Türkçe", "İngilizce"}),
            provides_accommodation=True,
            season_start=date(2027, 5, 15),
        )
        base.update(kw)
        return JobSpec(**base)

    def cand(self, **kw):
        base = dict(
            department="reception",
            experience_years=3,
            languages=frozenset({"Türkçe", "İngilizce"}),
            needs_accommodation=True,
            accepts_types=frozenset({"seasonal", "full_time"}),
            available_from=None,
        )
        base.update(kw)
        return CandidateSpec(**base)

    def test_perfect_match_is_100(self):
        r = compute_match(self.job(), self.cand(), TODAY)
        self.assertEqual(r.score, 100)
        self.assertEqual(r.level, "high")

    def test_parts_sum_to_score_and_max_is_100(self):
        r = compute_match(self.job(), self.cand(department="kitchen", experience_years=1), TODAY)
        self.assertEqual(sum(p.points for p in r.parts), r.score)
        self.assertEqual(sum(p.max_points for p in r.parts), 100)

    def test_wrong_department_loses_30(self):
        r = compute_match(self.job(), self.cand(department="kitchen"), TODAY)
        self.assertEqual(r.score, 70)

    def test_partial_language(self):
        r = compute_match(self.job(), self.cand(languages=frozenset({"Türkçe"})), TODAY)
        lang = next(p for p in r.parts if p.key == "language")
        self.assertEqual(lang.points, 13)  # 25 * 1/2 = 12.5 → 13
        self.assertIn("İngilizce", lang.note)

    def test_no_language_requirement_gives_full_points(self):
        r = compute_match(self.job(languages=frozenset()), self.cand(languages=frozenset()), TODAY)
        self.assertEqual(r.score, 100)

    def test_experience_scales_and_caps(self):
        half = compute_match(self.job(min_experience=4), self.cand(experience_years=2), TODAY)
        exp = next(p for p in half.parts if p.key == "experience")
        self.assertEqual(exp.points, 10)
        more = compute_match(self.job(min_experience=2), self.cand(experience_years=20), TODAY)
        self.assertEqual(next(p for p in more.parts if p.key == "experience").points, 20)

    def test_zero_experience_required(self):
        r = compute_match(self.job(min_experience=0), self.cand(experience_years=0), TODAY)
        self.assertEqual(r.score, 100)

    def test_accommodation_needed_but_not_provided(self):
        r = compute_match(self.job(provides_accommodation=False), self.cand(), TODAY)
        self.assertEqual(r.score, 90)

    def test_accommodation_not_needed_is_fine_either_way(self):
        r = compute_match(
            self.job(provides_accommodation=False), self.cand(needs_accommodation=False), TODAY
        )
        self.assertEqual(r.score, 100)

    def test_employment_type_not_accepted(self):
        r = compute_match(self.job(), self.cand(accepts_types=frozenset({"full_time"})), TODAY)
        self.assertEqual(r.score, 90)

    def test_available_after_season_start(self):
        r = compute_match(self.job(), self.cand(available_from=date(2027, 6, 1)), TODAY)
        self.assertEqual(r.score, 95)

    def test_available_before_season_start(self):
        r = compute_match(self.job(), self.cand(available_from=date(2027, 5, 1)), TODAY)
        self.assertEqual(r.score, 100)

    def test_non_seasonal_far_future_availability(self):
        r = compute_match(
            self.job(employment_type="full_time", season_start=None),
            self.cand(available_from=TODAY + timedelta(days=90)),
            TODAY,
        )
        self.assertEqual(r.score, 95)

    def test_score_never_out_of_range(self):
        worst = compute_match(
            self.job(provides_accommodation=False),
            self.cand(
                department="kitchen",
                experience_years=0,
                languages=frozenset(),
                accepts_types=frozenset(),
                available_from=date(2030, 1, 1),
            ),
            TODAY,
        )
        self.assertEqual(worst.score, 0)
        self.assertEqual(worst.level, "low")


# ----------------------------------------------------------------------------
# Yardımcı: test verisi
# ----------------------------------------------------------------------------
class DataMixin:
    @classmethod
    def make_employer(cls, username, company_name):
        User = get_user_model()
        user = User.objects.create_user(username=username, password="test-pass-123")
        company = Company.objects.create(name=company_name)
        EmployerProfile.objects.create(user=user, company=company)
        return user, company

    @classmethod
    def make_job(cls, company, **kw):
        defaults = dict(
            title="Resepsiyon", department="reception", city="girne",
            employment_type="full_time",
        )
        defaults.update(kw)
        return JobPosting.objects.create(company=company, **defaults)

    _candidate_seq = 0

    @classmethod
    def make_candidate(cls, name="Ali Veli", email=None, **kw):
        DataMixin._candidate_seq += 1
        defaults = dict(department="reception", experience_years=2)
        defaults.update(kw)
        return Candidate.objects.create(
            full_name=name,
            email=email or f"aday{DataMixin._candidate_seq}@ornek.test",
            **defaults,
        )


# ----------------------------------------------------------------------------
# Erişim: sadece işveren girer, sadece kendi işletmesinin verisini görür
# ----------------------------------------------------------------------------
class AccessControlTests(DataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a, cls.company_a = cls.make_employer("isveren_a", "Şirket A")
        cls.user_b, cls.company_b = cls.make_employer("isveren_b", "Şirket B")
        cls.job_a = cls.make_job(cls.company_a, title="A İlanı")
        cls.job_b = cls.make_job(cls.company_b, title="B İlanı")
        cls.app_a = Application.objects.create(job=cls.job_a, candidate=cls.make_candidate("Aday Bir"))
        cls.app_b = Application.objects.create(job=cls.job_b, candidate=cls.make_candidate("Aday İki"))

    def test_anonymous_redirected_to_login(self):
        for name, args in [
            ("dashboard", []), ("job_list", []), ("application_list", []),
            ("market", []), ("job_detail", [self.job_a.pk]),
            ("application_detail", [self.app_a.pk]),
        ]:
            resp = self.client.get(reverse("employer:" + name, args=args))
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn(reverse("employer:login"), resp["Location"], name)

    def test_logged_in_user_without_employer_profile_gets_403(self):
        User = get_user_model()
        User.objects.create_superuser("admin", "a@a.com", "test-pass-123")
        self.client.login(username="admin", password="test-pass-123")
        for name in ["dashboard", "job_list", "application_list", "market"]:
            self.assertEqual(self.client.get(reverse("employer:" + name)).status_code, 403, name)

    def test_employer_cannot_open_other_companys_job_or_application(self):
        self.client.login(username="isveren_a", password="test-pass-123")
        self.assertEqual(self.client.get(reverse("employer:job_detail", args=[self.job_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("employer:job_edit", args=[self.job_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("employer:application_add", args=[self.job_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("employer:application_detail", args=[self.app_b.pk])).status_code, 404)

    def test_employer_cannot_change_other_companys_application_or_job(self):
        self.client.login(username="isveren_a", password="test-pass-123")
        resp = self.client.post(
            reverse("employer:application_detail", args=[self.app_b.pk]),
            {"status": ApplicationStatus.ACCEPTED, "employer_note": "x"},
        )
        self.assertEqual(resp.status_code, 404)
        self.app_b.refresh_from_db()
        self.assertEqual(self.app_b.status, ApplicationStatus.SENT)

        resp = self.client.post(reverse("employer:job_toggle", args=[self.job_b.pk]))
        self.assertEqual(resp.status_code, 404)
        self.job_b.refresh_from_db()
        self.assertEqual(self.job_b.status, "open")

    def test_lists_only_show_own_company(self):
        self.client.login(username="isveren_a", password="test-pass-123")
        self.assertContains(self.client.get(reverse("employer:job_list")), "A İlanı")
        self.assertNotContains(self.client.get(reverse("employer:job_list")), "B İlanı")
        resp = self.client.get(reverse("employer:application_list"))
        self.assertContains(resp, "Aday Bir")
        self.assertNotContains(resp, "Aday İki")
        resp = self.client.get(reverse("employer:dashboard"))
        self.assertNotContains(resp, "Aday İki")

    def test_logout_requires_post(self):
        self.client.login(username="isveren_a", password="test-pass-123")
        self.assertEqual(self.client.get(reverse("employer:logout")).status_code, 405)
        resp = self.client.post(reverse("employer:logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.get(reverse("employer:dashboard")).status_code, 302)

    def test_login_works_and_wrong_password_fails(self):
        resp = self.client.post(reverse("employer:login"), {"username": "isveren_a", "password": "yanlis"})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse("employer:login"), {"username": "isveren_a", "password": "test-pass-123"})
        self.assertRedirects(resp, reverse("employer:dashboard"))

    def test_job_toggle_rejects_get(self):
        self.client.login(username="isveren_a", password="test-pass-123")
        self.assertEqual(self.client.get(reverse("employer:job_toggle", args=[self.job_a.pk])).status_code, 405)


# ----------------------------------------------------------------------------
# İlanlar (sezonluk doğrulama, form akışı)
# ----------------------------------------------------------------------------
class JobFlowTests(DataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.company = cls.make_employer("ik", "Şirket")
        cls.tr = Language.objects.get(name="Türkçe")

    def setUp(self):
        self.client.login(username="ik", password="test-pass-123")

    def payload(self, **kw):
        data = {
            "title": "Garson", "department": "service", "city": "girne",
            "employment_type": "full_time", "positions": 2, "description": "",
            "min_experience_years": 1, "salary_min": "", "salary_max": "",
            "currency": "TRY", "season_start": "", "season_end": "",
        }
        data.update(kw)
        return data

    def test_create_job_assigns_company_and_languages(self):
        resp = self.client.post(
            reverse("employer:job_create"),
            self.payload(required_languages=[self.tr.pk], provides_accommodation="on"),
        )
        job = JobPosting.objects.get(title="Garson")
        self.assertRedirects(resp, reverse("employer:job_detail", args=[job.pk]))
        self.assertEqual(job.company, self.company)
        self.assertTrue(job.provides_accommodation)
        self.assertFalse(job.provides_meals)
        self.assertEqual(list(job.required_languages.all()), [self.tr])

    def test_seasonal_requires_dates(self):
        resp = self.client.post(reverse("employer:job_create"), self.payload(employment_type="seasonal"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(JobPosting.objects.filter(title="Garson").exists())
        self.assertContains(resp, "başlangıç tarihi zorunludur")

    def test_seasonal_end_before_start_rejected(self):
        resp = self.client.post(
            reverse("employer:job_create"),
            self.payload(employment_type="seasonal", season_start="2027-09-30", season_end="2027-05-15"),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(JobPosting.objects.filter(title="Garson").exists())

    def test_seasonal_ok_and_dates_cleared_when_not_seasonal(self):
        self.client.post(
            reverse("employer:job_create"),
            self.payload(employment_type="seasonal", season_start="2027-05-15", season_end="2027-09-30"),
        )
        job = JobPosting.objects.get(title="Garson")
        self.assertEqual(job.season_start, date(2027, 5, 15))
        # Tipi değiştirince tarihler temizlenir
        self.client.post(
            reverse("employer:job_edit", args=[job.pk]),
            self.payload(employment_type="full_time", season_start="2027-05-15", season_end="2027-09-30"),
        )
        job.refresh_from_db()
        self.assertIsNone(job.season_start)
        self.assertIsNone(job.season_end)

    def test_salary_max_below_min_rejected(self):
        resp = self.client.post(
            reverse("employer:job_create"), self.payload(salary_min=50000, salary_max=40000)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(JobPosting.objects.filter(title="Garson").exists())

    def test_edit_page_prefills_dates(self):
        job = self.make_job(
            self.company, employment_type="seasonal",
            season_start=date(2027, 5, 15), season_end=date(2027, 9, 30),
        )
        resp = self.client.get(reverse("employer:job_edit", args=[job.pk]))
        self.assertContains(resp, 'value="2027-05-15"')

    def test_toggle_close_and_reopen(self):
        job = self.make_job(self.company)
        self.client.post(reverse("employer:job_toggle", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, "closed")
        self.client.post(reverse("employer:job_toggle", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, "open")

    def test_job_pages_render_even_with_no_data(self):
        job = self.make_job(self.company)
        for name, args in [("dashboard", []), ("job_list", []), ("job_detail", [job.pk]),
                           ("application_list", []), ("market", []),
                           ("job_create", []), ("job_edit", [job.pk])]:
            self.assertEqual(self.client.get(reverse("employer:" + name, args=args)).status_code, 200, name)


# ----------------------------------------------------------------------------
# Başvuru akışı, sıralama, durum takibi
# ----------------------------------------------------------------------------
class ApplicationFlowTests(DataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.company = cls.make_employer("ik", "Şirket")
        cls.en = Language.objects.get(name="İngilizce")
        cls.tr = Language.objects.get(name="Türkçe")
        cls.job = cls.make_job(cls.company, min_experience_years=2)
        cls.job.required_languages.set([cls.tr, cls.en])

        cls.good = cls.make_candidate("İyi Aday", experience_years=3)
        cls.good.languages.set([cls.tr, cls.en])
        cls.weak = cls.make_candidate("Zayıf Aday", department="kitchen", experience_years=0)
        cls.mid = cls.make_candidate("Orta Aday", experience_years=2)
        cls.mid.languages.set([cls.tr])
        # Ekleme sırası bilerek karışık
        for c in (cls.weak, cls.mid, cls.good):
            Application.objects.create(job=cls.job, candidate=c)

    def setUp(self):
        self.client.login(username="ik", password="test-pass-123")

    def test_job_detail_sorts_by_score_desc(self):
        resp = self.client.get(reverse("employer:job_detail", args=[self.job.pk]))
        names = [a.candidate.full_name for a in resp.context["applicants"]]
        self.assertEqual(names, ["İyi Aday", "Orta Aday", "Zayıf Aday"])
        scores = [a.match.score for a in resp.context["applicants"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(scores[0], 100)

    def test_application_list_sort_filter_and_min_score(self):
        resp = self.client.get(reverse("employer:application_list"))
        names = [a.candidate.full_name for a in resp.context["applications"]]
        self.assertEqual(names[0], "İyi Aday")
        resp = self.client.get(reverse("employer:application_list"), {"min_score": 90})
        self.assertEqual([a.candidate.full_name for a in resp.context["applications"]], ["İyi Aday"])
        resp = self.client.get(reverse("employer:application_list"), {"status": "accepted"})
        self.assertEqual(len(resp.context["applications"]), 0)

    def test_application_list_bad_filter_values_do_not_crash(self):
        for params in [{"job": "abc"}, {"job": "99999"}, {"min_score": "x"}, {"status": "zzz"}, {"sort": "q"}]:
            self.assertEqual(self.client.get(reverse("employer:application_list"), params).status_code, 200, params)

    def test_status_change_writes_log_and_note_only_does_not(self):
        app = Application.objects.get(candidate=self.good)
        url = reverse("employer:application_detail", args=[app.pk])
        resp = self.client.post(url, {"status": "interview", "employer_note": "Aranacak"})
        self.assertRedirects(resp, url)
        app.refresh_from_db()
        self.assertEqual(app.status, "interview")
        self.assertEqual(app.employer_note, "Aranacak")
        log = ApplicationStatusLog.objects.get(application=app)
        self.assertEqual((log.old_status, log.new_status, log.changed_by), ("sent", "interview", self.user))

        # Sadece not değişirse yeni log yok
        self.client.post(url, {"status": "interview", "employer_note": "Yeni not"})
        self.assertEqual(ApplicationStatusLog.objects.filter(application=app).count(), 1)

    def test_invalid_status_rejected(self):
        app = Application.objects.get(candidate=self.good)
        resp = self.client.post(reverse("employer:application_detail", args=[app.pk]), {"status": "hacked", "employer_note": ""})
        self.assertEqual(resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "sent")

    def test_application_detail_shows_breakdown_and_history(self):
        app = Application.objects.get(candidate=self.mid)
        resp = self.client.get(reverse("employer:application_detail", args=[app.pk]))
        self.assertContains(resp, "Eksik dil: İngilizce")
        self.assertEqual(resp.status_code, 200)

    def test_add_application_creates_candidate_application_and_log(self):
        data = {
            "full_name": "Yeni Kişi", "email": "yeni@ornek.test", "phone": "", "city": "",
            "department": "reception", "experience_years": 5, "languages": [self.tr.pk],
            "accepts_full_time": "on", "available_from": "",
            "summary": "",
        }
        resp = self.client.post(reverse("employer:application_add", args=[self.job.pk]), data)
        app = Application.objects.get(candidate__email="yeni@ornek.test")
        self.assertRedirects(resp, reverse("employer:application_detail", args=[app.pk]))
        self.assertEqual(app.job, self.job)
        self.assertEqual(app.candidate.added_by_company, self.company)
        self.assertEqual(app.logs.count(), 1)

    def test_duplicate_email_on_same_job_rejected(self):
        data = {
            "full_name": "Tekrar", "email": f" {self.good.email.upper()} ", "department": "reception",
            "experience_years": 1, "accepts_full_time": "on",
        }
        before = Application.objects.count()
        resp = self.client.post(reverse("employer:application_add", args=[self.job.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Application.objects.count(), before)
        self.assertContains(resp, "zaten başvuru var")

    def test_candidate_must_accept_at_least_one_type(self):
        data = {"full_name": "Hiç", "email": "hic@ornek.test", "department": "reception", "experience_years": 1}
        resp = self.client.post(reverse("employer:application_add", args=[self.job.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Candidate.objects.filter(email="hic@ornek.test").exists())

    def test_dashboard_counts(self):
        resp = self.client.get(reverse("employer:dashboard"))
        self.assertEqual(resp.context["total_apps"], 3)
        self.assertEqual(resp.context["pending_total"], 3)
        self.assertEqual(resp.context["pending"][0].candidate.full_name, "İyi Aday")


# ----------------------------------------------------------------------------
# Piyasa
# ----------------------------------------------------------------------------
class MarketTests(DataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.company = cls.make_employer("ik", "Benim Otel")
        cls.other_company = Company.objects.create(name="Rakip Otel")
        cls.third = Company.objects.create(name="Üçüncü Otel")
        cls.mine = cls.make_job(
            cls.company, title="Benim Resepsiyon", salary_min=40000, salary_max=50000
        )
        today = timezone.localdate()
        cls.rival = cls.make_job(
            cls.other_company, title="Rakip Resepsiyon", provides_accommodation=True,
            provides_meals=True, salary_min=50000, salary_max=60000, min_experience_years=3,
        )
        cls.rival2 = cls.make_job(
            cls.third, title="Üçüncü Resepsiyon", provides_accommodation=True,
            salary_min=48000, salary_max=58000,
        )
        cls.closed = cls.make_job(cls.other_company, title="Kapalı İlan", status="closed")
        cls.expired = cls.make_job(
            cls.other_company, title="Bitmiş Sezon", employment_type="seasonal",
            season_start=today - timedelta(days=200), season_end=today - timedelta(days=10),
        )
        cls.seasonal = cls.make_job(
            cls.other_company, title="Yaz Garson", department="service", employment_type="seasonal",
            provides_accommodation=True,
            season_start=date(timezone.localdate().year + 1, 5, 15),
            season_end=date(timezone.localdate().year + 1, 9, 30),
        )

    def setUp(self):
        self.client.login(username="ik", password="test-pass-123")

    def titles(self, params=None):
        resp = self.client.get(reverse("employer:market"), params or {})
        self.assertEqual(resp.status_code, 200)
        return {j.title for j in resp.context["page"]}

    def test_market_excludes_own_closed_and_expired(self):
        t = self.titles()
        self.assertNotIn("Benim Resepsiyon", t)
        self.assertNotIn("Kapalı İlan", t)
        self.assertNotIn("Bitmiş Sezon", t)
        self.assertEqual(t, {"Rakip Resepsiyon", "Üçüncü Resepsiyon", "Yaz Garson"})

    def test_market_filters(self):
        self.assertEqual(self.titles({"seasonal": "on"}), {"Yaz Garson"})
        self.assertEqual(self.titles({"meals": "on"}), {"Rakip Resepsiyon"})
        self.assertEqual(
            self.titles({"accommodation": "on"}),
            {"Rakip Resepsiyon", "Üçüncü Resepsiyon", "Yaz Garson"},
        )
        self.assertEqual(self.titles({"department": "service"}), {"Yaz Garson"})
        # Türkçe harf / büyük-küçük harf farkı arama sonucunu bozmamalı
        for q in ("üçüncü", "ÜÇÜNCÜ", "ucuncu", "Üçüncü Otel"):
            self.assertEqual(self.titles({"q": q}), {"Üçüncü Resepsiyon"}, q)
        # Şirket adına göre de bulunur (ı/i farkı yok sayılır)
        self.assertEqual(self.titles({"q": "rakıp"}), {"Rakip Resepsiyon", "Yaz Garson"})
        self.assertEqual(self.titles({"q": "olmayan-bir-sey"}), set())

    def test_market_season_range_overlap(self):
        y = timezone.localdate().year + 1
        self.assertEqual(self.titles({"season_from": f"{y}-06-01", "season_to": f"{y}-06-30"}), {"Yaz Garson"})
        self.assertEqual(self.titles({"season_from": f"{y}-10-15"}), set() | self.titles({"season_from": f"{y}-10-15"}))
        self.assertEqual(self.titles({"season_from": f"{y}-10-15"}), set())

    def test_market_bad_params_do_not_crash(self):
        for params in [{"season_from": "yanlis"}, {"language": "abc"}, {"page": "zzz"}, {"department": "nope"},
                       {"season_from": "2027-09-01", "season_to": "2027-01-01"}]:
            self.assertEqual(self.client.get(reverse("employer:market"), params).status_code, 200, params)


# ----------------------------------------------------------------------------
# Komutlar ve varsayılan veriler
# ----------------------------------------------------------------------------
class CommandTests(TestCase):
    def test_default_languages_exist_after_migrate(self):
        self.assertTrue(Language.objects.filter(name="İngilizce").exists())

    def test_create_employer_command(self):
        call_command("create_employer", username="yeni_isveren", company="Yeni Şirket",
                     password="Cok-Guclu-Sifre-742!")
        user = get_user_model().objects.get(username="yeni_isveren")
        self.assertEqual(user.employer_profile.company.name, "Yeni Şirket")
        self.assertFalse(user.is_staff)
        self.assertTrue(self.client.login(username="yeni_isveren", password="Cok-Guclu-Sifre-742!"))

    def test_create_employer_rejects_duplicate_and_weak_password(self):
        from django.core.management.base import CommandError
        call_command("create_employer", username="x_isveren", company="S", password="Cok-Guclu-Sifre-742!")
        with self.assertRaises(CommandError):
            call_command("create_employer", username="x_isveren", company="S", password="Cok-Guclu-Sifre-742!")
        with self.assertRaises(CommandError):
            call_command("create_employer", username="y_isveren", company="S", password="123")

    def test_seed_demo_is_idempotent_and_pages_render(self):
        call_command("seed_isveren_demo", verbosity=0)
        call_command("seed_isveren_demo", verbosity=0)
        self.assertEqual(Company.objects.filter(name="Demo Otel").count(), 1)
        self.assertTrue(self.client.login(username="isveren_demo", password="demo12345"))
        job = JobPosting.objects.filter(company__name="Demo Otel").first()
        app = Application.objects.filter(job__company__name="Demo Otel").first()
        for name, args in [("dashboard", []), ("job_list", []), ("job_detail", [job.pk]),
                           ("application_list", []), ("application_detail", [app.pk]),
                           ("market", [])]:
            self.assertEqual(self.client.get(reverse("employer:" + name, args=args)).status_code, 200, name)


# ----------------------------------------------------------------------------
# Karşılaştır sekmesi kaldırıldı; işletme türleri; işveren kaydı
# ----------------------------------------------------------------------------
from .models import BusinessType, Department  # noqa: E402

User = get_user_model()


class CompareRemovedTests(DataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.company = cls.make_employer("isveren_x", "Bir İşletme")

    def test_compare_url_is_gone_and_nav_has_no_link(self):
        self.client.login(username="isveren_x", password="test-pass-123")
        self.assertEqual(self.client.get("/isveren/karsilastir/").status_code, 404)
        html = self.client.get(reverse("employer:dashboard")).content.decode()
        self.assertNotIn("Karşılaştır", html)
        self.assertNotIn("İK", html)
        job = self.make_job(self.company)
        self.assertNotIn("Piyasa özeti", self.client.get(reverse("employer:job_detail", args=[job.pk])).content.decode())
        self.assertIn("İşveren Portalı", html)

    def test_job_detail_and_market_have_no_compare_buttons_and_still_render(self):
        job = self.make_job(self.company)
        other = Company.objects.create(name="Diğer", business_type="farm")
        self.make_job(other, title="Bahçe İlanı", department="agriculture")
        self.client.login(username="isveren_x", password="test-pass-123")
        for url in (reverse("employer:job_detail", args=[job.pk]), reverse("employer:market")):
            html = self.client.get(url).content.decode()
            self.assertNotIn("karşılaştır", html.lower())


class BusinessTypeTests(DataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.company = cls.make_employer("isveren_y", "Benim Otel")
        orchard = Company.objects.create(name="Portakal Bahçesi", business_type=BusinessType.FARM, city="guzelyurt")
        cafe = Company.objects.create(name="Sahil Kafe", business_type=BusinessType.CAFE, city="girne")
        cls.j_orchard = cls.make_job(orchard, title="Portakal Toplama", department=Department.AGRICULTURE)
        cls.j_cafe = cls.make_job(cafe, title="Barista", department="service")

    def titles(self, params=None):
        resp = self.client.get(reverse("employer:market"), params or {})
        self.assertEqual(resp.status_code, 200)
        return {j.title for j in resp.context["page"]}

    def test_default_business_type_is_other(self):
        self.assertEqual(self.company.business_type, "other")

    def test_market_filter_by_business_type(self):
        self.client.login(username="isveren_y", password="test-pass-123")
        self.assertEqual(self.titles({"business_type": "farm"}), {"Portakal Toplama"})
        self.assertEqual(self.titles({"business_type": "cafe"}), {"Barista"})
        self.assertEqual(self.titles(), {"Portakal Toplama", "Barista"})
        self.assertEqual(self.titles({"business_type": "yok"}), {"Portakal Toplama", "Barista"})

    def test_market_shows_business_type_label(self):
        self.client.login(username="isveren_y", password="test-pass-123")
        self.assertContains(self.client.get(reverse("employer:market")), "Bahçe / Çiftlik")

    def test_agriculture_job_can_be_created_by_employer(self):
        self.client.login(username="isveren_y", password="test-pass-123")
        data = {
            "title": "Hasat İşçisi", "department": "agriculture", "city": "guzelyurt",
            "employment_type": "seasonal", "positions": 5, "min_experience_years": 0,
            "currency": "TRY", "season_start": "2026-11-15", "season_end": "2027-03-31",
            "provides_accommodation": "on", "provides_meals": "on",
        }
        resp = self.client.post(reverse("employer:job_create"), data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(JobPosting.objects.filter(title="Hasat İşçisi", company=self.company).exists())


class EmployerRegisterTests(TestCase):
    URL = "/isveren/kayit/"

    def data(self, **kw):
        d = {
            "first_name": "Ali", "last_name": "Veli", "business_type": "farm",
            "company_name": "Yılmaz Portakal Bahçesi", "city": "guzelyurt", "phone": "0533",
            "email": "yeni@example.com", "username": "yeniisveren",
            "password1": "Cok-Guclu-Sifre-91", "password2": "Cok-Guclu-Sifre-91",
        }
        d.update(kw)
        return d

    def test_page_is_public_and_login_links_to_it(self):
        self.assertEqual(self.client.get(self.URL).status_code, 200)
        self.assertContains(self.client.get("/isveren/giris/"), "/isveren/kayit/")

    def test_register_creates_company_user_profile_and_can_login(self):
        resp = self.client.post(self.URL, self.data())
        self.assertRedirects(resp, "/isveren/giris/")
        profile = EmployerProfile.objects.get(user__username="yeniisveren")
        self.assertEqual(profile.company.name, "Yılmaz Portakal Bahçesi")
        self.assertEqual(profile.company.business_type, "farm")
        self.assertTrue(self.client.login(username="yeniisveren", password="Cok-Guclu-Sifre-91"))
        self.assertEqual(self.client.get("/isveren/").status_code, 200)

    def test_every_business_type_can_register(self):
        for i, (value, _label) in enumerate(BusinessType.choices):
            resp = self.client.post(self.URL, self.data(
                business_type=value, company_name=f"İşletme {i}", username=f"u{i}", email=f"u{i}@x.com"))
            self.assertEqual(resp.status_code, 302, value)
        self.assertEqual(Company.objects.count(), len(BusinessType.choices))

    def test_cannot_join_existing_company_by_name(self):
        Company.objects.create(name="Demo Otel")
        self.client.post(self.URL, self.data(company_name="  demo   OTEL "))
        self.assertEqual(Company.objects.count(), 1)
        self.assertFalse(User.objects.filter(username="yeniisveren").exists())

    def test_invalid_business_type_city_or_password_rejected_without_orphans(self):
        self.client.post(self.URL, self.data(business_type="yok"))
        self.client.post(self.URL, self.data(city="yok"))
        self.client.post(self.URL, self.data(password1="12345678", password2="12345678"))
        self.client.post(self.URL, self.data(password2="baska-sifre-77"))
        self.assertEqual((User.objects.count(), Company.objects.count(), EmployerProfile.objects.count()), (0, 0, 0))

    def test_duplicate_username_and_email_rejected(self):
        User.objects.create_user("yeniisveren", "yeni@example.com", "x")
        self.client.post(self.URL, self.data(company_name="Baska"))
        self.client.post(self.URL, self.data(company_name="Baska", username="diger"))
        self.assertEqual(Company.objects.count(), 0)

    def test_new_employer_sees_nothing_of_others(self):
        other = Company.objects.create(name="Baska Otel")
        JobPosting.objects.create(company=other, title="Gizli ilan", department="kitchen", city="girne")
        self.client.post(self.URL, self.data())
        self.client.login(username="yeniisveren", password="Cok-Guclu-Sifre-91")
        self.assertNotContains(self.client.get("/isveren/ilanlar/"), "Gizli ilan")

    def test_logged_in_user_redirected_from_register(self):
        self.client.post(self.URL, self.data())
        self.client.login(username="yeniisveren", password="Cok-Guclu-Sifre-91")
        self.assertRedirects(self.client.get(self.URL), "/isveren/")


class CreateEmployerCommandTests(TestCase):
    def test_create_employer_sets_business_type_and_defaults_to_other(self):
        call_command("create_employer", username="bahce", company="Bahçem", business_type="farm",
                     password="Cok-Guclu-Sifre-742!")
        self.assertEqual(Company.objects.get(name="Bahçem").business_type, "farm")
        call_command("create_employer", username="eski", company="Eski Otel", password="Cok-Guclu-Sifre-742!")
        self.assertEqual(Company.objects.get(name="Eski Otel").business_type, "other")

    def test_seed_demo_includes_orchard_and_cafe(self):
        call_command("seed_isveren_demo", verbosity=0)
        self.assertTrue(Company.objects.filter(business_type="farm").exists())
        self.assertTrue(JobPosting.objects.filter(department="agriculture").exists())
