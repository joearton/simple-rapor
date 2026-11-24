from decimal import Decimal, InvalidOperation
import json

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .audit import catat_audit
from .reporting import (
    ReportError,
    ReportIncomplete,
    ajukan,
    buka_kunci,
    konteks_rapor,
    konteks_rapor_siswa,
    kembalikan,
    periksa_kelengkapan,
    rapor_terkunci,
    setujui,
    susun_report_card,
    terbitkan,
)
from .forms import (
    AcademicYearForm,
    AdminResetPasswordForm,
    AssessmentComponentFormSet,
    AssessmentForm,
    CapaianPembelajaranForm,
    EvaluasiFormatifForm,
    EvaluasiSumatifForm,
    ClassGroupForm,
    GradeConfigurationForm,
    KelasForm,
    LoginForm,
    MateriPembelajaranForm,
    ProfileForm,
    SchoolForm,
    SemesterForm,
    StyledPasswordChangeForm,
    StudentForm,
    SubjectForm,
    TeacherForm,
    TugasPembelajaranForm,
    TujuanPembelajaranForm,
    UserForm,
)
from .models import (
    AcademicYear,
    Assessment,
    AssessmentComponent,
    AssessmentObjective,
    AssessmentResult,
    AuditLog,
    ClassGroup,
    EvaluasiFormatif,
    EvaluasiSumatif,
    Extracurricular,
    FormativeScore,
    GradeConfiguration,
    HomeroomNote,
    LearningMaterial,
    LearningObjective,
    LearningOutcome,
    LearningTask,
    LearningTaskSubmission,
    ReportCard,
    ReportSubjectGrade,
    School,
    Semester,
    Student,
    Subject,
    SummativeLM,
    SummativeScore,
    Teacher,
    TeachingAssignment,
)
from .permissions import (
    admin_required,
    boleh_kelola_mapel,
    can_manage_homeroom,
    get_teacher,
    guru_penilai,
    is_admin,
    is_kepala_sekolah,
    is_portal_siswa,
    is_wali_kelas,
    can_view_reports,
    super_admin_required,
    mapel_untuk_user,
    siswa_portal,
)
from .services import (
    MAX_LM,
    bulatkan,
    daftar_mapel,
    daftar_siswa,
    data_leger,
    data_rapor,
    deskripsi_capaian,
    hitung_nilai,
    kelas_aktif,
    konfigurasi_nilai,
    nilai_formatif_map,
    ringkasan_sumatif,
    semester_aktif,
    tujuan_aktif,
)


class LoginSekolahView(LoginView):
    template_name = 'akademik/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if is_portal_siswa(self.request.user):
            return reverse('akademik:portal_dashboard')
        return super().get_success_url()


def logout_sekolah(request):
    logout(request)
    messages.success(request, 'Anda telah keluar dari aplikasi.')
    return redirect('akademik:login')


class UbahPasswordView(PasswordChangeView):
    template_name = 'akademik/password_change.html'
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy('akademik:dashboard')

    def form_valid(self, form):
        messages.success(self.request, 'Password berhasil diubah.')
        return super().form_valid(form)


def _kelas():
    return kelas_aktif()


def _semester():
    return semester_aktif()


def _angka(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None


def _angka_bulat(value, minimal=0, maksimal=100):
    angka = _angka(value)
    if angka is None:
        return None
    if angka < minimal or angka > maksimal:
        return None
    return angka


PER_PAGE = 25


def _paginate(request, queryset):
    return Paginator(queryset, PER_PAGE).get_page(request.GET.get('page'))


def _q(request):
    return (request.GET.get('q') or '').strip()


def _filter_siswa_text(qs, q):
    if q:
        qs = qs.filter(
            Q(nama__icontains=q) | Q(nis__icontains=q) | Q(nisn__icontains=q)
        )
    return qs


def _tolak_mapel(request):
    messages.error(request, 'Anda tidak mengampu mata pelajaran ini.')
    return redirect('akademik:dashboard')


def _kelas_terkunci(kelas, semester):
    if kelas is None or semester is None:
        return False
    return ReportCard.objects.filter(
        semester=semester, class_group=kelas, status='PUBLISHED'
    ).exists()


def _tolak_halaman(request):
    messages.error(request, 'Halaman ini hanya dapat diakses admin atau wali kelas.')
    return redirect('akademik:dashboard')


@login_required
def dashboard(request):
    if is_portal_siswa(request.user):
        return redirect('akademik:portal_dashboard')
    semester = _semester()
    kelas = _kelas()
    admin = is_admin(request.user)
    kepala = is_kepala_sekolah(request.user)
    guru = get_teacher(request.user)
    if kepala:
        tahun_aktif = semester.academic_year if semester else None
        mapel_qs = list(
            Subject.objects.filter(academic_year=tahun_aktif)
            if tahun_aktif else Subject.objects.none()
        )
    else:
        mapel_qs = list(mapel_untuk_user(request.user))
    siswa_qs = daftar_siswa(kelas)
    total_siswa = siswa_qs.count()

    mapel_cards = []
    total_terisi = 0
    total_target = 0
    tahun_aktif = semester.academic_year if semester else None
    for mapel in mapel_qs:
        penugasan = None
        if kelas:
            penugasan = TeachingAssignment.objects.filter(
                subject=mapel, class_group=kelas
            ).select_related('teacher').first()
        terisi = 0
        if semester and kelas:
            terisi = SummativeScore.objects.filter(
                subject=mapel, semester=semester, student__in=daftar_siswa(kelas)
            ).count()
        target = total_siswa
        total_terisi += terisi
        total_target += target
        mapel_cards.append({
            'subject': mapel,
            'jumlah_tp': mapel.tujuan_list.filter(
                academic_year=tahun_aktif, aktif=True
            ).count() if tahun_aktif else 0,
            'terisi': terisi,
            'target': target,
            'persen': int(terisi / target * 100) if target else 0,
            'guru': penugasan.teacher if penugasan else None,
        })

    progres = int(total_terisi / total_target * 100) if total_target else 0
    return render(request, 'akademik/dashboard.html', {
        'admin': admin,
        'kepala': kepala,
        'guru': guru,
        'mapel_cards': mapel_cards,
        'total_siswa': total_siswa,
        'total_mapel': len(mapel_qs),
        'total_tp': sum(c['jumlah_tp'] for c in mapel_cards),
        'progres': progres,
        'jumlah_nilai': total_terisi,
        'target_nilai': total_target,
        'jumlah_guru': Teacher.objects.count(),
        'jumlah_penugasan': TeachingAssignment.objects.count(),
        'jumlah_wali': ClassGroup.objects.exclude(wali_kelas_guru=None).count(),
        'wali_kelas': is_wali_kelas(request.user),
    })


@login_required
@super_admin_required
def identitas(request):
    school = School.get_solo()
    kelas = _kelas()
    semester = _semester()
    academic_year = semester.academic_year if semester else AcademicYear.get_aktif()

    if request.method == 'POST':
        form = SchoolForm(request.POST, request.FILES, instance=school)
        kelas_form = KelasForm(request.POST, instance=kelas, prefix='kelas') if kelas else None
        if form.is_valid() and (kelas_form is None or kelas_form.is_valid()):
            with transaction.atomic():
                form.save()
                if kelas_form is not None:
                    kelas_form.save()
            catat_audit(
                request.user, 'UPDATE', school,
                deskripsi='Perbarui identitas/pengaturan sekolah', request=request,
            )
            messages.success(request, 'Identitas dan pengaturan sekolah berhasil disimpan.')
            return redirect('akademik:identitas')
        messages.error(request, 'Periksa kembali isian identitas.')
    else:
        form = SchoolForm(instance=school)
        kelas_form = KelasForm(instance=kelas, prefix='kelas') if kelas else None

    return render(request, 'akademik/identitas.html', {
        'form': form,
        'kelas_form': kelas_form,
        'academic_year': academic_year,
        'semester': semester,
    })


@login_required
def siswa_list(request):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    kelas = _kelas()
    if kelas:
        qs = Student.objects.in_class(kelas)
    else:
        qs = Student.objects.none()
    q = _q(request)
    qs = _filter_siswa_text(qs, q)
    jk = request.GET.get('jk') or ''
    status = request.GET.get('status') or 'aktif'
    if jk in ('L', 'P'):
        qs = qs.filter(jenis_kelamin=jk)
    if status == 'aktif':
        qs = qs.filter(aktif=True)
    elif status == 'nonaktif':
        qs = qs.filter(aktif=False)
    page_obj = _paginate(request, qs.order_by('no_urut'))
    return render(request, 'akademik/siswa_list.html', {
        'siswa_list': page_obj,
        'page_obj': page_obj,
        'total': page_obj.paginator.count,
        'bisa_ubah': is_admin(request.user),
        'q': q,
        'jk_filter': jk,
        'status_filter': status,
    })


@login_required
@admin_required
def siswa_form(request, pk=None):
    siswa = get_object_or_404(Student, pk=pk) if pk else None
    kelas = _kelas()
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=siswa)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.class_group_id is None:
                obj.class_group = kelas
            obj.save()
            messages.success(request, f'Data siswa {obj.nama} disimpan.')
            return redirect('akademik:siswa_list')
    else:
        form = StudentForm(instance=siswa)
    return render(request, 'akademik/siswa_form.html', {'form': form, 'siswa': siswa})


@login_required
@admin_required
def siswa_hapus(request, pk):
    siswa = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        nama = siswa.nama
        siswa.delete()
        messages.success(request, f'Data siswa {nama} dihapus.')
    return redirect('akademik:siswa_list')


@login_required
def mapel_menu(request, mode='tp'):
    semester = _semester()
    tahun = semester.academic_year if semester else AcademicYear.get_aktif()
    subjects = mapel_untuk_user(request.user).annotate(
        jumlah_tp=Count(
            'tujuan_list',
            filter=Q(tujuan_list__academic_year=tahun, tujuan_list__aktif=True),
        )
    )
    konfigurasi = {
        'tp': {
            'judul': 'Tujuan Pembelajaran (TP)',
            'deskripsi': 'Susun tujuan pembelajaran / lingkup materi setiap mata pelajaran.',
            'url_name': 'akademik:tp_list',
        },
        'formatif': {
            'judul': 'Asesmen Formatif',
            'deskripsi': 'Input nilai TP (skala 1-4) dan lihat deskripsi capaian otomatis.',
            'url_name': 'akademik:formatif_entry',
        },
        'sumatif': {
            'judul': 'Asesmen Sumatif',
            'deskripsi': 'Input nilai LM, STS, dan SAS untuk menghitung nilai rapor.',
            'url_name': 'akademik:sumatif_entry',
        },
    }[mode]
    return render(request, 'akademik/mapel_menu.html', {
        'subjects': subjects,
        'konfigurasi': konfigurasi,
        'mode': mode,
        'guru': get_teacher(request.user),
    })


@login_required
def tp_list(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id)
    if not boleh_kelola_mapel(request.user, subject):
        return _tolak_mapel(request)
    semester = _semester()
    tahun = semester.academic_year if semester else AcademicYear.get_aktif()
    guru = guru_penilai(request.user, subject)
    q = _q(request)
    status = request.GET.get('status') or 'aktif'
    qs = subject.tujuan_list.filter(academic_year=tahun)
    if status == 'aktif':
        qs = qs.filter(aktif=True)
    elif status == 'arsip':
        qs = qs.filter(aktif=False)
    if q:
        qs = qs.filter(deskripsi__icontains=q)
    page_obj = _paginate(request, qs.order_by('nomor'))

    if request.method == 'POST':
        aksi = request.POST.get('aksi', 'simpan')
        if aksi in ('hapus', 'aktifkan'):
            tp = get_object_or_404(
                LearningObjective, pk=request.POST.get('tp_id'),
                subject=subject, academic_year=tahun,
            )
            if aksi == 'aktifkan':
                tp.aktif = True
                tp.save(update_fields=['aktif'])
                messages.success(request, 'Tujuan pembelajaran diaktifkan kembali.')
            elif tp.nilai_formatif.exists():
                tp.aktif = False
                tp.save(update_fields=['aktif'])
                messages.success(
                    request,
                    'TP memiliki nilai sehingga diarsipkan, bukan dihapus. '
                    'Nilai dan rapor lama tetap aman.',
                )
            else:
                tp.delete()
                messages.success(request, 'Tujuan pembelajaran dihapus.')
            return redirect(request.get_full_path())

        with transaction.atomic():
            for tp in page_obj.object_list:
                deskripsi = request.POST.get(f'tp_{tp.id}', '').strip()
                if deskripsi and (
                    deskripsi != tp.deskripsi or (guru and tp.guru_id != guru.id)
                ):
                    tp.deskripsi = deskripsi
                    if guru:
                        tp.guru = guru
                    tp.save()
            nomor_baru = (
                subject.tujuan_list.filter(academic_year=tahun)
                .order_by('-nomor').values_list('nomor', flat=True).first()
                or 0
            ) + 1
            for i in range(1, 4):
                deskripsi = request.POST.get(f'baru_{i}', '').strip()
                if deskripsi:
                    LearningObjective.objects.create(
                        subject=subject, academic_year=tahun, nomor=nomor_baru,
                        deskripsi=deskripsi, guru=guru,
                    )
                    nomor_baru += 1
        messages.success(request, 'Tujuan pembelajaran disimpan.')
        return redirect(request.get_full_path())

    return render(request, 'akademik/tp_list.html', {
        'subject': subject,
        'objectives': page_obj,
        'page_obj': page_obj,
        'baris_baru': range(1, 4),
        'guru': guru,
        'q': q,
        'status_filter': status,
        'tahun': tahun,
        'active_tab': 'tp',
    })


