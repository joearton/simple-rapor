from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import ClassGroup, Semester, Teacher, TeachingAssignment


def is_admin(user):
    return bool(user.is_authenticated and (user.is_superuser or user.is_staff))


def get_teacher(user):
    if not user.is_authenticated:
        return None
    return (
        Teacher.objects.select_related('user')
        .filter(user=user, aktif=True)
        .first()
    )


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


def penugasan_mapel(user, subject, class_group=None):
    """Pembagian mengajar untuk mapel pada kelas aktif."""
    guru = get_teacher(user)
    if guru is None:
        return None
    kelas = class_group or active_class()
    if kelas is None:
        return None
    return (
        TeachingAssignment.objects.select_related('teacher', 'subject')
        .filter(teacher=guru, subject=subject, class_group=kelas)
        .first()
    )


def boleh_kelola_mapel(user, subject, class_group=None):
    if is_admin(user):
        return True
    return penugasan_mapel(user, subject, class_group) is not None


def guru_penilai(user, subject, class_group=None):
    """Guru yang dicatat sebagai penilai: guru login, atau guru pengampu (admin)."""
    guru = get_teacher(user)
    if guru is not None:
        return guru
    kelas = class_group or active_class()
    if kelas is None:
        return None
    penugasan = TeachingAssignment.objects.filter(
        subject=subject, class_group=kelas
    ).select_related('teacher').first()
    return penugasan.teacher if penugasan else None


def mapel_untuk_user(user):
    """Mapel yang boleh diakses pengguna pada kelas aktif."""
    from .models import Subject

    if is_admin(user):
        return Subject.objects.all()
    guru = get_teacher(user)
    kelas = active_class()
    if guru is None or kelas is None:
        return Subject.objects.none()
    return Subject.objects.filter(
        penugasan__teacher=guru, penugasan__class_group=kelas
    ).distinct()


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            messages.error(request, 'Halaman ini khusus admin sekolah.')
            return redirect('akademik:dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper
