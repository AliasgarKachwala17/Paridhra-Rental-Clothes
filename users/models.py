import random
from datetime import timedelta
from django.db import models
from django.utils import timezone

class OTPRequest(models.Model):
    email      = models.EmailField()
    code       = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "code"]),
        ]

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    @classmethod
    def create_otp(cls, email):
        code = f"{random.randint(0, 999999):06}"
        return cls.objects.create(email=email, code=code)