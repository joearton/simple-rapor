import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.db import transaction
from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import (
    AssessmentComponent,
    AssessmentResult,
    ClassGroup,
    Extracurricular,
    FormativeScore,
    Grade,
    HomeroomNote,
    LearningMaterial,
    LearningObjective,
    LearningOutcome,
    LearningTask,
    Student,
    SummativeLM,
    SummativeScore,
    Teacher,
    TeachingAssignment,
)
from .services import MAX_LM, data_leger, daftar_mapel, daftar_siswa, tujuan_aktif

BULAN = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11,
    'desember': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
    'december': 12,
}

KIND_INFO = {
    'siswa': {
        'judul': 'Data Siswa',
        'deskripsi': 'Impor data peserta didik dari file Excel. Data dicocokkan berdasarkan NISN, NIS, nama, atau nomor urut.',
        'import': True,
        'mapel': False,
    },
    'guru': {
        'judul': 'Data Guru',
        'deskripsi': 'Impor profil guru. Akun login tidak dibuat otomatis; tautkan akun melalui laman Data Guru atau Manajemen Pengguna.',
        'import': True,
        'mapel': False,
    },
    'mapel': {
        'judul': 'Mata Pelajaran',
        'deskripsi': 'Impor daftar mata pelajaran beserta guru pengampu pada kelas aktif.',
        'import': True,
        'mapel': False,
    },
    'kelas': {
        'judul': 'Kelas',
        'deskripsi': 'Impor daftar kelas per tahun pelajaran. Tingkat dicocokkan dengan master Tingkat Kelas.',
        'import': True,
        'mapel': False,
    },
    'tp': {
        'judul': 'Tujuan Pembelajaran',
        'deskripsi': 'Impor TP untuk mata pelajaran yang dipilih. Nomor TP yang sama akan diperbarui.',
        'import': True,
        'mapel': True,
    },
    'cp': {
        'judul': 'Capaian Pembelajaran',
        'deskripsi': 'Impor CP untuk mata pelajaran yang dipilih. Cocokkan berdasarkan kode atau urutan.',
        'import': True,
        'mapel': True,
    },
    'materi': {
        'judul': 'Materi Pembelajaran',
        'deskripsi': 'Impor materi dan tautkan ke TP berdasarkan nomor TP.',
        'import': True,
        'mapel': True,
    },
    'tugas': {
        'judul': 'Tugas Pembelajaran',
        'deskripsi': 'Impor tugas beserta TP dan kelas terkait. Cocokkan berdasarkan judul tugas.',
        'import': True,
        'mapel': True,
    },
    'formatif': {
        'judul': 'Nilai Formatif',
        'deskripsi': 'Impor nilai TP skala 1-4. Sel kosong tidak mengubah nilai yang sudah ada.',
        'import': True,
        'mapel': True,
    },
    'sumatif': {
        'judul': 'Nilai Sumatif',
        'deskripsi': 'Impor nilai LM, STS, dan SAS. Sel kosong tidak mengubah nilai yang sudah ada.',
        'import': True,
        'mapel': True,
    },
    'catatan': {
        'judul': 'Catatan & Absensi',
        'deskripsi': 'Impor catatan wali kelas dan ketidakhadiran untuk kelas aktif.',
        'import': True,
        'mapel': False,
    },
    'ekskul': {
        'judul': 'Ekstrakurikuler',
        'deskripsi': 'Impor hingga lima kegiatan ekstrakurikuler per siswa.',
        'import': True,
        'mapel': False,
    },
    'leger': {
        'judul': 'Leger Nilai',
        'deskripsi': 'Unduh rekap nilai seluruh mata pelajaran. Leger hanya tersedia untuk ekspor.',
        'import': False,
        'mapel': False,
    },
}


class ExcelImportError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('; '.join(errors))


