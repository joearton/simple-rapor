from datetime import datetime
from pathlib import Path
from shutil import copy2

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Cadangkan database SQLite ke folder backups/ atau path tertentu.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            help='Path file cadangan. Default: backups/db-YYYYmmdd-HHMMSS.sqlite3',
        )

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if 'sqlite3' not in database['ENGINE']:
            raise CommandError(
                'Perintah ini hanya untuk SQLite. Gunakan mysqldump untuk MariaDB.'
            )
        sumber = Path(database['NAME'])
        if not sumber.exists():
            raise CommandError(f'Database tidak ditemukan: {sumber}')

        if options.get('output'):
            tujuan = Path(options['output'])
        else:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            tujuan = settings.BASE_DIR / 'backups' / f'db-{stamp}.sqlite3'
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        copy2(sumber, tujuan)
        self.stdout.write(self.style.SUCCESS(f'Cadangan dibuat: {tujuan}'))
