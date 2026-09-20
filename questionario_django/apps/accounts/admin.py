from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "created_at", "is_staff")
    search_fields = ("email", "name")
    readonly_fields = ("created_at",)
    ordering = ("name",)