@login_required
def formatif_entry(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id)
    if not boleh_kelola_mapel(request.user, subject):
        return _tolak_mapel(request)
    semester = _semester()
    objectives = list(tujuan_aktif(subject, semester)) if semester else []
    kelas = _kelas()
    guru = guru_penilai(request.user, subject)
    q = _q(request)
    status = request.GET.get('status') or ''
    base = (
        Student.objects.in_class(kelas).filter(aktif=True) if kelas
        else Student.objects.none()
    )
    base = _filter_siswa_text(base, q)
    if status in ('sudah', 'belum') and semester:
        base = base.annotate(
            jml=Count(
                'nilai_formatif',
                filter=Q(
                    nilai_formatif__objective__subject=subject,
                    nilai_formatif__semester=semester,
                ),
            )
        )
        base = base.filter(jml__gt=0) if status == 'sudah' else base.filter(jml=0)
    page_obj = _paginate(request, base.order_by('no_urut'))
    students = list(page_obj)

    if request.method == 'POST':
        if _kelas_terkunci(kelas, semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(request.get_full_path())
        if request.POST.get('aksi') == 'sinkron_deskripsi':
            jumlah = 0
            with transaction.atomic():
                for score in FormativeScore.objects.filter(
                    student__in=students,
                    objective__subject=subject,
                    objective__academic_year=semester.academic_year,
                    semester=semester,
                ).select_related('objective'):
                    if score.deskripsi_tp != score.objective.deskripsi:
                        score.deskripsi_tp = score.objective.deskripsi
                        score.save(update_fields=['deskripsi_tp'])
                        jumlah += 1
            messages.success(
                request,
                f'Deskripsi disinkronkan dari TP untuk {jumlah} nilai. '
                'Deskripsi rapor akan memakai teks terbaru.',
            )
            return redirect(request.get_full_path())
        jumlah = 0
        with transaction.atomic():
            for siswa in students:
                for tp in objectives:
                    nilai = request.POST.get(f'f_{siswa.id}_{tp.id}')
                    if nilai in (None, ''):
                        FormativeScore.objects.filter(
                            student=siswa, objective=tp, semester=semester
                        ).delete()
                        continue
                    angka = _angka_bulat(nilai, 1, 4)
                    if angka is None:
                        continue
                    FormativeScore.objects.update_or_create(
                        student=siswa, objective=tp, semester=semester,
                        defaults={'nilai': int(angka), 'guru': guru},
                    )
                    jumlah += 1
        catat_audit(
            request.user, 'UPDATE', subject,
            deskripsi=f'Simpan nilai formatif {subject.nama}: {jumlah} nilai',
            request=request,
        )
        messages.success(request, f'Nilai formatif disimpan ({jumlah} nilai terisi).')
        return redirect(request.get_full_path())

    rows = []
    for siswa in students:
        nilai = nilai_formatif_map(siswa, subject, semester)
        capaian = deskripsi_capaian(siswa, subject, semester, objectives)
        rows.append({
            'siswa': siswa,
            'nilai': [
                {'tp': tp, 'nilai': nilai.get(tp.id)} for tp in objectives
            ],
            'capaian': capaian,
        })
    return render(request, 'akademik/formatif_entry.html', {
        'subject': subject,
        'objectives': objectives,
        'rows': rows,
        'semester': semester,
        'guru': guru,
        'q': q,
        'status_filter': status,
        'page_obj': page_obj,
        'tp_data': [
            {'id': tp.id, 'nomor': tp.nomor, 'deskripsi': tp.deskripsi}
            for tp in objectives
        ],
    })


@login_required
def sumatif_entry(request, subject_id):
    subject = get_object_or_404(Subject, pk=subject_id)
    if not boleh_kelola_mapel(request.user, subject):
        return _tolak_mapel(request)
    semester = _semester()
    guru = guru_penilai(request.user, subject)
    kelas = _kelas()
    q = _q(request)
    status = request.GET.get('status') or ''
    base = (
        Student.objects.in_class(kelas).filter(aktif=True) if kelas
        else Student.objects.none()
    )
    base = _filter_siswa_text(base, q)
    if status in ('sudah', 'belum') and semester:
        base = base.annotate(
            jml=Count(
                'nilai_sumatif',
                filter=Q(
                    nilai_sumatif__subject=subject,
                    nilai_sumatif__semester=semester,
                ),
            )
        )
        base = base.filter(jml__gt=0) if status == 'sudah' else base.filter(jml=0)
    page_obj = _paginate(request, base.order_by('no_urut'))
    students = list(page_obj)

    if request.method == 'POST':
        if _kelas_terkunci(kelas, semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(request.get_full_path())
        with transaction.atomic():
            for siswa in students:
                for nomor in range(1, MAX_LM + 1):
                    nilai = _angka_bulat(request.POST.get(f'lm_{siswa.id}_{nomor}'))
                    if nilai is None:
                        SummativeLM.objects.filter(
                            student=siswa, subject=subject, semester=semester, nomor=nomor
                        ).delete()
                        continue
                    SummativeLM.objects.update_or_create(
                        student=siswa, subject=subject, semester=semester, nomor=nomor,
                        defaults={'nilai': nilai, 'guru': guru},
                    )
                sts = _angka_bulat(request.POST.get(f'sts_{siswa.id}'))
                non_tes = _angka_bulat(request.POST.get(f'sasn_{siswa.id}'))
                tes = _angka_bulat(request.POST.get(f'sast_{siswa.id}'))
                if sts is None and non_tes is None and tes is None:
                    SummativeScore.objects.filter(
                        student=siswa, subject=subject, semester=semester
                    ).delete()
                    continue
                SummativeScore.objects.update_or_create(
                    student=siswa, subject=subject, semester=semester,
                    defaults={'sts': sts, 'sas_non_tes': non_tes, 'sas_tes': tes, 'guru': guru},
                )
        catat_audit(
            request.user, 'UPDATE', subject,
            deskripsi=f'Simpan nilai sumatif {subject.nama}', request=request,
        )
        messages.success(request, 'Nilai sumatif disimpan.')
        return redirect(request.get_full_path())

    return render(request, 'akademik/sumatif_entry.html', {
        'subject': subject,
        'rows': ringkasan_sumatif(students, subject, semester),
        'lm_range': range(1, MAX_LM + 1),
        'guru': guru,
        'kelas': kelas,
        'q': q,
        'status_filter': status,
        'page_obj': page_obj,
    })


@login_required
def catatan_entry(request):
    kelas = _kelas()
    if not can_manage_homeroom(request.user, kelas):
        messages.error(request, 'Catatan hanya dapat diisi oleh wali kelas atau admin.')
        return redirect('akademik:dashboard')
    semester = _semester()
    guru = get_teacher(request.user) or (kelas.wali_kelas_guru if kelas else None)
    q = _q(request)
    status = request.GET.get('status') or ''
    base = (
        Student.objects.in_class(kelas).filter(aktif=True) if kelas
        else Student.objects.none()
    )
    base = _filter_siswa_text(base, q)
    if status in ('sudah', 'belum') and semester:
        base = base.annotate(
            jml=Count('catatan', filter=Q(catatan__semester=semester))
        )
        base = base.filter(jml__gt=0) if status == 'sudah' else base.filter(jml=0)
    page_obj = _paginate(request, base.order_by('no_urut'))
    students = list(page_obj)

    if request.method == 'POST':
        if _kelas_terkunci(kelas, semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(request.get_full_path())
        with transaction.atomic():
            for siswa in students:
                catatan = request.POST.get(f'catatan_{siswa.id}', '').strip()
                sakit = int(_angka(request.POST.get(f'sakit_{siswa.id}')) or 0)
                izin = int(_angka(request.POST.get(f'izin_{siswa.id}')) or 0)
                alpa = int(_angka(request.POST.get(f'alpa_{siswa.id}')) or 0)
                if not catatan and not (sakit or izin or alpa):
                    HomeroomNote.objects.filter(student=siswa, semester=semester).delete()
                    continue
                HomeroomNote.objects.update_or_create(
                    student=siswa, semester=semester,
                    defaults={
                        'catatan': catatan, 'sakit': sakit, 'izin': izin, 'alpa': alpa,
                        'guru': guru, 'academic_year': semester.academic_year,
                    },
                )
        messages.success(request, 'Catatan dan absensi disimpan.')
        return redirect(request.get_full_path())

    data = {
        n.student_id: n
        for n in HomeroomNote.objects.filter(semester=semester, student__in=students)
    }
    rows = [{'siswa': siswa, 'catatan': data.get(siswa.id)} for siswa in students]
    return render(request, 'akademik/catatan_entry.html', {
        'rows': rows,
        'guru': guru,
        'kelas': kelas,
        'q': q,
        'status_filter': status,
        'page_obj': page_obj,
    })


@login_required
def ekskul_entry(request):
    kelas = _kelas()
    if not can_manage_homeroom(request.user, kelas):
        messages.error(request, 'Data ekstrakurikuler hanya dapat diisi oleh wali kelas atau admin.')
        return redirect('akademik:dashboard')
    semester = _semester()
    slots = range(1, 6)
    guru = get_teacher(request.user) or (kelas.wali_kelas_guru if kelas else None)
    q = _q(request)
    status = request.GET.get('status') or ''
    base = (
        Student.objects.in_class(kelas).filter(aktif=True) if kelas
        else Student.objects.none()
    )
    base = _filter_siswa_text(base, q)
    if status in ('sudah', 'belum') and semester:
        base = base.annotate(
            jml=Count('ekstrakurikuler', filter=Q(ekstrakurikuler__semester=semester))
        )
        base = base.filter(jml__gt=0) if status == 'sudah' else base.filter(jml=0)
    page_obj = _paginate(request, base.order_by('no_urut'))
    students = list(page_obj)

    if request.method == 'POST':
        if _kelas_terkunci(kelas, semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(request.get_full_path())
        with transaction.atomic():
            for siswa in students:
                for urutan in slots:
                    nama = request.POST.get(f'eks_{siswa.id}_{urutan}', '').strip()
                    predikat = request.POST.get(f'pred_{siswa.id}_{urutan}', '').strip()
                    deskripsi = request.POST.get(f'desk_{siswa.id}_{urutan}', '').strip()
                    if not (nama or predikat or deskripsi):
                        Extracurricular.objects.filter(
                            student=siswa, semester=semester, urutan=urutan
                        ).delete()
                        continue
                    Extracurricular.objects.update_or_create(
                        student=siswa, semester=semester, urutan=urutan,
                        defaults={
                            'nama': nama, 'predikat': predikat, 'deskripsi': deskripsi,
                            'guru': guru, 'academic_year': semester.academic_year,
                        },
                    )
        messages.success(request, 'Data ekstrakurikuler disimpan.')
        return redirect(request.get_full_path())

    data = {}
    for eks in Extracurricular.objects.filter(semester=semester, student__in=students):
        data.setdefault(eks.student_id, {})[eks.urutan] = eks
    rows = []
    for siswa in students:
        isi = data.get(siswa.id, {})
        rows.append({'siswa': siswa, 'ekskul': [isi.get(i) for i in slots]})
    return render(request, 'akademik/ekskul_entry.html', {
        'rows': rows,
        'slots': slots,
        'guru': guru,
        'kelas': kelas,
        'q': q,
        'status_filter': status,
        'page_obj': page_obj,
    })


@login_required
def leger(request):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    class_group = _kelas()
    semester = _semester()
    q = _q(request)
    base = (
        Student.objects.in_class(class_group).filter(aktif=True) if class_group
        else Student.objects.none()
    )
    base = _filter_siswa_text(base, q)
    page_obj = _paginate(request, base.order_by('no_urut'))
    return render(request, 'akademik/leger.html', {
        'leger': data_leger(class_group, semester, students=page_obj.object_list),
        'semester': semester,
        'class_group': class_group,
        'page_obj': page_obj,
        'q': q,
    })


@login_required
def rapor_index(request):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    kelas = _kelas()
    semester = _semester()
    q = _q(request)
    base = (
        Student.objects.in_class(kelas).filter(aktif=True) if kelas
        else Student.objects.none()
    )
    base = _filter_siswa_text(base, q)
    page_obj = _paginate(request, base.order_by('no_urut'))
    cards = {}
    if semester:
        cards = {
            card.student_id: card
            for card in ReportCard.objects.filter(
                semester=semester, student__in=page_obj.object_list
            ).select_related('approved_by')
        }
    rows = [
        {'siswa': siswa, 'card': cards.get(siswa.id)}
        for siswa in page_obj.object_list
    ]
    return render(request, 'akademik/rapor_index.html', {
        'siswa_list': page_obj,
        'rows': rows,
        'semester': semester,
        'page_obj': page_obj,
        'q': q,
        'bisa_kelola': can_view_reports(request.user),
        'bisa_setujui': is_admin(request.user) or is_kepala_sekolah(request.user),
        'bisa_buka': is_admin(request.user),
    })


@login_required
def rapor_detail(request, student_id):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    student = get_object_or_404(Student, pk=student_id)
    data = konteks_rapor_siswa(student, _semester())
    return render(request, 'akademik/rapor_print.html', data)


@login_required
def rapor_sampul(request, student_id):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    student = get_object_or_404(Student, pk=student_id)
    semester = _semester()
    card = ReportCard.objects.filter(student=student, semester=semester).first()
    return render(request, 'akademik/rapor_sampul.html', {
        'student': student,
        'semester': semester,
        'class_group': card.class_group if card else None,
        'school': School.get_solo(),
    })


@login_required
def cetak_semua(request):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    semester = _semester()
    students = daftar_siswa(_kelas())
    data = [konteks_rapor_siswa(siswa, semester) for siswa in students]
    return render(request, 'akademik/rapor_semua.html', {
        'data': data,
        'semester': semester,
        'school': School.get_solo(),
    })


@login_required
def rapor_susun(request, student_id):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    student = get_object_or_404(Student, pk=student_id)
    try:
        susun_report_card(student, _semester(), request.user)
    except ReportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Rapor {student.nama} disusun.')
    return redirect('akademik:rapor_index')


@login_required
def rapor_susun_semua(request):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    semester = _semester()
    siswa_qs = daftar_siswa(_kelas())
    berhasil = 0
    gagal = 0
    for siswa in siswa_qs:
        try:
            susun_report_card(siswa, semester, request.user)
        except ReportError:
            gagal += 1
        else:
            berhasil += 1
    messages.success(
        request,
        f'Rapor disusun: {berhasil} siswa' + (f', {gagal} dilewati.' if gagal else '.'),
    )
    return redirect('akademik:rapor_index')


@login_required
def rapor_ajukan(request, pk):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    card = get_object_or_404(ReportCard, pk=pk)
    try:
        ajukan(card, request.user)
    except ReportIncomplete as exc:
        for issue in exc.issues[:8]:
            messages.error(request, issue)
    except ReportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Rapor {card.student.nama} diajukan untuk review.')
    return redirect('akademik:rapor_index')


@login_required
def rapor_setujui(request, pk):
    if not (is_admin(request.user) or is_kepala_sekolah(request.user)):
        return _tolak_halaman(request)
    card = get_object_or_404(ReportCard, pk=pk)
    try:
        setujui(card, request.user)
    except ReportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Rapor {card.student.nama} disetujui.')
    return redirect('akademik:rapor_index')


@login_required
def rapor_terbitkan(request, pk):
    if not (is_admin(request.user) or is_kepala_sekolah(request.user)):
        return _tolak_halaman(request)
    card = get_object_or_404(ReportCard, pk=pk)
    try:
        terbitkan(card, request.user)
    except ReportIncomplete as exc:
        for issue in exc.issues[:8]:
            messages.error(request, issue)
    except ReportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Rapor {card.student.nama} diterbitkan dan dikunci.')
    return redirect('akademik:rapor_index')


@login_required
def rapor_buka_kunci(request, pk):
    if not is_admin(request.user):
        return _tolak_halaman(request)
    card = get_object_or_404(ReportCard, pk=pk)
    try:
        buka_kunci(card, request.user, request.POST.get('alasan', ''))
    except ReportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Kunci rapor {card.student.nama} dibuka untuk revisi.')
    return redirect('akademik:rapor_index')


@login_required
def rapor_kembalikan(request, pk):
    if not (is_admin(request.user) or is_kepala_sekolah(request.user)):
        return _tolak_halaman(request)
    card = get_object_or_404(ReportCard, pk=pk)
    try:
        kembalikan(card, request.user, request.POST.get('alasan', ''))
    except ReportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Rapor {card.student.nama} dikembalikan ke revisi.')
    return redirect('akademik:rapor_index')


def _pdf_response(request, html, filename):
    from django.conf import settings
    from weasyprint import CSS, HTML

    stylesheets = []
    for nama in ('app.css', 'rapor.css'):
        path = settings.BASE_DIR / 'static' / 'css' / nama
        if path.exists():
            stylesheets.append(CSS(filename=str(path)))
    pdf = HTML(
        string=html, base_url=request.build_absolute_uri('/')
    ).write_pdf(stylesheets=stylesheets)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}.pdf"'
    return response


@login_required
def rapor_pdf(request, student_id):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    student = get_object_or_404(Student, pk=student_id)
    semester = _semester()
    data = konteks_rapor_siswa(student, semester)
    html = render_to_string('akademik/rapor_print.html', data, request=request)
    nama = f'rapor-{student.nis or student.id}-{semester.nama}'
    return _pdf_response(request, html, nama)


@login_required
def rapor_pdf_semua(request):
    if not can_view_reports(request.user):
        return _tolak_halaman(request)
    semester = _semester()
    data = [konteks_rapor_siswa(siswa, semester) for siswa in daftar_siswa(_kelas())]
    html = render_to_string(
        'akademik/rapor_semua.html',
        {'data': data, 'semester': semester, 'school': School.get_solo()},
        request=request,
    )
    return _pdf_response(
        request, html,
        f'rapor-kelas-{(data[0]["class_group"].nama_lengkap if data and data[0].get("class_group") else "semua")}',
    )


# ---------------- Portal Siswa/Orang Tua ----------------

@login_required
def portal_dashboard(request):
    students = list(siswa_portal(request.user))
    cards = (
        ReportCard.objects.filter(student__in=students, status='PUBLISHED')
        .select_related('student', 'class_group', 'semester', 'semester__academic_year')
        .order_by('-semester__academic_year__tahun', '-semester__nama')
        if students else ReportCard.objects.none()
    )
    return render(request, 'akademik/portal_dashboard.html', {
        'students': students,
        'cards': cards,
    })


def _card_portal(request, card_id):
    students = siswa_portal(request.user)
    return get_object_or_404(
        ReportCard.objects.select_related(
            'student', 'class_group', 'semester', 'semester__academic_year'
        ),
        pk=card_id, status='PUBLISHED', student__in=students,
    )


@login_required
def portal_rapor(request, card_id):
    card = _card_portal(request, card_id)
    return render(request, 'akademik/portal_rapor.html', konteks_rapor(card))


@login_required
def portal_rapor_pdf(request, card_id):
    card = _card_portal(request, card_id)
    data = konteks_rapor(card)
    html = render_to_string('akademik/rapor_pdf.html', data, request=request)
    nama = f'rapor-{card.student.nis or card.student.id}-{card.semester.nama}'
    return _pdf_response(request, html, nama)


@login_required
@admin_required
def guru_list(request):
    guru_qs = Teacher.objects.select_related('user').prefetch_related(
        'penugasan__subject', 'penugasan__class_group', 'kelas_wali'
    )
    q = _q(request)
    status = request.GET.get('status') or ''
    mapel_id = request.GET.get('mapel') or ''
    wali = request.GET.get('wali') or ''
    if q:
        guru_qs = guru_qs.filter(
            Q(nama__icontains=q) | Q(nip__icontains=q) | Q(nktam__icontains=q)
            | Q(user__username__icontains=q)
        )
    if status == 'aktif':
        guru_qs = guru_qs.filter(aktif=True)
    elif status == 'nonaktif':
        guru_qs = guru_qs.filter(aktif=False)
    if mapel_id:
        guru_qs = guru_qs.filter(penugasan__subject_id=mapel_id).distinct()
    if wali == 'ya':
        guru_qs = guru_qs.filter(kelas_wali__isnull=False)
    elif wali == 'tidak':
        guru_qs = guru_qs.filter(kelas_wali__isnull=True)
    page_obj = _paginate(request, guru_qs)
    rows = []
    for guru in page_obj:
        rows.append({
            'guru': guru,
            'mapel': sorted({p.subject.nama for p in guru.penugasan.all()}),
            'wali': list(guru.kelas_wali.all()),
        })
    return render(request, 'akademik/guru_list.html', {
        'rows': rows,
        'page_obj': page_obj,
        'q': q,
        'status_filter': status,
        'mapel_filter': mapel_id,
        'wali_filter': wali,
        'subjects': daftar_mapel(),
    })


@login_required
@admin_required
def guru_form(request, pk=None):
    guru = get_object_or_404(Teacher, pk=pk) if pk else None
    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=guru)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'Data guru {obj.nama} disimpan.')
            return redirect('akademik:guru_list')
    else:
        form = TeacherForm(instance=guru)
    return render(request, 'akademik/guru_form.html', {'form': form, 'guru': guru})


@login_required
@admin_required
def guru_hapus(request, pk):
    guru = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        nama = guru.nama
        user = guru.user
        guru.delete()
        if user and not user.is_superuser and not user.is_staff:
            user.delete()
        messages.success(request, f'Data guru {nama} dihapus.')
    return redirect('akademik:guru_list')


@login_required
@admin_required
def mapel_list(request):
    kelas = _kelas()
    semester = _semester()
    tahun_aktif = semester.academic_year if semester else AcademicYear.get_aktif()
    tahun_id = request.GET.get('tahun') or (tahun_aktif.id if tahun_aktif else '')
    tahun = AcademicYear.objects.filter(pk=tahun_id).first() if tahun_id else None
    subjects = Subject.objects.filter(academic_year=tahun) if tahun else Subject.objects.none()
    subjects = subjects.annotate(
        jumlah_tp=Count(
            'tujuan_list',
            filter=Q(tujuan_list__academic_year=tahun, tujuan_list__aktif=True),
        )
    )
    q = _q(request)
    guru_id = request.GET.get('guru') or ''
    if q:
        subjects = subjects.filter(
            Q(nama__icontains=q) | Q(kode__icontains=q) | Q(deskripsi__icontains=q)
        )
    if guru_id and kelas and tahun == tahun_aktif:
        subjects = subjects.filter(
            penugasan__teacher_id=guru_id, penugasan__class_group=kelas
        ).distinct()
    page_obj = _paginate(request, subjects.order_by('urutan', 'nama'))
    penugasan = {}
    if kelas and tahun == tahun_aktif:
        for p in TeachingAssignment.objects.filter(
            class_group=kelas, subject__in=page_obj.object_list
        ).select_related('teacher', 'subject'):
            if p.semester_id:
                penugasan[p.subject_id] = p.teacher
            else:
                penugasan.setdefault(p.subject_id, p.teacher)
    rows = [{'subject': s, 'guru': penugasan.get(s.id)} for s in page_obj]
    return render(request, 'akademik/mapel_list.html', {
        'rows': rows,
        'kelas': kelas,
        'page_obj': page_obj,
        'q': q,
        'guru_filter': guru_id,
        'teachers': Teacher.objects.filter(aktif=True),
        'tahun': tahun,
        'tahun_id': str(tahun.id) if tahun else '',
        'daftar_tahun': AcademicYear.objects.all(),
    })


@login_required
@admin_required
def mapel_form(request, pk=None):
    subject = get_object_or_404(Subject, pk=pk) if pk else None
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'Mata pelajaran {obj.nama} disimpan.')
            return redirect(f"{reverse('akademik:mapel_list')}?tahun={obj.academic_year_id}")
    else:
        initial = {}
        tahun_id = request.GET.get('tahun')
        if tahun_id:
            initial['academic_year'] = tahun_id
        elif not subject:
            tahun = _semester().academic_year if _semester() else AcademicYear.get_aktif()
            if tahun:
                initial['academic_year'] = tahun
        form = SubjectForm(instance=subject, initial=initial)
    return render(request, 'akademik/mapel_form.html', {'form': form, 'subject': subject})


