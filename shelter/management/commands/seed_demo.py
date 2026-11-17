from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from shelter.models import (
    Animal,
    AnimalPhoto,
    Organization,
    Submission,
    User,
    VolunteerHour,
)


class Command(BaseCommand):
    help = "Populate an unused prototype database with current-format demonstration records."

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.exists() or Animal.objects.exists():
            self.stdout.write(
                "Demo seeding skipped: database already contains accounts or animals."
            )
            return
        Organization.current()
        for email, name, role, phone in [
            ("admin@tailtrails.test", "Alex Morgan", "Administrator", "(619) 555-0100"),
            ("employee@tailtrails.test", "Jordan Lee", "Employee", "(619) 555-0101"),
            ("volunteer@tailtrails.test", "Sam Rivera", "Volunteer", "(619) 555-0102"),
        ]:
            User.objects.create_user(
                username=email,
                email=email,
                full_name=name,
                role=role,
                phone=phone,
                password="Trail123!",
            )
        records = [
            {
                "animal_id": "TT-1001",
                "name": "Milo",
                "species": "Dog",
                "breed": "Terrier Mix",
                "age": 3,
                "age_unit": "Years",
                "sex": "Male",
                "color": "Tan",
                "weight": Decimal("10.886"),
                "spay_status": "Spayed/Neutered",
                "status": "Available",
                "held_at": "Kennel",
                "kennel_location": "North Campus",
                "kennel_id": "A-12",
                "intake_date": date(2026, 9, 8),
                "placed_date": date(2026, 9, 8),
                "intake_type": "Stray",
                "intake_location": "Downtown",
                "public_description": "Friendly, curious, and always ready for a walk.",
                "temperament": "Friendly",
                "good_with": "Dogs, Children",
                "house_trained": "Yes",
                "leash_skills": "Yes",
                "vaccination_status": "Up to Date",
                "heartworm_status": "Negative",
                "medical_conditions": "No known conditions",
                "behavior_notes": "Eager to greet visitors; settles quickly after exercise.",
                "general_notes": "Completed intake exam.",
                "fleas_status": "Negative",
            },
            {
                "animal_id": "TT-1002",
                "name": "Luna",
                "species": "Cat",
                "breed": "Domestic Shorthair",
                "age": 2,
                "age_unit": "Years",
                "sex": "Female",
                "color": "Blue/Gray",
                "weight": Decimal("4.082"),
                "spay_status": "Spayed/Neutered",
                "status": "Available",
                "held_at": "Foster Home",
                "foster_caregiver": "Taylor Foster",
                "intake_date": date(2026, 9, 17),
                "placed_date": date(2026, 9, 17),
                "intake_type": "Owner Surrender",
                "public_description": "A calm, affectionate companion who loves sunny windows.",
                "temperament": "Shy, Friendly",
                "good_with": "Cats",
                "vaccination_status": "Up to Date",
                "heartworm_status": "Negative",
                "behavior_notes": "Warms up gently with quiet attention.",
                "general_notes": "Foster caregiver reports excellent litter habits.",
                "leash_skills": "",
                "fleas_status": "Negative",
                "foster_phone": "(619) 555-0123",
                "foster_address": "123 Example Lane, San Diego, CA (demo)",
            },
            {
                "animal_id": "TT-1003",
                "name": "Hazel",
                "species": "Rabbit",
                "breed": "Mini Lop",
                "age": 14,
                "age_unit": "Months",
                "sex": "Female",
                "color": "Brown",
                "weight": Decimal("2.268"),
                "spay_status": "Unknown",
                "status": "Pending Adoption",
                "held_at": "Kennel",
                "kennel_location": "Small Animal Wing",
                "kennel_id": "R-04",
                "intake_date": date(2026, 10, 3),
                "placed_date": date(2026, 10, 3),
                "intake_type": "Transfer",
                "temperament": "Shy",
                "good_with": "Children",
                "behavior_notes": "Enjoys leafy greens and cardboard tunnels.",
                "general_notes": "Transfer paperwork verified.",
                "vaccination_status": "Unvaccinated",
                "leash_skills": "",
                "heartworm_status": "Unknown",
                "fleas_status": "Negative",
            },
            {
                "animal_id": "TT-1004",
                "name": "Poppy",
                "species": "Dog",
                "breed": "Australian Cattle Dog Mix",
                "age": 5,
                "age_unit": "Years",
                "sex": "Female",
                "color": "Brown",
                "weight": Decimal("21.772"),
                "spay_status": "Spayed/Neutered",
                "status": "Not Available",
                "held_at": "Foster Home",
                "foster_caregiver": "Morgan Foster",
                "intake_date": date(2026, 8, 21),
                "placed_date": date(2026, 8, 21),
                "intake_type": "Stray",
                "intake_location": "East County",
                "temperament": "Anxious",
                "good_with": "Dogs",
                "house_trained": "Yes",
                "leash_skills": "No",
                "vaccination_status": "Up to Date",
                "heartworm_status": "Negative",
                "medical_conditions": "Recovering from minor surgery",
                "medications": "Carprofen",
                "behavior_notes": "Responds well to calm introductions.",
                "general_notes": "Medical hold through next evaluation.",
                "fleas_status": "Negative",
                "foster_phone": "(619) 555-0123",
                "foster_address": "123 Example Lane, San Diego, CA (demo)",
                "coat_pattern": "Brindle",
            },
        ]
        photo_sets = {
            "TT-1001": [
                "https://images.unsplash.com/photo-1558788353-f76d92427f16?auto=format&fit=crop&w=1200&q=85",
                "https://images.unsplash.com/photo-1518717758536-85ae29035b6d?auto=format&fit=crop&w=1200&q=85",
                "https://images.unsplash.com/photo-1561037404-61cd46aa615b?auto=format&fit=crop&w=1200&q=85",
            ],
            "TT-1002": [
                "https://images.unsplash.com/photo-1573865526739-10659fec78a5?auto=format&fit=crop&w=1200&q=85",
                "https://images.unsplash.com/photo-1495360010541-f48722b34f7d?auto=format&fit=crop&w=1200&q=85",
            ],
            "TT-1003": [
                "https://images.unsplash.com/photo-1585110396000-c9ffd4e4b308?auto=format&fit=crop&w=1200&q=85"
            ],
            "TT-1004": [
                "https://images.unsplash.com/photo-1552053831-71594a27632d?auto=format&fit=crop&w=1200&q=85"
            ],
        }
        for values in records:
            animal = Animal(**values)
            animal.full_clean()
            animal.save()
            for position, url in enumerate(photo_sets[animal.animal_id]):
                AnimalPhoto.objects.create(
                    animal=animal, external_url=url, position=position
                )
        volunteer = User.objects.get(username="volunteer@tailtrails.test")
        VolunteerHour.objects.create(
            user=volunteer,
            activity_date=date(2026, 10, 15),
            hours=Decimal("3.5"),
            activity_type="Dog Walking",
            notes="Morning enrichment walk",
        )
        Submission.objects.create(
            animal=Animal.objects.get(animal_id="TT-1001"),
            user=volunteer,
            observations="Milo sat calmly for brushing and checked in often.",
            temperament="Friendly",
            good_with="Dogs",
            notes="May photograph well outdoors",
        )
        self.stdout.write(self.style.SUCCESS("Demo data ready"))
