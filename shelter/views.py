import asyncio
import logging
import json
import re
from functools import wraps
from pathlib import Path
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q, Sum, Case, When, F, FloatField
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import AccountForm, AnimalForm, OrganizationForm, SubmissionForm, UserManageForm, VolunteerHourForm
from .branding import favicon_urls
from .branding_images import branding_preview_bytes, delete_branding_asset, process_branding_asset, validate_branding_upload
from .diagnostics import system_snapshot
from .models import Animal, AnimalPhoto, Organization, PhotoUploadBatch, Submission, SubmissionPhoto, User, VolunteerHour
from .images import delete_photo_files
from .photo_batches import cancel_photo_batch, create_photo_batch, finalize_photo_batch, parse_crop_payload
from .confirmation import AnimalDeleteForm
from .models import PendingPhoto


def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not request.user.is_superuser and request.user.role not in allowed:
                raise PermissionDenied
            return fn(request, *args, **kwargs)
        return wrapped
    return decorator


def home(request): return render(request, "home.html", {"animals": Animal.objects.filter(status="Available", is_archived=False).prefetch_related("photos")[:3]})
def healthz(request): return JsonResponse({"status": "ok", "version": settings.APP_VERSION})

def media_file(request, path):
    if path.startswith("private-originals/"):
        raise Http404
    from django.views.static import serve
    return serve(request, path, document_root=settings.MEDIA_ROOT)

@roles("Administrator", "Employee")
def original_photo(request, kind, pk):
    if kind == "animal": photo = get_object_or_404(AnimalPhoto, pk=pk)
    elif kind == "submission": photo = get_object_or_404(SubmissionPhoto, pk=pk)
    else: raise Http404
    if not photo.original_image: raise Http404
    filename = photo.original_filename or Path(photo.original_image.name).name
    try: response = FileResponse(photo.original_image.open("rb"), as_attachment=True, filename=filename)
    except OSError: raise Http404
    return response

def sign_in(request):
    if request.user.is_authenticated: return redirect("animals")
    if request.method == "POST":
        email = request.POST.get("email", "").lower().strip()
        user = authenticate(request, username=email, password=request.POST.get("password", ""))
        if user and user.is_active:
            login(request, user); messages.success(request, f"Welcome back, {user.full_name.split()[0]}!")
            return redirect(request.GET.get("next") or "animals")
        messages.error(request, "Email or password is incorrect, or the account is inactive.")
    return render(request, "login.html")

@require_POST
def sign_out(request): logout(request); messages.success(request, "You have been signed out."); return redirect("home")

def animals(request):
    qs = Animal.objects.prefetch_related("photos")
    public = not request.user.is_authenticated
    can_archive = request.user.is_authenticated and (request.user.is_superuser or request.user.role in ("Administrator", "Employee"))
    include_archived = can_archive and request.GET.get("include_archived") == "1"
    if not include_archived: qs = qs.filter(is_archived=False)
    if public: qs = qs.filter(status="Available")
    q = request.GET.get("q", "").strip()
    if q: qs = qs.filter(Q(name__icontains=q) | Q(animal_id__icontains=q))
    for field in ("species", "sex", "status", "held_at", "spay_status"):
        if request.GET.get(field): qs = qs.filter(**{field: request.GET[field]})
    if request.GET.get("color"):
        qs = qs.filter(color__iregex=r"(^|,\s*)" + re.escape(request.GET["color"]) + r"(\s*,|$)")
    if request.GET.get("breed"): qs = qs.filter(breed__icontains=request.GET["breed"])
    sort = request.GET.get("sort", "name_asc")
    qs = qs.annotate(age_days=Case(When(age_unit="Weeks", then=F("age") * 7), When(age_unit="Months", then=F("age") * 30.4375), default=F("age") * 365.25, output_field=FloatField()))
    order = {
        "name_asc": (Lower("name").asc(), "id"),
        "name_desc": (Lower("name").desc(), "id"),
        "age_asc": ("age_days", "id"),
        "age_desc": ("-age_days", "id"),
        "id_asc": ("animal_id",),
        "id_desc": ("-animal_id",),
    }.get(sort, (Lower("name").asc(), "id"))
    return render(request, "animals.html", {"animals": qs.order_by(*order), "public": public, "sort": sort, "can_archive": can_archive, "include_archived": include_archived})

