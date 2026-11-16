import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def default_photo_batch_expiry():
    return timezone.now() + timedelta(minutes=max(1, settings.PHOTO_BATCH_TTL_MINUTES))


def pending_photo_path(instance, filename):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"private-originals/pending/{instance.batch_id}/{uuid.uuid4().hex}.{suffix}"


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "Administrator"
        EMPLOYEE = "Employee"
        VOLUNTEER = "Volunteer"
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VOLUNTEER)
    manual_adjustment = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    join_date = models.DateField(auto_now_add=True)
    REQUIRED_FIELDS = ["email", "full_name", "phone"]

    @property
    def total_hours(self):
        recorded = self.hour_entries.aggregate(total=models.Sum("hours"))["total"] or 0
        return recorded + self.manual_adjustment

    def __str__(self): return self.full_name or self.username


class Organization(models.Model):
    name = models.CharField(max_length=160, default="Second Chance Animal Center")
    primary_color = models.CharField(max_length=7, default="#245C4A")
    secondary_color = models.CharField(max_length=7, default="#D47A45")
    logo = models.ImageField(upload_to="branding/web/", blank=True)
    logo_original = models.FileField(upload_to="private-originals/branding/logo/", blank=True)
    logo_original_filename = models.CharField(max_length=255, blank=True)
    logo_crop = models.JSONField(default=dict, blank=True)
    banner = models.ImageField(upload_to="branding/web/", blank=True)
    banner_original = models.FileField(upload_to="private-originals/branding/banner/", blank=True)
    banner_original_filename = models.CharField(max_length=255, blank=True)
    banner_crop = models.JSONField(default=dict, blank=True)
    favicon = models.ImageField(
        upload_to="branding/web/",
        blank=True,
        help_text="Optional square browser icon. When omitted, the logo or default heart mark is used.",
    )
    favicon_original = models.FileField(upload_to="private-originals/branding/favicon/", blank=True)
    favicon_original_filename = models.CharField(max_length=255, blank=True)
    favicon_crop = models.JSONField(default=dict, blank=True)

    @classmethod
    def current(cls): return cls.objects.first() or cls.objects.create()


class Animal(models.Model):
    SPECIES = [(x, x) for x in ("Dog", "Cat", "Rabbit", "Other")]
    STATUSES = [(x, x) for x in ("Available", "Pending Adoption", "Not Available")]
    SEXES = [(x, x) for x in ("Male", "Female", "Unknown")]
    LOCATIONS = [(x, x) for x in ("Kennel", "Foster Home")]
    SPAY = [(x, x) for x in ("Spayed", "Neutered", "Nursing", "Unknown")]
    animal_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=20, choices=SPECIES)
    breed = models.CharField(max_length=120)
    age = models.DecimalField(max_digits=5, decimal_places=1, validators=[MinValueValidator(0)])
    age_unit = models.CharField(max_length=10, choices=[("Months", "Months"), ("Years", "Years")])
    sex = models.CharField(max_length=10, choices=SEXES)
    intake_date = models.DateField()
    intake_type = models.CharField(max_length=50)
    intake_location = models.CharField(max_length=120)
    found_by = models.CharField(max_length=160, blank=True)
    microchip = models.CharField(max_length=80, blank=True)
    held_at = models.CharField(max_length=20, choices=LOCATIONS)
    specific_location = models.CharField(max_length=100, blank=True)
    kennel_id = models.CharField(max_length=50, blank=True)
    foster_caregiver = models.CharField(max_length=160, blank=True)
    placed_date = models.DateField()
    expected_stay = models.CharField(max_length=50, blank=True)
    transfer_date = models.DateField(null=True, blank=True)
    color = models.CharField(max_length=50)
    coat_type = models.CharField(max_length=50, blank=True)
    coat_length = models.CharField(max_length=30, blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    height = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    medical_conditions = models.TextField(blank=True)
    medications = models.TextField(blank=True)
    vaccination_status = models.CharField(max_length=50, default="Unknown")
    heartworm_status = models.CharField(max_length=50, default="Unknown")
    flea_prevention = models.CharField(max_length=20, default="Unknown")
    spay_status = models.CharField(max_length=20, choices=SPAY)
    spay_notes = models.TextField(blank=True)
    litter_size = models.PositiveIntegerField(null=True, blank=True)
    litter_dob = models.DateField(null=True, blank=True)
    temperament = models.CharField(max_length=200, blank=True)
    good_with = models.CharField(max_length=200, blank=True)
    energy_level = models.CharField(max_length=20, default="Unknown")
    house_trained = models.CharField(max_length=20, default="Unknown")
    leash_skills = models.CharField(max_length=30, default="Unknown")
    behavior_notes = models.TextField(blank=True)
    previous_owner = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUSES)
    public_description = models.TextField(blank=True)
    general_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: ordering = ["name"]

    def clean(self):
        errors = {}
        if self.status == "Available" and not self.public_description.strip(): errors["public_description"] = "Required when the animal is available."
        if self.held_at == "Kennel" and (not self.specific_location or not self.kennel_id): errors["specific_location"] = "Kennel location and ID are required."
        if self.held_at == "Foster Home" and not self.foster_caregiver: errors["foster_caregiver"] = "A foster caregiver is required."
        if self.spay_status == "Nursing" and not self.litter_size: errors["litter_size"] = "Litter size is required for a nursing animal."
        if errors: raise ValidationError(errors)

    @property
    def primary_photo(self): return self.photos.order_by("position", "id").first()
    @property
    def size_class(self):
        if self.weight is None: return "Unknown"
        w = float(self.weight)
        if self.species == "Dog": return "Small" if w < 25 else "Medium" if w < 60 else "Large" if w < 100 else "Extra Large"
        if self.species == "Cat": return "Small" if w < 8 else "Medium" if w < 13 else "Large"
        return "Unknown"
    def __str__(self): return f"{self.name} ({self.animal_id})"


