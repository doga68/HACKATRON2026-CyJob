from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


# ----------------------------------------------------------------------------
# Seçenek listeleri
# ----------------------------------------------------------------------------
class Department(models.TextChoices):
    RECEPTION = "reception", "Resepsiyon"
    KITCHEN = "kitchen", "Mutfak"
    SERVICE = "service", "Servis (Restoran / Bar)"
    HOUSEKEEPING = "housekeeping", "Kat Hizmetleri"
    SALES = "sales", "Satış & Pazarlama"
    ACCOUNTING = "accounting", "Muhasebe & Finans"
    TECHNICAL = "technical", "Teknik Servis"
    SECURITY = "security", "Güvenlik"
    ANIMATION = "animation", "Animasyon & Eğlence"
    AGRICULTURE = "agriculture", "Tarım & Hasat (bahçe, sera)"
    GENERAL = "general", "Genel İşçi / Yardımcı"
    OTHER = "other", "Diğer"


class BusinessType(models.TextChoices):
    """İşveren türleri: otel, restoran, kafe, bahçe/çiftlik vb."""

    HOTEL = "hotel", "Otel / Tatil köyü"
    RESTAURANT = "restaurant", "Restoran"
    CAFE = "cafe", "Kafe / Pastane"
    BAR = "bar", "Bar / Eğlence mekanı"
    FARM = "farm", "Bahçe / Çiftlik / Tarım (portakal, narenciye vb.)"
    SHOP = "shop", "Market / Mağaza"
    OTHER = "other", "Diğer"


class City(models.TextChoices):
    LEFKOSA = "lefkosa", "Lefkoşa"
    GIRNE = "girne", "Girne"
    GAZIMAGUSA = "gazimagusa", "Gazimağusa"
    GUZELYURT = "guzelyurt", "Güzelyurt"
    ISKELE = "iskele", "İskele"
    LEFKE = "lefke", "Lefke"


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Tam zamanlı"
    PART_TIME = "part_time", "Yarı zamanlı"
    SEASONAL = "seasonal", "Sezonluk"


class Currency(models.TextChoices):
    TRY = "TRY", "TL"
    EUR = "EUR", "EUR"
    GBP = "GBP", "GBP"
    USD = "USD", "USD"


class JobStatus(models.TextChoices):
    OPEN = "open", "Açık"
    CLOSED = "closed", "Kapalı"


class ApplicationStatus(models.TextChoices):
    SENT = "sent", "Gönderildi"
    REVIEWED = "reviewed", "İncelendi"
    INTERVIEW = "interview", "Görüşmeye çağrıldı"
    ACCEPTED = "accepted", "Kabul edildi"
    REJECTED = "rejected", "Reddedildi"


