import os
import sys

from django.apps import AppConfig


class ClassifierConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'classifier'

    def ready(self):
        if os.environ.get("DJANGO_SKIP_MODEL_LOAD"):
            return
        # `runserver`'s autoreloader spawns a watcher process first (RUN_MAIN
        # unset) which then execs the real server process (RUN_MAIN="true").
        # Only load the heavy models in the process that actually serves
        # requests, otherwise every other management command / WSGI process.
        autoreload_enabled = "runserver" in sys.argv and "--noreload" not in sys.argv
        is_watcher_process = autoreload_enabled and os.environ.get("RUN_MAIN") != "true"
        if not is_watcher_process:
            from classifier.services.registry import registry
            registry.load_all()