class AnimalPhoto(models.Model):
    animal = models.ForeignKey(Animal, related_name="photos", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="animals/web/%Y/%m/", blank=True, validators=[FileExtensionValidator(["jpg"])])
    original_image = models.FileField(upload_to="private-originals/animals/%Y/%m/", blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True)
    caption = models.CharField(max_length=180, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["position", "id"]
    @property
    def url(self): return self.image.url if self.image else self.external_url
    @property
    def has_original(self): return bool(self.original_image)
    def clean(self):
        if not self.image and not self.external_url: raise ValidationError("A photo file or URL is required.")


class PhotoUploadBatch(models.Model):
    class Workflow(models.TextChoices):
        STAFF = "staff", "Staff gallery"
        VOLUNTEER = "volunteer", "Volunteer submission"
    class Status(models.TextChoices):
        PENDING = "pending_crop", "Pending crop"
        FINALIZING = "finalizing", "Finalizing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="photo_upload_batches", on_delete=models.CASCADE)
    animal = models.ForeignKey(Animal, related_name="photo_upload_batches", on_delete=models.CASCADE)
    workflow = models.CharField(max_length=20, choices=Workflow.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    submission_data = models.JSONField(default=dict, blank=True)
    make_primary = models.BooleanField(default=False)
    expires_at = models.DateTimeField(default=default_photo_batch_expiry, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: ordering = ["-created_at"]
    @property
    def is_expired(self): return timezone.now() >= self.expires_at


class PendingPhoto(models.Model):
    batch = models.ForeignKey(PhotoUploadBatch, related_name="photos", on_delete=models.CASCADE)
    original = models.FileField(upload_to=pending_photo_path)
    original_filename = models.CharField(max_length=255)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["position", "id"]


class AnimalHistory(models.Model):
    animal = models.ForeignKey(Animal, related_name="history", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    summary = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created_at"]


class Submission(models.Model):
    STATUS = [(x, x) for x in ("Pending", "Approved", "Rejected")]
    animal = models.ForeignKey(Animal, related_name="submissions", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="submissions", on_delete=models.PROTECT)
    observations = models.TextField(blank=True, max_length=1000)
    temperament = models.CharField(max_length=200, blank=True)
    good_with = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True, max_length=500)
    status = models.CharField(max_length=20, choices=STATUS, default="Pending")
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, related_name="reviewed_submissions", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ["-created_at"]


class SubmissionPhoto(models.Model):
    submission = models.ForeignKey(Submission, related_name="photos", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="submissions/web/%Y/%m/", blank=True, validators=[FileExtensionValidator(["jpg"])])
    original_image = models.FileField(upload_to="private-originals/submissions/%Y/%m/", blank=True)
    original_filename = models.CharField(max_length=255, blank=True)


class VolunteerHour(models.Model):
    user = models.ForeignKey(User, related_name="hour_entries", on_delete=models.PROTECT)
    activity_date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0.01)])
    activity_type = models.CharField(max_length=60)
    notes = models.CharField(max_length=250, blank=True)
    class Meta: ordering = ["-activity_date", "-id"]

