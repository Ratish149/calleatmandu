from django.db import models

from common.models import BaseModel


# Create your models here.
class Faq(BaseModel):
    question = models.TextField()
    answer = models.TextField()

    def __str__(self):
        return self.question

    class Meta:
        verbose_name = "Faq"
        verbose_name_plural = "Faqs"
