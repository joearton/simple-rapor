# Analisis Kebutuhan — Sistem Informasi Akademik dan Rapor

Dokumen ini menjadi dasar persetujuan sebelum refactor besar. Aplikasi yang ada sudah berjalan, sehingga strategi yang dipilih adalah **evolusi bertahap**, bukan menulis ulang dari nol.

## 1. Tujuan

Membangun sistem akademik dan rapor SMP Muhammadiyah Soekarno Hatta Kotabumi yang:

- Mengelola tahun pelajaran, semester, kelas, siswa, guru, mapel, dan penugasan mengajar.
- Mengelola CP, TP, lingkup materi, tugas, asesmen formatif, dan asesmen sumatif.
- Menghasilkan nilai rapor secara konsisten dan dapat dikonfigurasi.
- Mencetak rapor, leger, dan rekap perkembangan.
- Menerapkan hak akses per peran dan menjaga integritas data historis.

## 2. Peran pengguna

| Peran | Kebutuhan utama | Status saat ini |
|---|---|---|
| Super Admin | Semua konfigurasi, pengguna, audit, backup | Sebagian (admin Django + panel pengguna) |
| Kepala Sekolah | Monitoring, persetujuan & penguncian rapor, leger semua kelas | Belum sebagai peran tersendiri |
| Operator/Tata Usaha | Siswa, guru, kelas, tahun pelajaran, administrasi | Sebagian (panel admin) |
| Guru Mata Pelajaran | Kelas/mapel yang diampu, TP, tugas, asesmen, nilai, deskripsi | Sudah (scoped per penugasan) |
| Wali Kelas | Data kelas, rekap nilai, catatan, absensi, ekskul, kesiapan rapor | Sudah (scoped per kelas) |
| Siswa/Orang Tua (opsional) | Melihat nilai/rapor terbit dan unduh PDF | Belum |

Target: gunakan Django `Group` + permission, ditambah relasi `User ↔ Teacher/Student/Guardian`. Jangan mengandalkan `is_staff` saja.

## 3. Kebutuhan fungsional

### 3.1 Master akademik
- Identitas sekolah, logo, kop, dan tata letak rapor.
- Tahun pelajaran (tanggal mulai/berakhir), semester, tingkat, rombel/kelas.
- Siswa dan riwayat penempatan kelas (`StudentEnrollment`), bukan menimpa kelas lama.
- Guru, mapel per tahun, dan penugasan guru–kelas–mapel–semester.
- Import/export Excel dengan validasi dan transaksi all-or-nothing.

### 3.2 Pembelajaran
- Capaian pembelajaran (CP), tujuan pembelajaran (TP), dan lingkup materi.
- Tugas pembelajaran: judul, deskripsi, instruksi, tanggal, tenggat, lampiran, bobot.
- Pengumpulan tugas dan nilai tugas (opsional untuk tahap awal; lihat prioritas).
- TP dan tugas bersifat dinamis, tidak dibuatkan tabel per mapel/semester.

### 3.3 Asesmen dan nilai
- Kategori: formatif, sumatif lingkup materi (LM), STS, SAS.
- Metode: tes, non-tes, observasi, praktik, proyek, portofolio, lainnya.
- Komponen asesmen dan hasil per siswa; satu hasil per siswa per komponen.
- Input grid ala spreadsheet, validasi, import/export, filter kelas/mapel/asesmen.
- Nilai formatif skala 1–4 dan deskripsi capaian otomatis yang dapat diedit guru.
- Rumus awal: rata-rata LM, rata-rata SAS, lalu rata-rata ketiga komponen; komponen kosong tidak dihitung nol.
- Konfigurasi bobot, pembulatan, batas nilai, dan ambang deskripsi.

### 3.4 Rapor
- Identitas siswa/sekolah, nilai akhir, deskripsi capaian, catatan, absensi, ekskul.
- Leger per kelas/mapel, rekap semester, rapor individual/massal.
- Status draf → diperiksa → disetujui → diterbitkan; kunci setelah terbit.
- PDF profesional (WeasyPrint) dan arsip publikasi.