@login_required
@admin_required
def mapel_hapus(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        nama = subject.nama
        try:
            subject.delete()
        except ProtectedError:
            messages.error(
                request,
                f'Mata pelajaran {nama} sudah dipakai snapshot rapor sehingga tidak dapat dihapus.',
            )
        else:
            messages.success(request, f'Mata pelajaran {nama} beserta data nilainya dihapus.')
    return redirect('akademik:mapel_list')


@login_required
@admin_required
def mengajar(request):
    kelas = _kelas()
    semester = _semester()
    year = semester.academic_year if semester else AcademicYear.get_aktif()
    teachers = Teacher.objects.filter(aktif=True)
    q = _q(request)
    subjects_qs = daftar_mapel()
    if q:
        subjects_qs = subjects_qs.filter(nama__icontains=q)
    page_obj = _paginate(request, subjects_qs)
    subjects = list(page_obj.object_list)

    if request.method == 'POST':
        if kelas is None or year is None:
            messages.error(request, 'Lengkapi identitas kelas dan tahun pelajaran terlebih dahulu.')
            return redirect('akademik:mengajar')
        with transaction.atomic():
            for subject in subjects:
                guru_id = request.POST.get(f'mapel_{subject.id}') or ''
                if not guru_id:
                    TeachingAssignment.objects.filter(
                        subject=subject, class_group=kelas, academic_year=year,
                        semester__isnull=True,
                    ).delete()
                    continue
                guru = teachers.filter(pk=guru_id).first()
                if guru is None:
                    continue
                TeachingAssignment.objects.update_or_create(
                    subject=subject, class_group=kelas, academic_year=year,
                    semester=None, defaults={'teacher': guru},
                )
            wali_id = request.POST.get('wali_kelas_guru') or ''
            wali = teachers.filter(pk=wali_id).first()
            kelas.wali_kelas_guru = wali
            if wali:
                kelas.wali_kelas = wali.nama
                kelas.nktam_wali = wali.nktam
            else:
                kelas.wali_kelas = ''
                kelas.nktam_wali = ''
            kelas.save(update_fields=['wali_kelas_guru', 'wali_kelas', 'nktam_wali'])
        messages.success(request, 'Pembagian tugas mengajar disimpan.')
        return redirect(request.get_full_path())

    penugasan = {}
    if kelas and year:
        qs = TeachingAssignment.objects.filter(
            class_group=kelas, academic_year=year, subject__in=subjects,
        ).select_related('teacher')
        if semester is not None:
            qs = qs.filter(Q(semester=semester) | Q(semester__isnull=True))
        for p in qs:
            if p.semester_id:
                penugasan[p.subject_id] = p.teacher_id
            else:
                penugasan.setdefault(p.subject_id, p.teacher_id)
    rows = [
        {'subject': s, 'guru_id': penugasan.get(s.id)} for s in subjects
    ]
    return render(request, 'akademik/mengajar.html', {
        'rows': rows,
        'teachers': teachers,
        'kelas': kelas,
        'semester': semester,
        'wali_kelas_guru_id': kelas.wali_kelas_guru_id if kelas else None,
        'page_obj': page_obj,
        'q': q,
    })


@login_required
def profil(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil akun berhasil diperbarui.')
            return redirect('akademik:profil')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'akademik/profil.html', {
        'form': form,
        'guru': get_teacher(request.user),
    })


@login_required
@super_admin_required
def pengguna_list(request):
    qs = User.objects.order_by('username')
    q = _q(request)
    role = request.GET.get('role') or ''
    status = request.GET.get('status') or ''
    if q:
        qs = qs.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if role == 'admin':
        qs = qs.filter(Q(is_staff=True) | Q(is_superuser=True))
    elif role == 'kepala':
        qs = qs.filter(groups__name='Kepala Sekolah')
    elif role == 'operator':
        qs = qs.filter(groups__name='Operator/Tata Usaha')
    elif role == 'guru':
        qs = qs.filter(guru__isnull=False).exclude(Q(is_staff=True) | Q(is_superuser=True))
    elif role == 'siswa':
        qs = qs.filter(student_profile__isnull=False)
    elif role == 'pengguna':
        qs = qs.filter(is_staff=False, is_superuser=False, guru__isnull=True)
    if status == 'aktif':
        qs = qs.filter(is_active=True)
    elif status == 'nonaktif':
        qs = qs.filter(is_active=False)
    page_obj = _paginate(request, qs)
    rows = []
    for user in page_obj:
        guru = getattr(user, 'guru', None)
        siswa = getattr(user, 'student_profile', None)
        if user.is_staff or user.is_superuser:
            peran = 'Administrator'
        elif guru:
            peran = 'Guru'
        elif siswa:
            peran = 'Siswa/Orang Tua'
        else:
            peran = 'Pengguna'
        rows.append({'user': user, 'guru': guru, 'siswa': siswa, 'peran': peran})
    return render(request, 'akademik/pengguna_list.html', {
        'rows': rows,
        'page_obj': page_obj,
        'q': q,
        'role_filter': role,
        'status_filter': status,
    })


@login_required
@super_admin_required
def pengguna_form(request, pk=None):
    target = get_object_or_404(User, pk=pk) if pk else None
    if request.method == 'POST':
        form = UserForm(request.POST, instance=target)
        if form.is_valid():
            role = form.cleaned_data['role']
            if target == request.user and role != 'super_admin':
                form.add_error('role', 'Anda tidak dapat menurunkan peran akun sendiri.')
            elif target == request.user and not form.cleaned_data.get('is_active'):
                form.add_error('is_active', 'Anda tidak dapat menonaktifkan akun sendiri.')
            elif (
                target
                and target.is_superuser
                and role != 'super_admin'
                and not User.objects.filter(is_superuser=True).exclude(pk=target.pk).exists()
            ):
                form.add_error('role', 'Harus ada minimal satu administrator.')
            else:
                obj = form.save()
                catat_audit(
                    request.user, 'UPDATE' if target else 'CREATE', obj,
                    deskripsi=f'Akun {obj.username} disimpan', request=request,
                )
                messages.success(request, f'Akun {obj.username} disimpan.')
                return redirect('akademik:pengguna_list')
    else:
        form = UserForm(instance=target)
    return render(request, 'akademik/pengguna_form.html', {'form': form, 'target': target})


@login_required
@super_admin_required
def pengguna_reset_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = AdminResetPasswordForm(target, request.POST)
        if form.is_valid():
            form.save()
            if target == request.user:
                update_session_auth_hash(request, target)
            catat_audit(
                request.user, 'UPDATE', target,
                deskripsi=f'Reset password akun {target.username}', request=request,
            )
            messages.success(request, f'Password akun {target.username} berhasil direset.')
            return redirect('akademik:pengguna_list')
    else:
        form = AdminResetPasswordForm(target)
    return render(request, 'akademik/pengguna_reset_password.html', {
        'form': form,
        'target': target,
    })


@login_required
@super_admin_required
def pengguna_hapus(request, pk):
    target = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if target == request.user:
            messages.error(request, 'Anda tidak dapat menghapus akun sendiri.')
        elif target.is_superuser and not User.objects.filter(is_superuser=True).exclude(pk=target.pk).exists():
            messages.error(request, 'Harus ada minimal satu administrator.')
        else:
            username = target.username
            catat_audit(
                request.user, 'DELETE', target,
                deskripsi=f'Hapus akun {username}', request=request,
            )
            target.delete()
            messages.success(request, f'Akun {username} dihapus.')
    return redirect('akademik:pengguna_list')


def _aktifkan_kelas_internal(kelas):
    year = kelas.academic_year
    AcademicYear.objects.update(aktif=False)
    year.aktif = True
    year.save(update_fields=['aktif'])

    semester = Semester.objects.filter(academic_year=year, aktif=True).first()
    if semester is None:
        semester = year.semester_list.order_by('nama').first()
    if semester is None:
        semester = Semester.objects.create(academic_year=year, nama='I')
    Semester.objects.update(aktif=False)
    semester.aktif = True
    semester.save(update_fields=['aktif'])

    ClassGroup.objects.update(aktif=False)
    kelas.aktif = True
    kelas.save(update_fields=['aktif'])


def _aktifkan_tahun_internal(tahun):
    AcademicYear.objects.update(aktif=False)
    tahun.aktif = True
    tahun.save(update_fields=['aktif'])
    semester = tahun.semester_list.order_by('nama').first()
    if semester is None:
        semester = Semester.objects.create(academic_year=tahun, nama='I')
    Semester.objects.update(aktif=False)
    semester.aktif = True
    semester.save(update_fields=['aktif'])
    kelas = tahun.kelas_list.order_by('tingkat', 'nama').first()
    ClassGroup.objects.update(aktif=False)
    if kelas:
        kelas.aktif = True
        kelas.save(update_fields=['aktif'])


def _aktifkan_semester_internal(semester):
    year = semester.academic_year
    AcademicYear.objects.update(aktif=False)
    year.aktif = True
    year.save(update_fields=['aktif'])
    Semester.objects.update(aktif=False)
    semester.aktif = True
    semester.save(update_fields=['aktif'])
    kelas = ClassGroup.objects.filter(academic_year=year, aktif=True).first()
    if kelas is None:
        kelas = year.kelas_list.order_by('tingkat', 'nama').first()
    ClassGroup.objects.update(aktif=False)
    if kelas:
        kelas.aktif = True
        kelas.save(update_fields=['aktif'])


@login_required
@admin_required
def tahun_list(request):
    tahun_qs = AcademicYear.objects.prefetch_related('semester_list', 'kelas_list')
    q = _q(request)
    status = request.GET.get('status') or ''
    if q:
        tahun_qs = tahun_qs.filter(tahun__icontains=q)
    if status == 'aktif':
        tahun_qs = tahun_qs.filter(aktif=True)
    elif status == 'nonaktif':
        tahun_qs = tahun_qs.filter(aktif=False)
    page_obj = _paginate(request, tahun_qs)
    rows = []
    for tahun in page_obj:
        rows.append({
            'tahun': tahun,
            'semesters': tahun.semester_list.all(),
            'classes': tahun.kelas_list.all(),
            'jumlah_siswa': Student.objects.filter(
                enrollments__academic_year=tahun
            ).distinct().count(),
            'jumlah_tp': LearningObjective.objects.filter(academic_year=tahun).count(),
            'jumlah_formatif': FormativeScore.objects.filter(
                semester__academic_year=tahun
            ).count(),
            'jumlah_sumatif': SummativeScore.objects.filter(
                semester__academic_year=tahun
            ).count(),
            'jumlah_catatan': HomeroomNote.objects.filter(
                semester__academic_year=tahun
            ).count(),
            'jumlah_ekskul': Extracurricular.objects.filter(
                semester__academic_year=tahun
            ).count(),
            'jumlah_eval_formatif': EvaluasiFormatif.objects.filter(
                subject__academic_year=tahun
            ).count(),
            'jumlah_eval_sumatif': EvaluasiSumatif.objects.filter(
                subject__academic_year=tahun
            ).count(),
        })
    return render(request, 'akademik/tahun_list.html', {
        'rows': rows,
        'page_obj': page_obj,
        'q': q,
        'status_filter': status,
    })


@login_required
@admin_required
def tahun_form(request, pk=None):
    tahun = get_object_or_404(AcademicYear, pk=pk) if pk else None
    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=tahun)
        if form.is_valid():
            obj = form.save()
            if not AcademicYear.objects.filter(aktif=True).exists():
                _aktifkan_tahun_internal(obj)
            messages.success(request, f'Tahun pelajaran {obj.tahun} disimpan.')
            return redirect('akademik:tahun_list')
    else:
        form = AcademicYearForm(instance=tahun)
    return render(request, 'akademik/tahun_form.html', {'form': form, 'tahun': tahun})


