from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.db import IntegrityError, transaction

from .models import (
    Application,
    ApplicationStatus,
    BusinessType,
    Candidate,
    City,
    Company,
    Department,
    EmploymentType,
    EmployerProfile,
    JobPosting,
    Language,
)


class EmployerAuthenticationForm(AuthenticationForm):
    """İşveren girişi: personel (iş arayan) hesapları bu kapıdan girmez."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not EmployerProfile.objects.filter(user=user).exists():
            raise forms.ValidationError(
                "Bu giriş sadece işveren hesapları içindir. İş arıyorsanız personel girişini kullanın.",
                code="not_employer",
            )


class DateInput(forms.DateInput):
    """Tarayıcı takvimi (type=date); ISO biçimi ile değeri doğru doldurur."""

    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class JobPostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = [
            "title",
            "department",
            "city",
            "employment_type",
            "positions",
            "description",
            "min_experience_years",
            "required_languages",
            "provides_accommodation",
            "provides_meals",
            "salary_min",
            "salary_max",
            "currency",
            "season_start",
            "season_end",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "required_languages": forms.CheckboxSelectMultiple,
            "season_start": DateInput(),
            "season_end": DateInput(),
        }
        help_texts = {
            "season_start": "Sadece 'Sezonluk' ilanlarda doldurulur (ör. 15 Mayıs).",
            "season_end": "Sadece 'Sezonluk' ilanlarda doldurulur (ör. 30 Eylül).",
            "required_languages": "Hiçbiri seçilmezse dil şartı aranmaz.",
        }


class CandidateForm(forms.ModelForm):
    """İşverenin elle başvuru eklemesi için aday formu."""

    class Meta:
        model = Candidate
        fields = [
            "full_name",
            "email",
            "phone",
            "city",
            "department",
            "experience_years",
            "languages",
            "needs_accommodation",
            "accepts_full_time",
            "accepts_part_time",
            "accepts_seasonal",
            "available_from",
            "summary",
        ]
        widgets = {
            "languages": forms.CheckboxSelectMultiple,
            "available_from": DateInput(),
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, job=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if self.job is not None and Application.objects.filter(
            job=self.job, candidate__email__iexact=email
        ).exists():
            raise forms.ValidationError("Bu e-posta ile bu ilana zaten başvuru var.")
        return email

    def clean(self):
        cleaned = super().clean()
        if not (
            cleaned.get("accepts_full_time")
            or cleaned.get("accepts_part_time")
            or cleaned.get("accepts_seasonal")
        ):
            raise forms.ValidationError(
                "Adayın en az bir çalışma tipini kabul etmesi gerekir."
            )
        return cleaned


class ApplicationUpdateForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status", "employer_note"]
        widgets = {"employer_note": forms.Textarea(attrs={"rows": 4})}


class ApplicationFilterForm(forms.Form):
    SORT_CHOICES = [("score", "Uyum skoru (yüksekten düşüğe)"), ("date", "Başvuru tarihi (yeniden eskiye)")]

    job = forms.ModelChoiceField(
        queryset=JobPosting.objects.none(),
        required=False,
        empty_label="Tüm ilanlar",
        label="İlan",
    )
    status = forms.ChoiceField(
        choices=[("", "Tüm durumlar")] + list(ApplicationStatus.choices),
        required=False,
        label="Durum",
    )
    min_score = forms.IntegerField(
        required=False, min_value=0, max_value=100, label="En az uyum (%)"
    )
    sort = forms.ChoiceField(choices=SORT_CHOICES, required=False, label="Sıralama")

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["job"].queryset = JobPosting.objects.filter(company=company)


class MarketFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Ara (başlık / işletme)", max_length=100)
    department = forms.ChoiceField(
        choices=[("", "Tüm departmanlar")] + list(Department.choices),
        required=False,
        label="Departman",
    )
    city = forms.ChoiceField(
        choices=[("", "Tüm şehirler")] + list(City.choices),
        required=False,
        label="Şehir",
    )
    business_type = forms.ChoiceField(
        choices=[("", "Tüm işletme türleri")] + list(BusinessType.choices),
        required=False,
        label="İşletme türü",
    )
    language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        required=False,
        empty_label="Tüm diller",
        label="Aranan dil",
    )
    accommodation = forms.BooleanField(required=False, label="Konaklama sağlayanlar")
    meals = forms.BooleanField(required=False, label="Yemek sağlayanlar")
    seasonal = forms.BooleanField(required=False, label="Sadece sezonluk")
    season_from = forms.DateField(
        required=False, label="Sezon aralığı (başlangıç)", widget=DateInput()
    )
    season_to = forms.DateField(
        required=False, label="Sezon aralığı (bitiş)", widget=DateInput()
    )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("season_from"), cleaned.get("season_to")
        if start and end and end < start:
            raise forms.ValidationError("Sezon aralığında bitiş, başlangıçtan önce olamaz.")
        return cleaned


class EmployerRegisterForm(forms.Form):
    """Yeni işletme + o işletmenin ilk işveren hesabını birlikte oluşturur.

    Otel, restoran, kafe, bahçe/çiftlik sahibi vb. herkes kayıt olabilir.

    GÜVENLİK: Var olan bir işletme adıyla kayıt kabul EDİLMEZ. Aksi halde herkes
    başka bir işletmenin adını yazıp o işletmenin başvurularını görebilirdi.
    Aynı işletmeye ikinci bir hesap eklemek için `create_employer` komutu kullanılır.
    """

    first_name = forms.CharField(label="Ad", max_length=150)
    last_name = forms.CharField(label="Soyad", max_length=150)
    business_type = forms.ChoiceField(
        label="İşletme türü", choices=[("", "---------")] + list(BusinessType.choices)
    )
    company_name = forms.CharField(
        label="İşletme adı",
        max_length=150,
        help_text="Ör. otel/restoran/kafe adı veya bahçenizin adı (\"Yılmaz Portakal Bahçesi\").",
    )
    city = forms.ChoiceField(label="Şehir", choices=[("", "---------")] + list(City.choices))
    phone = forms.CharField(label="Telefon", max_length=30, required=False)
    email = forms.EmailField(label="E-posta")
    username = forms.CharField(label="Kullanıcı adı", max_length=150)
    password1 = forms.CharField(label="Şifre", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Şifre (tekrar)", widget=forms.PasswordInput)

    def clean_company_name(self):
        name = " ".join(self.cleaned_data["company_name"].split())
        if not name:
            raise forms.ValidationError("İşletme adı boş olamaz.")
        if Company.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(
                "Bu işletme adı zaten kayıtlı. İşletmenize ikinci bir hesap eklemek için "
                "sistem yöneticisiyle iletişime geçin."
            )
        return name

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu kullanıcı adı alınmış.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta ile zaten bir hesap var.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Şifreler aynı değil.")
            else:
                user = get_user_model()(
                    username=cleaned.get("username", ""),
                    email=cleaned.get("email", ""),
                    first_name=cleaned.get("first_name", ""),
                    last_name=cleaned.get("last_name", ""),
                )
                try:
                    password_validation.validate_password(p1, user)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self):
        """İşletme + kullanıcı + profil ya hep birlikte oluşur ya hiç oluşmaz."""
        d = self.cleaned_data
        try:
            with transaction.atomic():
                company = Company.objects.create(
                    name=d["company_name"], city=d["city"], business_type=d["business_type"]
                )
                user = get_user_model().objects.create_user(
                    username=d["username"],
                    email=d["email"],
                    password=d["password1"],
                    first_name=d["first_name"],
                    last_name=d["last_name"],
                )
                EmployerProfile.objects.create(user=user, company=company, phone=d["phone"])
        except IntegrityError:
            # Aynı anda yapılan iki kayıt aynı adı/kullanıcıyı almış olabilir.
            raise forms.ValidationError(
                "İşletme adı veya kullanıcı adı az önce başka biri tarafından alındı. "
                "Lütfen tekrar deneyin."
            )
        return user
