from django.core.management.base import BaseCommand

from classifier.services.registry import registry


class Command(BaseCommand):
    help = "Load all 3 models once outside the dev server, to sanity-check for import/DLL conflicts."

    def handle(self, *args, **options):
        registry.load_all()
        for key, status in registry.status().items():
            if status["loaded"]:
                self.stdout.write(self.style.SUCCESS(f"{key}: loaded OK"))
            else:
                self.stdout.write(self.style.ERROR(f"{key}: FAILED - {status['error']}"))
