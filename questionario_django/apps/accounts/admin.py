from django.contrib import admin

from .models import PendingRegistration, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "registration_number", "created_at", "is_staff")
    search_fields = ("email", "name", "registration_number")
    readonly_fields = ("created_at",)
    ordering = ("name",)


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(admin.ModelAdmin):
    """So' leitura, pra inspecao -- sem expor code_hash/password_hash."""

    list_display = ("email", "name", "registration_number", "created_at", "attempts")
    search_fields = ("email", "name", "registration_number")
    fields = ("email", "name", "registration_number", "attempts", "code_expires_at", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
