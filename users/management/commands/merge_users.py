from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rentals.models import RentalOrder

User = get_user_model()

class Command(BaseCommand):
    help = "Merge duplicate Google and OTP users based on email"

    def handle(self, *args, **kwargs):
        duplicates = {}
        for user in User.objects.all():
            email = user.email.lower()
            if email in duplicates:
                duplicates[email].append(user)
            else:
                duplicates[email] = [user]

        for email, users in duplicates.items():
            if len(users) > 1:
                self.stdout.write(self.style.WARNING(f"Found duplicates for {email}: {[u.id for u in users]}"))

                # Pick the first as the "main" user
                main_user = users[0]

                for dup in users[1:]:
                    # Reassign rental orders to main user
                    orders = RentalOrder.objects.filter(user=dup)
                    for order in orders:
                        order.user = main_user
                        order.save()

                    # Merge auth_provider if needed
                    if dup.auth_provider == "google":
                        main_user.auth_provider = "google"
                        main_user.save()

                    # Delete duplicate user
                    dup.delete()

                self.stdout.write(self.style.SUCCESS(f"Merged users for {email} into {main_user.id}"))
