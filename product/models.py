from django.db import models
from django.template.defaultfilters import slugify

from common.models import BaseModel

# Create your models here.


class Category(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    image = models.FileField(upload_to="category/images/", null=True, blank=True)

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
    image = models.FileField(upload_to="subcategory/images/", null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


def product_thumbnail_upload_path(instance, filename):
    folder = instance.slug or (slugify(instance.name) if instance.name else "unnamed")
    return f"product/{folder}/thumbnail/{filename}"


def product_image_upload_path(instance, filename):
    product_name = instance.product.name if instance.product else "unnamed"
    folder = instance.product.slug or (
        slugify(product_name) if product_name else "unnamed"
    )
    return f"product/{folder}/images/{filename}"


class Product(BaseModel):
    class ProductType(models.TextChoices):
        VEG = "VEG", "Veg"
        NON_VEG = "NON_VEG", "Non-Veg"
        EGG = "EGG", "Egg"

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.FloatField()
    type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        db_index=True,
        null=True,
        blank=True,
    )
    thumbnail_image = models.FileField(upload_to=product_thumbnail_upload_path)
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, null=True, blank=True
    )
    sub_category = models.ForeignKey(
        "Subcategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_best_seller = models.BooleanField(default=False)
    prepare_time = models.CharField(
        max_length=10, null=True, blank=True, help_text="in minutes"
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
    name = models.CharField(max_length=100)  # e.g. "Extra Cheese"
    additional_price = models.FloatField(default=0.0)  # surcharge on top of base price

    class Meta:
        ordering = ["additional_price", "name"]

    def __str__(self):
        return f"{self.product.name} › {self.name} (+{self.additional_price})"


class ProductImage(BaseModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.FileField(upload_to=product_image_upload_path)

    def __str__(self):
        return f"{self.product.name} Image"
