# Arsitektur Aplikasi

## 1. Gaya arsitektur

Django MVT monolith dengan service layer. Frontend memakai Django Template + Bootstrap 5 dan JavaScript ringan (Fetch/AJAX hanya untuk autosave, validasi, grafik). Tidak ada SPA terpisah.

```text
Browser
  ↓ HTTP
URLs → Views (thin) → Forms/Serializers (validation)
                    ↓
             Service Layer (business rules)
                    ↓
         Models / ORM (transactions, constraints)
                    ↓
                SQLite → MariaDB
```

Prinsip:
- View hanya mengatur request/response dan permission.
- Perhitungan nilai, deskripsi, kelayakan rapor, dan publikasi berada di service.
- Semua operasi nilai massal memakai `transaction.atomic`.
- Query difilter berdasarkan tahun pelajaran, kelas, dan penugasan guru.

## 2. Struktur target (modular apps)

```text
config/                      # settings, urls, asgi/wsgi
apps/
  accounts/                  # User, Group, role, profil, audit log
  school/                    # SchoolProfile, AcademicYear, Semester, Grade
  academics/                 # ClassGroup, Student, Enrollment, Teacher,
                             # Subject, TeachingAssignment
  learning/                  # LearningOutcome, Objective, Material,
                             # LearningTask, Submission, TaskScore
  assessment/                # Assessment, Component, Objective, Result,
                             # Rubric, GradeConfiguration, services
  reporting/                 # ReportCard, SubjectGrade, Description,
                             # Attendance, Note, Extracurricular,
                             # Publication, PDF/Excel
  dashboard/                 # agregasi statistik per peran
  integrations/              # Excel import/export, backup, PDF helpers
templates/
  components/                # sidebar, navbar, table, form, filter, dll.
  academics/ learning/ assessment/ reporting/ dashboard/
static/
docs/
```

### Strategi dari kondisi sekarang

Saat ini kode berada di satu app `akademik`. Refactor dilakukan bertahap:
1. Tambah apps baru dan pindahkan model dengan migrasi `db_table`/state.
2. Pertahankan URL dan alur yang sudah berjalan selama migrasi.
3. Data lama dibackfill (TP/tugas, nilai, rapor) sebelum tabel lama dihapus.
4. Test regresi wajib lulus di setiap tahap.

## 3. Komponen reusable

- Layout: sidebar, topbar, breadcrumb, user menu.
- Data: filter bar, tabel, pagination, empty state, badge status.
- Form: field wrapper, tab form, date picker, error ringkasan.
- Feedback: toast/alert, modal konfirmasi, loading state.
- Nilai: grid sel, navigasi keyboard, indikator tersimpan, live total.
- Laporan: header rapor, tabel nilai, blok tanda tangan, template PDF.

## 4. Alur kerja per peran

**Super Admin**
1. Atur identitas sekolah dan tahun/semester aktif.
2. Kelola pengguna, group/permission, audit, backup.
3. Pantau seluruh data dan status publikasi rapor.

**Kepala Sekolah**
1. Dashboard ringkas semua kelas.
2. Periksa kelengkapan nilai dan draf rapor.
3. Setujui draf, kunci periode, terbitkan, atau kembalikan untuk revisi.

**Operator/TU**
1. Buat tahun/semester dan rombel.
2. Kelola siswa/guru, enrollment, penugasan mengajar.
3. Import/export master data.

**Guru Mapel**
1. Lihat kelas/mapel yang ditugaskan.
2. Susun CP/TP/materi/tugas.
3. Buat asesmen dan komponen.
4. Input nilai grid; sistem menghitung total dan deskripsi.
5. Kirim hasil untuk finalisasi.

**Wali Kelas**
1. Lihat siswa kelasnya dan rekap semua mapel.
2. Isi catatan, absensi, ekskul.
3. Periksa kelengkapan rapor dan ajukan ke kepala sekolah.

**Siswa/Orang Tua (opsional)**
1. Login, lihat nilai/rapor yang sudah terbit.
2. Unduh PDF; tidak dapat mengubah data.

## 5. Hak akses

- Gunakan `Group`:
  - `Super Admin`, `Kepala Sekolah`, `Operator`, `Guru`, `Wali Kelas`, `Siswa`.
- Permission kustom: `view_all_school_data`, `approve_report`, `publish_report`,
  `unlock_report`, `manage_grade_config`, `view_student_report`.
- Object-level helper:
  - guru hanya untuk `TeachingAssignment` miliknya;
  - wali hanya untuk `ClassGroup.wali_kelas`;
  - kepala sekolah untuk seluruh kelas pada tahun aktif;
  - siswa hanya miliknya.
- Semua view memakai decorator/mixin permission, bukan hanya menyembunyikan menu.

## 6. Integritas dan transaksi

- Unique constraints: NIS/NISN per sekolah, satu enrollment aktif per siswa per tahun,
  satu nilai per siswa per komponen.
- Nilai/rapor terkunci tidak dapat diubah melalui service; error 403/409.
- Import divalidasi seluruh baris lalu disimpan atomik.
- Audit log mencatat user, aksi, objek, nilai lama/baru, waktu, IP.
- Backup: perintah `dumpdata` + file media, atau salinan SQLite saat maintenance.

## 7. Integrasi

- **Excel**: openpyxl; template per entitas; validasi header; laporan error per baris.
- **PDF**: WeasyPrint dari template HTML rapor; font lokal.
- **Chart.js**: dashboard statistik; data dari endpoint JSON kecil.
- **AJAX**: autosave nilai, refresh ringkasan, cek kelengkapan rapor.

## 8. Deployment dan konfigurasi

- Settings dipisah base/dev/prod; `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, database dari env.
- SQLite untuk sekolah tunggal; siap MariaDB dengan `DATABASES` env.
- Static via WhiteNoise atau web server; media di volume persisten.
- Migrasi otomatis saat deploy; backup sebelum migrasi.
