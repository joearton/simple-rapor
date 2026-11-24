from datetime import datetime
from pathlib import Path
from shutil import copy2

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Pulihkan database SQLite dari file cadangan.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='File cadangan SQLite.')
        parser.add_argument(
            '--yes', action='store_true',
            help='Wajib disertakan untuk benar-benar menimpa database aktif.',
        )

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if 'sqlite3' not in database['ENGINE']:
            raise CommandError(
                'Perintah ini hanya untuk SQLite. Gunakan mysql untuk MariaDB.'
            )
        if not options['yes']:
            raise CommandError(
                'Gunakan --yes untuk mengonfirmasi pemulihan database.'
            )
        sumber = Path(options['file'])
        if not sumber.exists():
            raise CommandError(f'File cadangan tidak ditemukan: {sumber}')

        aktif = Path(database['NAME'])
        if aktif.exists():
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            cadangan = aktif.with_name(f'{aktif.name}.sebelum-restore-{stamp}')
            copy2(aktif, cadangan)
            self.stdout.write(f'Database lama disimpan: {cadangan}')

        copy2(sumber, aktif)
        self.stdout.write(self.style.SUCCESS(f'Database dipulihkan dari: {sumber}'))
