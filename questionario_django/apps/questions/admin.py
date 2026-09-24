from django.contrib import admin

from .models import CommentReport, CommentSeen, Question, QuestionComment, Topic


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "statement", "status", "author", "topic", "created_at")
    list_filter = ("status", "topic")
    search_fields = ("statement", "author__email", "author__name")
    # embedding (VectorField -> numpy array) nao pode ser readonly_fields direto:
    # o display_for_field do admin faz "value in field.empty_values", e a comparacao
    # elementwise do numpy array levanta ValueError ("truth value... ambiguous").
    exclude = ("embedding",)
    readonly_fields = ("embedding_preview", "created_at")

    def embedding_preview(self, obj):
        return f"vector[{len(obj.embedding)}]"

    embedding_preview.short_description = "Embedding"


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(QuestionComment)
class QuestionCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "author", "removed", "created_at")
    list_filter = ("removed",)
    search_fields = ("text", "author__email", "author__name")


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ("id", "comment", "reporter", "reason_category", "status", "created_at")
    list_filter = ("status", "reason_category")


@admin.register(CommentSeen)
class CommentSeenAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "last_seen_at")
