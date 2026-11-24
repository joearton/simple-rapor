import datetime as dt
import os
from decimal import Decimal

import openpyxl
from django.core.management.base import BaseCommand, CommandError

from akademik.models import (
    AcademicYear,
    ClassGroup,
    Extracurricular,
    FormativeScore,
    LearningObjective,
    School,
    Semester,
    Student,
    Subject,
    Teacher,
)

BULAN = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11,
    'desember': 12,
}


def teks(value):
    if value is None:
        return ''
    return str(value).strip()


def teks_angka(value):
    if value in (None, ''):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def ke_tanggal(value):
    if value in (None, ''):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    parts = str(value).replace(',', ' ').split()
    if len(parts) != 3:
        return None
    try:
        hari = int(parts[0])
        bulan = BULAN.get(parts[1].lower())
        tahun = int(parts[2])
        if not bulan:
            return None
        return dt.date(tahun, bulan, hari)
    except (ValueError, TypeError):
        return None


def ke_desimal(value):
    if value in (None, '', '-'):
        return None
    try:
        return Decimal(str(value).replace(',', '.'))
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Impor data siswa, mapel, TP, nilai formatif, dan ekskul dari file Excel rapor.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Lokasi file Excel (.xlsx)')
        parser.add_argument(
            '--tanpa-nilai', action='store_true',
            help='Hanya impor master data (tanpa nilai formatif dan ekskul).',
        )

    def handle(self, *args, **options):
        path = options['file']
        if not os.path.exists(path):
            raise CommandError(f'File tidak ditemukan: {path}')
        tanpa_nilai = options['tanpa_nilai']

        wb = openpyxl.load_workbook(path, data_only=True)
        ident = wb['IDENTITAS']

        def sel(row, col):
            return ident.cell(row=row, column=col).value

        school = School.get_solo()
        school.nama = teks(sel(4, 4)) or school.nama
        school.npsn = teks_angka(sel(5, 4))
        school.nss = teks_angka(sel(6, 4))
        school.alamat = teks(sel(7, 4))
        school.kode_pos = teks_angka(sel(8, 4))
        school.desa = teks(sel(9, 4))
        school.kecamatan = teks(sel(10, 4))
        school.kabupaten = teks(sel(11, 4))
        school.provinsi = teks(sel(12, 4))
        school.website = teks(sel(13, 4))
        school.email = teks(sel(14, 4))
        school.kepala_sekolah = teks(sel(15, 4))
        school.nktam_kepala = teks_angka(sel(16, 4))
        tempat_tanggal = teks(sel(23, 4))
        if ',' in tempat_tanggal:
            school.tempat_rapor = tempat_tanggal.split(',')[0].strip()

        if 'SAMPUL' in wb.sheetnames:
            sampul = wb['SAMPUL']
            majelis_1 = teks(sampul['C37'].value)
            majelis_2 = teks(sampul['C38'].value)
            pimpinan = teks(sampul['C39'].value)
            if majelis_1:
                school.majelis = f'{majelis_1} {majelis_2}'.strip()
            if pimpinan:
                school.pimpinan_daerah = pimpinan

        school.save()
        self.stdout.write(f'  Sekolah: {school.nama}')

        tahun = teks(sel(22, 4)) or '2026/2027'
        academic_year, _ = AcademicYear.objects.update_or_create(
            tahun=tahun, defaults={'aktif': True}
        )
        AcademicYear.objects.exclude(pk=academic_year.pk).update(aktif=False)

        nama_semester = teks(sel(21, 4)) or 'I'
        if nama_semester not in ('I', 'II'):
            nama_semester = 'I'
        semester, _ = Semester.objects.update_or_create(
            academic_year=academic_year, nama=nama_semester, defaults={'aktif': True}
        )
        Semester.objects.exclude(pk=semester.pk).update(aktif=False)

        tingkat = teks(sel(19, 4)) or 'VII'
        nama_kelas = teks(sel(19, 5)) or 'Al-Lathif'
        nama_wali = teks(sel(17, 4))
        nktam_wali = teks_angka(sel(18, 4))
        wali_guru = None
        if nama_wali:
            wali_guru = Teacher.objects.filter(nama__iexact=nama_wali).first()
            if wali_guru is None:
                wali_guru = Teacher.objects.create(nama=nama_wali, nktam=nktam_wali)
            elif nktam_wali and not wali_guru.nktam:
                wali_guru.nktam = nktam_wali
                wali_guru.save(update_fields=['nktam'])
        kelas, _ = ClassGroup.objects.update_or_create(
            academic_year=academic_year, tingkat=tingkat, nama=nama_kelas,
            defaults={
                'fase': teks(sel(20, 4)) or 'D',
                'wali_kelas_guru': wali_guru,
                'wali_kelas': nama_wali,
                'nktam_wali': nktam_wali,
            },
        )
        self.stdout.write(f'  Kelas: {kelas.nama_lengkap} ({academic_year.tahun}, semester {semester.nama})')
        if not ClassGroup.objects.filter(aktif=True).exists():
            kelas.aktif = True
            kelas.save(update_fields=['aktif'])
        if wali_guru:
            self.stdout.write(f'  Wali kelas: {wali_guru.nama}')

        subjects = {}
        for row in range(5, 40):
            nama = teks(sel(row, 8))
            nomor = sel(row, 7)
            if not nama or nomor is None:
                break
            subject, _ = Subject.objects.update_or_create(
                nama=nama, defaults={'urutan': int(nomor)}
            )
            subjects[nama] = subject
        self.stdout.write(f'  Mata pelajaran: {len(subjects)}')

        siswa_dari_excel = {}
        ws_siswa = wb['Data Siswa']
        jumlah_siswa = 0
        for row in range(6, ws_siswa.max_row + 1):
            nama = teks(ws_siswa.cell(row=row, column=5).value)
            no_urut = ws_siswa.cell(row=row, column=2).value
            if not nama or no_urut is None:
                continue
            siswa, _ = Student.objects.update_or_create(
                class_group=kelas, no_urut=int(no_urut),
                defaults={
                    'nis': teks_angka(ws_siswa.cell(row=row, column=3).value),
                    'nisn': teks_angka(ws_siswa.cell(row=row, column=4).value),
                    'nama': nama,
                    'jenis_kelamin': teks(ws_siswa.cell(row=row, column=6).value) or 'L',
                    'tempat_lahir': teks(ws_siswa.cell(row=row, column=7).value),
                    'tanggal_lahir': ke_tanggal(ws_siswa.cell(row=row, column=8).value),
                    'agama': teks(ws_siswa.cell(row=row, column=9).value),
                    'pendidikan_sebelumnya': teks(ws_siswa.cell(row=row, column=10).value),
                    'alamat': teks(ws_siswa.cell(row=row, column=11).value),
                    'nama_ayah': teks(ws_siswa.cell(row=row, column=12).value),
                    'nama_ibu': teks(ws_siswa.cell(row=row, column=13).value),
                    'pekerjaan_ayah': teks(ws_siswa.cell(row=row, column=14).value),
                    'pekerjaan_ibu': teks(ws_siswa.cell(row=row, column=15).value),
                    'alamat_orang_tua': teks(ws_siswa.cell(row=row, column=16).value),
                    'aktif': True,
                },
            )
            siswa_dari_excel[nama] = siswa
            jumlah_siswa += 1
        self.stdout.write(f'  Peserta didik: {jumlah_siswa}')

        jumlah_tp = 0
        for nomor_sheet in range(1, 14):
            nama_sheet = f'TP{nomor_sheet}'
            if nama_sheet not in wb.sheetnames:
                continue
            ws_tp = wb[nama_sheet]
            nama_mapel = teks(ws_tp['D3'].value)
            subject = subjects.get(nama_mapel)
            if not subject:
                continue
            for row in range(9, ws_tp.max_row + 1):
                nomor = ws_tp.cell(row=row, column=4).value
                deskripsi = teks(ws_tp.cell(row=row, column=5).value)
                if nomor is None or not deskripsi:
                    continue
                LearningObjective.objects.update_or_create(
                    subject=subject, academic_year=academic_year, nomor=int(nomor),
                    defaults={'deskripsi': deskripsi, 'aktif': True},
                )
                jumlah_tp += 1
        self.stdout.write(f'  Tujuan pembelajaran: {jumlah_tp}')

        if tanpa_nilai:
            self.stdout.write(self.style.SUCCESS('Impor master data selesai.'))
            return

        jumlah_nilai = 0
        for nomor_sheet in range(1, 14):
            nama_sheet = f'F{nomor_sheet}'
            if nama_sheet not in wb.sheetnames:
                continue
            ws_f = wb[nama_sheet]
            nama_mapel = teks(ws_f['A2'].value).replace('Mata Pelajaran', '').strip()
            subject = subjects.get(nama_mapel)
            if not subject:
                continue
            objectives = {
                o.nomor: o for o in subject.tujuan_list.filter(academic_year=academic_year)
            }
            for row in range(11, ws_f.max_row + 1):
                nama = teks(ws_f.cell(row=row, column=2).value)
                if not nama:
                    continue
                siswa = siswa_dari_excel.get(nama)
                if not siswa:
                    continue
                for kolom in range(3, 18):
                    nilai = ws_f.cell(row=row, column=kolom).value
                    tp_nomor = kolom - 2
                    objective = objectives.get(tp_nomor)
                    if objective is None or not isinstance(nilai, (int, float)):
                        continue
                    if not 1 <= nilai <= 4:
                        continue
                    FormativeScore.objects.update_or_create(
                        student=siswa, objective=objective, semester=semester,
                        defaults={'nilai': int(nilai)},
                    )
                    jumlah_nilai += 1
        self.stdout.write(f'  Nilai formatif: {jumlah_nilai}')

        jumlah_ekskul = 0
        ws_eks = wb['EKS']
        for row in range(12, ws_eks.max_row + 1):
            nama = teks(ws_eks.cell(row=row, column=4).value)
            if not nama:
                continue
            siswa = siswa_dari_excel.get(nama)
            if not siswa:
                continue
            for slot in range(5):
                kolom = 5 + slot * 3
                nama_eks = teks(ws_eks.cell(row=row, column=kolom).value)
                predikat = teks(ws_eks.cell(row=row, column=kolom + 1).value)
                deskripsi = teks(ws_eks.cell(row=row, column=kolom + 2).value)
                if not (nama_eks or predikat or deskripsi):
                    continue
                Extracurricular.objects.update_or_create(
                    student=siswa, semester=semester, urutan=slot + 1,
                    defaults={
                        'nama': nama_eks, 'predikat': predikat, 'deskripsi': deskripsi,
                        'guru': wali_guru,
                    },
                )
                jumlah_ekskul += 1
        self.stdout.write(f'  Ekstrakurikuler: {jumlah_ekskul}')

        self.stdout.write(self.style.SUCCESS('Impor data Excel selesai.'))
