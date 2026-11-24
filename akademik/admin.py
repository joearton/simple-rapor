from django.contrib import admin

from .models import (
    AcademicYear,
    Assessment,
    AssessmentComponent,
    AssessmentObjective,
    AssessmentResult,
    AssessmentRubric,
    AuditLog,
    ClassGroup,
    EvaluasiFormatif,
    EvaluasiSumatif,
    Extracurricular,
    ExtracurricularActivity,
    ExtracurricularEnrollment,
    ExtracurricularPredicate,
    FormativeScore,
    Grade,
    GradeConfiguration,
    HomeroomNote,
    LearningMaterial,
    LearningObjective,
    LearningOutcome,
    LearningTask,
    LearningTaskSubmission,
    ReportCard,
    ReportCompetencyDescription,
    ReportExtracurricular,
    ReportSubjectGrade,
    School,
    Semester,
    Student,
    StudentEnrollment,
    Subject,
    SummativeLM,
    SummativeScore,
    Teacher,
    TeachingAssignment,
)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kepala_sekolah', 'kecamatan')


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('nama', 'fase', 'urutan', 'aktif')
    list_editable = ('fase', 'urutan', 'aktif')


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('tahun', 'aktif')


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('nama', 'academic_year', 'aktif')
    list_filter = ('aktif',)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nik', 'nip', 'nktam', 'jabatan', 'username', 'aktif')
    list_filter = ('aktif', 'jenis_kelamin')
    search_fields = ('nama', 'nik', 'nip', 'nktam', 'jabatan', 'user__username')


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ('grade', 'nama', 'fase', 'nama_wali', 'academic_year')
    list_filter = ('academic_year', 'grade')
    exclude = ('tingkat',)


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_group', 'academic_year', 'status')
    list_filter = ('academic_year', 'class_group', 'status')
    search_fields = ('student__nama', 'student__nis', 'student__nisn')


class LearningObjectiveInline(admin.TabularInline):
    model = LearningObjective
    extra = 1


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('urutan', 'kode', 'nama', 'academic_year')
    list_filter = ('academic_year',)
    list_editable = ('nama',)
    inlines = [LearningObjectiveInline]


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('subject', 'teacher', 'class_group', 'academic_year', 'semester')
    list_filter = ('academic_year', 'semester', 'class_group', 'teacher')
    search_fields = ('subject__nama', 'teacher__nama')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('no_urut', 'nama', 'nis', 'nisn', 'jenis_kelamin', 'class_group', 'aktif')
    list_filter = ('class_group', 'aktif', 'jenis_kelamin')
    search_fields = ('nama', 'nis', 'nisn')
    ordering = ('no_urut',)


@admin.register(LearningObjective)
class LearningObjectiveAdmin(admin.ModelAdmin):
    list_display = ('subject', 'academic_year', 'nomor', 'kode', 'guru', 'aktif', 'deskripsi')
    list_filter = ('subject', 'academic_year', 'aktif', 'guru')
    search_fields = ('deskripsi', 'kode')


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ('subject', 'kode', 'fase', 'urutan', 'aktif')
    list_filter = ('subject', 'fase', 'aktif')
    search_fields = ('kode', 'deskripsi')


@admin.register(LearningMaterial)
class LearningMaterialAdmin(admin.ModelAdmin):
    list_display = ('subject', 'kode', 'judul', 'urutan', 'aktif')
    list_filter = ('subject', 'aktif')
    search_fields = ('kode', 'judul', 'deskripsi')
    filter_horizontal = ('objectives',)


@admin.register(LearningTask)
class LearningTaskAdmin(admin.ModelAdmin):
    list_display = ('judul', 'subject', 'academic_year', 'status', 'bobot', 'batas_pengumpulan')
    list_filter = ('subject', 'academic_year', 'status')
    search_fields = ('judul', 'deskripsi', 'instruksi')
    filter_horizontal = ('class_groups', 'objectives')


@admin.register(LearningTaskSubmission)
class LearningTaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ('task', 'student', 'status', 'nilai', 'submitted_at', 'dinilai_oleh')
    list_filter = ('status', 'task__subject', 'task__academic_year')
    search_fields = ('task__judul', 'student__nama', 'student__nis', 'student__nisn')


@admin.register(FormativeScore)
class FormativeScoreAdmin(admin.ModelAdmin):
    list_display = ('student', 'objective', 'semester', 'guru', 'nilai')
    list_filter = ('objective__subject', 'semester', 'guru')


@admin.register(SummativeScore)
class SummativeScoreAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'subject', 'semester', 'guru', 'sts', 'sas_non_tes', 'sas_tes', 'nilai_rapor',
    )
    list_filter = ('subject', 'semester', 'guru')


