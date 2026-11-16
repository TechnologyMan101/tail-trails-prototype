import json
import re
from django import forms
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from .models import Animal, Organization, Submission, User, VolunteerHour
from .images import PHOTO_ACCEPT, validate_photo_upload
from .branding_images import BRANDING_ACCEPT, validate_branding_upload


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": PHOTO_ACCEPT}))
        super().__init__(*args, **kwargs)
    def clean(self, data, initial=None):
        clean_one = super().clean
        return [clean_one(item, initial) for item in data] if isinstance(data, (list, tuple)) else ([clean_one(data, initial)] if data else [])


class AnimalForm(forms.ModelForm):
    photos = MultipleFileField(required=False, help_text=f"JPG, PNG, HEIC, or HEIF, up to {settings.MAX_PHOTO_SIZE_MB} MiB each; five total.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.status == "Euthanized":
            self.fields["status"].disabled = True
            self.fields["status"].help_text = "This confirmed status is permanent."
        else:
            self.fields["status"].choices = [(value, label) for value, label in self.fields["status"].choices if value != "Euthanized"]
        if self.instance.pk and self.instance.photos.count() >= 5:
            self.fields["photos"].widget.attrs.update({
                "disabled": True,
                "aria-disabled": "true",
                "data-photo-limit-reached": "true",
            })

    class Meta:
        model = Animal
        exclude = ("animal_id", "created_at", "updated_at")
        widgets = {field: forms.Textarea(attrs={"rows": 3}) for field in (
            "medical_conditions", "medications", "spay_notes", "behavior_notes",
            "previous_owner", "public_description", "general_notes",
        )}
        widgets.update({field: forms.DateInput(attrs={"type": "date"}) for field in ("intake_date", "placed_date", "transfer_date", "litter_dob")})
    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        for photo in photos:
            if photo.size > settings.MAX_PHOTO_SIZE_MB * 1024 * 1024: raise forms.ValidationError(f"{photo.name} is larger than {settings.MAX_PHOTO_SIZE_MB} MiB.")
            validate_photo_upload(photo)
        return photos


class EuthanasiaConfirmationForm(forms.Form):
    confirm = forms.BooleanField(label="I confirm this animal was euthanized and understand this status cannot be reversed.")
    password = forms.CharField(label="Your current password", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Your password is incorrect.")
        return password


class SubmissionForm(forms.ModelForm):
    photos = MultipleFileField(required=False, help_text=f"Up to five JPG, PNG, HEIC, or HEIF files, {settings.MAX_PHOTO_SIZE_MB} MiB each.")
    class Meta:
        model = Submission
        fields = ("observations", "temperament", "good_with", "notes")
        widgets = {"observations": forms.Textarea(attrs={"rows": 6}), "notes": forms.Textarea(attrs={"rows": 4})}
    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        if len(photos) > 5: raise forms.ValidationError("A submission can contain no more than five photos.")
        for photo in photos:
            if photo.size > settings.MAX_PHOTO_SIZE_MB * 1024 * 1024: raise forms.ValidationError(f"{photo.name} is larger than {settings.MAX_PHOTO_SIZE_MB} MiB.")
            validate_photo_upload(photo)
        return photos
    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(x) for x in ("observations", "temperament", "good_with", "notes")) and not cleaned.get("photos"):
            raise forms.ValidationError("Add an observation, behavior, note, or photo.")
        return cleaned


class VolunteerHourForm(forms.ModelForm):
    class Meta:
        model = VolunteerHour
        fields = ("activity_date", "hours", "activity_type", "notes")
        widgets = {"activity_date": forms.DateInput(attrs={"type": "date"})}


class OrganizationForm(forms.ModelForm):
    logo_upload = forms.FileField(required=False, label="Logo", help_text=f"JPG or PNG, up to {settings.BRANDING_MAX_SIZE_MB} MiB. Select a square crop; transparency is preserved.", widget=forms.FileInput(attrs={"accept": BRANDING_ACCEPT["logo"]}))
    banner_upload = forms.FileField(required=False, label="Banner", help_text=f"JPG, PNG, HEIC, or HEIF, up to {settings.BRANDING_MAX_SIZE_MB} MiB. Select the visible banner crop.", widget=forms.FileInput(attrs={"accept": BRANDING_ACCEPT["banner"]}))
    favicon_upload = forms.FileField(required=False, label="Favicon", help_text=f"JPG or PNG, up to {settings.BRANDING_MAX_SIZE_MB} MiB. Select a square crop. The logo or default heart is used when omitted.", widget=forms.FileInput(attrs={"accept": BRANDING_ACCEPT["favicon"]}))
    logo_remove = forms.BooleanField(required=False)
    banner_remove = forms.BooleanField(required=False)
    favicon_remove = forms.BooleanField(required=False)
    logo_crop = forms.CharField(required=False, widget=forms.HiddenInput)
    banner_crop = forms.CharField(required=False, widget=forms.HiddenInput)
    favicon_crop = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance:
            for kind in ("logo", "banner", "favicon"):
                self.fields[f"{kind}_crop"].initial = json.dumps(getattr(self.instance, f"{kind}_crop") or {})

    class Meta:
        model = Organization
        fields = ("name", "primary_color", "secondary_color")

    def _clean_upload(self, kind):
        upload = self.cleaned_data.get(f"{kind}_upload")
        if upload and isinstance(upload, UploadedFile):
            validate_branding_upload(upload, kind)
        return upload

    def clean_logo_upload(self): return self._clean_upload("logo")
    def clean_banner_upload(self): return self._clean_upload("banner")
    def clean_favicon_upload(self): return self._clean_upload("favicon")

    def _clean_crop(self, kind):
        raw = self.cleaned_data.get(f"{kind}_crop") or "{}"
        try:
            crop = json.loads(raw)
            if not isinstance(crop, dict):
                raise ValueError
            for key in ("x", "y", "width", "height"):
                if key in crop and not 0 <= float(crop[key]) <= 1:
                    raise ValueError
            return crop
        except (TypeError, ValueError, json.JSONDecodeError):
            raise forms.ValidationError("Choose a valid crop area.")

    def clean_logo_crop(self): return self._clean_crop("logo")
    def clean_banner_crop(self): return self._clean_crop("banner")
    def clean_favicon_crop(self): return self._clean_crop("favicon")
    def clean(self):
        data = super().clean()
        for kind in ("logo", "banner", "favicon"):
            if data.get(f"{kind}_upload") and data.get(f"{kind}_remove"):
                self.add_error(f"{kind}_upload", "Choose a replacement or remove the existing image, not both.")
        for key in ("primary_color", "secondary_color"):
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", data.get(key, "")): self.add_error(key, "Enter a six-digit hex color.")
        return data


class UserManageForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    total_volunteer_hours = forms.DecimalField(min_value=0, required=False)
    class Meta: model = User; fields = ("full_name", "email", "phone", "role", "is_active")
    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.instance.pk and not password: raise forms.ValidationError("A password is required for a new user.")
        if password: validate_password(password, self.instance)
        return password


class AccountForm(forms.ModelForm):
    current_password = forms.CharField(widget=forms.PasswordInput, required=False)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)
    class Meta: model = User; fields = ("full_name", "email", "phone")
    def clean(self):
        data = super().clean()
        if any(data.get(x) for x in ("current_password", "new_password", "confirm_password")):
            if not self.instance.check_password(data.get("current_password", "")): self.add_error("current_password", "Current password is incorrect.")
            if data.get("new_password") != data.get("confirm_password"): self.add_error("confirm_password", "Passwords do not match.")
            if data.get("new_password"): validate_password(data["new_password"], self.instance)
        return data

