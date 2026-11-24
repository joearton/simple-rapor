from functools import wraps

from django.contrib import messages
from django.contrib.auth.models import Group
from django.db.models import Q
from django.shortcuts import redirect

from .models import ClassGroup, Semester, Student, Teacher, TeachingAssignment

ROLE_SUPER = 'Super Admin'
ROLE_KEPALA = 'Kepala Sekolah'
ROLE_OPERATOR = 'Operator/Tata Usaha'
ROLE_GURU = 'Guru Mata Pelajaran'
ROLE_WALI = 'Wali Kelas'
ROLE_SISWA = 'Siswa/Orang Tua'

ROLE_GROUPS = [
    ROLE_SUPER, ROLE_KEPALA, ROLE_OPERATOR, ROLE_GURU, ROLE_WALI, ROLE_SISWA,
]


def _in_group(user, name):
    return bool(user.is_authenticated and user.groups.filter(name=name).exists())


def is_super_admin(user):
    return bool(
        user.is_authenticated
        and (user.is_superuser or _in_group(user, ROLE_SUPER))
    )


def is_operator(user):
    return _in_group(user, ROLE_OPERATOR)


def is_kepala_sekolah(user):
    return _in_group(user, ROLE_KEPALA)


def is_admin(user):
    """Akses pengelolaan akademik: Super Admin atau Operator/TU."""
    return bool(user.is_authenticated and (is_super_admin(user) or is_operator(user)))


def get_teacher(user):
    if not user.is_authenticated:
        return None
    return (
        Teacher.objects.select_related('user')
        .filter(user=user, aktif=True)
        .first()
    )


def is_guru(user):
    return get_teacher(user) is not None


def role_label(user):
    if not user.is_authenticated:
        return '-'
    if is_super_admin(user):
        return ROLE_SUPER
    if is_operator(user):
        return ROLE_OPERATOR
    if is_kepala_sekolah(user):
        return ROLE_KEPALA
    if get_teacher(user) is not None:
        return ROLE_GURU
    if Student.objects.filter(user=user).exists() or _in_group(user, ROLE_SISWA):
        return ROLE_SISWA
    return 'Pengguna'


def is_portal_siswa(user):
    """True untuk akun siswa/orang tua yang hanya boleh melihat rapor terbit."""
    if not user.is_authenticated:
        return False
    if user.is_staff or is_super_admin(user) or is_operator(user) or is_kepala_sekolah(user):
        return False
    if get_teacher(user) is not None:
        return False
    return (
        Student.objects.filter(user=user).exists()
        or _in_group(user, ROLE_SISWA)
    )


def siswa_portal(user):
    if not user.is_authenticated:
        return Student.objects.none()
    return Student.objects.filter(user=user).select_related('class_group')


def active_semester():
    return Semester.objects.filter(aktif=True).first() or Semester.objects.first()


def active_class():
    return (
        ClassGroup.objects.filter(academic_year__aktif=True, aktif=True).first()
        or ClassGroup.objects.filter(academic_year__aktif=True).first()
        or ClassGroup.objects.first()
    )


def is_wali_kelas(user, class_group=None):
    guru = get_teacher(user)
    if guru is None:
        return False
    kelas = class_group or active_class()
    return bool(kelas and kelas.wali_kelas_guru_id == guru.id)


def can_manage_homeroom(user, class_group=None):
    return is_admin(user) or is_wali_kelas(user, class_group)


def _penugasan_terpilih(subject, class_group, semester=None):
    """Penugasan mapel/kelas; utamakan semester aktif, lalu penugasan setahun."""
    qs = TeachingAssignment.objects.filter(subject=subject, class_group=class_group)
    if semester is not None:
        penugasan = qs.filter(semester=semester).select_related('teacher').first()
        if penugasan is not None:
            return penugasan
    return qs.filter(semester__isnull=True).select_related('teacher').first()


def penugasan_mapel(user, subject, class_group=None):
    """Pembagian mengajar untuk mapel pada kelas aktif."""
    guru = get_teacher(user)
    if guru is None:
        return None
    kelas = class_group or active_class()
    if kelas is None:
        return None
    penugasan = _penugasan_terpilih(subject, kelas, active_semester())
    if penugasan is not None and penugasan.teacher_id == guru.id:
        return penugasan
    return None


def boleh_kelola_mapel(user, subject, class_group=None):
    if is_admin(user):
        return True
    guru = get_teacher(user)
    if guru is None:
        return False
    if class_group is None:
        return TeachingAssignment.objects.filter(
            teacher=guru, subject=subject,
            academic_year=subject.academic_year_id,
        ).exists()
    return penugasan_mapel(user, subject, class_group) is not None


def guru_penilai(user, subject, class_group=None):
    """Guru yang dicatat sebagai penilai: guru login, atau guru pengampu (admin)."""
    guru = get_teacher(user)
    if guru is not None:
        return guru
    kelas = class_group or active_class()
    if kelas is None:
        return None
    penugasan = _penugasan_terpilih(subject, kelas, active_semester())
    return penugasan.teacher if penugasan else None


def mapel_untuk_user(user):
    """Mapel yang diampu pengguna pada tahun aktif, lintas kelas."""
    from .models import Subject

    semester = active_semester()
    tahun = semester.academic_year if semester else None
    base = Subject.objects.filter(academic_year=tahun) if tahun else Subject.objects.none()
    if is_admin(user):
        return base
    guru = get_teacher(user)
    if guru is None:
        return Subject.objects.none()
    penugasan_filter = Q(penugasan__teacher=guru)
    if semester is not None:
        penugasan_filter &= (
            Q(penugasan__semester=semester) | Q(penugasan__semester__isnull=True)
        )
    return base.filter(penugasan_filter).distinct()


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            messages.error(request, 'Halaman ini khusus admin sekolah.')
            return redirect('akademik:dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper


def super_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_super_admin(request.user):
            messages.error(request, 'Halaman ini khusus Super Admin.')
            return redirect('akademik:dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper


def can_view_reports(user, class_group=None):
    return is_admin(user) or is_kepala_sekolah(user) or is_wali_kelas(user, class_group)


def set_user_role(user, role):
    groups = list(Group.objects.filter(name__in=ROLE_GROUPS))
    user.groups.remove(*groups)
    if role:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)


def ensure_role_groups():
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)
