from datetime import date
from decimal import Decimal

from django.db import connection, DatabaseError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ScopeUpgradeTests(TransactionTestCase):
    def test_upgrade_removes_logs_and_preserves_records_and_permanent_confirmation(self):
        executor = MigrationExecutor(connection)
        old_target = [('shelter', '0013_auditevent')]
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(old_target)
            old = executor.loader.project_state(old_target).apps
            user = old.get_model('shelter', 'User').objects.create(
                username='upgrade', email='upgrade@test.com', role='Volunteer', manual_adjustment=Decimal('-3'),
            )
            animal = old.get_model('shelter', 'Animal').objects.create(
                animal_id='UPGRADE', name='Preserved', age=2, intake_date=date.today(), placed_date=date.today(),
                status='Deceased', deceased_at=timezone.now(), deceased_by_id=user.pk, deceased_reason='Natural causes',
            )
            old.get_model('shelter', 'VolunteerHour').objects.create(
                user=user, activity_date=date.today(), hours=5, activity_type='Walking',
            )
            old.get_model('shelter', 'AnimalHistory').objects.create(animal=animal, user=user, summary='Old history')
            old.get_model('shelter', 'AuditEvent').objects.create(action='old.test', category='routine')
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            from shelter.models import Animal, User
            preserved = Animal.objects.get(pk=animal.pk)
            self.assertEqual(preserved.deceased_reason, 'Natural causes')
            self.assertEqual(preserved.deceased_by_id, user.pk)
            self.assertEqual(preserved.deceased_at, animal.deceased_at)
            self.assertEqual(preserved.heartworm_status, '')  # No invented medical result.
            self.assertEqual(User.objects.get(pk=user.pk).total_hours, Decimal('2'))
            for table in ('shelter_auditevent', 'shelter_animalhistory'):
                self.assertNotIn(table, connection.introspection.table_names())
            with self.assertRaises(DatabaseError), transaction.atomic():
                Animal.objects.filter(pk=animal.pk).update(status='Available')
        finally:
            MigrationExecutor(connection).migrate(latest)
