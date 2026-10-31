from django.contrib import admin

from .models import (
    Application,
    ApplicationStatusLog,
    Candidate,
    Company,
    EmployerProfile,
    JobPosting,
    Language,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "business_type", "city", "created_at")
    list_filter = ("business_type", "city")
    search_fields = ("name",)


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "phone")


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "department", "employment_type", "status")
    list_filter = ("status", "department", "employment_type", "company")
    search_fields = ("title", "company__name")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "department", "experience_years")
    search_fields = ("full_name", "email")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "applied_at")
    list_filter = ("status",)


admin.site.register(ApplicationStatusLog)
