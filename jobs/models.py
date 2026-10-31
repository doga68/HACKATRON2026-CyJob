from django.conf import settings
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField("Departman", max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Departman"
        verbose_name_plural = "Departmanlar"

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField("Dil", max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Dil"
        verbose_name_plural = "Diller"

    def __str__(self):
        return self.name


class JobType(models.TextChoices):
    FULL_TIME = "full_time", "Tam zamanlı"
    PART_TIME = "part_time", "Yarı zamanlı"
    SEASONAL = "seasonal", "Sezonluk"


class Profile(models.Model):
    """Kullanıcı rolü + iş arayan bilgileri.
    İK tarafını eklerken role='hr' kullanabilirsiniz."""

    class Role(models.TextChoices):
        JOBSEEKER = "jobseeker", "İş Arayan"
        HR = "hr", "İnsan Kaynakları"

    class Availability(models.TextChoices):
        ANY = "any", "Hepsi uygun"
        FULL_TIME = "full_time", "Tam zamanlı"
        PART_TIME = "part_time", "Yarı zamanlı"
        SEASONAL = "seasonal", "Sezonluk"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.JOBSEEKER)
    phone = models.CharField("Telefon", max_length=30, blank=True)
    languages = models.ManyToManyField(Language, verbose_name="Bildiği diller", blank=True)
    experience_years = models.PositiveIntegerField("Deneyim (yıl)", default=0)
    department = models.ForeignKey(
        Department, verbose_name="Çalışmak istediği departman",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    availability = models.CharField(
        "Çalışma uygunluğu", max_length=20,
        choices=Availability.choices, default=Availability.ANY,
    )
    needs_accommodation = models.BooleanField("Konaklama ihtiyacım var", default=False)
    about = models.TextField("Kısa tanıtım", blank=True)
    cv = models.FileField("CV", upload_to="cv/", blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def is_jobseeker(self):
        return self.role == self.Role.JOBSEEKER


class Job(models.Model):
    title = models.CharField("İlan başlığı", max_length=150)
    hotel_name = models.CharField("Otel / İşletme", max_length=150)
    location = models.CharField("Konum", max_length=100, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, verbose_name="Departman")
    description = models.TextField("Açıklama")
    job_type = models.CharField("Çalışma türü", max_length=20, choices=JobType.choices,
                                default=JobType.FULL_TIME)
    season_start = models.DateField("Sezon başlangıç", null=True, blank=True)
    season_end = models.DateField("Sezon bitiş", null=True, blank=True)

    required_languages = models.ManyToManyField(Language, verbose_name="Gerekli diller", blank=True)
    min_experience = models.PositiveIntegerField("Min. deneyim (yıl)", default=0)

    provides_accommodation = models.BooleanField("Konaklama sağlanır", default=False)
    provides_meals = models.BooleanField("Yemek sağlanır", default=False)
    salary_info = models.CharField("Maaş bilgisi", max_length=100, blank=True)

    application_deadline = models.DateField("Son başvuru tarihi", null=True, blank=True)
    is_active = models.BooleanField("Yayında", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "İlan"
        verbose_name_plural = "İlanlar"

    def __str__(self):
        return f"{self.title} - {self.hotel_name}"

    @property
    def is_open(self):
        if not self.is_active:
            return False
        if self.application_deadline and self.application_deadline < timezone.localdate():
            return False
        return True


class Application(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "Gönderildi"
        REVIEWED = "reviewed", "İncelendi"
        INTERVIEW = "interview", "Görüşmeye çağrıldı"
        ACCEPTED = "accepted", "Kabul edildi"
        REJECTED = "rejected", "Reddedildi"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField("Durum", max_length=20, choices=Status.choices, default=Status.SENT)
    match_score = models.PositiveIntegerField("Uyum skoru (%)", default=0)
    cover_note = models.TextField("Ön yazı", blank=True)
    hr_note = models.TextField("İK notu (adaya görünür)", blank=True)
    interview_date = models.DateTimeField("Görüşme tarihi", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("job", "applicant")
        verbose_name = "Başvuru"
        verbose_name_plural = "Başvurular"

    def __str__(self):
        return f"{self.applicant} -> {self.job} [{self.get_status_display()}]"


class StatusHistory(models.Model):
    """Başvuru durum takibi için zaman çizelgesi."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=20, choices=Application.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.application_id}: {self.status}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notifications")
    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.CASCADE)
    message = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
