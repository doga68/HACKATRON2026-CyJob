from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Application, Notification, StatusHistory

MESSAGES = {
    Application.Status.REVIEWED: "başvurunuz incelendi.",
    Application.Status.INTERVIEW: "için görüşmeye davet edildiniz!",
    Application.Status.ACCEPTED: "başvurunuz KABUL edildi. Tebrikler!",
    Application.Status.REJECTED: "başvurunuz maalesef olumsuz sonuçlandı.",
}


@receiver(pre_save, sender=Application)
def remember_old_status(sender, instance, **kwargs):
    if instance.pk:
        instance._old_status = (
            Application.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        )
    else:
        instance._old_status = None


@receiver(post_save, sender=Application)
def on_application_saved(sender, instance, created, **kwargs):
    if created:
        StatusHistory.objects.create(application=instance, status=instance.status)
        return
    if instance._old_status != instance.status:
        StatusHistory.objects.create(application=instance, status=instance.status)
        text = MESSAGES.get(instance.status)
        if text:
            job = instance.job
            Notification.objects.create(
                user=instance.applicant,
                application=instance,
                message=f"{job.hotel_name} - {job.title}: {text}",
            )
