# ERD — Entity Relationship Diagram

Diagram ditulis dengan Mermaid. Nama model mengikuti rancangan target pada `database-design.md`.

## 1. Master akademik

```mermaid
erDiagram
    SchoolProfile {
        int id PK
        string nama
        string npsn
        string alamat
        string kepala_sekolah
    }
    AcademicYear {
        int id PK
        string tahun
        date tanggal_mulai
        date tanggal_berakhir
        bool aktif
        bool is_locked
    }
    Semester {
        int id PK
        int academic_year_id FK
        string nama
        bool aktif
    }
    Grade {
        int id PK
        string nama
        string fase
    }
    ClassGroup {
        int id PK
        int academic_year_id FK
        int grade_id FK
        string nama
        int wali_kelas_id FK
        bool aktif
    }
    Student {
        int id PK
        string nis
        string nisn
        string nama
        string jenis_kelamin
    }
    StudentGuardian {
        int id PK
        int student_id FK
        string tipe
        string nama
        string pekerjaan
    }
    StudentEnrollment {
        int id PK
        int student_id FK
        int class_group_id FK
        int academic_year_id FK
        string status
    }
    Teacher {
        int id PK
        int user_id FK
        string nama
        string nik
        string jabatan
    }
    Subject {
        int id PK
        int academic_year_id FK
        string kode
        string nama
        int urutan
    }
    TeachingAssignment {
        int id PK
        int teacher_id FK
        int subject_id FK
        int class_group_id FK
        int academic_year_id FK
        int semester_id FK
    }

    AcademicYear ||--o{ Semester : memiliki
    AcademicYear ||--o{ ClassGroup : memiliki
    AcademicYear ||--o{ Subject : memiliki
    AcademicYear ||--o{ StudentEnrollment : mencatat
    Grade ||--o{ ClassGroup : tingkat
    ClassGroup ||--o{ StudentEnrollment : berisi
    Student ||--o{ StudentEnrollment : riwayat
    Student ||--o{ StudentGuardian : memiliki
    ClassGroup ||--o{ TeachingAssignment : kelas
    Subject ||--o{ TeachingAssignment : mapel
    Teacher ||--o{ TeachingAssignment : mengajar
    Semester ||--o{ TeachingAssignment : periode
```

## 2. Pembelajaran

```mermaid
erDiagram
    Subject {
        int id PK
        int academic_year_id FK
        string nama
    }
    LearningOutcome {
        int id PK
        int subject_id FK
        string kode
        text deskripsi
        string fase
    }
    LearningObjective {
        int id PK
        int subject_id FK
        int learning_outcome_id FK
        int academic_year_id FK
        string kode
        text deskripsi
        int urutan
        bool aktif
    }
    LearningMaterial {
        int id PK
        int subject_id FK
        string judul
        text deskripsi
    }
    LearningTask {
        int id PK
        int subject_id FK
        int academic_year_id FK
        string judul
        text instruksi
        date tanggal_pemberian
        date batas_pengumpulan
        decimal bobot
        string status
    }
    LearningTaskSubmission {
        int id PK
        int task_id FK
        int student_id FK
        string file
        datetime submitted_at
        string status
    }
    LearningTaskScore {
        int id PK
        int submission_id FK
        decimal nilai
        text catatan_guru
        int dinilai_oleh_id FK
    }

    Subject ||--o{ LearningOutcome : memiliki
    LearningOutcome ||--o{ LearningObjective : menurunkan
    Subject ||--o{ LearningObjective : memiliki
    Subject ||--o{ LearningMaterial : materi
    LearningMaterial }o--o{ LearningObjective : mencakup
    Subject ||--o{ LearningTask : tugas
    LearningTask }o--o{ LearningObjective : sasaran
    LearningTask ||--o{ LearningTaskSubmission : dikumpulkan
    Student ||--o{ LearningTaskSubmission : mengumpulkan
    LearningTaskSubmission ||--|| LearningTaskScore : dinilai
    Teacher ||--o{ LearningTaskScore : menilai
```