@admin.register(SummativeLM)
class SummativeLMAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'semester', 'guru', 'nomor', 'nilai')
    list_filter = ('subject', 'semester', 'guru')


@admin.register(HomeroomNote)
class HomeroomNoteAdmin(admin.ModelAdmin):
    list_display = ('student', 'semester', 'guru', 'sakit', 'izin', 'alpa')
    list_filter = ('semester', 'guru')


@admin.register(Extracurricular)
class ExtracurricularAdmin(admin.ModelAdmin):
    list_display = ('student', 'urutan', 'nama', 'predikat', 'guru')
    list_filter = ('semester', 'guru')


@admin.register(ExtracurricularActivity)
class ExtracurricularActivityAdmin(admin.ModelAdmin):
    list_display = ('nama', 'pembina', 'urutan', 'aktif')
    list_filter = ('aktif', 'pembina')
    search_fields = ('nama', 'deskripsi')


@admin.register(ExtracurricularPredicate)
class ExtracurricularPredicateAdmin(admin.ModelAdmin):
    list_display = ('label', 'batas_min', 'urutan', 'aktif')
    list_editable = ('batas_min', 'urutan', 'aktif')


@admin.register(ExtracurricularEnrollment)
class ExtracurricularEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'activity', 'semester', 'nilai', 'predikat')
    list_filter = ('activity', 'semester', 'activity__aktif')
    search_fields = ('student__nama', 'activity__nama')


@admin.register(EvaluasiFormatif)
class EvaluasiFormatifAdmin(admin.ModelAdmin):
    list_display = ('nama', 'subject', 'jenis', 'tanggal', 'bobot', 'aktif')
    list_filter = ('jenis', 'aktif', 'subject')
    search_fields = ('nama', 'deskripsi')


@admin.register(EvaluasiSumatif)
class EvaluasiSumatifAdmin(admin.ModelAdmin):
    list_display = ('nama', 'subject', 'jenis', 'tanggal', 'bobot', 'aktif')
    list_filter = ('jenis', 'aktif', 'subject')
    search_fields = ('nama', 'deskripsi')


class AssessmentComponentInline(admin.TabularInline):
    model = AssessmentComponent
    extra = 1


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('nama', 'subject', 'semester', 'kategori', 'status', 'aktif')
    list_filter = ('kategori', 'status', 'aktif', 'semester', 'subject')
    search_fields = ('nama', 'deskripsi')
    inlines = [AssessmentComponentInline]


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'component', 'nilai', 'status', 'dinilai_oleh')
    list_filter = ('status', 'component__assessment__kategori', 'component__assessment__subject')
    search_fields = ('student__nama', 'student__nis', 'student__nisn')


@admin.register(AssessmentObjective)
class AssessmentObjectiveAdmin(admin.ModelAdmin):
    list_display = ('assessment', 'objective', 'bobot')
    list_filter = ('assessment__kategori', 'assessment__subject')


@admin.register(AssessmentRubric)
class AssessmentRubricAdmin(admin.ModelAdmin):
    list_display = ('component', 'level', 'urutan')
    list_filter = ('component__assessment__subject',)


@admin.register(GradeConfiguration)
class GradeConfigurationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'bobot_lm', 'bobot_sts', 'bobot_sas', 'aktif')
    list_filter = ('aktif', 'academic_year', 'subject')


class ReportSubjectGradeInline(admin.TabularInline):
    model = ReportSubjectGrade
    extra = 0
    readonly_fields = ('nilai_akhir',)


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_group', 'semester', 'status', 'approved_by', 'published_at')
    list_filter = ('status', 'semester', 'class_group')
    search_fields = ('student__nama', 'student__nis', 'student__nisn')
    inlines = [ReportSubjectGradeInline]


@admin.register(ReportSubjectGrade)
class ReportSubjectGradeAdmin(admin.ModelAdmin):
    list_display = ('report_card', 'subject', 'nilai_akhir', 'predikat')
    list_filter = ('report_card__semester', 'subject')
    search_fields = ('report_card__student__nama', 'subject__nama')


@admin.register(ReportCompetencyDescription)
class ReportCompetencyDescriptionAdmin(admin.ModelAdmin):
    list_display = ('subject_grade', 'tipe', 'objective', 'urutan')
    list_filter = ('tipe',)


@admin.register(ReportExtracurricular)
class ReportExtracurricularAdmin(admin.ModelAdmin):
    list_display = ('report_card', 'urutan', 'nama', 'predikat')
    list_filter = ('report_card__semester',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'aksi', 'model', 'object_id', 'deskripsi')
    list_filter = ('aksi', 'model', 'created_at')
    search_fields = ('deskripsi', 'object_id', 'user__username')
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
