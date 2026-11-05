from django.db import models

from account.models import Branch


class BillPrintConfig(models.Model):
    bill_title = models.CharField(
        max_length=100, null=True, blank=True, default="Call Eat Mandu"
    )
    bill_footer = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )
    branch = models.OneToOneField(
        Branch,
        on_delete=models.CASCADE,
        related_name="bill_print_config",
    )

    class Meta:
        db_table = "stats_billprintconfig"

    def __str__(self):
        return f"{self.bill_title} - {self.branch.name}"
