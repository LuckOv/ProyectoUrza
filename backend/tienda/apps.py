import os
import sys
from django.apps import AppConfig


class TiendaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tienda"
    verbose_name = "Tienda URZA"

    def ready(self):
        # Iniciar bot de Telegram automáticamente en segundo plano al levantar 'manage.py runserver'
        # RUN_MAIN == 'true' asegura que solo corra en el worker de Django (no en el proceso watcher)
        # y no interfiere con migraciones, tests o si se corre 'manage.py run_telegram_bot' por separado.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") == "true":
            auto_start = os.environ.get("TELEGRAM_AUTO_START", "true").lower() in ("true", "1", "si", "yes")
            if auto_start:
                from tienda import telegram_notif
                if telegram_notif.esta_configurado():
                    from tienda.management.commands.run_telegram_bot import iniciar_bot_background
                    iniciar_bot_background()