def _teks(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _ke_tanggal(value):
    if value in (None, ''):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    teks = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(teks, fmt).date()
        except ValueError:
            pass
    parts = re.split(r'[\s,]+', teks)
    if len(parts) == 3:
        try:
            return dt.date(int(parts[2]), BULAN[parts[1].lower()], int(parts[0]))
        except (ValueError, KeyError):
            return None
    return None


def _ke_int(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    teks = str(value).strip().replace(',', '.')
    try:
        return int(float(teks))
    except ValueError:
        return None


def _ke_desimal(value):
    if value in (None, '', '-'):
        return None
    teks = str(value).strip().replace(',', '.')
    try:
        return Decimal(teks)
    except (InvalidOperation, ValueError):
        return None


def _ke_bool(value, default=True):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return value
    teks = str(value).strip().lower()
    return teks not in ('0', 'tidak', 'nonaktif', 'false', 'no', 'n')


def _response(wb, filename):
    data = BytesIO()
    wb.save(data)
    data.seek(0)
    response = HttpResponse(
        data.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _sheet(wb, title, headers, widths):
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    fill = PatternFill('solid', fgColor='0D6B4A')
    font = Font(bold=True, color='FFFFFF')
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = 'A2'
    return ws


def _buka(file_obj):
    try:
        wb = load_workbook(file_obj, data_only=True)
    except Exception:
        raise ExcelImportError(['File tidak dapat dibaca. Pastikan format .xlsx yang benar.'])
    return wb


def _baris_data(ws):
    for index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(value in (None, '') for value in row):
            continue
        yield index, row


def _cari_siswa(kelas, nisn='', nis='', nama=''):
    qs = Student.objects.in_class(kelas)
    siswa = qs.filter(nisn=nisn).first() if nisn else None
    if siswa is None and nis:
        siswa = qs.filter(nis=nis).first()
    if siswa is None and nama:
        siswa = qs.filter(nama__iexact=nama).first()
    return siswa


def _nama_file(prefix, suffix=''):
    stamp = dt.date.today().strftime('%Y%m%d')
    bersih = re.sub(r'[^A-Za-z0-9_-]+', '-', suffix).strip('-')
    if bersih:
        return f'{prefix}-{bersih}-{stamp}.xlsx'
    return f'{prefix}-{stamp}.xlsx'


# ---------------- SISWA ----------------

SISWA_HEADERS = [
    'No Urut', 'NIS', 'NISN', 'Nama Peserta Didik', 'L/P', 'Tempat Lahir',
    'Tanggal Lahir', 'Agama', 'Pendidikan Sebelumnya', 'Alamat', 'Nama Ayah',
    'Nama Ibu', 'Pekerjaan Ayah', 'Pekerjaan Ibu', 'Alamat Orang Tua',
]
SISWA_WIDTHS = [8, 14, 16, 30, 6, 18, 15, 12, 22, 30, 22, 22, 20, 20, 30]


def export_siswa(kelas, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Data Siswa', SISWA_HEADERS, SISWA_WIDTHS)
    if not template and kelas:
        for siswa in daftar_siswa(kelas):
            ws.append([
                siswa.no_urut, siswa.nis, siswa.nisn, siswa.nama, siswa.jenis_kelamin,
                siswa.tempat_lahir, siswa.tanggal_lahir, siswa.agama,
                siswa.pendidikan_sebelumnya, siswa.alamat, siswa.nama_ayah,
                siswa.nama_ibu, siswa.pekerjaan_ayah, siswa.pekerjaan_ibu,
                siswa.alamat_orang_tua,
            ])
            ws.cell(row=ws.max_row, column=7).number_format = 'DD-MM-YYYY'
    return _response(wb, _nama_file('data-siswa', kelas.nama_lengkap if kelas else ''))


def import_siswa(file_obj, kelas):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 15 - len(row))
            nama = _teks(values[3])
            if not nama:
                errors.append(f'Baris {baris}: nama peserta didik wajib diisi.')
                continue
            no_urut = _ke_int(values[0])
            nis = _teks(values[1])
            nisn = _teks(values[2])
            siswa = _cari_siswa(kelas, nisn=nisn, nis=nis, nama=nama)
            baru = siswa is None
            if baru:
                siswa = Student(class_group=kelas)
                if no_urut is None:
                    qs_siswa = Student.objects.in_class(kelas)
                    terakhir = qs_siswa.order_by('-no_urut').first()
                    no_urut = (terakhir.no_urut + 1) if terakhir else 1
                siswa.no_urut = no_urut
            elif no_urut is not None:
                siswa.no_urut = no_urut
            siswa.nama = nama
            siswa.nis = nis
            siswa.nisn = nisn
            jk = _teks(values[4]).upper()
            siswa.jenis_kelamin = jk if jk in ('L', 'P') else siswa.jenis_kelamin or 'L'
            siswa.tempat_lahir = _teks(values[5])
            tanggal = _ke_tanggal(values[6])
            if values[6] not in (None, '') and tanggal is None:
                errors.append(f'Baris {baris}: tanggal lahir "{values[6]}" tidak dikenali.')
                continue
            siswa.tanggal_lahir = tanggal
            siswa.agama = _teks(values[7])
            siswa.pendidikan_sebelumnya = _teks(values[8])
            siswa.alamat = _teks(values[9])
            siswa.nama_ayah = _teks(values[10])
            siswa.nama_ibu = _teks(values[11])
            siswa.pekerjaan_ayah = _teks(values[12])
            siswa.pekerjaan_ibu = _teks(values[13])
            siswa.alamat_orang_tua = _teks(values[14])
            siswa.aktif = True
            try:
                siswa.save()
            except Exception as exc:
                errors.append(f'Baris {baris}: gagal menyimpan ({exc}).')
                continue
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- GURU ----------------

GURU_HEADERS = [
    'Nama Guru', 'NIK', 'NIP', 'NKTAM', 'L/P', 'Tempat Lahir', 'Tanggal Lahir',
    'Pendidikan', 'Jurusan', 'Tahun Lulus', 'Jabatan', 'Email', 'No. HP',
    'Alamat', 'Aktif', 'Username', 'Mapel Diampu',
]
GURU_WIDTHS = [30, 18, 16, 14, 6, 18, 15, 28, 26, 12, 26, 26, 16, 34, 10, 20, 35]


def export_guru(kelas, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Data Guru', GURU_HEADERS, GURU_WIDTHS)
    if not template:
        for guru in Teacher.objects.select_related('user').prefetch_related('penugasan__subject'):
            mapel = ', '.join(sorted({p.subject.nama for p in guru.penugasan.all()}))
            ws.append([
                guru.nama, guru.nik, guru.nip, guru.nktam, guru.jenis_kelamin,
                guru.tempat_lahir, guru.tanggal_lahir, guru.pendidikan, guru.jurusan,
                guru.tahun_lulus, guru.jabatan, guru.email, guru.no_hp, guru.alamat,
                'Ya' if guru.aktif else 'Tidak', guru.username, mapel,
            ])
            ws.cell(row=ws.max_row, column=7).number_format = 'DD-MM-YYYY'
    return _response(wb, _nama_file('data-guru'))


def import_guru(file_obj, kelas=None, tahun=None):
    from django.contrib.auth.models import User

    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 17 - len(row))
            nama = _teks(values[0])
            if not nama:
                errors.append(f'Baris {baris}: nama guru wajib diisi.')
                continue
            nik = _teks(values[1])
            nip = _teks(values[2])
            guru = Teacher.objects.filter(nik=nik).first() if nik else None
            if guru is None and nip:
                guru = Teacher.objects.filter(nip=nip).first()
            if guru is None:
                guru = Teacher.objects.filter(nama__iexact=nama).first()
            baru = guru is None
            if baru:
                guru = Teacher()
            guru.nama = nama
            guru.nik = nik
            guru.nip = nip
            guru.nktam = _teks(values[3])
            jk = _teks(values[4]).upper()
            guru.jenis_kelamin = jk if jk in ('L', 'P') else guru.jenis_kelamin or 'L'
            guru.tempat_lahir = _teks(values[5])
            tanggal = _ke_tanggal(values[6])
            if values[6] not in (None, '') and tanggal is None:
                errors.append(f'Baris {baris}: tanggal lahir "{values[6]}" tidak dikenali.')
                continue
            guru.tanggal_lahir = tanggal
            guru.pendidikan = _teks(values[7])
            guru.jurusan = _teks(values[8])
            guru.tahun_lulus = _teks(values[9])
            guru.jabatan = _teks(values[10])
            guru.email = _teks(values[11])
            guru.no_hp = _teks(values[12])
            guru.alamat = _teks(values[13])
            guru.aktif = _ke_bool(values[14], True)
            guru.save()
            username = _teks(values[15])
            if username and not guru.user_id:
                user = User.objects.filter(username__iexact=username).first()
                if user and not Teacher.objects.filter(user=user).exists():
                    guru.user = user
                    guru.save(update_fields=['user'])
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- KELAS ----------------

KELAS_HEADERS = ['Tingkat', 'Nama Kelas', 'Fase', 'Wali Kelas']
KELAS_WIDTHS = [12, 30, 8, 30]


def export_kelas(tahun, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Data Kelas', KELAS_HEADERS, KELAS_WIDTHS)
    if not template and tahun:
        kelas_qs = ClassGroup.objects.filter(academic_year=tahun).select_related(
            'grade', 'wali_kelas_guru'
        ).order_by('grade__urutan', 'nama')
        for kelas in kelas_qs:
            ws.append([
                kelas.grade.nama if kelas.grade_id else kelas.tingkat,
                kelas.nama,
                kelas.fase,
                kelas.nama_wali,
            ])
    return _response(wb, _nama_file('data-kelas', tahun.tahun if tahun else ''))


def import_kelas(file_obj, tahun):
    if tahun is None:
        raise ExcelImportError(['Tahun pelajaran belum ditetapkan.'])
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 4 - len(row))
            tingkat = _teks(values[0])
            nama = _teks(values[1])
            if not tingkat or not nama:
                errors.append(f'Baris {baris}: tingkat dan nama kelas wajib diisi.')
                continue
            fase = _teks(values[2]) or 'D'
            grade, _ = Grade.objects.get_or_create(
                nama=tingkat,
                defaults={'fase': fase, 'urutan': 0, 'aktif': True},
            )
            defaults = {'tingkat': grade.nama, 'fase': fase}
            wali_nama = _teks(values[3])
            if wali_nama:
                wali = Teacher.objects.filter(nama__iexact=wali_nama).first()
                if wali is None:
                    errors.append(f'Baris {baris}: guru "{wali_nama}" tidak ditemukan.')
                    continue
                defaults.update({
                    'wali_kelas_guru': wali,
                    'wali_kelas': wali.nama,
                    'nktam_wali': wali.nktam,
                })
            else:
                defaults.update({
                    'wali_kelas_guru': None,
                    'wali_kelas': '',
                    'nktam_wali': '',
                })
            _, baru = ClassGroup.objects.update_or_create(
                academic_year=tahun,
                grade=grade,
                nama=nama,
                defaults=defaults,
            )
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- MAPEL ----------------

MAPEL_HEADERS = ['Urutan', 'Kode', 'Nama Mata Pelajaran', 'Deskripsi', 'Guru Pengampu', 'Jumlah TP']
MAPEL_WIDTHS = [10, 14, 34, 40, 30, 12]


def export_mapel(kelas, tahun, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Mata Pelajaran', MAPEL_HEADERS, MAPEL_WIDTHS)
    penugasan = {}
    if kelas and tahun:
        for p in TeachingAssignment.objects.filter(
            class_group=kelas, academic_year=tahun
        ).select_related('teacher'):
            penugasan[p.subject_id] = p.teacher.nama
    if not template:
        for subject in daftar_mapel(tahun):
            ws.append([
                subject.urutan, subject.kode, subject.nama, subject.deskripsi,
                penugasan.get(subject.id, ''),
                subject.tujuan_list.filter(academic_year=tahun).count() if tahun else 0,
            ])
    return _response(wb, _nama_file('mata-pelajaran'))


def import_mapel(file_obj, kelas=None, tahun=None):
    from .models import Subject

    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    if tahun is None:
        raise ExcelImportError(['Tahun pelajaran aktif belum ditetapkan.'])
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 6 - len(row))
            nama = _teks(values[2])
            if not nama:
                errors.append(f'Baris {baris}: nama mata pelajaran wajib diisi.')
                continue
            urutan = _ke_int(values[0])
            subject, baru = Subject.objects.update_or_create(
                academic_year=tahun, nama=nama,
                defaults={
                    'urutan': urutan or 0,
                    'kode': _teks(values[1]),
                    'deskripsi': _teks(values[3]),
                },
            )
            guru_nama = _teks(values[4])
            if guru_nama and kelas and tahun and guru_nama.lower() not in ('belum ditetapkan', '-'):
                guru = Teacher.objects.filter(nama__iexact=guru_nama).first()
                if guru is None:
                    errors.append(f'Baris {baris}: guru "{guru_nama}" tidak ditemukan.')
                else:
                    TeachingAssignment.objects.update_or_create(
                        subject=subject, class_group=kelas, academic_year=tahun,
                        defaults={'teacher': guru},
                    )
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- TP ----------------

TP_HEADERS = [
    'No TP', 'Tujuan Pembelajaran / Lingkup Materi', 'Guru Pengampu', 'Status',
    'Kode TP', 'CP Terkait',
]
TP_WIDTHS = [8, 90, 26, 10, 14, 16]


def export_tp(subject, academic_year, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Tujuan Pembelajaran', TP_HEADERS, TP_WIDTHS)
    if not template:
        qs = subject.tujuan_list.filter(academic_year=academic_year).select_related(
            'guru', 'learning_outcome'
        )
        for tp in qs:
            cp = tp.learning_outcome
            ws.append([
                tp.nomor, tp.deskripsi, tp.guru.nama if tp.guru else '',
                'Aktif' if tp.aktif else 'Arsip', tp.kode,
                (cp.kode or str(cp.urutan)) if cp else '',
            ])
    return _response(wb, _nama_file('tp', f'{subject.nama}-{academic_year.tahun}'))


def import_tp(file_obj, subject, academic_year, guru=None):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    cps = list(LearningOutcome.objects.filter(subject=subject))
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 6 - len(row))
            nomor = _ke_int(values[0])
            deskripsi = _teks(values[1])
            if nomor is None or not deskripsi:
                errors.append(f'Baris {baris}: nomor dan tujuan pembelajaran wajib diisi.')
                continue
            cp_label = _teks(values[5])
            cp = None
            if cp_label:
                cp = next(
                    (item for item in cps if (item.kode or '').lower() == cp_label.lower()),
                    None,
                )
                if cp is None and cp_label.isdigit():
                    cp = next((item for item in cps if item.urutan == int(cp_label)), None)
                if cp is None:
                    errors.append(f'Baris {baris}: CP "{cp_label}" tidak ditemukan.')
                    continue
            defaults = {
                'deskripsi': deskripsi,
                'kode': _teks(values[4]),
                'learning_outcome': cp,
                'aktif': not _teks(values[3]).lower().startswith('arsip'),
            }
            if guru:
                defaults['guru'] = guru
            tp, baru = LearningObjective.objects.update_or_create(
                subject=subject, academic_year=academic_year, nomor=nomor,
                defaults=defaults,
            )
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- CP ----------------

CP_HEADERS = ['Kode', 'Fase', 'Capaian Pembelajaran', 'Urutan', 'Status']
CP_WIDTHS = [14, 8, 90, 10, 12]


def _nomor_dari_teks(teks):
    return [int(n) for n in re.findall(r'\d+', str(teks or ''))]


def export_cp(subject, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Capaian Pembelajaran', CP_HEADERS, CP_WIDTHS)
    if not template:
        for cp in LearningOutcome.objects.filter(subject=subject).order_by('urutan', 'kode'):
            ws.append([
                cp.kode, cp.fase, cp.deskripsi, cp.urutan,
                'Aktif' if cp.aktif else 'Arsip',
            ])
    return _response(wb, _nama_file('cp', subject.nama))


def import_cp(file_obj, subject):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 5 - len(row))
            kode = _teks(values[0])
            deskripsi = _teks(values[2])
            urutan = _ke_int(values[3])
            if not deskripsi:
                errors.append(f'Baris {baris}: capaian pembelajaran wajib diisi.')
                continue
            cp = None
            if kode:
                cp = LearningOutcome.objects.filter(subject=subject, kode=kode).first()
            if cp is None and urutan is not None:
                cp = LearningOutcome.objects.filter(subject=subject, urutan=urutan).first()
            baru = cp is None
            if baru:
                cp = LearningOutcome(subject=subject)
                if urutan is None:
                    urutan = (
                        LearningOutcome.objects.filter(subject=subject)
                        .order_by('-urutan').values_list('urutan', flat=True).first()
                        or 0
                    ) + 1
                cp.urutan = urutan
            elif urutan is not None:
                cp.urutan = urutan
            cp.kode = kode
            kelas = ClassGroup.objects.filter(academic_year=subject.academic_year).first()
            cp.fase = _teks(values[1]) or (kelas.fase if kelas else 'D')
            cp.deskripsi = deskripsi
            cp.aktif = not _teks(values[4]).lower().startswith('arsip')
            try:
                cp.save()
            except Exception as exc:
                errors.append(f'Baris {baris}: gagal menyimpan CP ({exc}).')
                continue
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- MATERI ----------------

MATERI_HEADERS = [
    'Kode', 'Judul Materi', 'Deskripsi', 'TP Terkait', 'Urutan', 'Status',
]
MATERI_WIDTHS = [14, 34, 60, 20, 10, 12]


def export_materi(subject, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Materi', MATERI_HEADERS, MATERI_WIDTHS)
    if not template:
        for materi in LearningMaterial.objects.filter(subject=subject).prefetch_related(
            'objectives'
        ).order_by('urutan', 'judul'):
            nomor_tp = ', '.join(str(tp.nomor) for tp in materi.objectives.all())
            ws.append([
                materi.kode, materi.judul, materi.deskripsi, nomor_tp,
                materi.urutan, 'Aktif' if materi.aktif else 'Arsip',
            ])
    return _response(wb, _nama_file('materi', subject.nama))


def import_materi(file_obj, subject):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    objectives = {
        tp.nomor: tp for tp in LearningObjective.objects.filter(
            subject=subject, academic_year=subject.academic_year
        )
    }
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 6 - len(row))
            kode = _teks(values[0])
            judul = _teks(values[1])
            urutan = _ke_int(values[4])
            if not judul:
                errors.append(f'Baris {baris}: judul materi wajib diisi.')
                continue
            materi = None
            if kode:
                materi = LearningMaterial.objects.filter(subject=subject, kode=kode).first()
            if materi is None:
                materi = LearningMaterial.objects.filter(subject=subject, judul=judul).first()
            baru = materi is None
            if baru:
                materi = LearningMaterial(subject=subject)
            materi.kode = kode
            materi.judul = judul
            materi.deskripsi = _teks(values[2])
            if urutan is not None:
                materi.urutan = urutan
            elif baru:
                materi.urutan = (
                    LearningMaterial.objects.filter(subject=subject)
                    .order_by('-urutan').values_list('urutan', flat=True).first()
                    or 0
                ) + 1
            materi.aktif = not _teks(values[5]).lower().startswith('arsip')
            try:
                materi.save()
            except Exception as exc:
                errors.append(f'Baris {baris}: gagal menyimpan materi ({exc}).')
                continue
            nomor_list = _nomor_dari_teks(values[3])
            terkait = []
            for nomor in nomor_list:
                tp = objectives.get(nomor)
                if tp is None:
                    errors.append(f'Baris {baris}: TP {nomor} tidak ditemukan.')
                else:
                    terkait.append(tp)
            materi.objectives.set(terkait)
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- TUGAS ----------------

TUGAS_HEADERS = [
    'Judul', 'Deskripsi', 'Instruksi', 'Tanggal Pemberian', 'Batas Pengumpulan',
    'Bobot', 'Status', 'TP Terkait', 'Kelas',
]
TUGAS_WIDTHS = [34, 50, 60, 16, 16, 10, 12, 20, 30]

STATUS_TUGAS = {
    'draf': 'DRAF',
    'draft': 'DRAF',
    'terbit': 'TERBIT',
    'tutup': 'TUTUP',
    'ditutup': 'TUTUP',
}


def export_tugas(subject, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Tugas', TUGAS_HEADERS, TUGAS_WIDTHS)
    if not template:
        qs = LearningTask.objects.filter(subject=subject).prefetch_related(
            'objectives', 'class_groups'
        ).order_by('judul')
        for tugas in qs:
            nomor_tp = ', '.join(str(tp.nomor) for tp in tugas.objectives.all())
            kelas = ', '.join(k.nama_lengkap for k in tugas.class_groups.all())
            ws.append([
                tugas.judul, tugas.deskripsi, tugas.instruksi,
                tugas.tanggal_pemberian, tugas.batas_pengumpulan,
                tugas.bobot, tugas.get_status_display(), nomor_tp, kelas,
            ])
            ws.cell(row=ws.max_row, column=4).number_format = 'DD-MM-YYYY'
            ws.cell(row=ws.max_row, column=5).number_format = 'DD-MM-YYYY'
    return _response(wb, _nama_file('tugas', subject.nama))


def _kelas_dari_teks(tahun, teks):
    daftar = [t.strip() for t in re.split(r'[,;]', str(teks or '')) if t.strip()]
    if not daftar:
        return [], []
    peta = {}
    for kelas in ClassGroup.objects.filter(academic_year=tahun):
        peta[kelas.nama_lengkap.lower()] = kelas
        peta[kelas.nama.lower()] = kelas
    ditemukan = []
    hilang = []
    for label in daftar:
        kelas = peta.get(label.lower())
        if kelas is None:
            hilang.append(label)
        else:
            ditemukan.append(kelas)
    return ditemukan, hilang


def import_tugas(file_obj, subject):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    dibuat = diperbarui = 0
    objectives = {
        tp.nomor: tp for tp in LearningObjective.objects.filter(
            subject=subject, academic_year=subject.academic_year
        )
    }
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 9 - len(row))
            judul = _teks(values[0])
            if not judul:
                errors.append(f'Baris {baris}: judul tugas wajib diisi.')
                continue
            tugas = LearningTask.objects.filter(
                subject=subject, academic_year=subject.academic_year, judul=judul
            ).first()
            baru = tugas is None
            if baru:
                tugas = LearningTask(subject=subject, academic_year=subject.academic_year)
            tugas.judul = judul
            tugas.deskripsi = _teks(values[1])
            tugas.instruksi = _teks(values[2])
            awal = _ke_tanggal(values[3])
            akhir = _ke_tanggal(values[4])
            if values[3] not in (None, '') and awal is None:
                errors.append(f'Baris {baris}: tanggal pemberian tidak dikenali.')
                continue
            if values[4] not in (None, '') and akhir is None:
                errors.append(f'Baris {baris}: batas pengumpulan tidak dikenali.')
                continue
            tugas.tanggal_pemberian = awal
            tugas.batas_pengumpulan = akhir
            bobot = _ke_desimal(values[5])
            tugas.bobot = bobot if bobot is not None else 0
            tugas.status = STATUS_TUGAS.get(_teks(values[6]).lower(), 'DRAF')
            try:
                tugas.save()
            except Exception as exc:
                errors.append(f'Baris {baris}: gagal menyimpan tugas ({exc}).')
                continue
            nomor_list = _nomor_dari_teks(values[7])
            terkait = []
            for nomor in nomor_list:
                tp = objectives.get(nomor)
                if tp is None:
                    errors.append(f'Baris {baris}: TP {nomor} tidak ditemukan.')
                else:
                    terkait.append(tp)
            tugas.objectives.set(terkait)
            kelas, hilang = _kelas_dari_teks(subject.academic_year, values[8])
            for label in hilang:
                errors.append(f'Baris {baris}: kelas "{label}" tidak ditemukan.')
            tugas.class_groups.set(kelas)
            if baru:
                dibuat += 1
            else:
                diperbarui += 1
        if errors:
            raise ExcelImportError(errors)
    return {'dibuat': dibuat, 'diperbarui': diperbarui}


# ---------------- FORMATIF ----------------

def export_formatif(subject, semester, kelas, template=False):
    objectives = list(tujuan_aktif(subject, semester))
    headers = ['No', 'NIS', 'NISN', 'Nama Peserta Didik'] + [
        f'TP {tp.nomor}' for tp in objectives
    ]
    widths = [6, 14, 16, 30] + [8] * len(objectives)
    wb = Workbook()
    ws = _sheet(wb, 'Formatif', headers, widths)
    if not template:
        for i, siswa in enumerate(daftar_siswa(kelas), start=1):
            values = dict(
                FormativeScore.objects.filter(
                    student=siswa, objective__subject=subject,
                    objective__academic_year=semester.academic_year,
                    semester=semester,
                ).values_list('objective_id', 'nilai')
            )
            ws.append(
                [i, siswa.nis, siswa.nisn, siswa.nama]
                + [values.get(tp.id) for tp in objectives]
            )
    if objectives:
        ws_info = wb.create_sheet('Keterangan TP')
        ws_info.append(['TP', 'Tujuan Pembelajaran / Lingkup Materi'])
        for cell in ws_info[1]:
            cell.font = Font(bold=True)
        ws_info.column_dimensions['A'].width = 10
        ws_info.column_dimensions['B'].width = 100
        for tp in objectives:
            ws_info.append([f'TP {tp.nomor}', tp.deskripsi])
    return _response(wb, _nama_file('formatif', f'{subject.nama}-{semester.nama}'))


def import_formatif(file_obj, subject, semester, kelas, guru=None):
    wb = _buka(file_obj)
    ws = wb.active
    objectives = {tp.nomor: tp for tp in tujuan_aktif(subject, semester)}
    header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    tp_columns = []
    for index, label in enumerate(header):
        if index < 4:
            continue
        match = re.search(r'(\d+)', str(label or ''))
        if match:
            tp_columns.append((index, int(match.group(1))))
    errors = []
    jumlah = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row)
            if len(values) < 4:
                errors.append(f'Baris {baris}: format tidak lengkap.')
                continue
            nis, nisn, nama = _teks(values[1]), _teks(values[2]), _teks(values[3])
            if not (nis or nisn or nama):
                continue
            if nama.lower().startswith('keterangan'):
                break
            siswa = _cari_siswa(kelas, nisn=nisn, nis=nis, nama=nama)
            if siswa is None:
                errors.append(f'Baris {baris}: siswa "{nama}" tidak ditemukan.')
                continue
            for index, tp_nomor in tp_columns:
                if index >= len(values):
                    continue
                value = values[index]
                if value in (None, ''):
                    continue
                objective = objectives.get(tp_nomor)
                if objective is None:
                    continue
                angka = _ke_int(value)
                if angka is None or angka < 1 or angka > 4:
                    errors.append(f'Baris {baris} TP {tp_nomor}: nilai harus 1-4.')
                    continue
                FormativeScore.objects.update_or_create(
                    student=siswa, objective=objective, semester=semester,
                    defaults={'nilai': angka, 'guru': guru},
                )
                jumlah += 1
        if errors:
            raise ExcelImportError(errors)
    return {'diperbarui': jumlah}


# ---------------- SUMATIF ----------------

def export_sumatif(subject, semester, kelas, template=False):
    headers = ['No', 'NIS', 'NISN', 'Nama Peserta Didik'] + [
        f'LM {i}' for i in range(1, MAX_LM + 1)
    ] + ['STS', 'SAS Non Tes', 'SAS Tes', 'Nilai Rapor (otomatis)']
    widths = [6, 14, 16, 30] + [8] * MAX_LM + [10, 12, 10, 16]
    wb = Workbook()
    ws = _sheet(wb, 'Sumatif', headers, widths)
    if not template:
        for i, siswa in enumerate(daftar_siswa(kelas), start=1):
            lm = {
                n: v for n, v in SummativeLM.objects.filter(
                    student=siswa, subject=subject, semester=semester
                ).values_list('nomor', 'nilai')
            }
            obj = SummativeScore.objects.filter(
                student=siswa, subject=subject, semester=semester
            ).first()
            ws.append(
                [i, siswa.nis, siswa.nisn, siswa.nama]
                + [lm.get(n) for n in range(1, MAX_LM + 1)]
                + [
                    obj.sts if obj else None,
                    obj.sas_non_tes if obj else None,
                    obj.sas_tes if obj else None,
                    obj.nilai_rapor if obj else None,
                ]
            )
    return _response(wb, _nama_file('sumatif', f'{subject.nama}-{semester.nama}'))


def import_sumatif(file_obj, subject, semester, kelas, guru=None):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    jumlah_lm = jumlah_nilai = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 4 + MAX_LM + 3 - len(row))
            nis, nisn, nama = _teks(values[1]), _teks(values[2]), _teks(values[3])
            siswa = _cari_siswa(kelas, nisn=nisn, nis=nis, nama=nama)
            if siswa is None:
                errors.append(f'Baris {baris}: siswa "{nama}" tidak ditemukan.')
                continue
            for nomor in range(1, MAX_LM + 1):
                value = values[3 + nomor]
                if value in (None, ''):
                    continue
                angka = _ke_desimal(value)
                if angka is None or angka < 0 or angka > 100:
                    errors.append(f'Baris {baris} LM {nomor}: nilai harus 0-100.')
                    continue
                SummativeLM.objects.update_or_create(
                    student=siswa, subject=subject, semester=semester, nomor=nomor,
                    defaults={'nilai': angka, 'guru': guru},
                )
                jumlah_lm += 1
            sts = _ke_desimal(values[4 + MAX_LM])
            non_tes = _ke_desimal(values[5 + MAX_LM])
            tes = _ke_desimal(values[6 + MAX_LM])
            for label, angka in (('STS', sts), ('SAS Non Tes', non_tes), ('SAS Tes', tes)):
                if angka is not None and (angka < 0 or angka > 100):
                    errors.append(f'Baris {baris}: {label} harus 0-100.')
            memiliki_akhir = any(v not in (None, '') for v in (
                values[4 + MAX_LM], values[5 + MAX_LM], values[6 + MAX_LM]
            ))
            if memiliki_akhir:
                defaults = {'guru': guru}
                if sts is not None:
                    defaults['sts'] = sts
                if non_tes is not None:
                    defaults['sas_non_tes'] = non_tes
                if tes is not None:
                    defaults['sas_tes'] = tes
                SummativeScore.objects.update_or_create(
                    student=siswa, subject=subject, semester=semester,
                    defaults=defaults,
                )
                jumlah_nilai += 1
        if errors:
            raise ExcelImportError(errors)
    return {'lm': jumlah_lm, 'nilai': jumlah_nilai}


# ---------------- ASESMEN GENERIK ----------------

def export_asesmen(assessment, kelas):
    components = list(assessment.components.all())
    headers = ['No', 'NIS', 'NISN', 'Nama Peserta Didik'] + [
        component.nama for component in components
    ]
    widths = [6, 14, 16, 30] + [12] * len(components)
    wb = Workbook()
    ws = _sheet(wb, 'Asesmen', headers, widths)
    results = {
        (hasil.student_id, hasil.component_id): hasil.nilai
        for hasil in AssessmentResult.objects.filter(
            component__in=components, student__in=daftar_siswa(kelas)
        )
    }
    for i, siswa in enumerate(daftar_siswa(kelas), start=1):
        ws.append(
            [i, siswa.nis, siswa.nisn, siswa.nama]
            + [results.get((siswa.id, component.id)) for component in components]
        )
    return _response(wb, _nama_file('asesmen', assessment.nama))


def import_asesmen(file_obj, assessment, kelas):
    wb = _buka(file_obj)
    ws = wb.active
    components = list(assessment.components.all())
    header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    kolom = {}
    for index, label in enumerate(header):
        if index < 4:
            continue
        component = next(
            (c for c in components if c.nama.strip().lower() == str(label or '').strip().lower()),
            None,
        )
        if component is not None:
            kolom[index] = component
    errors = []
    jumlah = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 4 - len(row))
            nis, nisn, nama = _teks(values[1]), _teks(values[2]), _teks(values[3])
            if not (nis or nisn or nama):
                continue
            siswa = _cari_siswa(kelas, nisn=nisn, nis=nis, nama=nama)
            if siswa is None:
                errors.append(f'Baris {baris}: siswa "{nama}" tidak ditemukan.')
                continue
            for index, component in kolom.items():
                if index >= len(values):
                    continue
                raw = values[index]
                if raw in (None, ''):
                    AssessmentResult.objects.filter(
                        component=component, student=siswa
                    ).delete()
                    continue
                nilai = _ke_desimal(raw)
                if nilai is None or nilai < 0 or nilai > component.nilai_maksimal:
                    errors.append(
                        f'Baris {baris} {component.nama}: nilai harus '
                        f'0-{component.nilai_maksimal}.'
                    )
                    continue
                AssessmentResult.objects.update_or_create(
                    component=component, student=siswa, defaults={'nilai': nilai},
                )
                jumlah += 1
        if errors:
            raise ExcelImportError(errors)
    return {'diperbarui': jumlah}