# ----------------------------------------------------------------------------
# İşletme (işveren) ve işveren kullanıcısı
# ----------------------------------------------------------------------------
class Company(models.Model):
    name = models.CharField("İşletme adı", max_length=150, unique=True)
    business_type = models.CharField(
        "İşletme türü",
        max_length=20,
        choices=BusinessType.choices,
        default=BusinessType.OTHER,
    )
    city = models.CharField("Şehir", max_length=20, choices=City.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "İşletme"
        verbose_name_plural = "İşletmeler"

    def __str__(self):
        return self.name


class EmployerProfile(models.Model):
    """Bir Django kullanıcısını bir işletmenin işveren hesabı yapar.

    Bu profili olmayan kullanıcılar (ör. sadece admin) işveren panelini göremez.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer_profile"
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="employer_staff"
    )
    phone = models.CharField("Telefon", max_length=30, blank=True)

    class Meta:
        verbose_name = "İşveren hesabı"
        verbose_name_plural = "İşveren hesapları"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.get_username()} – {self.company}"


class Language(models.Model):
    name = models.CharField("Dil", max_length=40, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Dil"
        verbose_name_plural = "Diller"

    def __str__(self):
        return self.name


# ----------------------------------------------------------------------------
# İlan
# ----------------------------------------------------------------------------
class JobPosting(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField("İlan başlığı", max_length=150)
    department = models.CharField(
        "Departman", max_length=20, choices=Department.choices
    )
    city = models.CharField("Şehir", max_length=20, choices=City.choices)
    employment_type = models.CharField(
        "Çalışma tipi",
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    positions = models.PositiveSmallIntegerField(
        "Kaç kişi aranıyor",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    description = models.TextField("Açıklama", blank=True)

    # Uyum skoruna giren şartlar
    min_experience_years = models.PositiveSmallIntegerField(
        "En az deneyim (yıl)",
        default=0,
        validators=[MaxValueValidator(60)],
    )
    required_languages = models.ManyToManyField(
        Language, blank=True, related_name="jobs", verbose_name="Aranan diller"
    )

    # Turizm için kritik yan haklar
    provides_accommodation = models.BooleanField("Konaklama sağlanır", default=False)
    provides_meals = models.BooleanField("Yemek sağlanır", default=False)

    salary_min = models.PositiveIntegerField("Maaş (en az)", null=True, blank=True)
    salary_max = models.PositiveIntegerField("Maaş (en çok)", null=True, blank=True)
    currency = models.CharField(
        "Para birimi", max_length=3, choices=Currency.choices, default=Currency.TRY
    )

    # Sezonluk işler
    season_start = models.DateField("Sezon başlangıcı", null=True, blank=True)
    season_end = models.DateField("Sezon bitişi", null=True, blank=True)

    status = models.CharField(
        "Durum", max_length=10, choices=JobStatus.choices, default=JobStatus.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "İlan"
        verbose_name_plural = "İlanlar"

    def __str__(self):
        return self.title

    # -- yardımcılar ---------------------------------------------------------
    @property
    def is_seasonal(self):
        return self.employment_type == EmploymentType.SEASONAL

    @property
    def is_expired(self):
        """Sezon bitiş tarihi geçmiş mi?"""
        return bool(self.season_end and self.season_end < timezone.localdate())

    @property
    def is_listed(self):
        """Piyasada diğer işverenlere görünür mü?"""
        return self.status == JobStatus.OPEN and not self.is_expired

    def clean(self):
        errors = {}
        if self.employment_type == EmploymentType.SEASONAL:
            if not self.season_start:
                errors["season_start"] = "Sezonluk ilanlarda başlangıç tarihi zorunludur."
            if not self.season_end:
                errors["season_end"] = "Sezonluk ilanlarda bitiş tarihi zorunludur."
            if self.season_start and self.season_end and self.season_end < self.season_start:
                errors["season_end"] = "Bitiş tarihi başlangıçtan önce olamaz."
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            errors["salary_max"] = "En çok maaş, en az maaştan küçük olamaz."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Sezonluk olmayan ilanlarda eski tarihler kalmasın.
        if self.employment_type != EmploymentType.SEASONAL:
            self.season_start = None
            self.season_end = None
        super().save(*args, **kwargs)


# ----------------------------------------------------------------------------
# Aday ve başvuru
# ----------------------------------------------------------------------------
class Candidate(models.Model):
    full_name = models.CharField("Ad soyad", max_length=120)
    email = models.EmailField("E-posta")
    phone = models.CharField("Telefon", max_length=30, blank=True)
    city = models.CharField("Şehir", max_length=20, choices=City.choices, blank=True)

    department = models.CharField(
        "Çalışmak istediği / deneyimli olduğu departman",
        max_length=20,
        choices=Department.choices,
    )
    experience_years = models.PositiveSmallIntegerField(
        "Deneyim (yıl)", default=0, validators=[MaxValueValidator(60)]
    )
    languages = models.ManyToManyField(
        Language, blank=True, related_name="candidates", verbose_name="Bildiği diller"
    )

    # Uygunluk
    needs_accommodation = models.BooleanField("Konaklamaya ihtiyacı var", default=False)
    accepts_full_time = models.BooleanField("Tam zamanlı çalışabilir", default=True)
    accepts_part_time = models.BooleanField("Yarı zamanlı çalışabilir", default=True)
    accepts_seasonal = models.BooleanField("Sezonluk çalışabilir", default=True)
    available_from = models.DateField("Ne zamandan itibaren müsait", null=True, blank=True)

    summary = models.TextField("Kısa özgeçmiş / not", blank=True)

    # Adayı işveren elle eklediyse hangi işletmenin eklediği (ileride iş arayan portalı için).
    added_by_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_candidates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Aday"
        verbose_name_plural = "Adaylar"

    def __str__(self):
        return self.full_name

    def accepted_types(self):
        types = set()
        if self.accepts_full_time:
            types.add(EmploymentType.FULL_TIME.value)
        if self.accepts_part_time:
            types.add(EmploymentType.PART_TIME.value)
        if self.accepts_seasonal:
            types.add(EmploymentType.SEASONAL.value)
        return frozenset(types)


class Application(models.Model):
    job = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="applications"
    )
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(
        "Durum",
        max_length=12,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.SENT,
    )
    employer_note = models.TextField("İşveren notu (sadece işveren görür)", blank=True)
    applied_at = models.DateTimeField("Başvuru zamanı", default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at", "-id"]
        verbose_name = "Başvuru"
        verbose_name_plural = "Başvurular"
        constraints = [
            models.UniqueConstraint(
                fields=["job", "candidate"], name="unique_candidate_per_job"
            )
        ]

    def __str__(self):
        return f"{self.candidate} → {self.job}"


class ApplicationStatusLog(models.Model):
    """Her durum değişikliğinin kaydı (iş arayan 'karanlıkta kalmasın' diye)."""

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="logs"
    )
    old_status = models.CharField(
        max_length=12, choices=ApplicationStatus.choices, blank=True
    )
    new_status = models.CharField(max_length=12, choices=ApplicationStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name = "Durum kaydı"
        verbose_name_plural = "Durum kayıtları"

    def __str__(self):
        return f"{self.application_id}: {self.old_status or '-'} → {self.new_status}"
