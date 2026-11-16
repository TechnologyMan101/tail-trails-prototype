import tempfile
import base64
import io
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from asgiref.sync import async_to_sync
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from PIL import Image
from shelter.branding import favicon_urls
from shelter.diagnostics import format_bytes
from shelter.forms import AnimalForm
from shelter.images import store_photo_upload
from shelter.models import Animal, AnimalPhoto, Organization, PhotoUploadBatch, Submission, SubmissionPhoto, User

PNG_BYTES = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def make_png(size, color):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def make_heic(size=(64, 48), color=(40, 120, 180)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="HEIF", quality=85)
    return output.getvalue()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TailTrailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Organization.objects.create()
        cls.admin = User.objects.create_user(username="admin@test.com", email="admin@test.com", password="Trail123!", full_name="Admin User", phone="(555) 555-0100", role="Administrator")
        cls.employee = User.objects.create_user(username="employee@test.com", email="employee@test.com", password="Trail123!", full_name="Employee User", phone="(555) 555-0101", role="Employee")
        cls.volunteer = User.objects.create_user(username="volunteer@test.com", email="volunteer@test.com", password="Trail123!", full_name="Volunteer User", phone="(555) 555-0102", role="Volunteer")
        cls.available = Animal.objects.create(animal_id="TT-2001", name="Milo", species="Dog", breed="Mix", age=3, age_unit="Years", sex="Male", intake_date=date.today(), intake_type="Stray", intake_location="Main", held_at="Kennel", specific_location="North", kennel_id="A1", placed_date=date.today(), color="Tan", spay_status="Neutered", status="Available", public_description="Friendly dog")
        cls.hidden = Animal.objects.create(animal_id="TT-2002", name="Hidden", species="Cat", breed="Mix", age=2, age_unit="Years", sex="Female", intake_date=date.today(), intake_type="Transfer", intake_location="Main", held_at="Kennel", specific_location="North", kennel_id="C1", placed_date=date.today(), color="Black", spay_status="Spayed", status="Not Available")
        AnimalPhoto.objects.create(animal=cls.available, external_url="https://example.com/one.jpg", position=0)
        AnimalPhoto.objects.create(animal=cls.available, external_url="https://example.com/two.jpg", position=1)

    def login(self, user): self.client.force_login(user)

    def animal_form_data(self, **overrides):
        data = {
            "name":"Milo", "species":"Dog", "breed":"Mix", "age":"3", "age_unit":"Years", "sex":"Male",
            "intake_date":date.today(), "intake_type":"Stray", "intake_location":"Main", "held_at":"Kennel",
            "specific_location":"North", "kennel_id":"A1", "placed_date":date.today(), "color":"Tan",
            "spay_status":"Neutered", "status":"Available", "public_description":"Friendly dog",
            "vaccination_status":"Unknown", "heartworm_status":"Unknown", "flea_prevention":"Unknown",
            "energy_level":"Unknown", "house_trained":"Unknown", "leash_skills":"Unknown",
        }
        data.update(overrides)
        return data

    def finalize_latest_batch(self, user, orientation="landscape", crop=None):
        batch = PhotoUploadBatch.objects.filter(user=user).latest("created_at")
        data = {}
        for photo in batch.photos.all():
            data[f"orientation_{photo.pk}"] = orientation
            data[f"crop_{photo.pk}"] = crop or '{"x":0,"y":0,"width":1,"height":1}'
        response = self.client.post(reverse("photo_batch_crop", args=[batch.pk]), data)
        batch.refresh_from_db()
        self.assertEqual(batch.status, PhotoUploadBatch.Status.COMPLETED)
        return response

    def test_public_only_sees_available_animals(self):
        page = self.client.get(reverse("animals"))
        self.assertContains(page, "Milo"); self.assertNotContains(page, "Hidden")
        self.assertContains(page, "<h3>Milo</h3>", html=True)
        self.assertNotContains(page, "photo-name")
        self.assertEqual(self.client.get(reverse("animal_profile", args=[self.hidden.pk])).status_code, 404)

    def test_home_and_search_cards_show_animal_names(self):
        home = self.client.get(reverse("home"))
        search = self.client.get(reverse("animals"))
        self.assertContains(home, "<h3>Milo</h3>", html=True)
        self.assertContains(search, "<h3>Milo</h3>", html=True)
        self.assertNotContains(home, "photo-name")
        self.assertNotContains(search, "photo-name")

    def test_public_header_and_card_label_styles_are_explicit(self):
        css = (settings.BASE_DIR / "static" / "style.css").read_text()
        self.assertIn(".topbar .button.ghost", css)
        self.assertIn("color:var(--primary)!important", css)
        self.assertIn("aspect-ratio:4/3", css)
        self.assertNotIn(".photo-name", css)

    def test_default_branding_generates_standard_favicon_variants(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, 'rel="icon" type="image/png" sizes="32x32"')
        self.assertContains(page, 'rel="apple-touch-icon" sizes="180x180"')
        generated = sorted(Path(settings.MEDIA_ROOT).glob("branding/generated/*.png"))
        self.assertEqual(len(generated), 2)
        self.assertEqual(sorted(Image.open(path).size for path in generated), [(32, 32), (180, 180)])

    def test_uploaded_favicon_overrides_logo_and_refreshes_variants(self):
        organization = Organization.current()
        organization.logo = SimpleUploadedFile("logo.png", make_png((80, 80), (30, 80, 210)), content_type="image/png")
        organization.save(update_fields=["logo"])
        logo_urls = favicon_urls(organization, force=True)
        organization.favicon = SimpleUploadedFile("favicon.png", make_png((80, 80), (210, 55, 45)), content_type="image/png")
        organization.save(update_fields=["favicon"])
        favicon_result = favicon_urls(organization, force=True)
        self.assertNotEqual(logo_urls["favicon_32_url"], favicon_result["favicon_32_url"])
        generated_32 = next(Path(settings.MEDIA_ROOT).glob("branding/generated/*-32.png"))
        with Image.open(generated_32) as icon:
            center = icon.convert("RGB").getpixel((16, 16))
        self.assertGreater(center[0], 180)
        self.assertLess(center[2], 100)

    def test_organization_settings_offer_favicon_upload_and_preview(self):
        self.login(self.admin)
        page = self.client.get(reverse("organization"))
        self.assertContains(page, 'name="favicon_upload"')
        self.assertContains(page, "Browser icon")

    def test_organization_settings_show_formats_croppers_and_color_pickers(self):
        self.login(self.admin)
        page = self.client.get(reverse("organization"))
        self.assertContains(page, "JPG or PNG, up to 25 MiB")
        self.assertContains(page, "JPG, PNG, HEIC, or HEIF")
        self.assertContains(page, 'accept="image/jpeg,image/png,image/heic,image/heif,.jpg,.jpeg,.png,.heic,.heif"')
        self.assertContains(page, "data-branding-cropper", count=3)
        self.assertContains(page, "data-crop-selection", count=3)
        self.assertContains(page, "data-crop-handle", count=12)
        self.assertContains(page, "crop-grid", count=12)
        self.assertNotContains(page, "data-crop-zoom")
        self.assertContains(page, 'type="color"', count=2)
        self.assertContains(page, "data-color-picker", count=2)

    def test_branding_uploads_retain_originals_and_generate_cropped_assets(self):
        self.login(self.admin)
        response = self.client.post(reverse("organization"), {
            "name": "Second Chance Animal Center",
            "primary_color": "#245C4A",
            "secondary_color": "#D47A45",
            "logo_upload": SimpleUploadedFile("wide-logo.png", make_png((600, 300), (20, 140, 90)), content_type="image/png"),
            "banner_upload": SimpleUploadedFile("banner.png", make_png((900, 900), (150, 60, 40)), content_type="image/png"),
            "favicon_upload": SimpleUploadedFile("icon.png", make_png((300, 500), (50, 80, 190)), content_type="image/png"),
            "logo_crop": '{"x":0.25,"y":0,"width":0.5,"height":1}',
            "banner_crop": '{"x":0,"y":0.333333,"width":1,"height":0.333333}',
            "favicon_crop": '{"x":0,"y":0.2,"width":1,"height":0.6}',
        })
        self.assertEqual(response.status_code, 302)
        organization = Organization.current()
        self.assertTrue(organization.logo.name.endswith(".png"))
        self.assertTrue(organization.banner.name.endswith(".jpg"))
        self.assertTrue(organization.favicon.name.endswith(".png"))
        self.assertEqual(organization.logo_original_filename, "wide-logo.png")
        self.assertEqual(organization.banner_original_filename, "banner.png")
        self.assertEqual(organization.favicon_original_filename, "icon.png")
        with Image.open(organization.logo.path) as logo:
            self.assertEqual(logo.size, (512, 512))
        with Image.open(organization.banner.path) as banner:
            self.assertEqual(banner.size, (1920, 640))

    def test_heic_branding_preview_is_server_rendered_and_admin_only(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("branding_preview", args=["banner"]),
            {"image": SimpleUploadedFile("banner.heic", make_heic((300, 200)), content_type="image/heic")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        with Image.open(io.BytesIO(response.content)) as preview:
            self.assertEqual(preview.format, "JPEG")
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("branding_preview", args=["banner"])).status_code, 403)

    def test_animal_sorting_options_change_result_order(self):
        self.hidden.name = "alice"
        self.hidden.status = "Available"
        self.hidden.public_description = "Friendly cat"
        self.hidden.save(update_fields=["name", "status", "public_description"])
        descending = self.client.get(reverse("animals"), {"sort": "name_desc"}).content.decode()
        ascending = self.client.get(reverse("animals"), {"sort": "name_asc"}).content.decode()
        self.assertLess(descending.find("<h3>Milo</h3>"), descending.find("<h3>alice</h3>"))
        self.assertLess(ascending.find("<h3>alice</h3>"), ascending.find("<h3>Milo</h3>"))
        self.assertIn('value="name_desc" selected', descending)
        self.assertIn("Apply sort", descending)

    def test_gallery_renders_all_photos_and_controls(self):
        page = self.client.get(reverse("animal_profile", args=[self.available.pk]))
        self.assertContains(page, "data-gallery")
        self.assertContains(page, "https://example.com/one.jpg")
        self.assertContains(page, "https://example.com/two.jpg")
        self.assertContains(page, "data-gallery-next")
        self.assertContains(page, "data-gallery-inline-next")
        self.assertContains(page, "data-gallery-inline-prev")
        self.assertContains(page, "2 photos")

    def test_lightbox_prevents_dialog_and_page_scrolling(self):
        css = (settings.BASE_DIR / "static" / "style.css").read_text()
        script = (settings.BASE_DIR / "static" / "app.js").read_text()
        self.assertIn(".gallery-lightbox{overflow:hidden!important", css)
        self.assertIn(".lightbox-open,.lightbox-open body{overflow:hidden!important}", css)
        self.assertIn("classList.add('lightbox-open')", script)
        self.assertIn("classList.remove('lightbox-open')", script)

    def test_role_boundaries(self):
        self.login(self.volunteer)
        self.assertEqual(self.client.get(reverse("animal_new")).status_code, 403)
        self.assertEqual(self.client.get(reverse("users")).status_code, 403)
        self.assertEqual(self.client.get(reverse("submit_update", args=[self.available.pk])).status_code, 200)
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("submissions")).status_code, 200)
        self.assertEqual(self.client.get(reverse("users")).status_code, 403)

    def test_staff_uploads_and_removes_gallery_photo(self):
        self.login(self.employee)
        original = self.available.photos.first()
        upload = SimpleUploadedFile("new.png", PNG_BYTES, content_type="image/png")
        data = self.animal_form_data(remove_photo=str(original.pk), photos=upload, make_new_primary="1")
        response = self.client.post(reverse("animal_edit", args=[self.available.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/photo-batches/", response.url)
        self.finalize_latest_batch(self.employee)
        self.assertEqual(self.available.photos.count(), 2)
        self.assertFalse(self.available.photos.filter(pk=original.pk).exists())
        generated = self.available.photos.exclude(original_image="").get()
        self.assertEqual(self.available.primary_photo.pk, generated.pk)
        self.assertEqual(generated.original_filename, "new.png")
        self.assertTrue(generated.original_image.name.endswith(".png"))
        self.assertTrue(generated.image.name.endswith(".jpg"))
        with Image.open(generated.image.path) as web_image:
            self.assertEqual(web_image.format, "JPEG")
            self.assertEqual(web_image.size, (1600, 1200))
        self.assertEqual(self.client.get(reverse("media_file", args=[generated.original_image.name])).status_code, 404)
        download = self.client.get(reverse("original_photo", args=["animal", generated.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertIn("new.png", download["Content-Disposition"])
        profile = self.client.get(reverse("animal_profile", args=[self.available.pk]))
        self.assertContains(profile, generated.image.url)
        self.assertContains(profile, "2 photos")
        self.assertContains(profile, "data-gallery-next")
        editor = self.client.get(reverse("animal_edit", args=[self.available.pk]))
        original_url = reverse("original_photo", args=["animal", generated.pk])
        self.assertContains(editor, f'href="{original_url}"')
        self.assertContains(editor, "Download original")
        self.assertContains(editor, f"Download original file for Milo photo")

    def test_external_photos_show_original_unavailable(self):
        self.login(self.employee)
        editor = self.client.get(reverse("animal_edit", args=[self.available.pk]))
        self.assertContains(editor, "Original unavailable", count=2)
        self.assertContains(editor, 'class="photo-manager"')
        styles = (settings.BASE_DIR / "static" / "style.css").read_text()
        self.assertIn("grid-template-columns:repeat(auto-fill,minmax(210px,1fr))", styles)
        self.assertIn("aspect-ratio:4/3;object-fit:cover", styles)

    def test_heic_upload_is_retained_and_converted_to_web_jpg(self):
        self.login(self.employee)
        upload = SimpleUploadedFile("shelter-photo.heic", make_heic(), content_type="image/heic")
        response = self.client.post(
            reverse("animal_edit", args=[self.available.pk]),
            self.animal_form_data(photos=upload, make_new_primary="1"),
        )
        self.assertEqual(response.status_code, 302)
        self.finalize_latest_batch(self.employee)
        photo = self.available.photos.exclude(original_image="").get()
        self.assertEqual(photo.original_filename, "shelter-photo.heic")
        self.assertTrue(photo.original_image.name.endswith(".heic"))
        self.assertTrue(photo.image.name.endswith(".jpg"))
        with Image.open(photo.image.path) as web_image:
            self.assertEqual(web_image.format, "JPEG")
            self.assertEqual(web_image.size, (1600, 1200))

    def test_photo_inputs_advertise_heic_and_heif(self):
        self.login(self.employee)
        editor = self.client.get(reverse("animal_edit", args=[self.available.pk]))
        for value in ("image/heic", "image/heif", ".heic", ".heif"):
            self.assertContains(editor, value)

    def test_photo_input_is_disabled_at_five_existing_photos(self):
        self.login(self.employee)
        for position in range(2, 5):
            AnimalPhoto.objects.create(animal=self.available, external_url=f"https://example.com/{position}.jpg", position=position)
        editor = self.client.get(reverse("animal_edit", args=[self.available.pk]))
        self.assertTrue(editor.context["form"].fields["photos"].widget.attrs["disabled"])
        self.assertContains(editor, "Maximum reached")
        self.assertContains(editor, "data-photo-limit-reached=\"true\"")

    def test_selecting_two_photos_with_four_existing_keeps_server_error(self):
        self.login(self.employee)
        AnimalPhoto.objects.create(animal=self.available, external_url="https://example.com/three.jpg", position=2)
        AnimalPhoto.objects.create(animal=self.available, external_url="https://example.com/four.jpg", position=3)
        uploads = [
            SimpleUploadedFile("one.png", PNG_BYTES, content_type="image/png"),
            SimpleUploadedFile("two.png", PNG_BYTES, content_type="image/png"),
        ]
        response = self.client.post(reverse("animal_edit", args=[self.available.pk]), self.animal_form_data(photos=uploads))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An animal gallery can contain no more than five photos.")
        self.assertContains(response, 'class="field-error-list"')
        self.assertEqual(self.available.photos.count(), 4)

    def test_upload_progress_is_accessible(self):
        self.login(self.employee)
        editor = self.client.get(reverse("animal_edit", args=[self.available.pk]))
        self.assertContains(editor, "data-upload-progress")
        self.assertContains(editor, 'role="status"')
        self.assertContains(editor, 'aria-live="polite"')
        script = (settings.BASE_DIR / "static" / "app.js").read_text()
        self.assertIn("new XMLHttpRequest()", script)
        self.assertIn("request.upload.addEventListener('progress'", script)
        self.assertIn("Upload progress will begin when you save.", script)
        self.assertIn("Overall upload:", script)
        self.assertIn("All ${fileCount} ${fileNoun} uploaded. Processing images", script)
        self.assertIn("new DOMParser().parseFromString", script)
        self.assertIn("initializePhotoEditors();", script)

    def test_successful_multi_upload_opens_crop_workspace_with_live_deadline(self):
        self.login(self.employee)
        uploads = [
            SimpleUploadedFile("one.png", make_png((400, 300), (30, 90, 150)), content_type="image/png"),
            SimpleUploadedFile("two.png", make_png((300, 500), (160, 80, 30)), content_type="image/png"),
        ]
        response = self.client.post(reverse("animal_edit", args=[self.available.pk]), self.animal_form_data(photos=uploads))
        self.assertEqual(response.status_code, 302)
        batch = PhotoUploadBatch.objects.get(user=self.employee, status=PhotoUploadBatch.Status.PENDING)
        self.assertEqual(batch.photos.count(), 2)
        crop_page = self.client.get(response.url)
        self.assertContains(crop_page, "Crop 2 photos")
        self.assertContains(crop_page, "data-photo-cropper", count=2)
        self.assertContains(crop_page, 'class="photo-crop-form"')
        self.assertContains(crop_page, "data-photo-crop-selection", count=2)
        self.assertContains(crop_page, "data-crop-handle", count=8)
        self.assertContains(crop_page, "crop-grid", count=8)
        self.assertNotContains(crop_page, "data-photo-crop-zoom")
        self.assertContains(crop_page, "data-batch-countdown")
        self.assertContains(crop_page, "Time remaining")
        self.assertEqual(self.available.photos.count(), 2)

    def test_expired_photo_batches_are_cleaned_with_private_files(self):
        self.login(self.employee)
        upload = SimpleUploadedFile("temporary.png", PNG_BYTES, content_type="image/png")
        self.client.post(reverse("animal_edit", args=[self.available.pk]), self.animal_form_data(photos=upload))
        batch = PhotoUploadBatch.objects.get(user=self.employee)
        pending = batch.photos.get()
        path = pending.original.path
        self.assertTrue(Path(path).exists())
        batch.expires_at = timezone.now() - timedelta(seconds=1)
        batch.save(update_fields=["expires_at"])
        call_command("cleanup_photo_batches", verbosity=0)
        self.assertFalse(PhotoUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertFalse(Path(path).exists())

    def test_cancelled_photo_batch_is_discarded_immediately(self):
        self.login(self.volunteer)
        upload = SimpleUploadedFile("cancel.png", PNG_BYTES, content_type="image/png")
        self.client.post(reverse("submit_update", args=[self.available.pk]), {"observations": "Cancel me", "photos": upload})
        batch = PhotoUploadBatch.objects.get(user=self.volunteer)
        path = batch.photos.get().original.path
        response = self.client.post(reverse("photo_batch_cancel", args=[batch.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PhotoUploadBatch.objects.filter(pk=batch.pk).exists())
        self.assertFalse(Path(path).exists())

    def test_cancelling_staff_batch_preserves_existing_gallery_changes(self):
        self.login(self.employee)
        existing = self.available.photos.first()
        upload = SimpleUploadedFile("replacement.png", PNG_BYTES, content_type="image/png")
        response = self.client.post(
            reverse("animal_edit", args=[self.available.pk]),
            self.animal_form_data(photos=upload, remove_photo=str(existing.pk)),
        )
        batch = PhotoUploadBatch.objects.get(user=self.employee)
        self.assertTrue(self.available.photos.filter(pk=existing.pk).exists())
        self.client.post(reverse("photo_batch_cancel", args=[batch.pk]))
        self.assertTrue(self.available.photos.filter(pk=existing.pk).exists())

    def test_example_password_uses_monospace_code_styling(self):
        page = self.client.get(reverse("login"))
        self.assertContains(page, "Password: <code>Trail123!</code>", html=True)
        css = (settings.BASE_DIR / "static" / "style.css").read_text()
        self.assertIn(".demo-note code{font-family:ui-monospace", css)

    @override_settings(PHOTO_WEB_SIZE=(900, 600))
    def test_portrait_upload_uses_exact_crop_without_letterboxing(self):
        self.login(self.employee)
        portrait = SimpleUploadedFile(
            "portrait.png",
            make_png((300, 900), (190, 35, 55)),
            content_type="image/png",
        )
        response = self.client.post(
            reverse("animal_edit", args=[self.available.pk]),
            self.animal_form_data(photos=portrait, make_new_primary="1"),
        )
        self.assertEqual(response.status_code, 302)
        self.finalize_latest_batch(self.employee, orientation="portrait")
        generated = self.available.photos.exclude(original_image="").get()
        with Image.open(generated.image.path) as web_image:
            self.assertEqual(web_image.size, (600, 900))
            corner = web_image.convert("RGB").getpixel((0, 0))
            self.assertGreater(corner[0], 140)
            self.assertLess(corner[1], 90)

    def test_profile_gallery_does_not_crop_generated_orientation(self):
        css = (settings.BASE_DIR / "static" / "style.css").read_text()
        self.assertIn(".gallery-main img{object-fit:contain!important}", css)

    def test_staff_can_choose_an_existing_cover_photo(self):
        self.login(self.employee)
        second = self.available.photos.order_by("position", "id")[1]
        response = self.client.post(
            reverse("animal_edit", args=[self.available.pk]),
            self.animal_form_data(primary_photo=str(second.pk)),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.available.primary_photo.pk, second.pk)
        editor = self.client.get(reverse("animal_edit", args=[self.available.pk]))
        self.assertContains(editor, f'name="primary_photo" value="{second.pk}" checked')
        self.assertContains(editor, "Current cover")

    def test_request_limit_allows_five_max_size_photos(self):
        self.assertEqual(settings.MAX_PHOTO_SIZE_MB, 25)
        self.assertGreaterEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 160 * 1024 * 1024)

    @override_settings(MAX_PHOTO_SIZE_MB=1)
    def test_per_file_photo_limit_is_enforced(self):
        oversized = SimpleUploadedFile("oversized.png", b"x" * (1024 * 1024 + 1), content_type="image/png")
        form = AnimalForm(
            data=self.animal_form_data(),
            files=MultiValueDict({"photos": [oversized]}),
            instance=self.available,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("oversized.png is larger than 1 MiB.", form.errors["photos"])

    def test_volunteer_submission_photos_are_converted_and_original_retained(self):
        self.login(self.volunteer)
        upload = SimpleUploadedFile("volunteer.png", PNG_BYTES, content_type="image/png")
        response = self.client.post(reverse("submit_update", args=[self.available.pk]), {"observations":"New photo", "photos":upload})
        self.assertEqual(response.status_code, 302)
        self.finalize_latest_batch(self.volunteer)
        photo = SubmissionPhoto.objects.get(submission__user=self.volunteer)
        self.assertEqual(photo.original_filename, "volunteer.png")
        self.assertTrue(photo.original_image.name.endswith(".png"))
        self.assertTrue(photo.image.name.endswith(".jpg"))

    def test_volunteer_can_track_only_their_own_submission_statuses(self):
        approved = Submission.objects.create(animal=self.available, user=self.volunteer, observations="Friendly", status="Approved")
        rejected = Submission.objects.create(animal=self.hidden, user=self.volunteer, observations="Old note", status="Rejected", rejection_reason="Please add more detail")
        other = User.objects.create_user(username="other@test.com", email="other@test.com", password="Trail123!", full_name="Other Volunteer", phone="555-0199", role="Volunteer")
        Submission.objects.create(animal=self.available, user=other, observations="Must remain private to its submitter")
        self.login(self.volunteer)
        pending_page = self.client.get(reverse("submissions"))
        self.assertContains(pending_page, "My submissions")
        self.assertContains(pending_page, "Pending <b>0</b>", html=True)
        self.assertNotContains(pending_page, "Must remain private")
        approved_page = self.client.get(reverse("submissions"), {"status": "Approved"})
        self.assertContains(approved_page, approved.observations)
        rejected_page = self.client.get(reverse("submissions"), {"status": "Rejected"})
        self.assertContains(rejected_page, rejected.rejection_reason)

    def test_volunteer_upload_has_editor_progress_and_capacity_guidance(self):
        self.login(self.volunteer)
        page = self.client.get(reverse("submit_update", args=[self.available.pk]))
        self.assertContains(page, "data-photo-editor")
        self.assertContains(page, "data-file-selection-message")
        self.assertContains(page, "data-upload-progress")
        self.assertContains(page, "2 of 5 official gallery spaces are currently used")
        self.assertContains(page, "they do not reserve gallery space")

    def test_staff_submission_review_shows_candidate_and_official_photos(self):
        submission = Submission.objects.create(animal=self.available, user=self.volunteer, observations="Photo update")
        candidate = store_photo_upload(
            SubmissionPhoto(submission=submission),
            SimpleUploadedFile("candidate.png", PNG_BYTES, content_type="image/png"),
        )
        self.login(self.employee)
        page = self.client.get(reverse("submissions"))
        self.assertContains(page, candidate.image.url)
        self.assertContains(page, "Submitted candidate photos")
        self.assertContains(page, "Current official gallery")
        self.assertContains(page, 'name="approve_photo"')
        self.assertContains(page, 'name="replace_photo"', count=2)
        self.assertContains(page, reverse("original_photo", args=["submission", candidate.pk]))

    def test_approval_can_select_candidate_subset_and_rechecks_capacity(self):
        submission = Submission.objects.create(animal=self.available, user=self.volunteer, observations="Several candidates")
        candidates = [
            store_photo_upload(
                SubmissionPhoto(submission=submission),
                SimpleUploadedFile(f"candidate-{number}.png", make_png((20, 20), (number * 30, 80, 120)), content_type="image/png"),
            )
            for number in range(1, 5)
        ]
        self.login(self.employee)
        over_capacity = self.client.post(
            reverse("review_submission", args=[submission.pk, "approve"]),
            {"approve_photo": [str(photo.pk) for photo in candidates]},
            follow=True,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, "Pending")
        self.assertContains(over_capacity, "keep the gallery at five or fewer")
        response = self.client.post(
            reverse("review_submission", args=[submission.pk, "approve"]),
            {"approve_photo": [str(photo.pk) for photo in candidates[:3]]},
        )
        self.assertEqual(response.status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.status, "Approved")
        self.assertEqual(self.available.photos.count(), 5)

    def test_legacy_uploaded_photo_is_backfilled(self):
        legacy = AnimalPhoto.objects.create(animal=self.hidden, image=SimpleUploadedFile("legacy.png", PNG_BYTES, content_type="image/png"))
        self.assertFalse(legacy.original_image)
        call_command("reprocess_photos", verbosity=0)
        legacy.refresh_from_db()
        self.assertTrue(legacy.original_image.name.endswith(".png"))
        self.assertTrue(legacy.image.name.endswith(".jpg"))

    @override_settings(PHOTO_WEB_SIZE=(800, 600))
    def test_all_photos_can_be_regenerated_from_retained_originals(self):
        upload = SimpleUploadedFile("portrait.png", make_png((300, 900), (40, 90, 180)), content_type="image/png")
        photo = store_photo_upload(AnimalPhoto(animal=self.hidden, position=3), upload)
        old_web_name = photo.image.name
        call_command("reprocess_photos", "--all", verbosity=0)
        photo.refresh_from_db()
        self.assertNotEqual(photo.image.name, old_web_name)
        self.assertTrue(photo.original_image)
        with Image.open(photo.image.path) as web_image:
            self.assertEqual(web_image.size, (600, 800))

    def test_submission_approval_updates_record(self):
        submission = Submission.objects.create(animal=self.available, user=self.volunteer, observations="Calm during brushing")
        self.login(self.employee)
        response = self.client.post(reverse("review_submission", args=[submission.pk, "approve"]))
        self.assertEqual(response.status_code, 302)
        submission.refresh_from_db(); self.available.refresh_from_db()
        self.assertEqual(submission.status, "Approved")
        self.assertIn("Calm during brushing", self.available.behavior_notes)

    def test_reverse_proxy_prefix(self):
        from config.wsgi import application
        from django.test.client import RequestFactory
        environ = RequestFactory().get("/", HTTP_X_FORWARDED_PREFIX="/tail-trails").environ
        headers = {}
        def start_response(status, response_headers): headers["status"] = status
        body = b"".join(application(environ, start_response)).decode()
        from django.urls import set_script_prefix
        set_script_prefix("/")
        self.assertTrue(headers["status"].startswith("200"))
        self.assertIn('href="/tail-trails/animals"', body)

    def test_health(self):
        health = self.client.get(reverse("healthz")).json()
        self.assertEqual(health["status"], "ok")
        self.assertEqual(settings.APP_VERSION, (settings.BASE_DIR / "VERSION").read_text().strip())
        self.assertEqual(health["version"], settings.APP_VERSION)

    def test_version_file_is_the_only_runtime_version_source(self):
        compose = (settings.BASE_DIR / "docker-compose.yml").read_text()
        dockerfile = (settings.BASE_DIR / "Dockerfile").read_text()
        environment_example = (settings.BASE_DIR / ".env.example").read_text()
        self.assertNotIn("APP_VERSION", compose)
        self.assertNotIn("APP_VERSION", dockerfile)
        self.assertNotIn("APP_VERSION", environment_example)

    def test_asgi_runtime_and_dependencies_are_release_locked(self):
        dockerfile = (settings.BASE_DIR / "Dockerfile").read_text()
        policy = (settings.BASE_DIR / "requirements.in").read_text()
        lock = (settings.BASE_DIR / "requirements.lock").read_text()
        self.assertIn("FROM python:3.14.10-slim", dockerfile)
        self.assertIn("--require-hashes -r requirements.lock", dockerfile)
        self.assertIn("uvicorn config.asgi:application", dockerfile)
        self.assertNotIn("gunicorn", dockerfile.lower())
        self.assertIn("Django~=5.2.0", policy)
        self.assertIn("django==5.2.19", lock)
        self.assertIn("uvicorn==0.54.0", lock)
        self.assertIn("pillow-heif>=1.8,<2", policy)
        self.assertIn("pillow-heif==1.8.1", lock)
        self.assertIn("--hash=sha256:", lock)
        self.assertEqual(settings.ASGI_APPLICATION, "config.asgi.application")

    def test_system_information_is_admin_only_and_reports_operations(self):
        self.login(self.admin)
        page = self.client.get(reverse("system_information"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, settings.APP_VERSION)
        self.assertContains(page, "Connected")
        self.assertContains(page, "Latest migration")
        self.assertContains(page, "Upload storage")
        self.assertContains(page, "Free")
        self.assertContains(page, "Server usage")
        self.assertContains(page, "Process resident memory")
        self.assertContains(page, "Logical CPUs")
        self.assertContains(page, "Swap space")
        self.assertContains(page, "Swap source")
        self.assertContains(page, "container-visible snapshots")
        self.assertEqual(page.context["refresh_interval"], 5)
        self.assertContains(page, 'data-system-refresh-form')
        self.assertContains(page, 'value="5" selected')
        self.assertEqual(
            self.client.get(reverse("system_information"), {"refresh": "2"}).context["refresh_interval"],
            2,
        )
        self.assertEqual(
            self.client.get(reverse("system_information"), {"refresh": "invalid"}).context["refresh_interval"],
            5,
        )
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("system_information")).status_code, 403)

    def test_system_information_uses_iec_binary_units(self):
        self.assertEqual(format_bytes(1024), "1.0 KiB")
        self.assertEqual(format_bytes(1024 ** 2), "1.0 MiB")
        self.assertEqual(format_bytes(1024 ** 3), "1.0 GiB")
        self.assertEqual(format_bytes(1024 ** 4), "1.0 TiB")
        self.login(self.admin)
        page = self.client.get(reverse("system_information"))
        self.assertContains(page, "25 MiB")
        self.assertContains(page, "160 MiB")

    def test_system_information_uses_an_admin_only_sse_stream(self):
        self.login(self.admin)
        with patch("shelter.views._system_snapshot_html", return_value="<section>updated</section>"):
            stream = self.client.get(reverse("system_information_stream"), {"refresh": "2"})
            self.assertEqual(stream.status_code, 200)
            self.assertEqual(stream["Content-Type"], "text/event-stream")
            self.assertEqual(stream["Cache-Control"], "no-cache, no-transform")
            self.assertEqual(stream["X-Accel-Buffering"], "no")

            async def first_event():
                iterator = stream.streaming_content.__aiter__()
                try:
                    return await anext(iterator)
                finally:
                    await iterator.aclose()

            event = async_to_sync(first_event)().decode()
            self.assertIn("event: snapshot", event)
            self.assertIn("<section>updated</section>", event)

        javascript = (settings.BASE_DIR / "static" / "app.js").read_text()
        self.assertIn("new EventSource", javascript)
        self.assertNotIn("window.location.reload()", javascript.split("const systemRefreshForm =")[1])

        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("system_information_stream")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("system_information_stream")).status_code, 401)

    def test_git_workflow_is_separate_and_linked(self):
        readme = (settings.BASE_DIR / "README.md").read_text()
        workflow = (settings.BASE_DIR / "GIT_WORKFLOW.md").read_text()
        self.assertIn("GIT_WORKFLOW.md", readme)
        self.assertIn("git archive", workflow)
        self.assertIn("$(cat VERSION)", workflow)

    def test_compose_publishes_only_on_ipv4_and_ipv6_loopback(self):
        compose = (settings.BASE_DIR / "docker-compose.yml").read_text()
        self.assertIn('"127.0.0.1:${TAILTRAILS_PORT:-8000}:8000"', compose)
        self.assertIn('"[::1]:${TAILTRAILS_PORT:-8000}:8000"', compose)
        self.assertNotIn('- "${TAILTRAILS_PORT:-8000}:8000"', compose)

    def test_cleanup_service_defaults_to_hourly_configurable_minutes(self):
        compose = (settings.BASE_DIR / "docker-compose.yml").read_text()
        environment_example = (settings.BASE_DIR / ".env.example").read_text()
        self.assertIn("PHOTO_BATCH_TTL_MINUTES=30", environment_example)
        self.assertIn("PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES=60", environment_example)
        self.assertIn('command: ["python", "manage.py", "run_photo_batch_cleanup"]', compose)
        self.assertIn("PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES: ${PHOTO_BATCH_CLEANUP_INTERVAL_MINUTES:-60}", compose)

    def test_reverse_proxy_examples_use_the_https_subdomain_layout(self):
        nginx = (settings.BASE_DIR / "nginx.example.conf").read_text()
        apache = (settings.BASE_DIR / "apache.example.conf").read_text()
        for configuration in (nginx, apache):
            self.assertIn("tailtrails.exampleshelter.com", configuration)
            self.assertIn("exampleshelter.com/fullchain.pem", configuration)
            self.assertIn("exampleshelter.com/privkey.pem", configuration)
            self.assertIn("Strict-Transport-Security", configuration)
            self.assertIn("127.0.0.1:8000", configuration)
        self.assertIn("return 301 https://$host$request_uri", nginx)
        self.assertIn("client_max_body_size 160m", nginx)
        self.assertIn("proxy_buffering off", nginx)
        self.assertNotIn("X-Forwarded-Prefix", nginx)
        self.assertIn("<VirtualHost *:80>", apache)
        self.assertIn("RewriteRule ^ https://tailtrails.exampleshelter.com%{REQUEST_URI}", apache)
        self.assertIn("<VirtualHost *:443>", apache)
