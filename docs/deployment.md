# Deployment, Backup, dan Pemulihan

## 1. Persiapan server

- Python 3.10+ dan virtualenv.
- Paket sistem untuk WeasyPrint (Pango/Cairo) sesuai distro.
- Jalankan:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

- Set `DEBUG=False`, `SECRET_KEY` produksi, dan `ALLOWED_HOSTS` di environment
  atau file settings produksi.
- Jalankan dengan WSGI (Gunicorn/uWSGI) di belakang Nginx, bukan `runserver`.
- Arahkan `/static/` dan `/media/` ke Nginx.

## 2. Database

Default pengembangan memakai SQLite. Untuk produksi skala sekolah, MariaDB
disarankan. Perubahan skema tetap melalui migrasi Django; hindari mengubah
tabel langsung.

Data demo untuk pengecekan:

```bash
python manage.py seed_demo
python manage.py seed_demo --force   # ganti data demo yang sudah ada
```

Akun demo memakai password `demo12345`:
`demo_kepsek`, `demo_operator`, `demo_wali`, `demo_guru`, `demo_siswa`.

## 3. Backup

SQLite:

```bash
python manage.py backup_db
python manage.py backup_db --output /path/aman/db-rapor.sqlite3
```

Cadangan disimpan di `backups/` secara default (diabaikan git). Jadwalkan
lewat cron, misalnya setiap hari pukul 23.00, dan salin hasilnya ke luar server.

MariaDB:

```bash
mysqldump -u rapor -p rapor_smpm > /path/aman/rapor-$(date +%F).sql
```

## 4. Restore

SQLite:

```bash
python manage.py restore_db --file backups/db-20261124-230000.sqlite3 --yes
```

Perintah membuat cadangan otomatis `db.sqlite3.sebelum-restore-*` sebelum
menimpa database aktif. Hentikan aplikasi terlebih dahulu agar tidak ada
penulisan bersamaan.

MariaDB:

```bash
mysql -u rapor -p rapor_smpm < /path/aman/rapor-2026-11-24.sql
```

## 5. Checklist rilis

1. `python manage.py check`
2. `python manage.py test`
3. `python manage.py makemigrations --check --dry-run`
4. `python manage.py migrate`
5. `python manage.py collectstatic --noinput`
6. Backup sebelum migrasi.
7. Uji login admin, guru, wali kelas, dan akun portal.
8. Uji satu rapor: susun → ajukan → setujui → terbitkan → PDF.
9. Pastikan audit log mencatat publikasi dan buka kunci.

## 6. Catatan keamanan

- Ganti password akun contoh sebelum produksi.
- Gunakan HTTPS.
- Batasi akses panel admin Django.
- Aktifkan backup terjadwal dan uji restore secara berkala.
- Jangan commit `db.sqlite3`, `media/`, atau folder `backups/`.
