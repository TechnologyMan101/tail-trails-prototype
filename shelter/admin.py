from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Animal,
    AnimalPhoto,
    Organization,
    Submission,
    SubmissionPhoto,
    User,
    VolunteerHour,
)


@admin.register(User)
class TailUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Tail Trails",
            {"fields": ("full_name", "phone", "role", "manual_adjustment")},
        ),
    )
    list_display = ("username", "full_name", "email", "role", "is_active")


class PhotoInline(admin.TabularInline):
    model = AnimalPhoto
    extra = 0
    fields = ("position", "web_preview", "original_download", "caption")
    readonly_fields = ("web_preview", "original_download")

    def web_preview(self, obj):
        return (
            format_html(
                '<img src="{}" style="width:120px;height:90px;object-fit:contain;background:#eef2ef">',
                obj.url,
            )
            if obj.pk and obj.url
            else "—"
        )

    def original_download(self, obj):
        if not obj.pk or not obj.original_image:
            return "No retained original"
        return format_html(
            '<a href="{}">Download original</a>',
            reverse("original_photo", args=["animal", obj.pk]),
        )


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

    list_display = ("animal_id", "name", "species", "status", "is_archived", "held_at")
    search_fields = ("animal_id", "name", "breed")
    list_filter = ("species", "status", "is_archived", "held_at")
    inlines = [PhotoInline]
    readonly_fields = ("deceased_at", "deceased_by", "deceased_reason")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "status" in form.base_fields:
            if obj and obj.status == "Deceased":
                form.base_fields["status"].disabled = True
            else:
                form.base_fields["status"].choices = [
                    (value, label)
                    for value, label in Animal.STATUSES
                    if value != "Deceased"
                ]
                form.base_fields[
                    "status"
                ].help_text = "Use the animal edit page to confirm deceased status with your password."
        return form


@admin.register(SubmissionPhoto)
class SubmissionPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "web_preview", "original_download")
    readonly_fields = ("submission", "web_preview", "original_download")
    fields = ("submission", "web_preview", "original_download")

    def web_preview(self, obj):
        return (
            format_html(
                '<img src="{}" style="width:160px;height:120px;object-fit:contain;background:#eef2ef">',
                obj.image.url,
            )
            if obj.image
            else "—"
        )

    def original_download(self, obj):
        if not obj.original_image:
            return "No retained original"
        return format_html(
            '<a href="{}">Download original</a>',
            reverse("original_photo", args=["submission", obj.pk]),
        )


admin.site.register([Organization, Submission, VolunteerHour])