@login_required
@admin_required
def tahun_hapus(request, pk):
    tahun = get_object_or_404(AcademicYear, pk=pk)
    if request.method == 'POST':
        if tahun.aktif:
            messages.error(request, 'Tahun pelajaran aktif tidak dapat dihapus.')
        elif tahun.kelas_list.exists() or tahun.semester_list.exists():
            messages.error(request, 'Hapus semester dan kelas pada tahun ini terlebih dahulu.')
        else:
            nama = tahun.tahun
            tahun.delete()
            messages.success(request, f'Tahun pelajaran {nama} dihapus.')
    return redirect('akademik:tahun_list')


@login_required
@admin_required
def tahun_aktifkan(request, pk):
    tahun = get_object_or_404(AcademicYear, pk=pk)
    if request.method == 'POST':
        _aktifkan_tahun_internal(tahun)
        messages.success(request, f'Tahun pelajaran {tahun.tahun} diaktifkan.')
    return redirect('akademik:tahun_list')


@login_required
@admin_required
def semester_form(request, pk=None):
    semester = get_object_or_404(Semester, pk=pk) if pk else None
    if request.method == 'POST':
        form = SemesterForm(request.POST, instance=semester)
        if form.is_valid():
            obj = form.save()
            if not Semester.objects.filter(aktif=True).exists():
                _aktifkan_semester_internal(obj)
            messages.success(request, f'Semester {obj.nama} {obj.academic_year.tahun} disimpan.')
            return redirect('akademik:tahun_list')
    else:
        initial = {}
        tahun_id = request.GET.get('tahun')
        if tahun_id:
            initial['academic_year'] = tahun_id
        form = SemesterForm(instance=semester, initial=initial)
    return render(request, 'akademik/semester_form.html', {'form': form, 'semester': semester})


