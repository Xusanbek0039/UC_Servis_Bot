from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.settings.models import BotSettings
from apps.products.services import ProductService


class Command(BaseCommand):
    help = "Initialize default data: superuser, bot settings, and initial UC packages"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default="admin", help="Admin username")
        parser.add_argument("--password", type=str, default="admin123", help="Admin password")
        parser.add_argument("--email", type=str, default="admin@example.com", help="Admin email")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        password = options["password"]
        email = options["email"]

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' successfully created! (Password: {password})"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists."))

        # Initialize BotSettings
        settings = BotSettings.load()
        self.stdout.write(self.style.SUCCESS("BotSettings initialized."))

        # Seed initial products
        ProductService.seed_default_products()
        self.stdout.write(self.style.SUCCESS("Default UC Packages seeded."))
