from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shelter", "0002_animalphoto_original_image_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="animalphoto",
            name="original_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="submissionphoto",
            name="original_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
