from django.contrib.auth.models import AbstractUser
from django.db import models
from django.template.defaultfilters import slugify

from common.models import BaseModel

# Create your models here.


class User(AbstractUser):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("reception", "Reception"),
        ("rider", "Rider"),
        ("kitchen", "Kitchen"),
        ("customer", "Customer"),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="customer")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    class Meta:
        db_table = "account_user"
        verbose_name = "user"
        verbose_name_plural = "users"


class Branch(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    address = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    phone = models.CharField(
        max_length=15,
    )
    image = models.FileField(upload_to="branch_images/", blank=True, null=True)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = "account_branch"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)
