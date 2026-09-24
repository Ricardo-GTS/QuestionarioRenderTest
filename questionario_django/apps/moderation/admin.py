from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "reporter", "reason", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("question__statement", "reporter__email")
    readonly_fields = ("created_at",)
