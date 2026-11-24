# Rancangan Basis Data

Database SQLite; hindari fitur SQLite-only agar mudah pindah ke MariaDB. Gunakan `DecimalField` untuk nilai/bobot, `DateField` untuk tanggal, dan `unique_together`/`UniqueConstraint`.

## 1. Master sekolah & akademik

### SchoolProfile
`nama, npsn, nss, alamat, kode_pos, kelurahan, kecamatan, kabupaten, provinsi, website, email, kepala_sekolah, nktam_kepala, logo, kop_rapor, layout_rapor(JSON), created_at, updated_at`

### AcademicYear
`tahun, tanggal_mulai, tanggal_berakhir, aktif, is_locked`
Relasi: 1-N `Semester`, 1-N `ClassGroup`, 1-N `Subject`, 1-N `TeachingAssignment`, 1-N `StudentEnrollment`.

### Semester
`academic_year FK, nama(I/II), tanggal_mulai, tanggal_berakhir, aktif`
Unique `(academic_year, nama)`.

### Grade
`nama(VII/VIII/IX), fase, urutan`

### ClassGroup
`academic_year FK, grade FK, nama, wali_kelas FK Teacher(null), aktif`
Unique `(academic_year, grade, nama)`.

### Student
`nis, nisn, nama, jenis_kelamin, tempat_lahir, tanggal_lahir, agama, pendidikan_sebelumnya, alamat, status`
Unique `(nis)`, `(nisn)`.

### StudentGuardian
`student FK, tipe(AYAH/IBU/WALI), nama, pekerjaan, no_hp, email, alamat`

### StudentEnrollment
`student FK, class_group FK, academic_year FK, tanggal_masuk, status(AKTIF/PINDAH/LULUS), keterangan`
Unique `(student, academic_year)`; riwayat tidak dihapus.

### Teacher
`user OneToOne(null), nama, nik, nip, nktam, jenis_kelamin, tempat_lahir, tanggal_lahir, pendidikan, jurusan, tahun_lulus, jabatan, email, no_hp, alamat, aktif`

### Subject
`academic_year FK, kode, nama, deskripsi, urutan, aktif`
Unique `(academic_year, nama)`, `(academic_year, kode)` jika kode wajib.

### TeachingAssignment
`teacher FK, subject FK, class_group FK, academic_year FK, semester FK(null), aktif`
Unique `(subject, class_group, semester)` – satu guru pengampu per mapel/kelas/semester.

## 2. Pembelajaran

### LearningOutcome (CP)
`subject FK, fase, kode, deskripsi, urutan, aktif`

### LearningObjective (TP)
`learning_outcome FK(null), subject FK, academic_year FK, kode, deskripsi, urutan, aktif`
Unique `(subject, academic_year, kode)`.

### LearningMaterial
`subject FK, kode, judul, deskripsi, urutan, aktif`
M2M ke `LearningObjective` (satu materi dapat mencakup beberapa TP).

### LearningTask
`subject FK, academic_year FK, judul, deskripsi, instruksi, tanggal_pemberian, batas_pengumpulan, lampiran, bobot, status(DRAF/TERBIT/TUTUP), created_by FK Teacher`
Relasi M2M ke `LearningObjective` dan M2M ke `Student`/`ClassGroup`.

### LearningTaskSubmission
`task FK, student FK, file, catatan_siswa, submitted_at, status`
Unique `(task, student)`.

### LearningTaskScore
`submission OneToOne, nilai, catatan_guru, dinilai_oleh FK Teacher, dinilai_at`

## 3. Asesmen

### Assessment
`subject FK, academic_year FK, semester FK, kelas FK(null), nama, kategori(FORMATIF/SUMATIF_LM/STS/SAS), metode(TES/NON_TES/OBSERVASI/PRAKTIK/PROYEK/PORTOFOLIO/LAIN), tanggal, bobot, deskripsi, status, created_by`
Unique `(subject, semester, nama)`.

### AssessmentComponent
`assessment FK, nama, tipe, urutan, bobot, nilai_maksimal, wajib`
Unique `(assessment, nama)`.

### AssessmentObjective
`assessment FK, objective FK, bobot`
Unique `(assessment, objective)`.

