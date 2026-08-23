from django.db import models
from django.utils.text import slugify

from common.models import BaseModel


# Create your models here.
class Blog(BaseModel):
    title = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(unique=True, blank=True, null=True, db_index=True)
    image = models.FileField(upload_to="blog/images/", null=True, blank=True)
    time_to_read = models.IntegerField(null=True, blank=True, help_text="in minutes")
    short_description = models.TextField()
    content = models.TextField()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
