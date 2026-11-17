import json
import re
from django import forms
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import UploadedFile
from .models import Animal, Organization, Submission, User, VolunteerHour
from .images import PHOTO_ACCEPT, validate_photo_upload
from .branding_images import BRANDING_ACCEPT, validate_branding_upload
from .animal_options import BREEDS, PATTERNS, COLORS


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
    color = forms.MultipleChoiceField(required=False, label="Coat colors", choices=[(s, s) for s in COLORS], widget=forms.CheckboxSelectMultiple(attrs={"class": "coat-color-options"}))
    fleas_status = forms.ChoiceField(label="Fleas", required=False, choices=[("", "---------"), ("Positive", "Positive"), ("Negative", "Negative")])
    deceased_reason = forms.CharField(required=False, label="Reason for deceased status", widget=forms.Textarea(attrs={"rows": 3}))
    deceased_confirm = forms.BooleanField(required=False, label="I confirm this animal is deceased and understand this status is permanent.")
    deceased_password = forms.CharField(required=False, label="Your current password", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    photos = MultipleFileField(required=False, help_text=f"JPG, PNG, HEIC, or HEIF, up to {settings.MAX_PHOTO_SIZE_MB} MiB each; five total.")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["breed"].widget = forms.TextInput(attrs={"data-chip-input": "breed", "data-chip-suggestions": json.dumps(BREEDS)})
        self.fields["breed"].help_text = "Choose multiple breed suggestions or enter custom values separated by commas."
        self.fields["coat_pattern"].widget = forms.TextInput(attrs={"data-chip-input": "pattern", "data-chip-suggestions": json.dumps(PATTERNS)})
        self.fields["coat_pattern"].help_text = "Choose multiple patterns or add your own, separated by commas."
        self.fields["specific_location"].label = "Kennel location"
        self.fields["intake_location"].label = "Intake location (strays only)"
        self.fields["has_microchip"].label = "Has Microchip"
        self.fields["microchip"].label = "Microchip ID"
        if not self.is_bound:
            self.initial["color"] = [s.strip() for s in (self.instance.color or "").split(",") if s.strip()]
        self.fields["weight"].help_text = "Kilograms; up to three decimal places (0.001 kg = 1 g)."
        self.fields["height"].help_text = "Centimeters; one decimal place (0.1 cm = 1 mm)."
        for name, precision in (("weight", 3), ("height", 1)):
            self.fields[name].widget = forms.TextInput(attrs={"inputmode": "decimal", "data-nonnegative-decimal": str(precision), "pattern": rf"[0-9]*[.]?[0-9]{{0,{precision}}}", "autocomplete": "off"})
        value = lambda name: self.data.get(name, "") if self.is_bound else self.initial.get(name, getattr(self.instance, name, ""))
        conditions = {
            "intake_location": value("intake_type") == "Stray",
            "previous_owner": value("intake_type") == "Owner Surrender",
            "specific_location": value("held_at") == "Kennel", "kennel_id": value("held_at") == "Kennel",
            "foster_caregiver": value("held_at") == "Foster Home", "foster_phone": value("held_at") == "Foster Home", "foster_address": value("held_at") == "Foster Home",
            "microchip": forms.BooleanField(required=False).clean(value("has_microchip")),
            "litter_size": value("spay_status") == "Nursing", "litter_dob": value("spay_status") == "Nursing",
            "leash_skills": value("species") in ("Dog", "Cat"),
        }
        for name, active in conditions.items():
            self.fields[name].required = False
            self.fields[name].disabled = not active
        self.fields["intake_location"].required = conditions["intake_location"]
        self.fields["microchip"].required = conditions["microchip"]
        for name in ("specific_location", "kennel_id", "foster_phone", "foster_address", "litter_size", "litter_dob"):
            self.fields[name].required = conditions[name]
        self.order_fields(["name", "species", "breed", "age", "age_unit", "sex", "intake_date", "intake_type", "previous_owner", "intake_location", "found_by", "has_microchip", "microchip", "held_at", "specific_location", "kennel_id", "foster_caregiver", "foster_phone", "foster_address", "placed_date", "expected_stay", "transfer_date", "color", "coat_pattern", "coat_type", "coat_length", "weight", "height", "medical_conditions", "medications", "vaccination_status", "vaccination_notes", "heartworm_status", "fleas_status", "spay_status", "litter_size", "litter_dob", "temperament", "good_with", "house_trained", "leash_skills", "behavior_notes", "public_description", "general_notes", "status", "is_archived"])
        self.was_deceased = self.instance.status == "Deceased"
        if self.instance.status == "Deceased":
            self.fields["status"].disabled = True
            self.fields["status"].help_text = "This confirmed status is permanent."
        if self.instance.pk and self.instance.photos.count() >= 5:
            self.fields["photos"].widget.attrs.update({
                "disabled": True,
                "aria-disabled": "true",
                "data-photo-limit-reached": "true",
            })

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("has_microchip"): cleaned["microchip"] = ""
        if cleaned.get("status") == "Deceased" and not self.was_deceased:
            if not cleaned.get("deceased_reason", "").strip():
                self.add_error("deceased_reason", "Enter a reason for recording this animal as deceased.")
            if not cleaned.get("deceased_confirm"):
                self.add_error("deceased_confirm", "Confirm that you understand this status is permanent.")
            if not self.user or not self.user.check_password(cleaned.get("deceased_password", "")):
                self.add_error("deceased_password", "Enter your correct current password.")
        return cleaned

    class Meta:
        model = Animal
        exclude = ("animal_id", "created_at", "updated_at", "spay_notes", "energy_level", "flea_prevention", "found_by")
        widgets = {field: forms.Textarea(attrs={"rows": 3}) for field in (
            "medical_conditions", "medications", "spay_notes", "behavior_notes",
            "previous_owner", "public_description", "general_notes", "foster_address", "vaccination_notes",
        )}
        widgets.update({field: forms.DateInput(attrs={"type": "date"}) for field in ("intake_date", "placed_date", "transfer_date", "litter_dob")})
    def clean_color(self):
        return ", ".join(self.cleaned_data["color"])

    def clean_foster_phone(self):
        phone = self.cleaned_data.get("foster_phone", "").strip()
        if not self.fields["foster_phone"].disabled and phone and not 7 <= len(re.sub(r"\D", "", phone)) <= 18:
            raise forms.ValidationError("Enter a phone number including the area code.")
        return phone
    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        for photo in photos:
            if photo.size > settings.MAX_PHOTO_SIZE_MB * 1024 * 1024: raise forms.ValidationError(f"{photo.name} is larger than {settings.MAX_PHOTO_SIZE_MB} MiB.")
            validate_photo_upload(photo)
        return photos


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

