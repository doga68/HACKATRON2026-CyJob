import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import BusinessType, Company, EmployerProfile


class Command(BaseCommand):
    help = "İşletme (işveren) hesabı oluşturur (şifre sorulur)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Giriş kullanıcı adı")
        parser.add_argument("--company", required=True, help="İşletme adı")
        parser.add_argument(
            "--business-type",
            default="other",
            choices=[v for v, _ in BusinessType.choices],
            help="İşletme türü: hotel, restaurant, cafe, bar, farm, shop, other",
        )
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--password",
            default=None,
            help="Verilmezse güvenli şekilde sorulur (tavsiye edilen).",
        )

    def handle(self, *args, **opts):
        User = get_user_model()
        username = opts["username"].strip()
        company_name = opts["company"].strip()
        if not username or not company_name:
            raise CommandError("Kullanıcı adı ve işletme adı boş olamaz.")
        if User.objects.filter(username=username).exists():
            raise CommandError(f"'{username}' kullanıcı adı zaten var.")

        password = opts["password"]
        if not password:
            password = getpass.getpass("Şifre: ")
            if password != getpass.getpass("Şifre (tekrar): "):
                raise CommandError("Şifreler aynı değil.")

        user = User(
            username=username,
            first_name=opts["first_name"],
            last_name=opts["last_name"],
            email=opts["email"],
        )
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("Şifre yetersiz: " + " ".join(exc.messages))

        with transaction.atomic():
            company, _ = Company.objects.get_or_create(
                name=company_name, defaults={"business_type": opts["business_type"]}
            )
            user.set_password(password)
            user.save()
            EmployerProfile.objects.create(user=user, company=company)

        self.stdout.write(
            self.style.SUCCESS(
                f"İşveren hesabı hazır: '{username}' ({company.name}). "
                "Giriş: http://127.0.0.1:8000/giris/"
            )
        )
