from .models import Semester, School
from .permissions import active_class, get_teacher, is_admin, is_wali_kelas


def sekolah(request):
    return {
        'sekolah': School.get_solo(),
        'semester_aktif': Semester.get_aktif(),
        'kelas_aktif': active_class(),
        'is_admin_sekolah': is_admin(request.user),
        'guru_login': get_teacher(request.user),
        'is_wali_kelas': is_wali_kelas(request.user),
    }
