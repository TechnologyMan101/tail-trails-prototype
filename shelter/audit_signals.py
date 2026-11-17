from django.db.models.signals import pre_save, post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import Animal, AnimalPhoto, Submission, SubmissionPhoto, User, VolunteerHour, Organization, PhotoUploadBatch
from .audit import record

TRACKED = (Animal, AnimalPhoto, Submission, SubmissionPhoto, User, VolunteerHour, Organization, PhotoUploadBatch)
SAFE = {'name', 'species', 'breed', 'age', 'age_unit', 'sex', 'status', 'is_archived', 'held_at', 'color', 'coat_pattern', 'coat_length', 'weight', 'height', 'spay_status', 'position', 'role', 'is_active', 'manual_adjustment', 'hours', 'activity_date', 'activity_type', 'primary_color', 'secondary_color'}
IGNORED = {'id', 'created_at', 'updated_at', 'last_login', 'date_joined', 'join_date'}


def snapshot(instance):
    return {f.name: str(getattr(instance, f.attname)) if getattr(instance, f.attname) is not None else None for f in instance._meta.fields if f.name not in IGNORED}


@receiver(pre_save)
def before_save(sender, instance, raw=False, **kwargs):
    if raw or sender not in TRACKED: return
    previous = sender.objects.filter(pk=instance.pk).first() if instance.pk else None
    instance._audit_before = snapshot(previous) if previous else {}


def emit(instance, operation, before, after):
    fields = set(before) | set(after)
    changes = {name: ({'before': before.get(name), 'after': after.get(name)} if name in SAFE else {'redacted': True}) for name in fields if before.get(name) != after.get(name)}
    if not changes and operation == 'updated': return
    animal_id = instance.pk if isinstance(instance, Animal) else getattr(instance, 'animal_id', None)
    if isinstance(instance, SubmissionPhoto):
        animal_id = instance.submission.animal_id
    category = 'operational' if isinstance(instance, PhotoUploadBatch) else 'routine'
    if operation == 'deleted' and isinstance(instance, Animal): category = 'critical'
    if isinstance(instance, User) and any(key in changes for key in ('role', 'is_active', 'password', 'manual_adjustment')): category = 'critical'
    if isinstance(instance, Animal) and ((operation != 'created' and any(key in changes for key in ('is_archived', 'deceased_at', 'deceased_by', 'deceased_reason'))) or instance.status == 'Deceased'): category = 'critical'
    record(category, f'{instance._meta.model_name}.{operation}', target=instance, changes=changes, animal_id=animal_id)


@receiver(post_save)
def after_save(sender, instance, created, raw=False, **kwargs):
    if not raw and sender in TRACKED:
        emit(instance, 'created' if created else 'updated', getattr(instance, '_audit_before', {}), snapshot(instance))


@receiver(post_delete)
def after_delete(sender, instance, **kwargs):
    if sender in TRACKED: emit(instance, 'deleted', snapshot(instance), {})


@receiver(user_logged_in)
def signed_in(sender, request, user, **kwargs): record('access', 'account.sign_in', actor=user)

@receiver(user_logged_out)
def signed_out(sender, request, user, **kwargs): record('access', 'account.sign_out', actor=user)

@receiver(user_login_failed)
def sign_in_failed(sender, credentials, request=None, **kwargs): record('access', 'account.sign_in', outcome='failure')