# ---------------- CATATAN ----------------

CATATAN_HEADERS = ['No', 'NIS', 'NISN', 'Nama Peserta Didik', 'Catatan Wali Kelas', 'Sakit', 'Izin', 'Alpa']
CATATAN_WIDTHS = [6, 14, 16, 30, 60, 8, 8, 8]


def export_catatan(kelas, semester, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Catatan', CATATAN_HEADERS, CATATAN_WIDTHS)
    if not template:
        for i, siswa in enumerate(daftar_siswa(kelas), start=1):
            note = HomeroomNote.objects.filter(student=siswa, semester=semester).first()
            ws.append([
                i, siswa.nis, siswa.nisn, siswa.nama,
                note.catatan if note else '', note.sakit if note else 0,
                note.izin if note else 0, note.alpa if note else 0,
            ])
    return _response(wb, _nama_file('catatan', kelas.nama_lengkap if kelas else ''))


def import_catatan(file_obj, kelas, semester, guru=None):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    jumlah = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 8 - len(row))
            nis, nisn, nama = _teks(values[1]), _teks(values[2]), _teks(values[3])
            siswa = _cari_siswa(kelas, nisn=nisn, nis=nis, nama=nama)
            if siswa is None:
                errors.append(f'Baris {baris}: siswa "{nama}" tidak ditemukan.')
                continue
            sakit = _ke_int(values[5]) or 0
            izin = _ke_int(values[6]) or 0
            alpa = _ke_int(values[7]) or 0
            catatan = _teks(values[4])
            if not catatan and not (sakit or izin or alpa):
                HomeroomNote.objects.filter(student=siswa, semester=semester).delete()
            else:
                HomeroomNote.objects.update_or_create(
                    student=siswa, semester=semester,
                    defaults={
                        'catatan': catatan, 'sakit': sakit, 'izin': izin,
                        'alpa': alpa, 'guru': guru,
                        'academic_year': semester.academic_year,
                    },
                )
            jumlah += 1
        if errors:
            raise ExcelImportError(errors)
    return {'diperbarui': jumlah}


