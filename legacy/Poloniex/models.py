from django.db import models
from datetime import datetime


class AvgPrice(models.Model):
    pkey = models.CharField(max_length=100)
    coin_name = models.CharField(max_length=10)
    last_update = models.DateTimeField(default=datetime(1900, 1, 1))
    avg_price = models.DecimalField(max_digits=17, decimal_places=8, default=0.00000000)
    coin_num = models.DecimalField(max_digits=17, decimal_places=8, default=0.00000000)
    is_margin = models.BooleanField(default=False)

    class meta:
        unique_together = (("pkey", "coin_name"),)