## 3. Asesmen

```mermaid
erDiagram
    Assessment {
        int id PK
        int subject_id FK
        int semester_id FK
        int class_group_id FK
        string nama
        string kategori
        string metode
        decimal bobot
        string status
    }
    AssessmentComponent {
        int id PK
        int assessment_id FK
        string nama
        string tipe
        decimal bobot
        decimal nilai_maksimal
    }
    AssessmentObjective {
        int id PK
        int assessment_id FK
        int objective_id FK
        decimal bobot
    }
    AssessmentResult {
        int id PK
        int component_id FK
        int student_id FK
        decimal nilai
        string predikat
        text catatan
        string status
    }
    AssessmentRubric {
        int id PK
        int component_id FK
        string level
        text deskripsi
    }
    GradeConfiguration {
        int id PK
        int academic_year_id FK
        int subject_id FK
        decimal bobot_lm
        decimal bobot_sts
        decimal bobot_sas
        decimal bobot_sas_tes
        decimal bobot_sas_non_tes
        string metode_pembulatan
        int jumlah_desimal
    }
    LearningObjective {
        int id PK
        string kode
        text deskripsi
    }
    Student {
        int id PK
        string nama
    }

    Assessment ||--o{ AssessmentComponent : memiliki
    Assessment ||--o{ AssessmentObjective : mengukur
    LearningObjective ||--o{ AssessmentObjective : dinilai
    AssessmentComponent ||--o{ AssessmentResult : hasil
    Student ||--o{ AssessmentResult : memperoleh
    AssessmentComponent ||--o{ AssessmentRubric : rubrik
    AcademicYear ||--o{ GradeConfiguration : konfigurasi
    Subject ||--o{ GradeConfiguration : konfigurasi
```

## 4. Rapor dan publikasi

```mermaid
erDiagram
    ReportCard {
        int id PK
        int student_id FK
        int class_group_id FK
        int semester_id FK
        string status
        datetime approved_at
        datetime published_at
        datetime locked_at
    }
    ReportSubjectGrade {
        int id PK
        int report_card_id FK
        int subject_id FK
        decimal nilai_lm
        decimal nilai_sts
        decimal nilai_sas
        decimal nilai_akhir
        text deskripsi_final
    }
    ReportCompetencyDescription {
        int id PK
        int report_subject_grade_id FK
        int objective_id FK
        string tipe
        text teks
    }
    StudentAttendance {
        int id PK
        int report_card_id FK
        int sakit
        int izin
        int alpa
    }
    StudentTeacherNote {
        int id PK
        int report_card_id FK
        text catatan
    }
    Extracurricular {
        int id PK
        string nama
        int pembina_id FK
    }
    StudentExtracurricular {
        int id PK
        int report_card_id FK
        int extracurricular_id FK
        string predikat
        text deskripsi
    }
    ReportPublication {
        int id PK
        int semester_id FK
        int class_group_id FK
        string status
        bool locked
        datetime published_at
    }
    ReportCard ||--o{ ReportSubjectGrade : nilai
    Subject ||--o{ ReportSubjectGrade : mapel
    ReportSubjectGrade ||--o{ ReportCompetencyDescription : deskripsi
    ReportCard ||--|| StudentAttendance : kehadiran
    ReportCard ||--|| StudentTeacherNote : catatan
    ReportCard ||--o{ StudentExtracurricular : ekskul
    Extracurricular ||--o{ StudentExtracurricular : kegiatan
    Semester ||--o{ ReportPublication : publikasi
    ClassGroup ||--o{ ReportPublication : publikasi
```

## 5. Alur status rapor

```text
DRAF → REVIEW (wali) → APPROVED (kepala sekolah) → PUBLISHED
  ↑         │                    │
  └─ REVISI ┘                    └─ UNLOCK (super admin, tercatat audit)
```

Semua transisi status dilakukan lewat service, bukan update langsung dari form.