# ---------------- EKSKUL ----------------

EKSKUL_HEADERS = ['No', 'NIS', 'NISN', 'Nama Peserta Didik'] + [
    item for i in range(1, 6) for item in (f'Ekstrakurikuler {i}', f'Predikat {i}', f'Deskripsi {i}')
]
EKSKUL_WIDTHS = [6, 14, 16, 30] + [22, 10, 30] * 5


def export_ekskul(kelas, semester, template=False):
    wb = Workbook()
    ws = _sheet(wb, 'Ekstrakurikuler', EKSKUL_HEADERS, EKSKUL_WIDTHS)
    if not template:
        data = {}
        for eks in Extracurricular.objects.filter(
            student__in=daftar_siswa(kelas), semester=semester
        ).order_by('urutan'):
            data.setdefault(eks.student_id, {})[eks.urutan] = eks
        for i, siswa in enumerate(daftar_siswa(kelas), start=1):
            isi = data.get(siswa.id, {})
            row = [i, siswa.nis, siswa.nisn, siswa.nama]
            for urutan in range(1, 6):
                eks = isi.get(urutan)
                row.extend([eks.nama if eks else '', eks.predikat if eks else '', eks.deskripsi if eks else ''])
            ws.append(row)
    return _response(wb, _nama_file('ekstrakurikuler', kelas.nama_lengkap if kelas else ''))