@login_required
@admin_required
def semester_hapus(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    if request.method == 'POST':
        if semester.aktif:
            messages.error(request, 'Semester aktif tidak dapat dihapus.')
        elif (
            semester.nilai_sumatif.exists()
            or semester.nilai_lm.exists()
            or semester.nilai_formatif.exists()
            or semester.catatan.exists()
            or semester.ekstrakurikuler.exists()
        ):
            messages.error(request, 'Semester ini sudah memiliki data nilai/catatan. Aktifkan semester lain atau hapus datanya terlebih dahulu.')
        else:
            nama = f'{semester.nama} {semester.academic_year.tahun}'
            semester.delete()
            messages.success(request, f'Semester {nama} dihapus.')
    return redirect('akademik:tahun_list')


@login_required
@admin_required
def semester_aktifkan(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    if request.method == 'POST':
        _aktifkan_semester_internal(semester)
        messages.success(request, f'Semester {semester.nama} {semester.academic_year.tahun} diaktifkan.')
    return redirect('akademik:tahun_list')


@login_required
@admin_required
def kelas_form(request, pk=None):
    kelas = get_object_or_404(ClassGroup, pk=pk) if pk else None
    if request.method == 'POST':
        form = ClassGroupForm(request.POST, instance=kelas)
        if form.is_valid():
            obj = form.save()
            if not ClassGroup.objects.filter(aktif=True).exists():
                _aktifkan_kelas_internal(obj)
            messages.success(request, f'Kelas {obj.nama_lengkap} disimpan.')
            return redirect('akademik:tahun_list')
    else:
        initial = {}
        tahun_id = request.GET.get('tahun')
        if tahun_id:
            initial['academic_year'] = tahun_id
        form = ClassGroupForm(instance=kelas, initial=initial)
    return render(request, 'akademik/kelas_form.html', {'form': form, 'kelas': kelas})


@login_required
@admin_required
def kelas_hapus(request, pk):
    kelas = get_object_or_404(ClassGroup, pk=pk)
    if request.method == 'POST':
        if kelas.aktif:
            messages.error(request, 'Kelas aktif tidak dapat dihapus.')
        elif (
            kelas.siswa_list.exists()
            or kelas.enrollments.exists()
            or kelas.penugasan.exists()
        ):
            messages.error(request, 'Kelas memiliki data siswa atau pembagian mengajar. Hapus datanya terlebih dahulu.')
        else:
            nama = kelas.nama_lengkap
            try:
                kelas.delete()
            except ProtectedError:
                messages.error(request, 'Kelas masih dirujuk riwayat penempatan siswa.')
            else:
                messages.success(request, f'Kelas {nama} dihapus.')
    return redirect('akademik:tahun_list')


@login_required
@admin_required
def kelas_aktifkan(request, pk):
    kelas = get_object_or_404(ClassGroup, pk=pk)
    if request.method == 'POST':
        _aktifkan_kelas_internal(kelas)
        messages.success(request, f'Kelas {kelas.nama_lengkap} diaktifkan.')
    return redirect('akademik:tahun_list')


def _subject_context(request):
    subject_id = request.GET.get('mapel') or request.POST.get('mapel')
    if not subject_id:
        return None
    return get_object_or_404(Subject, pk=subject_id)


def _boleh_ekspor_impor(request, kind, subject=None):
    if kind in ('siswa', 'guru', 'mapel', 'kelas'):
        return is_admin(request.user)
    if kind in ('tp', 'formatif', 'sumatif', 'cp', 'materi', 'tugas'):
        return subject is not None and boleh_kelola_mapel(request.user, subject)
    if kind in ('catatan', 'ekskul'):
        return can_manage_homeroom(request.user, _kelas())
    if kind == 'leger':
        return can_view_reports(request.user)
    return False


def _kembali_ekspor_impor(kind, subject=None):
    if kind == 'siswa':
        return reverse('akademik:siswa_list')
    if kind == 'guru':
        return reverse('akademik:guru_list')
    if kind == 'mapel':
        return reverse('akademik:mapel_list')
    if kind == 'kelas':
        return reverse('akademik:tahun_list')
    if kind == 'tp':
        return reverse('akademik:tp_list', args=[subject.id])
    if kind == 'cp':
        return reverse('akademik:cp_list', args=[subject.id])
    if kind == 'materi':
        return reverse('akademik:materi_list', args=[subject.id])
    if kind == 'tugas':
        return reverse('akademik:tugas_pembelajaran_list', args=[subject.id])
    if kind == 'formatif':
        return reverse('akademik:formatif_entry', args=[subject.id])
    if kind == 'sumatif':
        return reverse('akademik:sumatif_entry', args=[subject.id])
    if kind == 'catatan':
        return reverse('akademik:catatan_entry')
    if kind == 'ekskul':
        return reverse('akademik:ekskul_entry')
    return reverse('akademik:leger')


@login_required
def ekspor_data(request, kind):
    from . import excel_io

    if kind not in excel_io.KIND_INFO:
        messages.error(request, 'Jenis ekspor tidak dikenal.')
        return redirect('akademik:dashboard')
    subject = _subject_context(request)
    if not _boleh_ekspor_impor(request, kind, subject):
        return _tolak_halaman(request)
    if excel_io.KIND_INFO[kind]['mapel'] and subject is None:
        messages.error(request, 'Pilih mata pelajaran terlebih dahulu.')
        return redirect('akademik:dashboard')

    kelas = _kelas()
    semester = _semester()
    tahun = semester.academic_year if semester else None
    template = request.GET.get('template') == '1'

    if kind == 'siswa':
        return excel_io.export_siswa(kelas, template)
    if kind == 'guru':
        return excel_io.export_guru(kelas, template)
    if kind == 'mapel':
        tahun_id = request.GET.get('tahun')
        if tahun_id:
            tahun = AcademicYear.objects.filter(pk=tahun_id).first() or tahun
        return excel_io.export_mapel(kelas, tahun, template)
    if kind == 'kelas':
        tahun_id = request.GET.get('tahun')
        if tahun_id:
            tahun = AcademicYear.objects.filter(pk=tahun_id).first() or tahun
        return excel_io.export_kelas(tahun, template)
    if kind == 'tp':
        return excel_io.export_tp(subject, tahun, template)
    if kind == 'cp':
        return excel_io.export_cp(subject, template)
    if kind == 'materi':
        return excel_io.export_materi(subject, template)
    if kind == 'tugas':
        return excel_io.export_tugas(subject, template)
    if kind == 'formatif':
        return excel_io.export_formatif(subject, semester, kelas, template)
    if kind == 'sumatif':
        return excel_io.export_sumatif(subject, semester, kelas, template)
    if kind == 'catatan':
        return excel_io.export_catatan(kelas, semester, template)
    if kind == 'ekskul':
        return excel_io.export_ekskul(kelas, semester, template)
    if kind == 'leger':
        return excel_io.export_leger(kelas, semester)
    return redirect('akademik:dashboard')


@login_required
def impor_data(request, kind):
    from . import excel_io

    info = excel_io.KIND_INFO.get(kind)
    if info is None or not info['import']:
        messages.error(request, 'Jenis impor tidak tersedia.')
        return redirect('akademik:dashboard')
    subject = _subject_context(request)
    if not _boleh_ekspor_impor(request, kind, subject):
        return _tolak_halaman(request)
    if info['mapel'] and subject is None:
        messages.error(request, 'Pilih mata pelajaran terlebih dahulu.')
        return redirect('akademik:dashboard')

    kelas = _kelas()
    semester = _semester()
    tahun = semester.academic_year if semester else None
    tahun_id = request.GET.get('tahun') or request.POST.get('tahun')
    if tahun_id:
        tahun = AcademicYear.objects.filter(pk=tahun_id).first() or tahun
    wali = get_teacher(request.user) or (kelas.wali_kelas_guru if kelas else None)
    back = _kembali_ekspor_impor(kind, subject)
    params = []
    if subject:
        params.append(f'mapel={subject.id}')
    if kind == 'kelas' and tahun:
        params.append(f'tahun={tahun.id}')
    query = ('?' + '&'.join(params)) if params else '?'
    ctx = {
        'info': info,
        'kind': kind,
        'subject': subject,
        'kelas': kelas,
        'semester': semester,
        'tahun': tahun,
        'back_url': back,
        'template_url': reverse('akademik:ekspor', args=[kind]) + query + ('&' if params else '') + 'template=1',
    }

    if request.method == 'POST':
        if kind in ('formatif', 'sumatif', 'catatan', 'ekskul') and _kelas_terkunci(kelas, semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(back)
        file_obj = request.FILES.get('file')
        if not file_obj:
            messages.error(request, 'Pilih file Excel yang akan diimpor.')
            return render(request, 'akademik/import_data.html', ctx)
        if not file_obj.name.lower().endswith(('.xlsx', '.xlsm')):
            messages.error(request, 'File harus berformat .xlsx.')
            return render(request, 'akademik/import_data.html', ctx)
        if kind == 'kelas':
            if tahun is None:
                messages.error(request, 'Pilih tahun pelajaran terlebih dahulu.')
                return redirect('akademik:tahun_list')
        elif kind != 'guru' and (semester is None or kelas is None):
            messages.error(request, 'Lengkapi pengaturan tahun pelajaran dan kelas terlebih dahulu.')
            return redirect('akademik:tahun_list')

        guru_mapel = guru_penilai(request.user, subject) if subject else None
        try:
            if kind == 'siswa':
                hasil = excel_io.import_siswa(file_obj, kelas)
            elif kind == 'guru':
                hasil = excel_io.import_guru(file_obj, kelas, tahun)
            elif kind == 'mapel':
                hasil = excel_io.import_mapel(file_obj, kelas, tahun)
            elif kind == 'kelas':
                hasil = excel_io.import_kelas(file_obj, tahun)
            elif kind == 'tp':
                hasil = excel_io.import_tp(file_obj, subject, tahun, guru_mapel)
            elif kind == 'cp':
                hasil = excel_io.import_cp(file_obj, subject)
            elif kind == 'materi':
                hasil = excel_io.import_materi(file_obj, subject)
            elif kind == 'tugas':
                hasil = excel_io.import_tugas(file_obj, subject)
            elif kind == 'formatif':
                hasil = excel_io.import_formatif(file_obj, subject, semester, kelas, guru_mapel)
            elif kind == 'sumatif':
                hasil = excel_io.import_sumatif(file_obj, subject, semester, kelas, guru_mapel)
            elif kind == 'catatan':
                hasil = excel_io.import_catatan(file_obj, kelas, semester, wali)
            else:
                hasil = excel_io.import_ekskul(file_obj, kelas, semester, wali)
        except excel_io.ExcelImportError as exc:
            for pesan in exc.errors[:8]:
                messages.error(request, pesan)
            if len(exc.errors) > 8:
                messages.error(request, f'... dan {len(exc.errors) - 8} kesalahan lainnya.')
            return redirect(back)

        ringkas = ', '.join(f'{k}: {v}' for k, v in hasil.items())
        messages.success(request, f'Impor {info["judul"]} selesai. {ringkas}.')
        return redirect(back)

    return render(request, 'akademik/import_data.html', ctx)


# ---------------- Tujuan Pembelajaran & Evaluasi (daftar/CRUD) ----------------

def _tahun_aktif():
    semester = _semester()
    return semester.academic_year if semester else AcademicYear.get_aktif()


def _mapel_boleh(user):
    return mapel_untuk_user(user)


def _mapel_dalam_queryset(user, subject):
    return _mapel_boleh(user).filter(pk=subject.pk).exists()


@login_required
def tugas_list(request, subject_id=None):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    mapel_filter = ''
    if subject_id:
        subject = get_object_or_404(allowed, pk=subject_id)
        mapel_filter = str(subject.id)
    else:
        mapel_filter = request.GET.get('mapel') or ''
    q = _q(request)
    status = request.GET.get('status') or 'aktif'
    qs = LearningObjective.objects.filter(
        academic_year=tahun, subject__in=allowed
    ).select_related('subject', 'guru')
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if q:
        qs = qs.filter(
            Q(deskripsi__icontains=q)
        )
    if status == 'aktif':
        qs = qs.filter(aktif=True)
    elif status == 'arsip':
        qs = qs.filter(aktif=False)
    page_obj = _paginate(request, qs.order_by('subject__urutan', 'nomor'))

    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        if aksi in ('hapus', 'aktifkan'):
            tp = get_object_or_404(LearningObjective, pk=request.POST.get('tp_id'))
            if tp.academic_year_id != (tahun.id if tahun else None) or not _mapel_dalam_queryset(
                request.user, tp.subject
            ):
                return _tolak_mapel(request)
            if aksi == 'aktifkan':
                tp.aktif = True
                tp.save(update_fields=['aktif'])
                messages.success(request, 'Tujuan pembelajaran diaktifkan kembali.')
            elif tp.nilai_formatif.exists():
                tp.aktif = False
                tp.save(update_fields=['aktif'])
                messages.success(
                    request,
                    'TP memiliki nilai sehingga diarsipkan, bukan dihapus.',
                )
            else:
                tp.delete()
                messages.success(request, 'Tujuan pembelajaran dihapus.')
            return redirect(request.get_full_path())

    return render(request, 'akademik/tp_list.html', {
        'objectives': page_obj,
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed.annotate(
            jumlah_tugas=Count(
                'tujuan_list',
                filter=Q(tujuan_list__academic_year=tahun),
            )
        ),
        'mapel_filter': mapel_filter,
        'q': q,
        'status_filter': status,
        'tahun': tahun,
    })


@login_required
def tugas_form(request, pk=None):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    instance = get_object_or_404(LearningObjective, pk=pk) if pk else None
    if instance and (
        instance.academic_year_id != (tahun.id if tahun else None)
        or not _mapel_dalam_queryset(request.user, instance.subject)
    ):
        return _tolak_mapel(request)

    if request.method == 'POST':
        form = TujuanPembelajaranForm(request.POST, instance=instance)
        form.fields['subject'].queryset = allowed
        if form.is_valid():
            subject = form.cleaned_data['subject']
            if not _mapel_dalam_queryset(request.user, subject):
                return _tolak_mapel(request)
            obj = form.save(commit=False)
            obj.academic_year = subject.academic_year
            if not obj.nomor:
                obj.nomor = (
                    LearningObjective.objects.filter(
                        subject=subject, academic_year=subject.academic_year
                    ).order_by('-nomor').values_list('nomor', flat=True).first()
                    or 0
                ) + 1
            bentrok = LearningObjective.objects.filter(
                subject=subject,
                academic_year=subject.academic_year,
                nomor=obj.nomor,
            ).exclude(pk=obj.pk)
            if bentrok.exists():
                form.add_error('nomor', 'Nomor tugas sudah dipakai pada mapel ini.')
            else:
                if not obj.guru_id:
                    obj.guru = guru_penilai(request.user, subject)
                obj.save()
                messages.success(request, 'Tujuan pembelajaran disimpan.')
                return redirect(f"{reverse('akademik:tp_menu')}?mapel={subject.id}")
    else:
        initial = {}
        mapel_id = request.GET.get('mapel')
        if mapel_id:
            subject = allowed.filter(pk=mapel_id).first()
            if subject:
                initial['subject'] = subject
                initial['guru'] = guru_penilai(request.user, subject)
        form = TujuanPembelajaranForm(instance=instance, initial=initial)
        form.fields['subject'].queryset = allowed
    return render(request, 'akademik/tp_form.html', {
        'form': form,
        'tugas': instance,
        'tahun': tahun,
    })


# ---------------- Capaian Pembelajaran (CP) ----------------

def _filter_mapel_dari_request(request, subject_id=None):
    """Kembalikan (allowed_subjects, subject_terpilih, mapel_filter)."""
    allowed = _mapel_boleh(request.user)
    subject = None
    if subject_id:
        subject = get_object_or_404(allowed, pk=subject_id)
    mapel_filter = str(subject.id) if subject else (request.GET.get('mapel') or '')
    if subject is None and mapel_filter:
        if str(mapel_filter).isdigit():
            subject = allowed.filter(pk=mapel_filter).first()
        else:
            mapel_filter = ''
    return allowed, subject, mapel_filter


def _status_filter_qs(qs, status):
    if status == 'aktif':
        return qs.filter(aktif=True)
    if status == 'arsip':
        return qs.filter(aktif=False)
    return qs


@login_required
def cp_list(request, subject_id=None):
    tahun = _tahun_aktif()
    allowed, subject, mapel_filter = _filter_mapel_dari_request(request, subject_id)
    if subject is not None:
        tahun = subject.academic_year
    q = _q(request)
    status = request.GET.get('status') or 'aktif'
    qs = LearningOutcome.objects.filter(subject__in=allowed).select_related('subject')
    if tahun:
        qs = qs.filter(subject__academic_year=tahun)
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if q:
        qs = qs.filter(Q(kode__icontains=q) | Q(deskripsi__icontains=q))
    qs = _status_filter_qs(qs, status)
    page_obj = _paginate(request, qs.order_by('subject__urutan', 'urutan', 'kode'))

    if request.method == 'POST':
        aksi = request.POST.get('aksi', '')
        cp = get_object_or_404(
            LearningOutcome, pk=request.POST.get('cp_id'),
            subject__in=allowed,
        )
        if aksi == 'aktifkan':
            cp.aktif = True
            cp.save(update_fields=['aktif'])
            messages.success(request, 'Capaian pembelajaran diaktifkan kembali.')
        elif aksi == 'hapus':
            if cp.tujuan_list.exists():
                cp.aktif = False
                cp.save(update_fields=['aktif'])
                messages.success(
                    request,
                    'CP masih dipakai TP sehingga diarsipkan, bukan dihapus.',
                )
            else:
                cp.delete()
                messages.success(request, 'Capaian pembelajaran dihapus.')
        return redirect(request.get_full_path())

    return render(request, 'akademik/cp_list.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed.annotate(
            jumlah_cp=Count('capaian_list', filter=Q(capaian_list__aktif=True))
        ),
        'subject': subject,
        'mapel_filter': mapel_filter,
        'q': q,
        'status_filter': status,
        'tahun': tahun,
        'active_tab': 'cp',
    })


@login_required
def cp_form(request, pk=None):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    instance = None
    if pk:
        instance = get_object_or_404(LearningOutcome, pk=pk)
        if not allowed.filter(pk=instance.subject_id).exists():
            return _tolak_mapel(request)
        tahun = instance.subject.academic_year

    if request.method == 'POST':
        form = CapaianPembelajaranForm(request.POST, instance=instance)
        form.fields['subject'].queryset = allowed
        if form.is_valid():
            subject = form.cleaned_data['subject']
            if not allowed.filter(pk=subject.pk).exists():
                return _tolak_mapel(request)
            obj = form.save(commit=False)
            obj.subject = subject
            if not obj.urutan:
                if instance is not None and instance.urutan:
                    obj.urutan = instance.urutan
                else:
                    obj.urutan = (
                        LearningOutcome.objects.filter(subject=subject)
                        .exclude(pk=obj.pk)
                        .order_by('-urutan').values_list('urutan', flat=True).first()
                        or 0
                    ) + 1
            obj.save()
            messages.success(request, 'Capaian pembelajaran disimpan.')
            return redirect('akademik:cp_list', subject_id=subject.id)
    else:
        initial = {}
        mapel_id = request.GET.get('mapel')
        if mapel_id:
            subject = allowed.filter(pk=mapel_id).first()
            if subject:
                initial['subject'] = subject
                kelas_awal = ClassGroup.objects.filter(
                    academic_year=subject.academic_year
                ).first()
                initial['fase'] = kelas_awal.fase if kelas_awal else 'D'
        form = CapaianPembelajaranForm(instance=instance, initial=initial)
        form.fields['subject'].queryset = allowed
    return render(request, 'akademik/cp_form.html', {
        'form': form,
        'cp': instance,
        'tahun': tahun,
    })


# ---------------- Materi Pembelajaran ----------------

@login_required
def materi_list(request, subject_id=None):
    tahun = _tahun_aktif()
    allowed, subject, mapel_filter = _filter_mapel_dari_request(request, subject_id)
    if subject is not None:
        tahun = subject.academic_year
    q = _q(request)
    status = request.GET.get('status') or 'aktif'
    qs = LearningMaterial.objects.filter(subject__in=allowed).select_related('subject')
    if tahun:
        qs = qs.filter(subject__academic_year=tahun)
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if q:
        qs = qs.filter(
            Q(kode__icontains=q) | Q(judul__icontains=q) | Q(deskripsi__icontains=q)
        )
    qs = _status_filter_qs(qs, status).prefetch_related('objectives')
    page_obj = _paginate(request, qs.order_by('subject__urutan', 'urutan', 'judul'))

    if request.method == 'POST':
        aksi = request.POST.get('aksi', '')
        materi = get_object_or_404(
            LearningMaterial, pk=request.POST.get('materi_id'),
            subject__in=allowed,
        )
        if aksi == 'aktifkan':
            materi.aktif = True
            materi.save(update_fields=['aktif'])
            messages.success(request, 'Materi diaktifkan kembali.')
        elif aksi == 'hapus':
            materi.delete()
            messages.success(request, 'Materi pembelajaran dihapus.')
        return redirect(request.get_full_path())

    return render(request, 'akademik/materi_list.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed.annotate(
            jumlah_materi=Count('materi_list', filter=Q(materi_list__aktif=True))
        ),
        'subject': subject,
        'mapel_filter': mapel_filter,
        'q': q,
        'status_filter': status,
        'tahun': tahun,
        'active_tab': 'materi',
    })