def animal_profile(request, pk):
    animal = get_object_or_404(Animal.objects.prefetch_related("photos"), pk=pk)
    if animal.is_archived and not (request.user.is_authenticated and (request.user.is_superuser or request.user.role in ("Administrator", "Employee"))): raise Http404
    if not request.user.is_authenticated and animal.status != "Available":
        raise Http404
    return render(request, "animal_profile.html", {"animal": animal})

@roles("Administrator", "Employee")
def animal_edit(request, pk=None):
    animal = get_object_or_404(Animal, pk=pk) if pk else None
    if request.method == "POST":
        form = AnimalForm(request.POST, request.FILES, instance=animal, user=request.user)
        remove_ids = {int(x) for x in request.POST.getlist("remove_photo") if x.isdigit()}
        primary_photo_id = request.POST.get("primary_photo", "")
        make_new_primary = request.POST.get("make_new_primary") == "1"
        current_count = animal.photos.exclude(id__in=remove_ids).count() if animal else 0
        uploads = request.FILES.getlist("photos")
        if current_count + len(uploads) > 5: form.add_error("photos", "An animal gallery can contain no more than five photos.")
        if primary_photo_id and animal:
            if not primary_photo_id.isdigit() or not animal.photos.filter(pk=primary_photo_id).exists():
                form.add_error("photos", "Choose a cover photo from this animal's gallery.")
            elif int(primary_photo_id) in remove_ids:
                form.add_error("photos", "The cover photo cannot also be removed.")
        if make_new_primary and not uploads:
            form.add_error("photos", "Select at least one new photo before making it the cover.")
        if form.is_valid():
            try:
                with transaction.atomic():
                    if animal:
                        # Recheck under lock after validation to reject stale editor saves.
                        locked = Animal.objects.select_for_update().get(pk=animal.pk)
                        if locked.status == "Deceased" and form.cleaned_data.get("status") != "Deceased":
                            raise ValidationError("This animal was confirmed deceased while you were editing. Reload the record.")
                    obj = form.save(commit=False)
                    confirming_deceased = obj.status == "Deceased" and not form.was_deceased
                    if confirming_deceased:
                        obj.deceased_at = timezone.now()
                        obj.deceased_by = request.user
                        obj.deceased_reason = form.cleaned_data["deceased_reason"].strip()
                    if not obj.animal_id:
                        number = 1001
                        while Animal.objects.filter(animal_id=f"TT-{number}").exists(): number += 1
                        obj.animal_id = f"TT-{number}"
                    obj.save(); form.save_m2m()
                    if not uploads:
                        if remove_ids:
                            for photo in obj.photos.filter(id__in=remove_ids):
                                delete_photo_files(photo)
                                photo.delete()
                        photos = list(obj.photos.order_by("position", "id"))
                        chosen_id = int(primary_photo_id) if primary_photo_id else None
                        if chosen_id:
                            photos.sort(key=lambda photo: photo.pk != chosen_id)
                        for position, photo in enumerate(photos): photo.position = position
                        AnimalPhoto.objects.bulk_update(photos, ["position"])
                    batch = create_photo_batch(
                        user=request.user, animal=obj, workflow=PhotoUploadBatch.Workflow.STAFF,
                        uploads=uploads, make_primary=make_new_primary,
                        form_data={"remove_ids": sorted(remove_ids), "primary_photo_id": primary_photo_id},
                    ) if uploads else None
                if batch:
                    messages.success(request, "Upload complete. Crop each photo before it is added to the gallery.")
                    return redirect("photo_batch_crop", batch_id=batch.pk)
                messages.success(request, f"Animal profile {obj.animal_id} saved.")
                return redirect("animal_profile", pk=obj.pk)
            except ValidationError as exc:
                form.add_error("photos", " ".join(exc.messages))
    else: form = AnimalForm(instance=animal, user=request.user)
    selected_primary_id = request.POST.get("primary_photo", "") if request.method == "POST" else str(animal.primary_photo.pk) if animal and animal.primary_photo else ""
    resumable = PhotoUploadBatch.objects.filter(user=request.user, animal=animal, workflow=PhotoUploadBatch.Workflow.STAFF, status__in=(PhotoUploadBatch.Status.PENDING, PhotoUploadBatch.Status.FAILED)).first() if animal else None
    return render(request, "animal_form.html", {"form": form, "animal": animal, "selected_primary_id": selected_primary_id, "resumable_batch": resumable})

