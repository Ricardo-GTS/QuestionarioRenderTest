from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.questions.urls")),
    path("", include("apps.quiz.urls")),
    path("", include("apps.moderation.urls")),
    path("", include("apps.core.urls")),
]