### 3.5 Administrasi dan keamanan
- Audit log aktivitas penting (nilai, rapor, konfigurasi).
- Backup/restore; validasi import; transaksi massal; larangan mengubah nilai terkunci.
- Filter data berdasarkan penugasan guru/kelas wali/peran.

## 4. Kebutuhan non-fungsional
- Django + SQLite (siap migrasi MariaDB), template server-side, Bootstrap 5.
- UI Bahasa Indonesia default; struktur siap i18n Inggris.
- Responsif, aksesibel, tabel besar tetap nyaman.
- Service layer untuk perhitungan nilai/deskripsi/rapor; view tipis.
- Unit + integration test untuk relasi, perhitungan, hak akses, import/export, PDF.
- Dokumentasi teknis dan panduan pengguna.

## 5. Kondisi aplikasi saat ini

Sudah tersedia:
- Login + captcha, panel pengguna, peran admin/guru/wali.
- Tahun pelajaran/semester/kelas, mapel per tahun, guru, siswa, penugasan.
- Tugas pembelajaran (model `LearningObjective` diperluas), evaluasi formatif/sumatif (rencana), grid nilai formatif/sumatif, leger, rapor dan sampul, catatan/ekskul terikat tahun.
- Import/export Excel, pengaturan identitas/logo/tata letak rapor, filter/paginasi.
- 97 test lulus.

Pembaruan Tahap 1–5 (24 Nov 2026):
- Peran Super Admin/Kepala Sekolah/Operator/Guru/Wali + audit log + dashboard per peran.
- Master `Grade`, `SchoolProfile`, riwayat `StudentEnrollment`, dan penugasan mengajar per semester.
- Roster kelas membaca riwayat enrollment; import/export data kelas tersedia.
- CP, materi, tugas pembelajaran, dan pengumpulan tugas tersedia beserta tab, filter, pagination, dan import/export.
- Asesmen generik (`Assessment`/`Component`/`Result`), konfigurasi bobot & pembulatan, grid autosave, serta deskripsi TP dengan ambang konfigurabel.
- Snapshot rapor, alur review/approval/publikasi dengan penguncian, PDF WeasyPrint, dan cetak massal per kelas.

Kesenjangan utama terhadap target:
1. Tabel nilai lama (`FormativeScore`, `SummativeLM/Score`) masih dipertahankan sebagai layar input dan disinkronkan ke model generik; target akhir menghapusnya.
2. Modul CP/materi/tugas/pengumpulan sudah tersedia; rubrik baru tersedia lewat admin, belum ada UI khusus.
3. Rapor sudah dimodelkan dengan snapshot, status, publikasi, dan locking.
4. Peran Kepala Sekolah/Operator/Guru/Wali sudah dipisah dan audit log tersedia; peran Siswa/Orang Tua belum.
5. PDF WeasyPrint sudah tersedia; backup/restore, deployment, dan dokumentasi pengguna lengkap belum.
6. Struktur masih satu app `akademik`; target modular apps.

## 6. Prioritas (MoSCoW)

**Must**
- Role-based access (Kepala Sekolah, Operator, Guru, Wali).
- Generic assessment + grade configuration + perhitungan teruji.
- ReportCard + status/locking + PDF.
- Audit log, validasi transaksi, backup.
- Migrasi data lama tanpa kehilangan riwayat.

**Should**
- CP, lingkup materi, task submission, rubrik.
- Dashboard statistik per peran.
- Portal siswa/orang tua.
- i18n Inggris.

**Could**
- Notifikasi, analitik tren, integrasi Dapodik.
**Won't (tahap ini)**
- Aplikasi mobile native, frontend SPA terpisah.

## 7. Keputusan yang menunggu persetujuan
1. Apakah target refactor mengikuti model generik penuh (Assessment/Result) atau mempertahankan tabel nilai saat ini lebih lama?
2. Apakah peran Kepala Sekolah/Operator dibuat sekarang atau setelah modul rapor?
3. Apakah portal siswa/orang tua masuk lingkup tahap ini?
4. Apakah PDF wajib memakai WeasyPrint sejak tahap rapor atau boleh print browser sementara?