@roles("Administrator", "Employee")
def animal_euthanize(request, pk):
    get_object_or_404(Animal, pk=pk)
    return redirect("animal_edit", pk=pk)


def _remove_orphan_files(files):
    from django.core.files.storage import default_storage
    for name in files:
        if AnimalPhoto.objects.filter(Q(image=name) | Q(original_image=name)).exists(): continue
        if SubmissionPhoto.objects.filter(Q(image=name) | Q(original_image=name)).exists(): continue
        if PendingPhoto.objects.filter(original=name).exists(): continue
        try: default_storage.delete(name)
        except OSError:
            logging.getLogger(__name__).exception('Unable to remove an unreferenced image file after animal deletion.')


@roles('Administrator')
def animal_delete(request, pk):
    animal = get_object_or_404(Animal, pk=pk)
    form = AnimalDeleteForm(request.POST or None, user=request.user, animal=animal)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            animal = Animal.objects.select_for_update().get(pk=pk)
            files = set()
            for model, query in ((AnimalPhoto, {'animal':animal}), (SubmissionPhoto, {'submission__animal':animal})):
                for photo in model.objects.filter(**query):
                    files.update(field.name for field in (photo.image, photo.original_image) if field)
            files.update(PendingPhoto.objects.filter(batch__animal=animal).values_list('original', flat=True))
            animal.delete()
            transaction.on_commit(lambda: _remove_orphan_files(files))
        messages.success(request, 'Animal record permanently deleted.')
        return redirect('animals')
    return render(request, 'animal_delete.html', {'animal':animal, 'form':form})


@roles('Administrator', 'Employee')
def hour_delete(request, pk):
    entry = get_object_or_404(VolunteerHour.objects.select_related('user'), pk=pk, user__role='Volunteer')
    if request.method == 'POST' and request.POST.get('confirm') == 'on':
        with transaction.atomic():
            user = get_object_or_404(User.objects.select_for_update(), pk=entry.user_id, role='Volunteer')
            get_object_or_404(VolunteerHour, pk=pk, user=user).delete()
        messages.success(request, 'Activity deleted. The manual adjustment was preserved.')
        return redirect(f"{reverse('volunteer_hours')}?user_id={user.pk}")
    return render(request, 'hour_delete.html', {'entry':entry, 'needs_confirmation':request.method=='POST'})


@roles("Volunteer")
def submit_update(request, pk):
    animal = get_object_or_404(Animal.objects.prefetch_related("photos"), pk=pk, is_archived=False)
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            uploads = request.FILES.getlist("photos")
            if uploads:
                try:
                    batch = create_photo_batch(
                        user=request.user, animal=animal, workflow=PhotoUploadBatch.Workflow.VOLUNTEER,
                        uploads=uploads,
                        form_data={key: form.cleaned_data.get(key, "") for key in ("observations", "temperament", "good_with", "notes")},
                    )
                    messages.success(request, "Upload complete. Crop each photo before submitting your update.")
                    return redirect("photo_batch_crop", batch_id=batch.pk)
                except ValidationError as exc:
                    form.add_error("photos", " ".join(exc.messages))
            else:
                submission = form.save(commit=False); submission.animal = animal; submission.user = request.user; submission.save()
                messages.success(request, "Your update was submitted for staff review."); return redirect("submissions")
    else: form = SubmissionForm()
    resumable = PhotoUploadBatch.objects.filter(user=request.user, animal=animal, workflow=PhotoUploadBatch.Workflow.VOLUNTEER, status__in=(PhotoUploadBatch.Status.PENDING, PhotoUploadBatch.Status.FAILED)).first()
    return render(request, "submit.html", {"animal": animal, "form": form, "resumable_batch": resumable})


