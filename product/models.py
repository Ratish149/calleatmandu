from django.db import models
from django.template.defaultfilters import slugify

from common.models import BaseModel

# Create your models here.


class Category(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Subcategory(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.FloatField()
    thumbnail_image = models.FileField(upload_to="product/thumbnail/")
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, null=True, blank=True
    )
    sub_category = models.ForeignKey(
        "Subcategory", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductExtra(BaseModel):
    """
    An optional add-on for a product.
    E.g. "Extra Cheese", "Crispy Fries", "Garlic Sauce"
    """

    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="extras"
    )
    name = models.CharField(max_length=100)           # e.g. "Extra Cheese"
    additional_price = models.FloatField(default=0.0) # surcharge on top of base price

    class Meta:
        ordering = ["additional_price", "name"]

    def __str__(self):
        return f"{self.product.name} › {self.name} (+{self.additional_price})"


class ProductImage(BaseModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.FileField(upload_to="product/images/")

    def __str__(self):
        return f"{self.product.name} Image"
