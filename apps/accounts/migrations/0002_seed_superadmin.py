from django.db import migrations
from django.contrib.auth.hashers import make_password

def seed_superadmin(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    if not User.objects.filter(email='admin@digitalprod.com').exists():
        User.objects.create(
            email='admin@digitalprod.com',
            full_name='System Administrator',
            role='superadmin',
            is_staff=True,
            is_superuser=True,
            is_active=True,
            password=make_password('adminpass'),
        )

def remove_superadmin(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(email='admin@digitalprod.com').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_superadmin, remove_superadmin),
    ]