@login_required
def photo_batch_crop(request, batch_id):
    batch = get_object_or_404(PhotoUploadBatch.objects.select_related("animal", "user").prefetch_related("photos"), pk=batch_id, user=request.user)
    if request.method == "POST":
        if timezone.now() >= batch.expires_at:
            messages.error(request, "This photo crop session has expired.")
        else:
            try:
                payload = parse_crop_payload(request.POST, list(batch.photos.all()))
                result_kind, result_id = finalize_photo_batch(batch.pk, request.user, payload)
                messages.success(request, "All photo crops were saved.")
                return redirect("animal_profile", pk=result_id) if result_kind == "animal" else redirect("submissions")
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                batch.refresh_from_db()
    return render(request, "photo_batch_crop.html", {
        "batch": batch,
        "server_now": timezone.now().isoformat(),
        "landscape_ratio": max(settings.PHOTO_WEB_SIZE) / min(settings.PHOTO_WEB_SIZE),
    })


@login_required
def photo_batch_preview(request, batch_id, photo_id):
    batch = get_object_or_404(PhotoUploadBatch, pk=batch_id, user=request.user)
    photo = get_object_or_404(batch.photos, pk=photo_id)
    photo.original.open("rb")
    try: raw = photo.original.read()
    finally: photo.original.close()
    return HttpResponse(branding_preview_bytes(raw), content_type="image/jpeg")


@require_POST
@login_required
def photo_batch_cancel(request, batch_id):
    batch = get_object_or_404(PhotoUploadBatch, pk=batch_id, user=request.user)
    animal_id = batch.animal_id
    workflow = batch.workflow
    cancel_photo_batch(batch)
    messages.success(request, "The unfinished photo upload was discarded.")
    return redirect("animal_edit", pk=animal_id) if workflow == PhotoUploadBatch.Workflow.STAFF else redirect("submit_update", pk=animal_id)

@roles("Administrator", "Employee", "Volunteer")
def submissions(request):
    status = request.GET.get("status", "Pending")
    if status not in {"Pending", "Approved", "Rejected"}:
        status = "Pending"
    base = Submission.objects.all()
    volunteer_view = request.user.role == "Volunteer" and not request.user.is_superuser
    if volunteer_view:
        base = base.filter(user=request.user)
    data = base.filter(status=status).select_related("animal", "user", "reviewed_by").prefetch_related("photos", "animal__photos")
    counts = {x: base.filter(status=x).count() for x in ("Pending", "Approved", "Rejected")}
    return render(request, "submissions.html", {
        "submissions": data,
        "status": status,
        "counts": counts,
        "volunteer_view": volunteer_view,
    })

@require_POST
@roles("Administrator", "Employee")
def review_submission(request, pk, action):
    with transaction.atomic():
        submission = get_object_or_404(Submission.objects.select_for_update().prefetch_related("photos"), pk=pk, status="Pending")
        animal = Animal.objects.select_for_update().get(pk=submission.animal_id)
        if action == "approve":
            submitted_photos = submission.photos.order_by("pk")
            selected_ids = {int(x) for x in request.POST.getlist("approve_photo") if x.isdigit()}
            selected_photos = list(submitted_photos.filter(pk__in=selected_ids))
            remove_ids = {int(x) for x in request.POST.getlist("replace_photo") if x.isdigit()}
            official_photos = animal.photos.order_by("position", "id")
            valid_remove_ids = set(official_photos.filter(pk__in=remove_ids).values_list("pk", flat=True))
            remaining = official_photos.exclude(pk__in=valid_remove_ids).count()
            if remaining + len(selected_photos) > 5:
                messages.error(request, "Select fewer submitted photos or enough official photos to keep the gallery at five or fewer.")
                return redirect(f"{reverse('submissions')}?status=Pending")
            for photo in official_photos.filter(pk__in=valid_remove_ids):
                delete_photo_files(photo)
                photo.delete()
            additions = [submission.observations]
            if submission.temperament or submission.good_with: additions.append(f"Observed: {submission.temperament}; Good with: {submission.good_with}")
            animal.behavior_notes = "\n".join(x for x in [animal.behavior_notes, *additions] if x)
            animal.general_notes = "\n".join(x for x in [animal.general_notes, submission.notes] if x)
            animal.save(update_fields=["behavior_notes", "general_notes", "updated_at"])
            start = animal.photos.count()
            for offset, photo in enumerate(selected_photos):
                AnimalPhoto.objects.create(animal=animal, image=photo.image.name, original_image=photo.original_image.name, original_filename=photo.original_filename, position=start + offset)
            submission.status = "Approved"
        elif action == "reject":
            submission.status = "Rejected"; submission.rejection_reason = request.POST.get("reason", "").strip()
        else:
            from django.http import Http404
            raise Http404
        submission.reviewed_by = request.user; submission.reviewed_at = timezone.now(); submission.save()
    messages.success(request, f"Submission {submission.status.lower()}."); return redirect(f"{reverse('submissions')}?status={submission.status}")

