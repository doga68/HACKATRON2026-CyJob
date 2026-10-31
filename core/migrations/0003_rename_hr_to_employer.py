"""HRProfile -> EmployerProfile, hr_note -> employer_note.

RenameModel / RenameField kullanıldığı için mevcut veriler (işveren hesapları ve
notlar) silinmez, olduğu gibi taşınır.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_business_type_and_departments"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name="HRProfile", new_name="EmployerProfile"),
        migrations.RenameField(model_name="application", old_name="hr_note", new_name="employer_note"),
        migrations.AlterField(
            model_name="employerprofile",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="employer_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="employerprofile",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="employer_staff",
                to="core.company",
            ),
        ),
    ]
