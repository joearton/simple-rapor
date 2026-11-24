from django.contrib import admin

from .models import (
    AcademicYear,
    AuditLog,
    ClassGroup,
    EvaluasiFormatif,
    EvaluasiSumatif,
    Extracurricular,
    FormativeScore,
    HomeroomNote,
    LearningObjective,
    School,
    Semester,
    Student,
    Subject,
    SummativeLM,
    SummativeScore,
    Teacher,
    TeachingAssignment,
)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kepala_sekolah', 'kecamatan')


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
    list_display = ('tingkat', 'nama', 'fase', 'nama_wali', 'academic_year')
    list_filter = ('academic_year',)


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
    list_display = ('subject', 'teacher', 'class_group', 'academic_year')
    list_filter = ('academic_year', 'class_group', 'teacher')
    search_fields = ('subject__nama', 'teacher__nama')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('no_urut', 'nama', 'nis', 'nisn', 'jenis_kelamin', 'class_group', 'aktif')
    list_filter = ('class_group', 'aktif', 'jenis_kelamin')
    search_fields = ('nama', 'nis', 'nisn')
    ordering = ('no_urut',)


@admin.register(LearningObjective)
class LearningObjectiveAdmin(admin.ModelAdmin):
    list_display = ('subject', 'academic_year', 'nomor', 'guru', 'aktif', 'deskripsi')
    list_filter = ('subject', 'academic_year', 'aktif', 'guru')
    search_fields = ('deskripsi',)


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