@roles("Administrator", "Employee")
@transaction.atomic
def volunteer_hours(request):
    volunteers = User.objects.filter(role="Volunteer").order_by("full_name")
    selected_id = request.POST.get("user_id") or request.GET.get("user_id") or volunteers.values_list("pk", flat=True).first()
    selected = get_object_or_404(volunteers, pk=selected_id) if selected_id else None
    if request.method == "POST" and selected:
        selected = get_object_or_404(User.objects.select_for_update(), pk=selected.pk, role='Volunteer')
        entry = get_object_or_404(VolunteerHour, pk=request.POST.get("hour_id"), user=selected) if request.POST.get("hour_id") else VolunteerHour(user=selected)
        form = VolunteerHourForm(request.POST, instance=entry)
        if form.is_valid(): form.save(); messages.success(request, "Volunteer hours saved."); return redirect(f"{reverse('volunteer_hours')}?user_id={selected.pk}")
    else:
        entry = get_object_or_404(VolunteerHour, pk=request.GET.get('edit'), user=selected) if selected and request.GET.get('edit') else None
        form = VolunteerHourForm(instance=entry)
    return render(request, "hours.html", {"volunteers": volunteers, "selected": selected, "entries": selected.hour_entries.all() if selected else [], "form": form, "editing_entry": entry if selected else None})

@roles("Administrator")
@transaction.atomic
def manage_users(request):
    selected_id = request.POST.get('id') if request.method == 'POST' else request.GET.get('edit')
    instance = get_object_or_404(User.objects.select_for_update(), pk=selected_id) if selected_id else None
    form = UserManageForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False); user.username = user.email.lower()
        if form.cleaned_data.get("password"): user.set_password(form.cleaned_data["password"])
        user.save()
        if user.role == "Volunteer" and form.cleaned_data.get("total_volunteer_hours") is not None:
            recorded = user.hour_entries.aggregate(total=Sum("hours"))["total"] or 0
            user.manual_adjustment = form.cleaned_data["total_volunteer_hours"] - recorded; user.save(update_fields=["manual_adjustment"])
        messages.success(request, "User account saved."); return redirect("users")
    return render(request, "users.html", {"users": User.objects.all().order_by("full_name"), "form": form, "editing_user": instance})