@login_required
def materi_form(request, pk=None):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    instance = None
    if pk:
        instance = get_object_or_404(LearningMaterial, pk=pk)
        if not allowed.filter(pk=instance.subject_id).exists():
            return _tolak_mapel(request)
        tahun = instance.subject.academic_year

    if request.method == 'POST':
        form = MateriPembelajaranForm(request.POST, instance=instance)
        form.fields['subject'].queryset = allowed
        form.fields['objectives'].queryset = LearningObjective.objects.filter(
            subject__in=allowed, aktif=True
        ).select_related('subject')
        if form.is_valid():
            subject = form.cleaned_data['subject']
            if not allowed.filter(pk=subject.pk).exists():
                return _tolak_mapel(request)
            obj = form.save(commit=False)
            obj.subject = subject
            if not obj.urutan:
                if instance is not None and instance.urutan:
                    obj.urutan = instance.urutan
                else:
                    obj.urutan = (
                        LearningMaterial.objects.filter(subject=subject)
                        .exclude(pk=obj.pk)
                        .order_by('-urutan').values_list('urutan', flat=True).first()
                        or 0
                    ) + 1
            obj.save()
            form.save_m2m()
            messages.success(request, 'Materi pembelajaran disimpan.')
            return redirect('akademik:materi_list', subject_id=subject.id)
    else:
        initial = {}
        mapel_id = request.GET.get('mapel')
        if mapel_id:
            subject = allowed.filter(pk=mapel_id).first()
            if subject:
                initial['subject'] = subject
        form = MateriPembelajaranForm(instance=instance, initial=initial)
        form.fields['subject'].queryset = allowed
        form.fields['objectives'].queryset = LearningObjective.objects.filter(
            subject__in=allowed, aktif=True
        ).select_related('subject')
    return render(request, 'akademik/materi_form.html', {
        'form': form,
        'materi': instance,
        'tahun': tahun,
    })


# ---------------- Tugas Pembelajaran ----------------

