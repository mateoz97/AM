# Generated by Django 5.2 on 2025-04-16 04:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0003_businessinvitation'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessjoinrequest',
            name='message',
            field=models.TextField(blank=True, null=True, verbose_name='Mensaje'),
        ),
    ]
