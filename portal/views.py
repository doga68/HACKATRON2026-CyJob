from django.shortcuts import render


def home(request):
    """Karşılama ekranı: personel / işveren kaydı ve giriş seçenekleri."""
    return render(request, "portal/home.html")
