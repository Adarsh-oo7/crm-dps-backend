from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_userotp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('superadmin', 'Super Admin'),
                    ('admin', 'Admin'),
                    ('manager', 'Manager'),
                    ('hr', 'HR'),
                    ('developer', 'Developer'),
                    ('designer', 'Designer'),
                    ('marketer', 'Marketer'),
                    ('support', 'Support'),
                    ('finance', 'Finance'),
                ],
                default='developer',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='fcm_token',
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
