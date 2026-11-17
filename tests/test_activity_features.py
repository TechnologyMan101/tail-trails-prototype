from datetime import date
from decimal import Decimal
import tempfile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.base import ContentFile
from shelter.models import User, Animal, AnimalPhoto, VolunteerHour


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ActivityFeaturesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name, role in [('admin','Administrator'),('employee','Employee'),('volunteer','Volunteer')]:
            setattr(cls,name,User.objects.create_user(username=name,email=f'{name}@test.com',password='Trail123!',full_name=name,role=role))
        cls.animal=Animal.objects.create(animal_id='TT-OPERATIONS',name='Test animal',age=1,age_unit='Years',species='Dog',breed='Mix',intake_date=date.today(),placed_date=date.today(),status='Not Available')

    def user_data(self, **overrides):
        data={'id':self.volunteer.pk,'full_name':'volunteer','email':self.volunteer.email,'phone':'6195550100','role':'Volunteer','is_active':'on'}
        data.update(overrides);return data

    def activity(self, hours='5'):
        return VolunteerHour.objects.create(user=self.volunteer,activity_date=date.today(),hours=hours,activity_type='Walking')

    def test_total_replacement_and_activity_edit_delete_preserve_adjustment(self):
        first=self.activity('5');self.activity('3');self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('users'),self.user_data(total_volunteer_hours='20')).status_code,302)
        self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.manual_adjustment,Decimal('12'))
        self.assertEqual(self.volunteer.total_hours,Decimal('20'));self.assertEqual(self.volunteer.hour_entries.count(),2)
        self.assertEqual(self.client.post(reverse('volunteer_hours'),{'user_id':self.volunteer.pk,'hour_id':first.pk,'activity_date':date.today(),'hours':'7','activity_type':'Walking'}).status_code,302)
        self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.total_hours,Decimal('22'))
        self.client.post(reverse('hour_delete',args=[first.pk]),{'confirm':'on'})
        self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.total_hours,Decimal('15'));self.assertEqual(self.volunteer.manual_adjustment,Decimal('12'))
        self.client.post(reverse('volunteer_hours'),{'user_id':self.volunteer.pk,'activity_date':date.today(),'hours':'2','activity_type':'Feeding'})
        self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.total_hours,Decimal('17'));self.assertEqual(self.volunteer.manual_adjustment,Decimal('12'))

    def test_role_round_trip_hides_but_preserves_hours(self):
        self.activity();self.volunteer.manual_adjustment=Decimal('4');self.volunteer.save();self.client.force_login(self.admin)
        for role in ('Employee','Administrator'):
            self.client.post(reverse('users'),self.user_data(role=role,total_volunteer_hours='0'))
            self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.total_hours,Decimal('9'));self.assertEqual(self.volunteer.hour_entries.count(),1)
            self.assertEqual(self.client.get(reverse('volunteer_hours')+f'?user_id={self.volunteer.pk}').status_code,404)
            self.client.force_login(self.volunteer);self.assertNotContains(self.client.get(reverse('account')),'Total volunteer hours');self.client.force_login(self.admin)
        self.client.post(reverse('users'),self.user_data(role='Volunteer'))
        self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.total_hours,Decimal('9'))
        self.client.force_login(self.volunteer);self.assertContains(self.client.get(reverse('account')),'Total volunteer hours')

    def test_hour_delete_permissions_and_confirmation(self):
        entry=self.activity();url=reverse('hour_delete',args=[entry.pk]);self.client.force_login(self.volunteer)
        self.assertEqual(self.client.post(url,{'confirm':'on'}).status_code,403)
        self.client.force_login(self.employee);self.assertEqual(self.client.get(reverse('volunteer_hours')+f'?user_id={self.volunteer.pk}&edit={entry.pk}').status_code,200)
        self.client.post(url,{});self.assertTrue(VolunteerHour.objects.filter(pk=entry.pk).exists())
        self.assertEqual(self.client.post(url,{'confirm':'on'}).status_code,302)

    def test_animal_delete_requires_admin_checkbox_and_password(self):
        url=reverse('animal_delete',args=[self.animal.pk]);self.client.force_login(self.employee)
        self.assertEqual(self.client.post(url,{'confirm':'on','password':'Trail123!'}).status_code,403)
        self.assertNotContains(self.client.get(reverse('animal_edit',args=[self.animal.pk])),'Delete animal record')
        self.client.force_login(self.admin);self.assertContains(self.client.get(reverse('animal_edit',args=[self.animal.pk])),'Delete animal record')
        self.assertEqual(self.client.get(url).status_code,200)
        for data in ({'confirm':'on','password':'wrong'},{'password':'Trail123!'}):
            self.assertEqual(self.client.post(url,data).status_code,200);self.assertTrue(Animal.objects.filter(pk=self.animal.pk).exists())
        self.assertEqual(self.client.post(url,{'confirm':'on','password':'Trail123!'}).status_code,302)
        self.assertFalse(Animal.objects.filter(pk=self.animal.pk).exists())

    def test_deleted_photo_files_are_removed_after_commit(self):
        photo=AnimalPhoto(animal=self.animal);photo.image.save('delete.jpg',ContentFile(b'test'),save=True)
        storage,name=photo.image.storage,photo.image.name;self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('animal_delete',args=[self.animal.pk]),{'confirm':'on','password':'Trail123!'})
            self.assertTrue(storage.exists(name))
        self.assertFalse(storage.exists(name))

    def test_delete_does_not_remove_a_file_shared_with_another_animal(self):
        photo=AnimalPhoto(animal=self.animal);photo.image.save('shared.jpg',ContentFile(b'test'),save=True)
        other=Animal.objects.create(animal_id='TT-OTHER',name='Other',age=1,intake_date=date.today(),placed_date=date.today(),status='Not Available')
        AnimalPhoto.objects.create(animal=other,image=photo.image.name)
        storage,name=photo.image.storage,photo.image.name
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True): self.client.post(reverse('animal_delete',args=[self.animal.pk]),{'confirm':'on','password':'Trail123!'})
        self.assertTrue(storage.exists(name))

    def test_negative_activity_hours_rejected_on_add_and_edit(self):
        first = self.activity('3')
        self.client.force_login(self.admin)
        for hour_id in ('', first.pk):
            for value in ('-1', '-0.01', '0'):
                response = self.client.post(reverse('volunteer_hours'), {'user_id':self.volunteer.pk, 'hour_id':hour_id, 'activity_date':date.today(), 'hours':value, 'activity_type':'Walking'})
                self.assertEqual(response.status_code, 200)
                self.assertIn('hours', response.context['form'].errors)
        first.refresh_from_db()
        self.assertEqual(first.hours, Decimal('3'))
        self.assertEqual(self.volunteer.hour_entries.count(), 1)

    def test_total_replacement_rejects_negative_input_but_keeps_signed_adjustment(self):
        self.activity('5');self.client.force_login(self.admin)
        response = self.client.post(reverse('users'), self.user_data(total_volunteer_hours='-1'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_volunteer_hours', response.context['form'].errors)
        self.volunteer.refresh_from_db();self.assertEqual(self.volunteer.total_hours, Decimal('5'))
        self.assertEqual(self.client.post(reverse('users'),self.user_data(total_volunteer_hours='2')).status_code, 302)
        self.volunteer.refresh_from_db()
        self.assertEqual(self.volunteer.manual_adjustment, Decimal('-3'))
        self.assertEqual(self.volunteer.total_hours, Decimal('2'))