### AssessmentResult
`component FK, student FK, nilai Decimal, predikat, catatan, tanggal, status(VALID/REVISI), dinilai_oleh`
Unique `(component, student)`.
Indeks: `(student, component)`, `(component, status)`.

### AssessmentRubric
`component FK, level, deskripsi, urutan`

### GradeConfiguration
`academic_year FK(null), subject FK(null), bobot_lm, bobot_sts, bobot_sas, bobot_sas_tes, bobot_sas_non_tes, metode_pembulatan, jumlah_desimal, nilai_min, nilai_max, ambang_unggul, ambang_perlu_bimbingan, aktif`
Prioritas konfigurasi: mapel → tahun → default sekolah.

## 4. Rapor

### ReportCard
`student FK, class_group FK, semester FK, status(DRAF/REVIEW/APPROVED/PUBLISHED/REVISI), catatan_wali, approved_by, approved_at, published_at, locked_at, nomor_urut`
Unique `(student, semester)`.

### ReportSubjectGrade
`report_card FK, subject FK, nilai_lm, nilai_sts, nilai_sas, nilai_akhir, predikat, deskripsi_otomatis, deskripsi_final, urutan`
Unique `(report_card, subject)`.

### ReportCompetencyDescription
`report_subject_grade FK, objective FK, tipe(UNGGUL/PERLU_BIMBINGAN), teks, urutan`
Menyimpan jejak TP yang mendasari deskripsi.

### StudentAttendance
`report_card FK, sakit, izin, alpa, catatan`
OneToOne.

### StudentTeacherNote
`report_card FK, catatan, created_by, updated_at`
OneToOne.

### Extracurricular
`nama, pembina FK Teacher(null), deskripsi, aktif`

### StudentExtracurricular
`report_card FK, extracurricular FK, predikat, deskripsi, urutan`
Unique `(report_card, urutan)`.

### ReportPublication
`semester FK, class_group FK, status, published_by, published_at, locked, catatan`
Mengunci seluruh rapor pada periode/kelas.

### AuditLog
`user FK(null), aksi, model, object_id, data_lama(JSON), data_baru(JSON), ip, user_agent, created_at`

## 5. Aturan hitung awal (mengikuti Excel)

```text
rata_lm  = average(nilai LM yang terisi)
rata_sas = average(nilai SAS tes, SAS non-tes yang terisi)
nilai_rapor = average(rata_lm, sts, rata_sas)   # hanya komponen terisi
```

Konfigurasi bobot dapat mengganti rumus:
```text
nilai = (bobot_lm*rata_lm + bobot_sts*sts + bobot_sas*rata_sas) / total_bobot_terisi
```
Nilai kosong tidak dihitung nol. Bulatkan hanya pada tahap akhir.

## 6. Pemetaan model saat ini → target

| Sekarang | Target | Catatan migrasi |
|---|---|---|
| School | SchoolProfile | rename/field tambah |
| AcademicYear, Semester, ClassGroup, Teacher, Subject, TeachingAssignment | sama | tambah constraint/permission |
| Student | Student + StudentEnrollment | backfill enrollment dari `class_group` |
| LearningObjective (TP+tugas) | LearningObjective + LearningTask | pisahkan field tugas |
| FormativeScore | Assessment(FORMATIF) + Component/Result | satu komponen per TP/tugas |
| SummativeLM / SummativeScore | Assessment(LM/STS/SAS) + Component/Result | komponen LM-1..n, STS, SAS tes/non-tes |
| HomeroomNote | StudentTeacherNote + StudentAttendance | pecah field |
| Extracurricular | Extracurricular + StudentExtracurricular | master + penilaian siswa |
| Perhitungan rapor di service | ReportCard + ReportSubjectGrade | snapshot hasil final |
| Print HTML | ReportCard + PDF + ReportPublication | status/lock |

## 7. Constraint dan integritas
- `StudentEnrollment`: satu aktif per siswa/tahun.
- `AssessmentResult`: satu nilai per siswa/komponen.
- `ReportCard`: satu per siswa/semester; nilai final immutable setelah `PUBLISHED`.
- `AcademicYear` aktif tunggal; `Semester` aktif tunggal (dapat dijaga service + constraint parsial di MariaDB).
- Semua FK `PROTECT` untuk data historis penting; `SET_NULL` hanya untuk relasi opsional.
