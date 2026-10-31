from django import forms
from django.contrib.auth.models import User

from .models import Department, Job, JobType, Language, Profile


class RegisterForm(forms.Form):
    first_name = forms.CharField(label="Ad", max_length=50)
    last_name = forms.CharField(label="Soyad", max_length=50)
    email = forms.EmailField(label="E-posta")
    phone = forms.CharField(label="Telefon", max_length=30, required=False)
    password1 = forms.CharField(label="Şifre", widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label="Şifre (tekrar)", widget=forms.PasswordInput)
    languages = forms.ModelMultipleChoiceField(
        label="Bildiğiniz diller", queryset=Language.objects.all(),
        required=False, widget=forms.CheckboxSelectMultiple,
    )
    experience_years = forms.IntegerField(label="Deneyim (yıl)", min_value=0, initial=0)
    department = forms.ModelChoiceField(
        label="Çalışmak istediğiniz departman", queryset=Department.objects.order_by("pk"), required=False
    )
    availability = forms.ChoiceField(label="Çalışma uygunluğu", choices=Profile.Availability.choices)
    needs_accommodation = forms.BooleanField(label="Konaklama ihtiyacım var", required=False)
    cv = forms.FileField(label="CV (PDF, DOC veya DOCX - en fazla 5 MB)")

    def clean_cv(self):
        f = self.cleaned_data["cv"]
        if not f.name.lower().endswith((".pdf", ".doc", ".docx")):
            raise forms.ValidationError("Sadece PDF, DOC veya DOCX yükleyebilirsiniz.")
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Dosya 5 MB'dan büyük olamaz.")
        return f

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Bu e-posta ile zaten kayıt var.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Şifreler eşleşmiyor.")
        return data

    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(
            username=d["email"], email=d["email"], password=d["password1"],
            first_name=d["first_name"], last_name=d["last_name"],
        )
        profile = Profile.objects.create(
            user=user, role=Profile.Role.JOBSEEKER, phone=d["phone"],
            experience_years=d["experience_years"], department=d["department"],
            availability=d["availability"], cv=d["cv"],
            needs_accommodation=d["needs_accommodation"],
        )
        profile.languages.set(d["languages"])
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(label="E-posta")
    password = forms.CharField(label="Şifre", widget=forms.PasswordInput)


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Ad", max_length=50)
    last_name = forms.CharField(label="Soyad", max_length=50)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.order_by("pk")

    class Meta:
        model = Profile
        fields = ["phone", "languages", "experience_years", "department", "availability",
                  "needs_accommodation", "about", "cv"]
        widgets = {
            "languages": forms.CheckboxSelectMultiple,
        }


class JobFilterForm(forms.Form):
    q = forms.CharField(label="Ara", required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.order_by("pk"),
                                        required=False, empty_label="Tümü", label="Departman")
    job_type = forms.ChoiceField(label="Çalışma türü",
                                 choices=[("", "Tümü")] + list(JobType.choices), required=False)
    language = forms.ModelChoiceField(queryset=Language.objects.all(), required=False,
                                      empty_label="Tümü", label="Dil")
    location = forms.CharField(label="Konum", required=False)
    accommodation = forms.BooleanField(label="Konaklama sağlayan işler", required=False)
    meals = forms.BooleanField(label="Yemek sağlayan işler", required=False)
    seasonal = forms.BooleanField(label="Sadece sezonluk işler", required=False)
    season_from = forms.DateField(label="Sezon başlangıcı bu tarihten sonra", required=False,
                                  widget=forms.DateInput(attrs={"type": "date"}))
    season_to = forms.DateField(label="Sezon bitişi bu tarihten önce", required=False,
                                widget=forms.DateInput(attrs={"type": "date"}))
    max_experience = forms.IntegerField(label="İstenen deneyim en fazla (yıl)",
                                        required=False, min_value=0)
    sort = forms.ChoiceField(label="Sırala", required=False, choices=[
        ("new", "En yeni"), ("match", "En uyumlu")])
