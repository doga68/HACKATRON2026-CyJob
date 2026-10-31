from django.contrib import admin

from .models import (Application, Department, Job, Language, Notification,
                     Profile, StatusHistory)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "hotel_name", "department", "job_type", "provides_accommodation",
                    "provides_meals", "is_active")
    list_filter = ("department", "job_type", "provides_accommodation", "provides_meals", "is_active")
    filter_horizontal = ("required_languages",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("applicant", "job", "match_score", "status", "created_at")
    list_filter = ("status", "job")
    ordering = ("-match_score",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "experience_years")
    list_filter = ("role",)


admin.site.register(Department)
admin.site.register(Language)
admin.site.register(Notification)
admin.site.register(StatusHistory)
