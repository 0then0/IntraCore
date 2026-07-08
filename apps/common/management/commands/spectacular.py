from drf_spectacular.management.commands.spectacular import Command as BaseCommand

DEFAULT_API_URLCONF = "config.api_urls"


class Command(BaseCommand):
    def handle(self, *args, **options):
        if options.get("urlconf") is None:
            options["urlconf"] = DEFAULT_API_URLCONF

        return super().handle(*args, **options)