def import_ekskul(file_obj, kelas, semester, guru=None):
    wb = _buka(file_obj)
    ws = wb.active
    errors = []
    jumlah = 0
    with transaction.atomic():
        for baris, row in _baris_data(ws):
            values = list(row) + [''] * max(0, 19 - len(row))
            nis, nisn, nama = _teks(values[1]), _teks(values[2]), _teks(values[3])
            siswa = _cari_siswa(kelas, nisn=nisn, nis=nis, nama=nama)
            if siswa is None:
                errors.append(f'Baris {baris}: siswa "{nama}" tidak ditemukan.')
                continue
            for slot in range(5):
                idx = 4 + slot * 3
                nama_eks = _teks(values[idx])
                predikat = _teks(values[idx + 1])
                deskripsi = _teks(values[idx + 2])
                if not (nama_eks or predikat or deskripsi):
                    Extracurricular.objects.filter(
                        student=siswa, semester=semester, urutan=slot + 1
                    ).delete()
                else:
                    Extracurricular.objects.update_or_create(
                        student=siswa, semester=semester, urutan=slot + 1,
                        defaults={
                            'nama': nama_eks, 'predikat': predikat,
                            'deskripsi': deskripsi, 'guru': guru,
                            'academic_year': semester.academic_year,
                        },
                    )
                    jumlah += 1
        if errors:
            raise ExcelImportError(errors)
    return {'diperbarui': jumlah}


# ---------------- LEGER ----------------

def export_leger(kelas, semester):
    leger = data_leger(kelas, semester)
    headers = ['No', 'Nama Peserta Didik', 'NIS', 'NISN'] + [
        s.nama for s in leger['subjects']
    ] + ['Rata-rata']
    widths = [6, 30, 14, 16] + [10] * len(leger['subjects']) + [12]
    wb = Workbook()
    ws = _sheet(wb, 'Leger', headers, widths)
    for i, row in enumerate(leger['rows'], start=1):
        siswa = row['siswa']
        ws.append(
            [i, siswa.nama, siswa.nis, siswa.nisn]
            + [float(n) if n is not None else None for n in row['nilai']]
            + [float(row['rata']) if row['rata'] is not None else None]
        )
    return _response(wb, _nama_file('leger', f'{kelas.nama_lengkap}-{semester.nama}' if kelas else ''))
