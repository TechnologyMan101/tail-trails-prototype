from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("shelter", "0003_original_filenames")]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="favicon",
            field=models.ImageField(
                blank=True,
                help_text="Optional square PNG or JPG. When omitted, the logo or default heart mark is used.",
                upload_to="branding/favicon-sources/",
                validators=[django.core.validators.FileExtensionValidator(["png", "jpg", "jpeg"])],
            ),
        ),
    ]
