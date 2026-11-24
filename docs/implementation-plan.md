# Rencana Implementasi Bertahap

Rancangan ini **belum mengubah skema inti** secara besar. Persetujuan diperlukan sebelum refactor model asesmen/rapor, karena menyentuh data historis.

## Tahap 0 — Dokumen desain (selesai)
- Analisis kebutuhan.
- Arsitektur aplikasi.
- Rancangan database.
- ERD.
- Wireframe UI.
- Rencana implementasi.

## Tahap 1 — Fondasi peran & keamanan
1. Tambah `Group`/permission: Super Admin, Kepala Sekolah, Operator, Guru, Wali, Siswa.
2. Migrasi akun guru yang ada ke group `Guru`.
3. Tambah unit/organisasi (jabatan) dan decorator object-level.
4. Audit log dasar untuk login, perubahan nilai, publikasi rapor.
5. Dashboard per peran dan menu sesuai izin.

**Kriteria terima:** test akses per peran; guru tidak bisa membuka mapel lain; kepala sekolah dapat melihat semua kelas.

## Tahap 2 — Normalisasi master akademik
1. `StudentEnrollment` + backfill dari kelas saat ini.
2. `SchoolProfile` (rename/tambah field), `Grade`.
3. `Subject` per tahun (sudah), `TeachingAssignment` per semester (perluas).
4. Validasi konsistensi tahun: mapel–kelas–penugasan–asesmen.
5. Import/export master dengan template baru.

**Kriteria terima:** riwayat kelas tidak hilang saat kenaikan kelas; data 2026/2027 tetap utuh.

## Tahap 3 — Pembelajaran (CP, TP, materi, tugas)
1. Pisahkan `LearningObjective` (TP) dan `LearningTask` (tugas).
2. Backfill task lama dari field tugas saat ini.
3. Tambah `LearningOutcome`, `LearningMaterial`, `LearningTaskSubmission`.
4. Form tab, filter, pagination, import/export.

**Kriteria terima:** jumlah TP/tugas dinamis; rapor lama tetap menggunakan snapshot deskripsi.

## Tahap 4 — Asesmen generik dan konfigurasi nilai
1. `Assessment`, `Component`, `Objective`, `Result`, `Rubric`.
2. Migrasi `FormativeScore`, `SummativeLM`, `SummativeScore` ke komponen/result.
3. `GradeConfiguration` + service perhitungan yang dapat dikonfigurasi.
4. Grid input (keyboard, autosave, validasi), import/export per asesmen.
5. Deskripsi otomatis dari TP dengan batas kategori konfigurabel.

**Kriteria terima:** hasil perhitungan identik dengan Excel untuk data contoh; satu siswa tidak punya result ganda; komponen kosong tidak dihitung nol.

## Tahap 5 — Rapor, approval, publikasi
1. `ReportCard`, `ReportSubjectGrade`, `ReportCompetencyDescription`.
2. Catatan/absensi/ekskul terhubung ke report card.
3. Alur DRAF → REVIEW → APPROVED → PUBLISHED, unlock dengan audit.
4. PDF WeasyPrint, leger kelas/mapel, rekap semester.
5. Pemeriksaan kelengkapan sebelum submit.

**Kriteria terima:** rapor terkunci tidak dapat diubah; PDF sesuai layout sekolah; cetak massal berhasil.

## Tahap 6 — Portal siswa/orang tua (opsional)
- Akun siswa/guardian, hanya melihat rapor terbit, unduh PDF.

## Tahap 7 — Hardening & dokumentasi final
- Backup/restore teruji, deployment, dokumentasi 12 file, screenshot aktual.
- Uji beban data satu angkatan.

## Risiko dan mitigasi
| Risiko | Mitigasi |
|---|---|
| Kehilangan nilai lama | backup sebelum migrasi, uji di salinan DB, migrasi reversible |
| Refactor terlalu besar | migrasi bertahap, tabel lama dipertahankan sampai verifikasi |
| Perbedaan rumus sekolah | GradeConfiguration + test kasus Excel |
| Hak akses bocor | test object-level + audit log |
| PDF tidak konsisten | template HTML tunggal untuk layar/PDF |

## Keputusan yang diminta
1. Setujui target arsitektur modular dan model generik asesmen.
2. Pilih prioritas tahap berikutnya: **Tahap 1 (role & audit)** atau **Tahap 4 (asesmen generik)**.
3. Konfirmasi apakah portal siswa/orang tua masuk lingkup.

Setelah disetujui, implementasi dilakukan bertahap dengan test regresi di setiap akhir tahap.