@login_required
def tugas_pembelajaran_list(request, subject_id=None):
    tahun = _tahun_aktif()
    allowed, subject, mapel_filter = _filter_mapel_dari_request(request, subject_id)
    if subject is not None:
        tahun = subject.academic_year
    q = _q(request)
    status = request.GET.get('status') or ''
    qs = LearningTask.objects.filter(subject__in=allowed).select_related(
        'subject', 'created_by'
    ).prefetch_related('class_groups', 'objectives')
    if tahun:
        qs = qs.filter(academic_year=tahun)
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if q:
        qs = qs.filter(
            Q(judul__icontains=q) | Q(deskripsi__icontains=q)
            | Q(instruksi__icontains=q)
        )
    if status in ('DRAF', 'TERBIT', 'TUTUP'):
        qs = qs.filter(status=status)
    page_obj = _paginate(request, qs)

    if request.method == 'POST':
        aksi = request.POST.get('aksi', '')
        tugas = get_object_or_404(
            LearningTask, pk=request.POST.get('tugas_id'), subject__in=allowed,
        )
        if aksi == 'hapus':
            if tugas.submissions.exists():
                messages.error(
                    request,
                    'Tugas sudah memiliki pengumpulan/nilai. Tutup tugas saja, '
                    'jangan dihapus.',
                )
            else:
                tugas.delete()
                messages.success(request, 'Tugas pembelajaran dihapus.')
        elif aksi in ('DRAF', 'TERBIT', 'TUTUP'):
            tugas.status = aksi
            tugas.save(update_fields=['status'])
            messages.success(request, f'Status tugas diubah menjadi {tugas.get_status_display()}.')
        return redirect(request.get_full_path())

    return render(request, 'akademik/tugas_list.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed.annotate(
            jumlah_tugas=Count('tugas_pembelajaran', filter=Q(tugas_pembelajaran__academic_year=tahun))
        ),
        'subject': subject,
        'mapel_filter': mapel_filter,
        'q': q,
        'status_filter': status,
        'tahun': tahun,
        'active_tab': 'tugas',
        'status_choices': LearningTask.STATUS,
    })


@login_required
def tugas_pembelajaran_form(request, pk=None):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    instance = None
    if pk:
        instance = get_object_or_404(LearningTask, pk=pk)
        if not allowed.filter(pk=instance.subject_id).exists():
            return _tolak_mapel(request)
        tahun = instance.academic_year

    def siapkan_pilihan(form):
        form.fields['subject'].queryset = allowed
        form.fields['class_groups'].queryset = ClassGroup.objects.filter(
            academic_year=tahun
        ).order_by('tingkat', 'nama') if tahun else ClassGroup.objects.none()
        form.fields['objectives'].queryset = LearningObjective.objects.filter(
            subject__in=allowed, academic_year=tahun, aktif=True
        ).select_related('subject').order_by('subject__urutan', 'nomor')

    if request.method == 'POST':
        form = TugasPembelajaranForm(request.POST, request.FILES, instance=instance)
        siapkan_pilihan(form)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            if not allowed.filter(pk=subject.pk).exists():
                return _tolak_mapel(request)
            if subject.academic_year_id != (tahun.id if tahun else None):
                form.add_error('subject', 'Mapel tidak berada pada tahun pelajaran aktif.')
            else:
                obj = form.save(commit=False)
                obj.subject = subject
                obj.academic_year = subject.academic_year
                if not obj.created_by_id:
                    obj.created_by = guru_penilai(request.user, subject)
                obj.save()
                form.save_m2m()
                messages.success(request, 'Tugas pembelajaran disimpan.')
                return redirect('akademik:tugas_pembelajaran_list', subject_id=subject.id)
    else:
        initial = {}
        mapel_id = request.GET.get('mapel')
        if mapel_id:
            subject = allowed.filter(pk=mapel_id).first()
            if subject:
                initial['subject'] = subject
        form = TugasPembelajaranForm(instance=instance, initial=initial)
        siapkan_pilihan(form)
    return render(request, 'akademik/tugas_form.html', {
        'form': form,
        'tugas': instance,
        'tahun': tahun,
    })


@login_required
def tugas_pembelajaran_detail(request, pk):
    allowed = _mapel_boleh(request.user)
    tugas = get_object_or_404(
        LearningTask.objects.select_related('subject').prefetch_related(
            'class_groups', 'objectives'
        ),
        pk=pk, subject__in=allowed,
    )
    kelas_qs = tugas.class_groups.all()
    if not kelas_qs.exists():
        kelas_qs = ClassGroup.objects.filter(academic_year=tugas.academic_year)
    kelas_id = request.GET.get('kelas') or request.POST.get('kelas')
    if not str(kelas_id or '').isdigit():
        kelas_id = None
    kelas = kelas_qs.filter(pk=kelas_id).first() if kelas_id else None
    if kelas is None:
        kelas = kelas_qs.filter(aktif=True).first() or kelas_qs.first()
    students = (
        Student.objects.in_class(kelas).filter(aktif=True).order_by('no_urut')
        if kelas else Student.objects.none()
    )
    students = list(students)

    if request.method == 'POST':
        jumlah = 0
        with transaction.atomic():
            for siswa in students:
                status = request.POST.get(f'status_{siswa.id}') or 'BELUM'
                nilai = _angka_bulat(request.POST.get(f'nilai_{siswa.id}'))
                berkas = request.FILES.get(f'file_{siswa.id}')
                if nilai is not None and status == 'BELUM':
                    status = 'DINILAI'
                elif berkas and status == 'BELUM':
                    status = 'TERKUMPUL'
                catatan = request.POST.get(f'catatan_{siswa.id}', '').strip()
                hapus_berkas = request.POST.get(f'hapus_file_{siswa.id}')
                if (
                    status == 'BELUM' and nilai is None and not catatan
                    and not berkas and not hapus_berkas
                ):
                    LearningTaskSubmission.objects.filter(
                        task=tugas, student=siswa
                    ).delete()
                    continue
                defaults = {
                    'status': status,
                    'nilai': nilai,
                    'catatan_guru': catatan,
                }
                if status == 'DINILAI' or nilai is not None:
                    defaults['dinilai_oleh'] = guru_penilai(request.user, tugas.subject)
                if berkas:
                    defaults['file'] = berkas
                elif hapus_berkas:
                    defaults['file'] = None
                submission, _ = LearningTaskSubmission.objects.update_or_create(
                    task=tugas, student=siswa, defaults=defaults,
                )
                if submission.status in ('TERKUMPUL', 'TERLAMBAT', 'DINILAI'):
                    if submission.submitted_at is None:
                        submission.submitted_at = timezone.now()
                        submission.save(update_fields=['submitted_at'])
                if submission.status == 'DINILAI' and submission.dinilai_at is None:
                    submission.dinilai_at = timezone.now()
                    submission.save(update_fields=['dinilai_at'])
                jumlah += 1
        messages.success(request, f'Pengumpulan tugas disimpan ({jumlah} siswa).')
        return redirect(request.get_full_path())

    submissions = {
        s.student_id: s for s in LearningTaskSubmission.objects.filter(
            task=tugas, student__in=students
        )
    }
    rows = [{'siswa': siswa, 'pengumpulan': submissions.get(siswa.id)} for siswa in students]
    return render(request, 'akademik/tugas_detail.html', {
        'tugas': tugas,
        'kelas_qs': kelas_qs,
        'kelas': kelas,
        'rows': rows,
        'status_choices': LearningTaskSubmission.STATUS,
    })



# ---------------- Asesmen Generik & Konfigurasi Nilai ----------------

@login_required
def asesmen_list(request):
    tahun = _tahun_aktif()
    semester = _semester()
    allowed = _mapel_boleh(request.user)
    q = _q(request)
    mapel_filter = request.GET.get('mapel') or ''
    kategori = request.GET.get('kategori') or ''
    status = request.GET.get('status') or ''
    qs = Assessment.objects.filter(subject__in=allowed).select_related(
        'subject', 'semester', 'class_group'
    ).prefetch_related('components')
    if semester:
        qs = qs.filter(semester=semester)
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if kategori in dict(Assessment.KATEGORI):
        qs = qs.filter(kategori=kategori)
    if status in dict(Assessment.STATUS):
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(nama__icontains=q) | Q(deskripsi__icontains=q))
    page_obj = _paginate(request, qs)

    if request.method == 'POST':
        asesmen = get_object_or_404(
            Assessment, pk=request.POST.get('asesmen_id'), subject__in=allowed
        )
        aksi = request.POST.get('aksi')
        if aksi == 'hapus':
            if asesmen.components.filter(results__isnull=False).exists():
                asesmen.aktif = False
                asesmen.save(update_fields=['aktif'])
                messages.success(request, 'Asesmen memiliki nilai sehingga diarsipkan.')
            else:
                asesmen.delete()
                messages.success(request, 'Asesmen dihapus.')
        elif aksi == 'aktifkan':
            asesmen.aktif = True
            asesmen.save(update_fields=['aktif'])
        return redirect(request.get_full_path())

    return render(request, 'akademik/asesmen_list.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed,
        'mapel_filter': mapel_filter,
        'kategori_filter': kategori,
        'status_filter': status,
        'kategori_choices': Assessment.KATEGORI,
        'tahun': tahun,
        'semester': semester,
        'q': q,
    })


@login_required
def asesmen_form(request, pk=None):
    allowed = _mapel_boleh(request.user)
    semester = _semester()
    instance = None
    if pk:
        instance = get_object_or_404(Assessment, pk=pk, subject__in=allowed)
        semester = instance.semester

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=instance)
        form.fields['subject'].queryset = allowed
        form.fields['class_group'].queryset = ClassGroup.objects.filter(
            academic_year=semester.academic_year if semester else None
        ) if semester else ClassGroup.objects.none()
        formset = AssessmentComponentFormSet(
            request.POST, instance=instance or Assessment()
        )
        if form.is_valid():
            obj = form.save(commit=False)
            obj.academic_year = obj.subject.academic_year
            obj.semester = semester
            if not obj.created_by_id:
                obj.created_by = guru_penilai(request.user, obj.subject)
            obj.save()
            formset = AssessmentComponentFormSet(request.POST, instance=obj)
            if formset.is_valid():
                formset.save()
                if not obj.components.exists():
                    maksimal = 4 if obj.kategori == 'FORMATIF' else 100
                    AssessmentComponent.objects.create(
                        assessment=obj, nama='Nilai', tipe='NILAI',
                        urutan=1, bobot=100, nilai_maksimal=maksimal,
                    )
                messages.success(request, 'Asesmen disimpan.')
                return redirect('akademik:asesmen_grid', pk=obj.id)
            messages.error(request, 'Periksa komponen asesmen.')
            instance = obj
        else:
            messages.error(request, 'Periksa data asesmen.')
    else:
        form = AssessmentForm(instance=instance)
        form.fields['subject'].queryset = allowed
        form.fields['class_group'].queryset = ClassGroup.objects.filter(
            academic_year=semester.academic_year
        ) if semester else ClassGroup.objects.none()
        formset = AssessmentComponentFormSet(instance=instance)

    return render(request, 'akademik/asesmen_form.html', {
        'form': form,
        'formset': formset,
        'asesmen': instance,
        'semester': semester,
    })


def _kelas_asesmen(asesmen, request):
    if asesmen.class_group_id:
        return asesmen.class_group
    kelas_qs = ClassGroup.objects.filter(academic_year=asesmen.academic_year)
    kelas_id = request.GET.get('kelas') or request.POST.get('kelas')
    if str(kelas_id or '').isdigit():
        kelas = kelas_qs.filter(pk=kelas_id).first()
        if kelas:
            return kelas
    return kelas_qs.filter(aktif=True).first() or kelas_qs.first()


