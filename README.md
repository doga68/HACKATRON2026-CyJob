# CyJob – Otel İş Portalı (Personel + İşveren, tek proje)

Üç parça tek Django projesinde birleşti:

| Adres | Ne | Uygulama |
|---|---|---|
| `/` | Ana ekran: "Personel olarak kayıt ol", "İşveren olarak kayıt ol", "Giriş yap" | `portal` |
| `/personel/` | İş arayan (personel) portalı: ilanlar, başvurularım, bildirimler, profil | `jobs` |
| `/isveren/` | İşveren portalı: panel, ilanlarım, başvurular, piyasa | `core` |
| `/admin/` | Yönetim paneli (logo ve isim burada da var) | Django admin |

Tema, logo ve isim `portal/static/portal/` altında ortaktır (`cyjob.css`, `logo.png`, `favicon.png`).
Ana ekranın renkleri ve animasyonları `s.html` ile birebir aynıdır; iç sayfalar aynı paleti kullanır.

## Kurulum (Windows / VS Code terminali)

```
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations jobs
python manage.py migrate
python manage.py runserver
```

Tarayıcı: http://127.0.0.1:8000/

Önemli: iki proje tek veritabanına (`db.sqlite3`) taşındı. Eski projelerdeki `db.sqlite3` dosyalarını
kopyalamayın; yeni, boş bir veritabanı ile başlanır.

### Hesaplar

- Personel: `/personel/kayit/` üzerinden e-posta ile kayıt (CV yükleme zorunlu).
- İşveren: `/isveren/kayit/` üzerinden kayıt, ya da komutla:
  `python manage.py create_employer --username isveren --company "İşletme Adı" --business-type hotel`
- Yönetici: `python manage.py createsuperuser` → `/admin/`

Her giriş kapısı yalnızca kendi rolünü kabul eder (işveren hesabı personel girişinden, personel hesabı işveren girişinden giremez).

### Örnek veri (isteğe bağlı)

Komut adları çakışmasın diye değişti:

```
python manage.py seed_personel_demo    # personel tarafı: örnek ilanlar, departman/dil listesi
python manage.py seed_isveren_demo     # işveren tarafı: isveren_demo / demo12345
```

### Testler

```
python manage.py test core
```

## Dosya yapısı

```
config/    ayarlar ve ana URL'ler
portal/    ana ekran + ortak tema (css, logo, favicon) + admin başlığı
jobs/      personel portalı   (URL ad alanı: jobs:)
core/      işveren portalı    (URL ad alanı: employer:)
```

## Bilinen sınır

Personel (`jobs`) ve işveren (`core`) tarafı şimdilik **ayrı veri modelleri** kullanır:
işverenin açtığı ilan personel ekranında görünmez, personelin başvurusu işveren panelinde görünmez.
İki tarafı veri olarak bağlamak ayrı bir iş (ortak ilan/başvuru modeli gerektirir).

Yayına alırken: `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY=<uzun rastgele değer>`, `DJANGO_ALLOWED_HOSTS=alanadiniz.com`, HTTPS.
