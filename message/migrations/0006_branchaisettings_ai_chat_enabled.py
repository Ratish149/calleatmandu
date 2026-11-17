from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("message", "0005_branchaisettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="branchaisettings",
            name="ai_chat_enabled",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