@login_required
def asesmen_grid(request, pk):
    allowed = _mapel_boleh(request.user)
    asesmen = get_object_or_404(
        Assessment.objects.select_related('subject', 'semester', 'class_group'),
        pk=pk, subject__in=allowed,
    )
    kelas = _kelas_asesmen(asesmen, request)
    students = (
        list(Student.objects.in_class(kelas).filter(aktif=True).order_by('no_urut'))
        if kelas else []
    )
    components = list(asesmen.components.all())
    hasil = {}
    for result in AssessmentResult.objects.filter(
        student__in=students, component__in=components
    ):
        hasil[(result.student_id, result.component_id)] = result

    if request.method == 'POST':
        if _kelas_terkunci(kelas, asesmen.semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(request.get_full_path())
        jumlah = 0
        with transaction.atomic():
            for siswa in students:
                for component in components:
                    raw = request.POST.get(f'n_{siswa.id}_{component.id}')
                    nilai = _angka_bulat(raw, 0, float(component.nilai_maksimal))
                    if raw in (None, ''):
                        AssessmentResult.objects.filter(
                            student=siswa, component=component
                        ).delete()
                        continue
                    if nilai is None:
                        continue
                    AssessmentResult.objects.update_or_create(
                        student=siswa, component=component,
                        defaults={
                            'nilai': nilai,
                            'dinilai_oleh': get_teacher(request.user)
                            or guru_penilai(request.user, asesmen.subject),
                        },
                    )
                    jumlah += 1
        messages.success(request, f'Nilai asesmen disimpan ({jumlah} nilai).')
        return redirect(request.get_full_path())

    rows = [
        {
            'siswa': siswa,
            'nilai': [
                {'component': component, 'hasil': hasil.get((siswa.id, component.id))}
                for component in components
            ],
        }
        for siswa in students
    ]
    kelas_qs = ClassGroup.objects.filter(academic_year=asesmen.academic_year)
    return render(request, 'akademik/asesmen_grid.html', {
        'asesmen': asesmen,
        'components': components,
        'rows': rows,
        'kelas': kelas,
        'kelas_qs': kelas_qs,
        'semester': asesmen.semester,
    })


@login_required
def asesmen_simpan(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST diperlukan.'}, status=405)
    allowed = _mapel_boleh(request.user)
    asesmen = get_object_or_404(Assessment, pk=pk, subject__in=allowed)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Data tidak valid.'}, status=400)
    component = asesmen.components.filter(pk=data.get('component')).first()
    student = Student.objects.filter(pk=data.get('student')).first()
    if component is None or student is None:
        return JsonResponse({'ok': False, 'error': 'Komponen/siswa tidak ditemukan.'}, status=404)
    if not student.enrollments.filter(academic_year=asesmen.academic_year).exists():
        return JsonResponse(
            {'ok': False, 'error': 'Siswa tidak terdaftar pada tahun asesmen.'}, status=400
        )
    if ReportCard.objects.filter(
        student=student, semester=asesmen.semester, status='PUBLISHED'
    ).exists():
        return JsonResponse(
            {'ok': False, 'error': 'Rapor siswa sudah terbit dan terkunci.'}, status=403
        )
    raw = data.get('nilai')
    if raw in (None, ''):
        AssessmentResult.objects.filter(component=component, student=student).delete()
        return JsonResponse({'ok': True, 'nilai': None})
    try:
        nilai = Decimal(str(raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return JsonResponse({'ok': False, 'error': 'Nilai tidak valid.'}, status=400)
    if nilai < 0 or nilai > component.nilai_maksimal:
        return JsonResponse(
            {'ok': False, 'error': f'Nilai harus 0-{component.nilai_maksimal}.'},
            status=400,
        )
    AssessmentResult.objects.update_or_create(
        component=component, student=student,
        defaults={
            'nilai': nilai,
            'dinilai_oleh': get_teacher(request.user)
            or guru_penilai(request.user, asesmen.subject),
        },
    )
    return JsonResponse({'ok': True, 'nilai': str(nilai)})


@login_required
def asesmen_ekspor(request, pk):
    from . import excel_io

    allowed = _mapel_boleh(request.user)
    asesmen = get_object_or_404(Assessment, pk=pk, subject__in=allowed)
    kelas = _kelas_asesmen(asesmen, request)
    return excel_io.export_asesmen(asesmen, kelas)


@login_required
def asesmen_impor(request, pk):
    from . import excel_io

    allowed = _mapel_boleh(request.user)
    asesmen = get_object_or_404(Assessment, pk=pk, subject__in=allowed)
    kelas = _kelas_asesmen(asesmen, request)
    if request.method == 'POST':
        if _kelas_terkunci(kelas, asesmen.semester):
            messages.error(request, 'Rapor kelas ini sudah terbit dan terkunci.')
            return redirect(f"{reverse('akademik:asesmen_grid', args=[asesmen.id])}?kelas={kelas.id if kelas else ''}")
        file_obj = request.FILES.get('file')
        if not file_obj:
            messages.error(request, 'Pilih file Excel.')
        elif not file_obj.name.lower().endswith(('.xlsx', '.xlsm')):
            messages.error(request, 'File harus berformat .xlsx.')
        else:
            try:
                hasil = excel_io.import_asesmen(file_obj, asesmen, kelas)
            except excel_io.ExcelImportError as exc:
                for pesan in exc.errors[:8]:
                    messages.error(request, pesan)
            else:
                messages.success(
                    request, f"Nilai asesmen diimpor ({hasil['diperbarui']} sel)."
                )
        return redirect(f"{reverse('akademik:asesmen_grid', args=[asesmen.id])}?kelas={kelas.id if kelas else ''}")
    return render(request, 'akademik/asesmen_impor.html', {
        'asesmen': asesmen,
        'kelas': kelas,
    })


@login_required
@admin_required
def konfigurasi_nilai_view(request):
    konfigurasi = GradeConfiguration.get_config()
    tahun_id = request.GET.get('tahun')
    mapel_id = request.GET.get('mapel')
    tahun = AcademicYear.objects.filter(pk=tahun_id).first() if str(tahun_id or '').isdigit() else None
    mapel = Subject.objects.filter(pk=mapel_id).first() if str(mapel_id or '').isdigit() else None
    if tahun or mapel:
        konfigurasi = (
            GradeConfiguration.objects.filter(
                academic_year=tahun, subject=mapel, aktif=True
            ).first()
            or GradeConfiguration(academic_year=tahun, subject=mapel)
        )
    if request.method == 'POST':
        form = GradeConfigurationForm(request.POST, instance=konfigurasi)
        if form.is_valid():
            obj = form.save()
            catat_audit(
                request.user, 'UPDATE', obj,
                deskripsi='Perbarui konfigurasi nilai', request=request,
            )
            messages.success(request, 'Konfigurasi nilai disimpan.')
            return redirect('akademik:konfigurasi_nilai')
        messages.error(request, 'Periksa konfigurasi nilai.')
    else:
        form = GradeConfigurationForm(instance=konfigurasi)
    return render(request, 'akademik/konfigurasi_nilai.html', {
        'form': form,
        'konfigurasi': konfigurasi,
        'tahun': tahun,
        'mapel': mapel,
        'daftar_tahun': AcademicYear.objects.all(),
        'daftar_mapel': Subject.objects.all(),
    })


@login_required
def evaluasi_formatif_list(request):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    q = _q(request)
    mapel_filter = request.GET.get('mapel') or ''
    jenis = request.GET.get('jenis') or ''
    status = request.GET.get('status') or ''
    qs = EvaluasiFormatif.objects.filter(subject__in=allowed).select_related('subject')
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if q:
        qs = qs.filter(Q(nama__icontains=q) | Q(deskripsi__icontains=q))
    if jenis:
        qs = qs.filter(jenis=jenis)
    if status == 'aktif':
        qs = qs.filter(aktif=True)
    elif status == 'nonaktif':
        qs = qs.filter(aktif=False)
    page_obj = _paginate(request, qs.order_by('subject__urutan', 'nama'))
    return render(request, 'akademik/evaluasi_formatif_list.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed,
        'mapel_filter': mapel_filter,
        'jenis_filter': jenis,
        'status_filter': status,
        'jenis_choices': EvaluasiFormatif.JENIS,
        'q': q,
        'tahun': tahun,
    })


@login_required
def evaluasi_formatif_form(request, pk=None):
    allowed = _mapel_boleh(request.user)
    instance = get_object_or_404(EvaluasiFormatif, pk=pk) if pk else None
    if instance and not _mapel_dalam_queryset(request.user, instance.subject):
        return _tolak_mapel(request)
    if request.method == 'POST':
        form = EvaluasiFormatifForm(request.POST, instance=instance)
        form.fields['subject'].queryset = allowed
        if form.is_valid():
            obj = form.save()
            messages.success(request, 'Evaluasi formatif disimpan.')
            return redirect(f"{reverse('akademik:formatif_menu')}?mapel={obj.subject_id}")
    else:
        initial = {}
        mapel_id = request.GET.get('mapel')
        if mapel_id:
            subject = allowed.filter(pk=mapel_id).first()
            if subject:
                initial['subject'] = subject
        form = EvaluasiFormatifForm(instance=instance, initial=initial)
        form.fields['subject'].queryset = allowed
    return render(request, 'akademik/evaluasi_formatif_form.html', {
        'form': form,
        'evaluasi': instance,
    })


@login_required
def evaluasi_formatif_hapus(request, pk):
    evaluasi = get_object_or_404(EvaluasiFormatif, pk=pk)
    if not _mapel_dalam_queryset(request.user, evaluasi.subject):
        return _tolak_mapel(request)
    if request.method == 'POST':
        nama = evaluasi.nama
        evaluasi.delete()
        messages.success(request, f'Evaluasi formatif "{nama}" dihapus.')
    return redirect('akademik:formatif_menu')


@login_required
def evaluasi_sumatif_list(request):
    tahun = _tahun_aktif()
    allowed = _mapel_boleh(request.user)
    q = _q(request)
    mapel_filter = request.GET.get('mapel') or ''
    jenis = request.GET.get('jenis') or ''
    status = request.GET.get('status') or ''
    qs = EvaluasiSumatif.objects.filter(subject__in=allowed).select_related('subject')
    if mapel_filter:
        qs = qs.filter(subject_id=mapel_filter)
    if q:
        qs = qs.filter(Q(nama__icontains=q) | Q(deskripsi__icontains=q))
    if jenis:
        qs = qs.filter(jenis=jenis)
    if status == 'aktif':
        qs = qs.filter(aktif=True)
    elif status == 'nonaktif':
        qs = qs.filter(aktif=False)
    page_obj = _paginate(request, qs.order_by('subject__urutan', 'nama'))
    return render(request, 'akademik/evaluasi_sumatif_list.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'subjects': allowed,
        'mapel_filter': mapel_filter,
        'jenis_filter': jenis,
        'status_filter': status,
        'jenis_choices': EvaluasiSumatif.JENIS,
        'q': q,
        'tahun': tahun,
    })


@login_required
def evaluasi_sumatif_form(request, pk=None):
    allowed = _mapel_boleh(request.user)
    instance = get_object_or_404(EvaluasiSumatif, pk=pk) if pk else None
    if instance and not _mapel_dalam_queryset(request.user, instance.subject):
        return _tolak_mapel(request)
    if request.method == 'POST':
        form = EvaluasiSumatifForm(request.POST, instance=instance)
        form.fields['subject'].queryset = allowed
        if form.is_valid():
            obj = form.save()
            messages.success(request, 'Evaluasi sumatif disimpan.')
            return redirect(f"{reverse('akademik:sumatif_menu')}?mapel={obj.subject_id}")
    else:
        initial = {}
        mapel_id = request.GET.get('mapel')
        if mapel_id:
            subject = allowed.filter(pk=mapel_id).first()
            if subject:
                initial['subject'] = subject
        form = EvaluasiSumatifForm(instance=instance, initial=initial)
        form.fields['subject'].queryset = allowed
    return render(request, 'akademik/evaluasi_sumatif_form.html', {
        'form': form,
        'evaluasi': instance,
    })


@login_required
def evaluasi_sumatif_hapus(request, pk):
    evaluasi = get_object_or_404(EvaluasiSumatif, pk=pk)
    if not _mapel_dalam_queryset(request.user, evaluasi.subject):
        return _tolak_mapel(request)
    if request.method == 'POST':
        nama = evaluasi.nama
        evaluasi.delete()
        messages.success(request, f'Evaluasi sumatif "{nama}" dihapus.')
    return redirect('akademik:sumatif_menu')


@login_required
@super_admin_required
def audit_log(request):
    q = _q(request)
    aksi = request.GET.get('aksi') or ''
    qs = AuditLog.objects.select_related('user')
    if q:
        qs = qs.filter(
            Q(deskripsi__icontains=q) | Q(model__icontains=q)
            | Q(user__username__icontains=q)
        )
    if aksi:
        qs = qs.filter(aksi=aksi)
    page_obj = _paginate(request, qs)
    return render(request, 'akademik/audit_log.html', {
        'rows': page_obj,
        'page_obj': page_obj,
        'q': q,
        'aksi_filter': aksi,
        'aksi_choices': AuditLog.AKSI,
    })


@login_required
def pilih_tahun_pelajaran(request):
    if not (is_admin(request.user) or is_kepala_sekolah(request.user)):
        messages.error(request, 'Anda tidak memiliki akses mengganti periode aktif.')
        return redirect('akademik:dashboard')
    if request.method != 'POST':
        return redirect('akademik:dashboard')
    tahun = get_object_or_404(AcademicYear, pk=request.POST.get('tahun'))
    _aktifkan_tahun_internal(tahun)
    catat_audit(
        request.user, 'ACTIVATE', tahun,
        deskripsi=f'Mengaktifkan tahun pelajaran {tahun.tahun}', request=request,
    )
    messages.success(request, f'Periode aktif diubah ke {tahun.tahun}.')
    next_url = request.POST.get('next') or ''
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = reverse('akademik:dashboard')
    return redirect(next_url)
