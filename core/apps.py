from django.apps import AppConfig

DEFAULT_LANGUAGES = [
    "Türkçe",
    "İngilizce",
    "Rusça",
    "Almanca",
    "Arapça",
    "Farsça",
    "Fransızca",
    "Ukraynaca",
    "İtalyanca",
]


def create_default_languages(sender, using="default", **kwargs):
    """migrate sonrası temel dil listesini (yoksa) ekler."""
    from django.db import connections

    from .models import Language

    if Language._meta.db_table not in connections[using].introspection.table_names():
        return
    for name in DEFAULT_LANGUAGES:
        Language.objects.using(using).get_or_create(name=name)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "İşveren Portalı"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(
            create_default_languages,
            sender=self,
            dispatch_uid="core_create_default_languages",
        )
