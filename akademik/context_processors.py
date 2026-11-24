from .models import AcademicYear, Semester, School
from .permissions import (
    active_class,
    get_teacher,
    is_admin,
    is_kepala_sekolah,
    is_operator,
    is_super_admin,
    is_wali_kelas,
    role_label,
)


def sekolah(request):
    user = request.user
    return {
        'sekolah': School.get_solo(),
        'semester_aktif': Semester.get_aktif(),
        'daftar_tahun': AcademicYear.objects.all(),
        'kelas_aktif': active_class(),
        'is_admin_sekolah': is_admin(user),
        'is_super_admin_sekolah': is_super_admin(user),
        'is_kepala_sekolah': is_kepala_sekolah(user),
        'is_operator_sekolah': is_operator(user),
        'guru_login': get_teacher(user),
        'is_wali_kelas': is_wali_kelas(user),
        'role_label': role_label(user),
    }
