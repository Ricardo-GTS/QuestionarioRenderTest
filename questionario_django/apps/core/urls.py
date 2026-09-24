from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("health", views.health, name="health"),
    path("admin/semestres", views.semesters, name="semesters"),
    path("admin/semestres/abrir", views.open_semester, name="open_semester"),
    path("admin/semestres/<int:semester_id>/reativar", views.reactivate_semester, name="reactivate_semester"),
    path("admin/semestres/selecionar", views.select_semester, name="select_semester"),
]