@require_POST
@roles("Administrator")
def user_toggle(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user: messages.error(request, "You cannot deactivate your own account.")
    else: target.is_active = not target.is_active; target.save(update_fields=["is_active"]); messages.success(request, "Account status updated.")
    return redirect("users")

@roles("Administrator")
def organization(request):
    org = Organization.current(); form = OrganizationForm(request.POST or None, request.FILES or None, instance=org)
    context = {
        "form": form,
        "branding_banner_ratio": settings.BRANDING_BANNER_SIZE[0] / settings.BRANDING_BANNER_SIZE[1],
        "branding_max_size": settings.BRANDING_MAX_SIZE_MB,
        "branding_timeout_seconds": max(1, settings.PHOTO_BATCH_TTL_MINUTES) * 60,
    }
    if request.method == "POST" and form.is_valid():
        deadline = request.session.get("branding_image_deadline")
        image_changes = any(form.cleaned_data.get(f"{kind}_upload") or (form.cleaned_data.get(f"{kind}_crop") or {}) != (getattr(org, f"{kind}_crop") or {}) for kind in ("logo", "banner", "favicon"))
        if image_changes and deadline and timezone.now().timestamp() >= deadline:
            form.add_error(None, "The image editing session expired. Reload and select your images again.")
            return render(request, "organization.html", context)
        org = form.save()
        try:
            for kind in ("logo", "banner", "favicon"):
                upload = form.cleaned_data.get(f"{kind}_upload")
                crop = form.cleaned_data.get(f"{kind}_crop") or {}
                original = getattr(org, f"{kind}_original")
                if form.cleaned_data.get(f"{kind}_remove"):
                    delete_branding_asset(org, kind)
                elif upload or (original and crop != (getattr(org, f"{kind}_crop") or {})):
                    process_branding_asset(org, kind, upload=upload, crop=crop)
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, "organization.html", context)
        favicon_urls(org, force=True)
        messages.success(request, "Organization settings saved.")
        request.session.pop("branding_image_deadline", None)
        return redirect("organization")
    return render(request, "organization.html", context)


@roles("Administrator")
def branding_preview(request, kind):
    if kind not in {"logo", "banner", "favicon"}:
        raise Http404
    if request.method == "POST":
        if request.POST.get("action") == "start":
            deadline = request.session.get("branding_image_deadline")
            if not deadline or timezone.now().timestamp() >= deadline:
                deadline = timezone.now().timestamp() + max(1, settings.PHOTO_BATCH_TTL_MINUTES) * 60
                request.session["branding_image_deadline"] = deadline
            return JsonResponse({"remaining_seconds": max(0, deadline - timezone.now().timestamp())})
        if request.POST.get("action") == "discard":
            request.session.pop("branding_image_deadline", None)
            return JsonResponse({"discarded": True})
        upload = request.FILES.get("image")
        if not upload:
            return JsonResponse({"error": "Choose an image to preview."}, status=400)
        try:
            validate_branding_upload(upload, kind)
            upload.seek(0)
            raw = upload.read()
        except ValidationError as exc:
            return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    elif request.method == "GET":
        org = Organization.current()
        source = getattr(org, f"{kind}_original") or getattr(org, kind)
        if not source:
            raise Http404
        source.open("rb")
        try:
            raw = source.read()
        finally:
            source.close()
    else:
        return JsonResponse({"error": "Method not allowed."}, status=405)
    try:
        return HttpResponse(branding_preview_bytes(raw), content_type="image/jpeg")
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)

@roles("Administrator")
def system_information(request):
    refresh_interval = _system_refresh_interval(request.GET.get("refresh"))
    return render(request, "system_information.html", {
        "system": system_snapshot(),
        "refresh_interval": refresh_interval,
    })


def _system_refresh_interval(value):
    try:
        interval = int(value or 5)
    except (TypeError, ValueError):
        interval = 5
    return interval if interval in {1, 2, 5} else 5


def _system_snapshot_html():
    return render_to_string("_system_snapshot.html", {"system": system_snapshot()})


async def system_information_stream(request):
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed."}, status=405)
    user = await request.auser()
    if not user.is_authenticated:
        return JsonResponse({"detail": "Authentication required."}, status=401)
    if not user.is_superuser and user.role != "Administrator":
        raise PermissionDenied

    interval = _system_refresh_interval(request.GET.get("refresh"))

    async def events():
        while True:
            html = await sync_to_async(_system_snapshot_html, thread_sensitive=True)()
            payload = json.dumps({"html": html}, cls=DjangoJSONEncoder)
            yield f"event: snapshot\ndata: {payload}\n\n"
            await asyncio.sleep(interval)

    response = StreamingHttpResponse(events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response

@login_required
def account(request):
    form = AccountForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.username = user.email.lower()
        if form.cleaned_data.get("new_password"): user.set_password(form.cleaned_data["new_password"])
        user.save(); messages.success(request, "Account settings saved.")
        if form.cleaned_data.get("new_password"): login(request, user)
        return redirect("account")
    return render(request, "account.html", {"form": form})

