import os
import django
from daphne.cli import CommandLineInterface

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clueless.settings')
django.setup()

CommandLineInterface().run(['-b', '0.0.0.0', '-p', '8000', 'clueless.asgi:application'])