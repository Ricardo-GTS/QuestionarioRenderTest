from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("health", views.health, name="health"),
    path("admin/semestres", views.semesters, name="semesters"),
    path("admin/semestres/abrir", views.open_semester, name="open_semester"),
    path("admin/semestres/<int:semester_id>/reativar", views.reactivate_semester, name="reactivate_semester"),
    path("admin/semestres/selecionar", views.select_semester, name="select_semester"),
    path("admin/semestres/<int:semester_id>/renomear", views.rename_semester_view, name="rename_semester"),
    path("admin/semestres/<int:semester_id>/planilha", views.download_sheet, name="download_sheet"),
    path("admin/semestres/<int:semester_id>/planilha/regenerar", views.regenerate_sheet, name="regenerate_sheet"),
    path("admin/semestres/planilha-periodo", views.export_range, name="export_range"),
]
