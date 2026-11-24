from decimal import Decimal
from io import BytesIO
import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from .models import (
    AcademicYear,
    Assessment,
    AssessmentComponent,
    AssessmentResult,
    ClassGroup,
    EvaluasiFormatif,
    EvaluasiSumatif,
    Extracurricular,
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
from .services import (
    angka,
    data_leger,
    data_rapor,
    deskripsi_capaian,
    hitung_nilai,
    ringkasan_sumatif,
)
from .reporting import (
    ReportIncomplete,
    ReportLocked,
    ajukan,
    buka_kunci,
    periksa_kelengkapan,
    setujui,
    susun_report_card,
    terbitkan,
)


class RaporTestBase(TestCase):
    def setUp(self):
        self.sekolah = School.objects.create(
            nama='SMP UJI', alamat='Jl. Uji', kepala_sekolah='Kepala Uji'
        )
        self.tahun = AcademicYear.objects.create(tahun='2026/2027', aktif=True)
        self.semester = Semester.objects.create(
            academic_year=self.tahun, nama='I', aktif=True
        )
        self.kelas = ClassGroup.objects.create(
            academic_year=self.tahun, tingkat='VII', nama='Uji', fase='D',
            wali_kelas='Wali Uji',
        )
        self.mapel = Subject.objects.create(
            academic_year=self.tahun, nama='Matematika', urutan=1
        )
        self.mapel2 = Subject.objects.create(
            academic_year=self.tahun, nama='Bahasa Indonesia', urutan=2
        )
        self.siswa = Student.objects.create(
            class_group=self.kelas, no_urut=1, nama='Siswa Uji', nis='1', nisn='2',
        )
        self.tp1 = LearningObjective.objects.create(
            subject=self.mapel, academic_year=self.tahun, nomor=1, deskripsi='menghitung bilangan bulat'
        )
        self.tp2 = LearningObjective.objects.create(
            subject=self.mapel, academic_year=self.tahun, nomor=2, deskripsi='menyelesaikan soal cerita'
        )
        self.tp3 = LearningObjective.objects.create(
            subject=self.mapel, academic_year=self.tahun, nomor=3, deskripsi='menjelaskan operasi pecahan'
        )


class PerhitunganTest(RaporTestBase):
    def test_deskripsi_capaian_mengikuti_nilai_tertinggi_dan_terendah(self):
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp2, semester=self.semester, nilai=2
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp3, semester=self.semester, nilai=3
        )

        hasil = deskripsi_capaian(self.siswa, self.mapel, self.semester)

        self.assertEqual(hasil['unggul'], self.tp1)
        self.assertEqual(hasil['perlu'], self.tp2)
        self.assertIn('Ananda sangat menguasai dalam menghitung bilangan bulat.', hasil['teks'])
        self.assertIn('Ananda perlu bimbingan dalam menyelesaikan soal cerita.', hasil['teks'])

    def test_deskripsi_kosong_tanpa_nilai(self):
        hasil = deskripsi_capaian(self.siswa, self.mapel, self.semester)
        self.assertEqual(hasil['teks'], '')

    def test_nilai_formatif_terpisah_per_semester(self):
        semester_2 = Semester.objects.create(
            academic_year=self.semester.academic_year, nama='II'
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4
        )

        hasil_1 = deskripsi_capaian(self.siswa, self.mapel, self.semester)
        hasil_2 = deskripsi_capaian(self.siswa, self.mapel, semester_2)

        self.assertEqual(hasil_1['unggul'], self.tp1)
        self.assertEqual(hasil_2['teks'], '')

    def test_nilai_rapor_rata_lm_sts_sas(self):
        for nomor, nilai in [(1, 80), (2, 90), (3, 100)]:
            SummativeLM.objects.create(
                student=self.siswa, subject=self.mapel, semester=self.semester,
                nomor=nomor, nilai=Decimal(nilai),
            )
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('80'), sas_non_tes=Decimal('90'), sas_tes=Decimal('100'),
        )
        nilai = SummativeScore.objects.get(student=self.siswa, subject=self.mapel)

        self.assertEqual(nilai.rata_lm, Decimal('90'))
        self.assertEqual(nilai.rata_sas, Decimal('95'))
        self.assertEqual(nilai.nilai_rapor.quantize(Decimal('0.01')), Decimal('88.33'))

    def test_leger_dan_ringkasan(self):
        SummativeLM.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            nomor=1, nilai=Decimal('100'),
        )
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('100'), sas_non_tes=Decimal('100'), sas_tes=Decimal('100'),
        )
        leger = data_leger(self.kelas, self.semester)

        self.assertEqual(len(leger['subjects']), 2)
        self.assertEqual(leger['rows'][0]['nilai'][0], Decimal('100'))
        self.assertIsNone(leger['rows'][0]['nilai'][1])

        rows = ringkasan_sumatif([self.siswa], self.mapel, self.semester)
        self.assertEqual(rows[0]['nilai_rapor'], Decimal('100'))

    def test_format_angka_indonesia(self):
        self.assertEqual(angka(Decimal('88.50')), '88,5')
        self.assertEqual(angka(None), '-')
        self.assertEqual(angka(Decimal('87.33')), '87,33')


class LoginTest(RaporTestBase):
    def test_halaman_wajib_login(self):
        response = self.client.get(reverse('akademik:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('akademik:login'), response.url)

    def test_laman_login_dapat_dibuka(self):
        response = self.client.get(reverse('akademik:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Masuk ke akun Anda')


class HalamanTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_uji', 'admin@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_semua_halaman_utama_dapat_dibuka(self):
        url_list = [
            reverse('akademik:dashboard'),
            reverse('akademik:identitas'),
            reverse('akademik:siswa_list'),
            reverse('akademik:siswa_tambah'),
            reverse('akademik:guru_list'),
            reverse('akademik:guru_tambah'),
            reverse('akademik:mapel_list'),
            reverse('akademik:mapel_tambah'),
            reverse('akademik:mengajar'),
            reverse('akademik:tahun_list'),
            reverse('akademik:tahun_tambah'),
            reverse('akademik:semester_tambah'),
            reverse('akademik:kelas_tambah'),
            reverse('akademik:pengguna_list'),
            reverse('akademik:pengguna_tambah'),
            reverse('akademik:profil'),
            reverse('akademik:ekspor', args=['siswa']),
            reverse('akademik:impor', args=['siswa']),
            reverse('akademik:tp_menu'),
            reverse('akademik:tp_list', args=[self.mapel.id]),
            reverse('akademik:tp_tambah'),
            reverse('akademik:formatif_menu'),
            reverse('akademik:formatif_evaluasi_tambah'),
            reverse('akademik:formatif_entry', args=[self.mapel.id]),
            reverse('akademik:sumatif_menu'),
            reverse('akademik:sumatif_evaluasi_tambah'),
            reverse('akademik:sumatif_entry', args=[self.mapel.id]),
            reverse('akademik:catatan_entry'),
            reverse('akademik:ekskul_entry'),
            reverse('akademik:leger'),
            reverse('akademik:rapor_index'),
            reverse('akademik:rapor_detail', args=[self.siswa.id]),
            reverse('akademik:rapor_sampul', args=[self.siswa.id]),
            reverse('akademik:cetak_semua'),
            reverse('akademik:ubah_password'),
        ]
        for url in url_list:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_simpan_nilai_formatif(self):
        data = {
            f'f_{self.siswa.id}_{self.tp1.id}': 4,
            f'f_{self.siswa.id}_{self.tp2.id}': 3,
        }
        response = self.client.post(
            reverse('akademik:formatif_entry', args=[self.mapel.id]), data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            FormativeScore.objects.filter(student=self.siswa).count(), 2
        )

        self.client.post(reverse('akademik:formatif_entry', args=[self.mapel.id]), {})
        self.assertEqual(FormativeScore.objects.filter(student=self.siswa).count(), 0)

    def test_rapor_menampilkan_nilai_dan_capaian(self):
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('90'), sas_non_tes=Decimal('90'), sas_tes=Decimal('90'),
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4
        )

        html = self.client.get(
            reverse('akademik:rapor_detail', args=[self.siswa.id])
        ).content.decode()

        self.assertIn(self.siswa.nama, html)
        self.assertIn('Ananda sangat menguasai', html)

    def test_identitas_tidak_tertukar_dengan_nama_kelas(self):
        response = self.client.post(reverse('akademik:identitas'), {
            'nama': 'SMP HASIL UBAH', 'alamat': 'Jl. Baru', 'tempat_rapor': 'Kotabumi',
            'judul_rapor': 'RAPOR UJI SEKOLAH',
            'subjudul_rapor': '(Uji)', 'ukuran_logo': 70, 'ukuran_font': 12,
            'font_rapor': 'arial', 'ukuran_kertas': 'F4',
            'label_ttd_orang_tua': 'Orang Tua/Wali',
            'label_ttd_kepala': 'Kepala Sekolah', 'label_ttd_wali': 'Wali Kelas',
            'tampilkan_logo': 'on', 'tampilkan_header': 'on', 'tampilkan_alamat': 'on',
            'tampilkan_ekskul': 'on', 'tampilkan_absensi': 'on', 'tampilkan_catatan': 'on',
            'tampilkan_ttd_orang_tua': 'on', 'tampilkan_ttd_kepala': 'on',
            'tampilkan_ttd_wali': 'on',
            'kelas-tingkat': 'VII', 'kelas-nama': 'Kelas Baru', 'kelas-fase': 'D',
        })
        self.assertEqual(response.status_code, 302)
        self.sekolah.refresh_from_db()
        self.kelas.refresh_from_db()
        self.assertEqual(self.sekolah.nama, 'SMP HASIL UBAH')
        self.assertEqual(self.sekolah.judul_rapor, 'RAPOR UJI SEKOLAH')
        self.assertEqual(self.sekolah.ukuran_kertas, 'F4')
        self.assertEqual(self.sekolah.font_rapor, 'arial')
        self.assertEqual(self.kelas.nama, 'Kelas Baru')


class AksesGuruTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_uji', 'admin@uji.id', 'rahasia123')

        self.user_guru = User.objects.create_user('guru_matematika', password='rahasia123')
        self.guru = Teacher.objects.create(nama='Guru Matematika', user=self.user_guru)
        self.user_lain = User.objects.create_user('guru_lain', password='rahasia123')
        self.guru_lain = Teacher.objects.create(nama='Guru Lain', user=self.user_lain)

        self.penugasan = TeachingAssignment.objects.create(
            teacher=self.guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )
        self.kelas.wali_kelas_guru = self.guru
        self.kelas.save()

    def test_guru_hanya_melihat_mapel_yang_diampu(self):
        self.client.force_login(self.user_guru)
        html = self.client.get(reverse('akademik:formatif_menu')).content.decode()
        self.assertIn('Matematika', html)
        self.assertNotIn('Bahasa Indonesia', html)

    def test_guru_dapat_mengisi_nilai_mapel_yang_diampu(self):
        self.client.force_login(self.user_guru)
        response = self.client.post(
            reverse('akademik:formatif_entry', args=[self.mapel.id]),
            {f'f_{self.siswa.id}_{self.tp1.id}': 4},
        )
        self.assertEqual(response.status_code, 302)
        nilai = FormativeScore.objects.get(student=self.siswa, objective=self.tp1)
        self.assertEqual(nilai.guru, self.guru)

        response = self.client.post(
            reverse('akademik:sumatif_entry', args=[self.mapel.id]),
            {f'sts_{self.siswa.id}': 90, f'sasn_{self.siswa.id}': 90, f'sast_{self.siswa.id}': 90},
        )
        self.assertEqual(response.status_code, 302)
        sumatif = SummativeScore.objects.get(student=self.siswa, subject=self.mapel)
        self.assertEqual(sumatif.guru, self.guru)

    def test_guru_tidak_dapat_mengisi_mapel_lain(self):
        self.client.force_login(self.user_guru)
        response = self.client.get(
            reverse('akademik:formatif_entry', args=[self.mapel2.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('akademik:dashboard'))

        response = self.client.post(
            reverse('akademik:sumatif_entry', args=[self.mapel2.id]),
            {f'sts_{self.siswa.id}': 90},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SummativeScore.objects.exists())

    def test_halaman_master_hanya_untuk_admin(self):
        self.client.force_login(self.user_guru)
        for name in ['identitas', 'guru_list', 'mapel_list', 'mengajar', 'siswa_tambah']:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(f'akademik:{name}')).status_code, 302
                )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('akademik:guru_list')).status_code, 200)

    def test_catatan_hanya_wali_atau_admin(self):
        self.client.force_login(self.user_lain)
        self.assertEqual(
            self.client.get(reverse('akademik:catatan_entry')).status_code, 302
        )
        self.client.force_login(self.user_guru)
        self.assertEqual(
            self.client.get(reverse('akademik:catatan_entry')).status_code, 200
        )

    def test_admin_membuat_akun_guru(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('akademik:guru_tambah'), {
            'nama': 'Guru Baru', 'jenis_kelamin': 'P', 'aktif': 'on',
            'username': 'guru_baru', 'password': 'rahasia123', 'akun_aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        guru = Teacher.objects.get(nama='Guru Baru')
        self.assertIsNotNone(guru.user)
        self.assertEqual(guru.user.username, 'guru_baru')
        self.assertTrue(guru.user.check_password('rahasia123'))
        self.assertFalse(guru.user.is_staff)

    def test_email_dan_nama_akun_guru_tersinkron(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('akademik:guru_ubah', args=[self.guru.id]), {
            'nama': 'Guru Matematika Baru', 'jenis_kelamin': 'L', 'aktif': 'on',
            'email': 'guru@uji.id', 'username': 'guru_matematika',
            'akun_aktif': 'on',
        })
        self.guru.refresh_from_db()
        self.guru.user.refresh_from_db()
        self.assertEqual(self.guru.user.first_name, 'Guru Matematika Baru')
        self.assertEqual(self.guru.user.email, 'guru@uji.id')


class PengaturanAkademikTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_akademik', 'a@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_aktifkan_tahun_sekaligus_semester_dan_kelas(self):
        year = AcademicYear.objects.create(tahun='2027/2028')
        semester = Semester.objects.create(academic_year=year, nama='I')
        kelas = ClassGroup.objects.create(
            academic_year=year, tingkat='VIII', nama='Baru', fase='D'
        )
        response = self.client.post(reverse('akademik:tahun_aktifkan', args=[year.id]))
        self.assertEqual(response.status_code, 302)
        year.refresh_from_db()
        semester.refresh_from_db()
        kelas.refresh_from_db()
        self.assertTrue(year.aktif)
        self.assertTrue(semester.aktif)
        self.assertTrue(kelas.aktif)
        self.assertFalse(ClassGroup.objects.get(pk=self.kelas.pk).aktif)

    def test_tahun_aktif_tidak_dapat_dihapus(self):
        response = self.client.post(
            reverse('akademik:tahun_hapus', args=[self.tahun.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AcademicYear.objects.filter(pk=self.tahun.id).exists())

    def test_tambah_semester_dan_kelas(self):
        response = self.client.post(reverse('akademik:semester_tambah'), {
            'academic_year': self.tahun.id, 'nama': 'II',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Semester.objects.filter(academic_year=self.tahun, nama='II').exists())

        guru = Teacher.objects.create(nama='Wali Baru')
        response = self.client.post(reverse('akademik:kelas_tambah'), {
            'academic_year': self.tahun.id, 'tingkat': 'IX', 'nama': 'Kelas IX',
            'fase': 'D', 'wali_kelas_guru': guru.id,
        })
        self.assertEqual(response.status_code, 302)
        kelas = ClassGroup.objects.get(academic_year=self.tahun, nama='Kelas IX')
        self.assertEqual(kelas.wali_kelas_guru, guru)
        self.assertEqual(kelas.wali_kelas, 'Wali Baru')


class PenggunaTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_user', 'a@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_admin_membuat_pengguna_biasa(self):
        response = self.client.post(reverse('akademik:pengguna_tambah'), {
            'username': 'operator1', 'first_name': 'Operator', 'last_name': 'Satu',
            'email': 'operator@uji.id', 'is_active': 'on', 'role': 'pengguna',
            'password': 'rahasia123',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='operator1')
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password('rahasia123'))

    def test_admin_menghubungkan_akun_dengan_data_guru(self):
        guru = Teacher.objects.create(nama='Guru Akun')
        response = self.client.post(reverse('akademik:pengguna_tambah'), {
            'username': 'guruakun', 'first_name': 'Guru', 'email': 'guru@uji.id',
            'is_active': 'on', 'role': 'guru', 'guru': guru.id,
            'password': 'rahasia123',
        })
        self.assertEqual(response.status_code, 302)
        guru.refresh_from_db()
        self.assertIsNotNone(guru.user)
        self.assertEqual(guru.user.username, 'guruakun')

    def test_admin_reset_password_pengguna(self):
        user = User.objects.create_user('resetme', password='lama12345')
        response = self.client.post(
            reverse('akademik:pengguna_reset_password', args=[user.id]),
            {'new_password1': 'baru12345', 'new_password2': 'baru12345'},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password('baru12345'))

    def test_pengguna_biasa_dan_guru_tidak_boleh_kelola_pengguna(self):
        user = User.objects.create_user('guru_saja', password='rahasia123')
        Teacher.objects.create(nama='Guru Saja', user=user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('akademik:pengguna_list')).status_code, 302)
        self.assertEqual(self.client.get(reverse('akademik:pengguna_tambah')).status_code, 302)

    def test_pengguna_dapat_edit_profil_sendiri(self):
        user = User.objects.create_user('profil1', password='rahasia123')
        self.client.force_login(user)
        response = self.client.post(reverse('akademik:profil'), {
            'username': 'profil1', 'first_name': 'Nama', 'last_name': 'Baru',
            'email': 'profil@uji.id',
        })
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Nama')
        self.assertEqual(user.last_name, 'Baru')
        self.assertEqual(user.email, 'profil@uji.id')


class EksporImporTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_excel', 'a@uji.id', 'rahasia123')
        self.user_guru = User.objects.create_user('guru_excel', password='rahasia123')
        self.guru = Teacher.objects.create(nama='Guru Excel', user=self.user_guru)
        TeachingAssignment.objects.create(
            teacher=self.guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )

    def _xlsx(self, headers, rows, nama='data.xlsx'):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        buf = BytesIO()
        wb.save(buf)
        return SimpleUploadedFile(
            nama, buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_ekspor_siswa_menghasilkan_excel(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('akademik:ekspor', args=['siswa']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])

    def test_impor_siswa(self):
        from .excel_io import SISWA_HEADERS

        self.client.force_login(self.admin)
        file = self._xlsx(SISWA_HEADERS, [
            [2, '999', '888', 'Siswa Impor', 'P', 'Kotabumi', '12 Januari 2014',
             'Islam', 'SD', 'Alamat', 'Ayah', 'Ibu', 'Kerja', 'Kerja', 'Alamat'],
        ])
        response = self.client.post(reverse('akademik:impor', args=['siswa']), {'file': file})
        self.assertEqual(response.status_code, 302)
        siswa = Student.objects.get(nama='Siswa Impor')
        self.assertEqual(siswa.nisn, '888')
        self.assertEqual(siswa.tanggal_lahir.isoformat(), '2014-01-12')

    def test_guru_dapat_ekspor_impor_formatif_mapelnya(self):
        from .excel_io import export_formatif

        self.client.force_login(self.user_guru)
        response = self.client.get(
            reverse('akademik:ekspor', args=['formatif']) + f'?mapel={self.mapel.id}'
        )
        self.assertEqual(response.status_code, 200)

        file = self._xlsx(
            ['No', 'NIS', 'NISN', 'Nama', 'TP 1', 'TP 2', 'TP 3'],
            [[1, self.siswa.nis, self.siswa.nisn, self.siswa.nama, 4, 3, 2]],
        )
        response = self.client.post(
            reverse('akademik:impor', args=['formatif']) + f'?mapel={self.mapel.id}',
            {'file': file},
        )
        self.assertEqual(response.status_code, 302)
        nilai = FormativeScore.objects.get(student=self.siswa, objective=self.tp1)
        self.assertEqual(nilai.nilai, 4)
        self.assertEqual(nilai.guru, self.guru)

    def test_guru_tidak_boleh_ekspor_mapel_lain(self):
        self.client.force_login(self.user_guru)
        response = self.client.get(
            reverse('akademik:ekspor', args=['formatif']) + f'?mapel={self.mapel2.id}'
        )
        self.assertEqual(response.status_code, 302)

    def test_ekspor_catatan_terbatas_wali(self):
        self.client.force_login(self.user_guru)
        self.assertEqual(
            self.client.get(reverse('akademik:ekspor', args=['catatan'])).status_code, 302
        )
        self.kelas.wali_kelas_guru = self.guru
        self.kelas.save()
        self.assertEqual(
            self.client.get(reverse('akademik:ekspor', args=['catatan'])).status_code, 200
        )

    def test_ekspor_leger_dan_template(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse('akademik:ekspor', args=['leger'])).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse('akademik:ekspor', args=['siswa']) + '?template=1').status_code, 200
        )

    def test_impor_sumatif(self):
        self.client.force_login(self.user_guru)
        headers = ['No', 'NIS', 'NISN', 'Nama'] + [
            f'LM {i}' for i in range(1, 11)
        ] + ['STS', 'SAS Non Tes', 'SAS Tes', 'Nilai Rapor (otomatis)']
        row = [1, self.siswa.nis, self.siswa.nisn, self.siswa.nama] + [
            80, 90, 100,
        ] + ['', '', '', '', '', '', ''] + [90, 80, 100, '']
        file = self._xlsx(headers, [row])
        response = self.client.post(
            reverse('akademik:impor', args=['sumatif']) + f'?mapel={self.mapel.id}',
            {'file': file},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SummativeLM.objects.get(
                student=self.siswa, subject=self.mapel, semester=self.semester, nomor=1
            ).nilai,
            Decimal('80'),
        )
        nilai = SummativeScore.objects.get(student=self.siswa, subject=self.mapel)
        self.assertEqual(nilai.sts, Decimal('90'))
        self.assertEqual(nilai.sas_tes, Decimal('100'))
        self.assertEqual(nilai.guru, self.guru)

    def test_impor_catatan_dan_ekskul_sebagai_wali(self):
        from .excel_io import CATATAN_HEADERS, EKSKUL_HEADERS

        self.kelas.wali_kelas_guru = self.guru
        self.kelas.save()
        self.client.force_login(self.user_guru)
        file = self._xlsx(
            CATATAN_HEADERS,
            [[1, self.siswa.nis, self.siswa.nisn, self.siswa.nama,
              'Catatan impor', 1, 2, 0]],
        )
        response = self.client.post(reverse('akademik:impor', args=['catatan']), {'file': file})
        self.assertEqual(response.status_code, 302)
        note = HomeroomNote.objects.get(student=self.siswa)
        self.assertEqual(note.catatan, 'Catatan impor')
        self.assertEqual(note.izin, 2)

        row = [1, self.siswa.nis, self.siswa.nisn, self.siswa.nama,
               'Basket', 'A', 'Sangat Baik'] + [''] * 12
        file = self._xlsx(EKSKUL_HEADERS, [row])
        response = self.client.post(reverse('akademik:impor', args=['ekskul']), {'file': file})
        self.assertEqual(response.status_code, 302)
        eks = Extracurricular.objects.get(student=self.siswa, urutan=1)
        self.assertEqual(eks.nama, 'Basket')
        self.assertEqual(eks.predikat, 'A')


class ScopingSidebarTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.user_guru = User.objects.create_user('guru_sidebar', password='rahasia123')
        self.guru = Teacher.objects.create(nama='Guru Sidebar', user=self.user_guru)
        TeachingAssignment.objects.create(
            teacher=self.guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )

    def test_guru_non_wali_tidak_melihat_menu_laporan(self):
        self.client.force_login(self.user_guru)
        html = self.client.get(reverse('akademik:dashboard')).content.decode()
        self.assertNotIn('Leger Nilai', html)
        self.assertNotIn('Cetak Rapor', html)
        self.assertNotIn('href="%s"' % reverse('akademik:siswa_list'), html)
        self.assertIn('Evaluasi Sumatif', html)
        self.assertEqual(self.client.get(reverse('akademik:leger')).status_code, 302)
        self.assertEqual(self.client.get(reverse('akademik:siswa_list')).status_code, 302)

    def test_wali_melihat_menu_laporan(self):
        self.kelas.wali_kelas_guru = self.guru
        self.kelas.save()
        self.client.force_login(self.user_guru)
        html = self.client.get(reverse('akademik:dashboard')).content.decode()
        self.assertIn('Leger Nilai', html)
        self.assertIn('Cetak Rapor', html)
        self.assertEqual(self.client.get(reverse('akademik:leger')).status_code, 200)
        self.assertEqual(self.client.get(reverse('akademik:siswa_list')).status_code, 200)


class TataLetakRaporTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_rapor', 'a@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_judul_dan_bagian_rapor_mengikuti_pengaturan(self):
        self.sekolah.judul_rapor = 'RAPOR UJI KHUSUS'
        self.sekolah.subjudul_rapor = '(Uji)'
        self.sekolah.tampilkan_ekskul = False
        self.sekolah.tampilkan_catatan = False
        self.sekolah.tampilkan_absensi = False
        self.sekolah.ukuran_kertas = 'F4'
        self.sekolah.font_rapor = 'arial'
        self.sekolah.save()
        html = self.client.get(
            reverse('akademik:rapor_detail', args=[self.siswa.id])
        ).content.decode()
        self.assertIn('RAPOR UJI KHUSUS', html)
        self.assertIn('(Uji)', html)
        self.assertNotIn('Ekstrakurikuler', html)
        self.assertNotIn('Ketidakhadiran', html)
        self.assertIn('font-arial', html)
        self.assertIn('215mm', html)


class PaginationFilterTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_page', 'a@uji.id', 'rahasia123')
        self.client.force_login(self.admin)
        for i in range(2, 31):
            Student.objects.create(
                class_group=self.kelas, no_urut=i, nama=f'Siswa {i:02d}',
                nis=f'{i:03d}', nisn=f'nisn{i:03d}', jenis_kelamin='P' if i % 2 else 'L',
            )

    def test_siswa_list_dibatasi_25_per_halaman(self):
        response = self.client.get(reverse('akademik:siswa_list'))
        self.assertEqual(response.context['page_obj'].paginator.count, 30)
        self.assertEqual(len(response.context['page_obj'].object_list), 25)

        response = self.client.get(reverse('akademik:siswa_list') + '?page=2')
        self.assertEqual(len(response.context['page_obj'].object_list), 5)

    def test_filter_pencarian_siswa(self):
        response = self.client.get(reverse('akademik:siswa_list') + '?q=Siswa 30')
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

        response = self.client.get(reverse('akademik:siswa_list') + '?jk=P')
        self.assertEqual(response.context['page_obj'].paginator.count, 14)

    def test_pengguna_list_paginasi_dan_filter_role(self):
        for i in range(1, 28):
            User.objects.create_user(f'user{i:02d}', password='rahasia123')
        response = self.client.get(reverse('akademik:pengguna_list'))
        self.assertEqual(len(response.context['page_obj'].object_list), 25)
        response = self.client.get(reverse('akademik:pengguna_list') + '?role=admin')
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_paginasi_tetap_menyimpan_nilai_halaman_lain(self):
        from .excel_io import export_formatif

        teacher_user = User.objects.create_user('guru_page', password='rahasia123')
        guru = Teacher.objects.create(nama='Guru Page', user=teacher_user)
        TeachingAssignment.objects.create(
            teacher=guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=3
        )
        self.client.force_login(teacher_user)
        url = reverse('akademik:formatif_entry', args=[self.mapel.id]) + '?page=2'
        siswa_page_2 = Student.objects.filter(class_group=self.kelas).order_by('no_urut')[25]
        response = self.client.post(
            url, {f'f_{siswa_page_2.id}_{self.tp1.id}': 4}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            FormativeScore.objects.get(student=self.siswa, objective=self.tp1).nilai, 3
        )
        self.assertEqual(
            FormativeScore.objects.get(student=siswa_page_2, objective=self.tp1).nilai, 4
        )


class TahunPelajaranTPTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_tp', 'a@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_tp_terpisah_per_tahun_pelajaran(self):
        tahun_lama = AcademicYear.objects.create(tahun='2025/2026')
        tp_lama = LearningObjective.objects.create(
            subject=self.mapel, academic_year=tahun_lama, nomor=1,
            deskripsi='TP dari tahun lama',
        )
        response = self.client.get(reverse('akademik:tp_list', args=[self.mapel.id]))
        ids = [tp.id for tp in response.context['objectives']]
        self.assertIn(self.tp1.id, ids)
        self.assertNotIn(tp_lama.id, ids)
        self.assertNotContains(response, 'TP dari tahun lama')

    def test_tp_dengan_nilai_diarsipkan_bukan_dihapus(self):
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4
        )
        response = self.client.post(
            reverse('akademik:tp_list', args=[self.mapel.id]),
            {'aksi': 'hapus', 'tp_id': self.tp1.id},
        )
        self.assertEqual(response.status_code, 302)
        self.tp1.refresh_from_db()
        self.assertFalse(self.tp1.aktif)
        self.assertTrue(
            FormativeScore.objects.filter(objective=self.tp1).exists()
        )

        response = self.client.post(
            reverse('akademik:tp_list', args=[self.mapel.id]) + '?status=arsip',
            {'aksi': 'aktifkan', 'tp_id': self.tp1.id},
        )
        self.assertEqual(response.status_code, 302)
        self.tp1.refresh_from_db()
        self.assertTrue(self.tp1.aktif)

    def test_rapor_menggunakan_tp_tahun_semester(self):
        tahun_lama = AcademicYear.objects.create(tahun='2025/2026')
        semester_lama = Semester.objects.create(academic_year=tahun_lama, nama='I')
        mapel_lama = Subject.objects.create(
            academic_year=tahun_lama, nama='Sejarah', urutan=1
        )
        tp_lama = LearningObjective.objects.create(
            subject=mapel_lama, academic_year=tahun_lama, nomor=1,
            deskripsi='materi tahun lalu',
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=tp_lama, semester=semester_lama, nilai=4
        )
        data_lama = data_rapor(self.siswa, semester_lama)
        baris_lama = next(
            row for row in data_lama['mapel_rows'] if row['subject'] == mapel_lama
        )
        self.assertIn('materi tahun lalu', baris_lama['capaian'])

    def test_deskripsi_rapor_memakai_snapshot_tp(self):
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4
        )
        self.tp1.deskripsi = 'deskripsi TP yang sudah diubah'
        self.tp1.save(update_fields=['deskripsi'])
        hasil = deskripsi_capaian(self.siswa, self.mapel, self.semester)
        self.assertIn('menghitung bilangan bulat', hasil['teks'])
        self.assertNotIn('deskripsi TP yang sudah diubah', hasil['teks'])


class CaptchaLoginTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_captcha', 'c@uji.id', 'rahasia123')

    def test_laman_login_menampilkan_captcha(self):
        response = self.client.get(reverse('akademik:login'))
        self.assertContains(response, 'captcha')
        self.assertContains(response, 'Kode Captcha')

    def test_login_berhasil_dengan_captcha(self):
        import datetime as dt

        from django.utils import timezone
        from captcha.models import CaptchaStore

        store = CaptchaStore.objects.create(
            hashkey='test-captcha-key', response='abcde',
            expiration=timezone.now() + dt.timedelta(minutes=5),
        )
        response = self.client.post(reverse('akademik:login'), {
            'username': 'admin_captcha',
            'password': 'rahasia123',
            'captcha_0': store.hashkey,
            'captcha_1': 'abcde',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_gagal_tanpa_captcha(self):
        response = self.client.post(reverse('akademik:login'), {
            'username': 'admin_captcha',
            'password': 'rahasia123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class TugasEvaluasiCrudTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_crud', 'crud@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_tambah_ubah_dan_arsip_tp(self):
        response = self.client.post(reverse('akademik:tp_tambah'), {
            'subject': self.mapel.id,
            'deskripsi': 'menyelesaikan operasi pecahan campuran',
            'aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        tugas = LearningObjective.objects.get(deskripsi='menyelesaikan operasi pecahan campuran')
        self.assertEqual(tugas.academic_year, self.tahun)
        self.assertEqual(tugas.nomor, 4)

        response = self.client.post(reverse('akademik:tp_ubah', args=[tugas.id]), {
            'subject': self.mapel.id,
            'nomor': tugas.nomor,
            'deskripsi': 'menyelesaikan operasi pecahan campuran dan desimal',
            'aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        tugas.refresh_from_db()
        self.assertEqual(tugas.deskripsi, 'menyelesaikan operasi pecahan campuran dan desimal')

        response = self.client.post(
            reverse('akademik:tp_list', args=[self.mapel.id]),
            {'aksi': 'hapus', 'tp_id': tugas.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            LearningObjective.objects.filter(deskripsi=tugas.deskripsi).exists()
        )

    def test_crud_evaluasi_formatif_dan_sumatif(self):
        response = self.client.post(reverse('akademik:formatif_evaluasi_tambah'), {
            'subject': self.mapel.id, 'nama': 'Kuis 1', 'jenis': 'kuis',
            'bobot': 10, 'aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        evaluasi = EvaluasiFormatif.objects.get(nama='Kuis 1')
        self.assertEqual(evaluasi.subject, self.mapel)

        response = self.client.post(
            reverse('akademik:formatif_evaluasi_ubah', args=[evaluasi.id]),
            {'subject': self.mapel.id, 'nama': 'Kuis Perbaikan', 'jenis': 'kuis',
             'bobot': 10, 'aktif': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        evaluasi.refresh_from_db()
        self.assertEqual(evaluasi.nama, 'Kuis Perbaikan')
        self.client.post(reverse('akademik:formatif_evaluasi_hapus', args=[evaluasi.id]))
        self.assertFalse(EvaluasiFormatif.objects.filter(nama='Kuis Perbaikan').exists())

        response = self.client.post(reverse('akademik:sumatif_evaluasi_tambah'), {
            'subject': self.mapel.id, 'nama': 'STS', 'jenis': 'sts',
            'bobot': 40, 'aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EvaluasiSumatif.objects.filter(nama='STS', subject=self.mapel).exists())

    def test_mapel_terikat_tahun_pelajaran(self):
        response = self.client.post(reverse('akademik:mapel_tambah'), {
            'academic_year': self.tahun.id, 'kode': 'MTK', 'nama': 'Matematika',
            'deskripsi': 'Mapel hitung', 'urutan': 9,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subject.objects.filter(nama='Matematika', kode='MTK').exists())

        tahun_lain = AcademicYear.objects.create(tahun='2030/2031')
        response = self.client.post(reverse('akademik:mapel_tambah'), {
            'academic_year': tahun_lain.id, 'kode': 'SEJ', 'nama': 'Sejarah',
            'deskripsi': 'Mapel sejarah', 'urutan': 1,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subject.objects.filter(nama='Sejarah', academic_year=tahun_lain).exists())

    def test_catatan_dan_ekskul_menyimpan_tahun(self):
        self.kelas.wali_kelas_guru = Teacher.objects.create(nama='Wali CRUD')
        self.kelas.save()
        wali = self.kelas.wali_kelas_guru
        user = User.objects.create_user('wali_crud', password='rahasia123')
        wali.user = user
        wali.save()
        self.client.force_login(user)
        self.client.post(reverse('akademik:catatan_entry'), {
            f'catatan_{self.siswa.id}': 'Catatan', f'sakit_{self.siswa.id}': 1,
            f'izin_{self.siswa.id}': 0, f'alpa_{self.siswa.id}': 0,
        })
        note = HomeroomNote.objects.get(student=self.siswa)
        self.assertEqual(note.academic_year, self.tahun)

        self.client.post(reverse('akademik:ekskul_entry'), {
            f'eks_{self.siswa.id}_1': 'Basket', f'pred_{self.siswa.id}_1': 'A',
            f'desk_{self.siswa.id}_1': 'Baik',
        })
        eks = Extracurricular.objects.get(student=self.siswa, urutan=1)
        self.assertEqual(eks.academic_year, self.tahun)


class RoleAuditTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_role', 'role@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_role_operator_dan_kepala_sekolah(self):
        response = self.client.post(reverse('akademik:pengguna_tambah'), {
            'username': 'operator_role', 'first_name': 'Operator',
            'email': 'operator@uji.id', 'is_active': 'on', 'role': 'operator',
            'password': 'rahasia123',
        })
        self.assertEqual(response.status_code, 302)
        operator = User.objects.get(username='operator_role')
        self.assertTrue(operator.groups.filter(name='Operator/Tata Usaha').exists())

        self.client.force_login(operator)
        self.assertEqual(self.client.get(reverse('akademik:mapel_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('akademik:pengguna_list')).status_code, 302)
        self.assertEqual(self.client.get(reverse('akademik:identitas')).status_code, 302)

        kepala = User.objects.create_user('kepala_role', password='rahasia123')
        from django.contrib.auth.models import Group
        kepala.groups.add(Group.objects.get(name='Kepala Sekolah'))
        self.client.force_login(kepala)
        self.assertEqual(self.client.get(reverse('akademik:leger')).status_code, 200)
        self.assertEqual(self.client.get(reverse('akademik:rapor_index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('akademik:mapel_list')).status_code, 302)

    def test_admin_bisa_melihat_audit_log(self):
        self.client.logout()
        self.client.login(username='admin_role', password='rahasia123')
        from akademik.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(aksi='LOGIN').exists())
        response = self.client.get(reverse('akademik:audit_log'))
        self.assertEqual(response.status_code, 200)

    def test_ganti_tahun_pelajaran_dari_topbar(self):
        tahun_baru = AcademicYear.objects.create(tahun='2028/2029')
        semester_baru = Semester.objects.create(academic_year=tahun_baru, nama='I')
        kelas_baru = ClassGroup.objects.create(
            academic_year=tahun_baru, tingkat='VIII', nama='Baru', fase='D'
        )
        response = self.client.post(reverse('akademik:pilih_tahun_pelajaran'), {
            'tahun': tahun_baru.id, 'next': reverse('akademik:dashboard'),
        })
        self.assertEqual(response.status_code, 302)
        tahun_baru.refresh_from_db()
        semester_baru.refresh_from_db()
        kelas_baru.refresh_from_db()
        self.assertTrue(tahun_baru.aktif)
        self.assertTrue(semester_baru.aktif)
        self.assertTrue(kelas_baru.aktif)
        self.assertFalse(AcademicYear.objects.get(pk=self.tahun.pk).aktif)


class ElemenUiTest(RaporTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_ui', 'ui@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def test_id_placeholder_dan_help_form(self):
        html = self.client.get(reverse('akademik:siswa_tambah')).content.decode()
        self.assertIn('id="form-siswa"', html)
        self.assertIn('placeholder="Masukkan', html)
        self.assertIn('data-help=', html)
        self.assertIn('id="app-layout"', html)
        self.assertIn('id="main-content"', html)

    def test_topbar_memiliki_chooser_periode(self):
        html = self.client.get(reverse('akademik:dashboard')).content.decode()
        self.assertIn('id="period-form"', html)
        self.assertIn('id="period-year-select"', html)
        self.assertIn('id="user-menu"', html)
        self.assertIn('id="dashboard-hero"', html)


class Tahap2StrukturTest(RaporTestBase):
    """Tahap 2: master Grade, riwayat enrollment, dan konsistensi tahun."""

    def test_siswa_otomatis_memiliki_enrollment(self):
        enrollment = StudentEnrollment.objects.get(student=self.siswa)
        self.assertEqual(enrollment.class_group, self.kelas)
        self.assertEqual(enrollment.academic_year, self.tahun)
        self.assertEqual(enrollment.status, 'AKTIF')

    def test_pindah_kelas_dalam_tahun_sama_memperbarui_enrollment(self):
        kelas_baru = ClassGroup.objects.create(
            academic_year=self.tahun, tingkat='VII', nama='Pindahan', fase='D'
        )
        self.siswa.class_group = kelas_baru
        self.siswa.save()

        self.assertEqual(self.siswa.enrollments.count(), 1)
        enrollment = self.siswa.enrollments.get()
        self.assertEqual(enrollment.class_group, kelas_baru)
        self.assertNotIn(self.siswa, Student.objects.in_class(self.kelas))
        self.assertIn(self.siswa, Student.objects.in_class(kelas_baru))

    def test_kenaikan_kelas_tidak_menghapus_riwayat(self):
        tahun_baru = AcademicYear.objects.create(tahun='2027/2028')
        kelas_baru = ClassGroup.objects.create(
            academic_year=tahun_baru, tingkat='VIII', nama='Naik', fase='D'
        )
        self.siswa.class_group = kelas_baru
        self.siswa.save()

        self.assertEqual(self.siswa.enrollments.count(), 2)
        lama = self.siswa.enrollment_for(self.tahun)
        baru = self.siswa.enrollment_for(tahun_baru)
        self.assertEqual(lama.class_group, self.kelas)
        self.assertEqual(baru.class_group, kelas_baru)
        # Roster kelas lama tetap dapat dilihat dari riwayat.
        self.assertIn(self.siswa, Student.objects.in_class(self.kelas))
        self.assertIn(self.siswa, Student.objects.in_class(kelas_baru))

    def test_enrollment_menolak_tahun_yang_tidak_sesuai(self):
        tahun_lain = AcademicYear.objects.create(tahun='2029/2030')
        enrollment = StudentEnrollment(
            student=self.siswa, class_group=self.kelas, academic_year=tahun_lain,
        )
        with self.assertRaises(ValidationError):
            enrollment.save()
        self.assertEqual(self.siswa.enrollments.count(), 1)

    def test_grade_terbentuk_dari_tingkat_dan_sinkron_dua_arah(self):
        kelas = ClassGroup.objects.create(
            academic_year=self.tahun, tingkat='VIII', nama='Delapan', fase='D'
        )
        self.assertIsNotNone(kelas.grade_id)
        self.assertEqual(kelas.grade.nama, 'VIII')

        kelas.grade = Grade.objects.create(nama='Kelas Khusus', fase='D', urutan=9)
        kelas.save()
        kelas.refresh_from_db()
        self.assertEqual(kelas.tingkat, 'Kelas Khusus')

    def test_ubah_tingkat_lewat_form_memperbarui_grade(self):
        admin = User.objects.create_superuser('admin_grade', 'g@uji.id', 'rahasia123')
        self.client.force_login(admin)
        response = self.client.post(
            reverse('akademik:kelas_ubah', args=[self.kelas.id]),
            {
                'academic_year': self.tahun.id,
                'tingkat': 'VIII',
                'nama': self.kelas.nama,
                'fase': 'D',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.kelas.refresh_from_db()
        self.assertEqual(self.kelas.tingkat, 'VIII')
        self.assertEqual(self.kelas.grade.nama, 'VIII')

    def test_penugasan_menolak_tahun_tidak_konsisten(self):
        tahun_lain = AcademicYear.objects.create(tahun='2027/2028')
        kelas_lain = ClassGroup.objects.create(
            academic_year=tahun_lain, tingkat='VIII', nama='Lain', fase='D'
        )
        penugasan = TeachingAssignment(
            teacher=Teacher.objects.create(nama='Guru Lain'),
            subject=self.mapel,
            class_group=kelas_lain,
            academic_year=tahun_lain,
        )
        with self.assertRaises(ValidationError):
            penugasan.save()

    def test_penugasan_per_semester_dan_setahun_dapat_berdampingan(self):
        guru = Teacher.objects.create(nama='Guru Semester')
        setahun = TeachingAssignment.objects.create(
            teacher=guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )
        per_semester = TeachingAssignment.objects.create(
            teacher=guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun, semester=self.semester,
        )
        self.assertIsNone(setahun.semester_id)
        self.assertEqual(per_semester.semester, self.semester)

        duplikat = TeachingAssignment(
            teacher=guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun, semester=self.semester,
        )
        with self.assertRaises(ValidationError):
            duplikat.save()

    def test_nilai_sumatif_menolak_semester_beda_tahun(self):
        tahun_lain = AcademicYear.objects.create(tahun='2027/2028')
        semester_lain = Semester.objects.create(academic_year=tahun_lain, nama='I')
        with self.assertRaises(ValidationError):
            SummativeScore.objects.create(
                student=self.siswa, subject=self.mapel, semester=semester_lain,
                sts=Decimal('80'),
            )

    def test_import_dan_export_kelas(self):
        from . import excel_io

        wb = Workbook()
        ws = wb.active
        ws.append(excel_io.KELAS_HEADERS)
        ws.append(['VIII', 'Impor Delapan', 'D', ''])
        data = BytesIO()
        wb.save(data)
        data.seek(0)

        hasil = excel_io.import_kelas(data, self.tahun)
        self.assertEqual(hasil['dibuat'], 1)
        kelas = ClassGroup.objects.get(academic_year=self.tahun, nama='Impor Delapan')
        self.assertEqual(kelas.grade.nama, 'VIII')
        self.assertEqual(kelas.tingkat, 'VIII')

        response = excel_io.export_kelas(self.tahun, template=True)
        isi = load_workbook(BytesIO(response.content)).active
        self.assertEqual(
            [cell.value for cell in isi[1]], excel_io.KELAS_HEADERS
        )

    def test_halaman_impor_kelas_dapat_dibuka(self):
        from django.contrib.auth.models import User as AuthUser

        admin = AuthUser.objects.create_superuser('admin_kelas', 'k@uji.id', 'rahasia123')
        self.client.force_login(admin)
        url = reverse('akademik:impor', args=['kelas']) + f'?tahun={self.tahun.id}'
        self.assertEqual(self.client.get(url).status_code, 200)
        export_url = reverse('akademik:ekspor', args=['kelas']) + f'?tahun={self.tahun.id}'
        self.assertEqual(self.client.get(export_url).status_code, 200)


class Tahap3PembelajaranTest(RaporTestBase):
    """Tahap 3: CP, materi, tugas, dan pengumpulan tugas."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_tahap3', 't3@uji.id', 'rahasia123')
        self.client.force_login(self.admin)
        self.guru = Teacher.objects.create(nama='Guru Tahap Tiga')
        TeachingAssignment.objects.create(
            teacher=self.guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )

    def test_crud_cp_dan_arsip_saat_dipakai_tp(self):
        response = self.client.post(reverse('akademik:cp_tambah'), {
            'subject': self.mapel.id, 'kode': 'CP.1', 'fase': 'D',
            'deskripsi': 'peserta didik mampu bernalar tentang bilangan',
            'urutan': '', 'aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        cp = LearningOutcome.objects.get(subject=self.mapel, kode='CP.1')
        self.assertEqual(cp.urutan, 1)

        tp = LearningObjective.objects.create(
            subject=self.mapel, learning_outcome=cp, academic_year=self.tahun,
            nomor=10, deskripsi='menjelaskan bilangan bulat',
        )
        self.client.post(reverse('akademik:cp_list', args=[self.mapel.id]), {
            'aksi': 'hapus', 'cp_id': cp.id,
        })
        cp.refresh_from_db()
        self.assertFalse(cp.aktif)
        self.assertTrue(LearningOutcome.objects.filter(pk=cp.id).exists())

        tp.delete()
        self.client.post(reverse('akademik:cp_list', args=[self.mapel.id]), {
            'aksi': 'hapus', 'cp_id': cp.id,
        })
        self.assertFalse(LearningOutcome.objects.filter(pk=cp.id).exists())

    def test_materi_menautkan_beberapa_tp(self):
        response = self.client.post(reverse('akademik:materi_tambah'), {
            'subject': self.mapel.id,
            'objectives': [self.tp1.id, self.tp2.id],
            'kode': 'M.1',
            'judul': 'Operasi Bilangan',
            'deskripsi': 'Materi operasi bilangan bulat',
            'urutan': '',
            'aktif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        materi = LearningMaterial.objects.get(subject=self.mapel, kode='M.1')
        self.assertEqual(materi.urutan, 1)
        self.assertEqual(materi.objectives.count(), 2)
        self.assertContains(
            self.client.get(reverse('akademik:materi_list', args=[self.mapel.id])),
            'Operasi Bilangan',
        )

    def test_tugas_terhubung_kelas_tp_dan_pembuat(self):
        response = self.client.post(reverse('akademik:tugas_pembelajaran_tambah'), {
            'subject': self.mapel.id,
            'class_groups': [self.kelas.id],
            'objectives': [self.tp1.id],
            'judul': 'Latihan Pecahan',
            'deskripsi': 'Kerjakan latihan',
            'instruksi': 'Tulis langkah pengerjaan',
            'tanggal_pemberian': '2026-11-20',
            'batas_pengumpulan': '2026-11-27',
            'bobot': '20',
            'status': 'TERBIT',
        })
        self.assertEqual(response.status_code, 302)
        tugas = LearningTask.objects.get(judul='Latihan Pecahan')
        self.assertEqual(tugas.academic_year, self.tahun)
        self.assertEqual(tugas.created_by, self.guru)
        self.assertEqual(tugas.objectives.get(), self.tp1)
        self.assertEqual(tugas.class_groups.get(), self.kelas)

    def test_tugas_menolak_tp_dari_mapel_lain(self):
        response = self.client.post(reverse('akademik:tugas_pembelajaran_tambah'), {
            'subject': self.mapel.id,
            'objectives': [LearningObjective.objects.create(
                subject=self.mapel2, academic_year=self.tahun, nomor=1,
                deskripsi='TP mapel lain',
            ).id],
            'judul': 'Tugas Salah',
            'bobot': '0', 'status': 'DRAF',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Semua TP harus berasal dari mata pelajaran yang sama',
                            status_code=200)
        self.assertFalse(LearningTask.objects.filter(judul='Tugas Salah').exists())

    def test_pengumpulan_tugas_disimpan_dari_halaman_detail(self):
        tugas = LearningTask.objects.create(
            subject=self.mapel, academic_year=self.tahun, judul='Tugas Kumpul',
            status='TERBIT', bobot=Decimal('10'),
        )
        tugas.class_groups.add(self.kelas)
        tugas.objectives.add(self.tp1)
        url = reverse('akademik:tugas_pembelajaran_detail', args=[tugas.id])
        self.assertEqual(self.client.get(url).status_code, 200)

        response = self.client.post(url, {
            'kelas': self.kelas.id,
            f'status_{self.siswa.id}': 'DINILAI',
            f'nilai_{self.siswa.id}': '88',
            f'catatan_{self.siswa.id}': 'Bagus',
        })
        self.assertEqual(response.status_code, 302)
        submission = LearningTaskSubmission.objects.get(task=tugas, student=self.siswa)
        self.assertEqual(submission.status, 'DINILAI')
        self.assertEqual(submission.nilai, Decimal('88'))
        self.assertEqual(submission.catatan_guru, 'Bagus')
        self.assertIsNotNone(submission.submitted_at)
        self.assertIsNotNone(submission.dinilai_at)

    def test_pengumpulan_menolak_siswa_tahun_lain(self):
        tahun_lain = AcademicYear.objects.create(tahun='2027/2028')
        kelas_lain = ClassGroup.objects.create(
            academic_year=tahun_lain, tingkat='VIII', nama='Lain', fase='D'
        )
        siswa_lain = Student.objects.create(
            class_group=kelas_lain, no_urut=1, nama='Siswa Tahun Lain'
        )
        tugas = LearningTask.objects.create(
            subject=self.mapel, academic_year=self.tahun, judul='Tugas Tahun Ini',
        )
        with self.assertRaises(ValidationError):
            LearningTaskSubmission.objects.create(task=tugas, student=siswa_lain)

    def test_import_export_cp_materi_tugas(self):
        from . import excel_io

        def berkas(headers, rows):
            wb = Workbook()
            ws = wb.active
            ws.append(headers)
            for row in rows:
                ws.append(row)
            data = BytesIO()
            wb.save(data)
            data.seek(0)
            return data

        # CP
        hasil = excel_io.import_cp(
            berkas(excel_io.CP_HEADERS, [
                ['CP.1', 'D', 'memahami bilangan bulat', '', 'Aktif'],
            ]),
            self.mapel,
        )
        self.assertEqual(hasil['dibuat'], 1)
        cp = LearningOutcome.objects.get(subject=self.mapel, kode='CP.1')

        # TP dengan tautan CP (kolom baru di akhir)
        hasil = excel_io.import_tp(
            berkas(excel_io.TP_HEADERS, [
                [10, 'menjelaskan bilangan', '', 'Aktif', 'TP.10', 'CP.1'],
            ]),
            self.mapel, self.tahun,
        )
        self.assertEqual(hasil['dibuat'], 1)

        # Materi
        hasil = excel_io.import_materi(
            berkas(excel_io.MATERI_HEADERS, [
                ['M.1', 'Bilangan Bulat', 'Materi', '10', '', 'Aktif'],
            ]),
            self.mapel,
        )
        self.assertEqual(hasil['dibuat'], 1)
        materi = LearningMaterial.objects.get(subject=self.mapel, kode='M.1')
        self.assertEqual(materi.objectives.count(), 1)

        # Tugas
        hasil = excel_io.import_tugas(
            berkas(excel_io.TUGAS_HEADERS, [
                ['Tugas Excel', 'Deskripsi', 'Instruksi', '2026-11-20',
                 '2026-11-27', '15', 'Terbit', '10', self.kelas.nama_lengkap],
            ]),
            self.mapel,
        )
        self.assertEqual(hasil['dibuat'], 1)
        tugas = LearningTask.objects.get(subject=self.mapel, judul='Tugas Excel')
        self.assertEqual(tugas.status, 'TERBIT')
        self.assertEqual(tugas.objectives.count(), 1)
        self.assertEqual(tugas.class_groups.get(), self.kelas)

        for respons in (
            excel_io.export_cp(self.mapel, template=True),
            excel_io.export_materi(self.mapel, template=True),
            excel_io.export_tugas(self.mapel, template=True),
        ):
            self.assertEqual(respons.status_code, 200)
            self.assertTrue(respons.content)

    def test_halaman_impor_ekspor_pembelajaran(self):
        from . import excel_io

        wb = Workbook()
        ws = wb.active
        ws.append(excel_io.CP_HEADERS)
        ws.append(['CP.9', 'D', 'capaian dari halaman impor', '', 'Aktif'])
        data = BytesIO()
        wb.save(data)
        unggah = SimpleUploadedFile(
            'cp.xlsx', data.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response = self.client.post(
            reverse('akademik:impor', args=['cp']) + f'?mapel={self.mapel.id}',
            {'file': unggah},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            LearningOutcome.objects.filter(subject=self.mapel, kode='CP.9').exists()
        )
        for kind in ('cp', 'materi', 'tugas'):
            with self.subTest(kind=kind):
                self.assertEqual(
                    self.client.get(
                        reverse('akademik:ekspor', args=[kind])
                        + f'?mapel={self.mapel.id}'
                    ).status_code,
                    200,
                )
                self.assertEqual(
                    self.client.get(
                        reverse('akademik:impor', args=[kind])
                        + f'?mapel={self.mapel.id}'
                    ).status_code,
                    200,
                )

    def test_semua_halaman_pembelajaran_dapat_dibuka(self):
        cp = LearningOutcome.objects.create(
            subject=self.mapel, kode='CP.1', deskripsi='CP uji',
        )
        materi = LearningMaterial.objects.create(
            subject=self.mapel, judul='Materi uji',
        )
        tugas = LearningTask.objects.create(
            subject=self.mapel, academic_year=self.tahun, judul='Tugas uji',
        )
        urls = [
            reverse('akademik:cp_menu'),
            reverse('akademik:cp_list', args=[self.mapel.id]),
            reverse('akademik:cp_tambah'),
            reverse('akademik:cp_ubah', args=[cp.id]),
            reverse('akademik:materi_menu'),
            reverse('akademik:materi_list', args=[self.mapel.id]),
            reverse('akademik:materi_tambah'),
            reverse('akademik:materi_ubah', args=[materi.id]),
            reverse('akademik:tugas_pembelajaran_list'),
            reverse('akademik:tugas_pembelajaran_list', args=[self.mapel.id]),
            reverse('akademik:tugas_pembelajaran_tambah'),
            reverse('akademik:tugas_pembelajaran_ubah', args=[tugas.id]),
            reverse('akademik:tugas_pembelajaran_detail', args=[tugas.id]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class Tahap4AsesmenTest(RaporTestBase):
    """Tahap 4: asesmen generik, sinkronisasi nilai, dan konfigurasi nilai."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_tahap4', 't4@uji.id', 'rahasia123')
        self.client.force_login(self.admin)
        self.guru = Teacher.objects.create(nama='Guru Tahap Empat')
        TeachingAssignment.objects.create(
            teacher=self.guru, subject=self.mapel, class_group=self.kelas,
            academic_year=self.tahun,
        )

    def test_sinyal_nilai_lama_membuat_asesmen_generik(self):
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4,
        )
        self.assertTrue(
            Assessment.objects.filter(
                subject=self.mapel, semester=self.semester, kategori='FORMATIF'
            ).exists()
        )
        self.assertTrue(
            AssessmentResult.objects.filter(
                student=self.siswa,
                component__assessment__kategori='FORMATIF',
                nilai=4,
            ).exists()
        )

        SummativeLM.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            nomor=1, nilai=Decimal('90'),
        )
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('80'), sas_non_tes=Decimal('90'), sas_tes=Decimal('100'),
        )
        kategori = set(
            AssessmentResult.objects.filter(
                student=self.siswa
            ).values_list('component__assessment__kategori', flat=True)
        )
        self.assertTrue({'FORMATIF', 'SUMATIF_LM', 'STS', 'SAS'} <= kategori)

    def test_simpan_ulang_tidak_membuat_result_ganda(self):
        score = FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=3,
        )
        score.nilai = 4
        score.save()
        hasil = AssessmentResult.objects.filter(
            student=self.siswa,
            component__assessment__kategori='FORMATIF',
        )
        self.assertEqual(hasil.count(), 1)
        self.assertEqual(hasil.first().nilai, Decimal('4'))

    def test_hitung_nilai_identik_dengan_rumus_excel(self):
        for nomor, nilai in [(1, 80), (2, 90), (3, 100)]:
            SummativeLM.objects.create(
                student=self.siswa, subject=self.mapel, semester=self.semester,
                nomor=nomor, nilai=Decimal(nilai),
            )
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('80'), sas_non_tes=Decimal('90'), sas_tes=Decimal('100'),
        )
        hasil = hitung_nilai(self.siswa, self.mapel, self.semester)
        self.assertEqual(hasil['rata_lm'], Decimal('90'))
        self.assertEqual(hasil['rata_sas'], Decimal('95'))
        self.assertEqual(hasil['nilai'], Decimal('88.33'))

        legacy = SummativeScore.objects.get(
            student=self.siswa, subject=self.mapel, semester=self.semester
        )
        self.assertEqual(
            legacy.nilai_rapor.quantize(Decimal('0.01')), hasil['nilai']
        )

    def test_komponen_kosong_tidak_dihitung_nol(self):
        SummativeLM.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            nomor=1, nilai=Decimal('80'),
        )
        hasil = hitung_nilai(self.siswa, self.mapel, self.semester)
        self.assertEqual(hasil['nilai'], Decimal('80'))
        self.assertIsNone(hasil['sts'])
        self.assertIsNone(hasil['rata_sas'])

    def test_konfigurasi_bobot_mengubah_perhitungan(self):
        GradeConfiguration.objects.create(
            subject=self.mapel, academic_year=self.tahun,
            bobot_lm=Decimal('2'), bobot_sts=Decimal('1'), bobot_sas=Decimal('1'),
            jumlah_desimal=2, metode_pembulatan='HALF_UP',
        )
        for nomor, nilai in [(1, 90), (2, 90)]:
            SummativeLM.objects.create(
                student=self.siswa, subject=self.mapel, semester=self.semester,
                nomor=nomor, nilai=Decimal(nilai),
            )
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('80'), sas_non_tes=Decimal('90'), sas_tes=Decimal('100'),
        )
        hasil = hitung_nilai(self.siswa, self.mapel, self.semester)
        # (2*90 + 1*80 + 1*95) / 4 = 88,75
        self.assertEqual(hasil['nilai'], Decimal('88.75'))

    def test_ambang_deskripsi_dari_konfigurasi(self):
        GradeConfiguration.objects.create(
            subject=self.mapel, academic_year=self.tahun,
            ambang_unggul=4, ambang_perlu_bimbingan=1,
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=4,
        )
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp2, semester=self.semester, nilai=2,
        )
        hasil = deskripsi_capaian(self.siswa, self.mapel, self.semester)
        self.assertEqual(hasil['unggul'], self.tp1)
        self.assertIsNone(hasil['perlu'])
        self.assertIn('sangat menguasai', hasil['teks'])
        self.assertNotIn('perlu bimbingan', hasil['teks'])

    def test_hitung_dari_asesmen_generik_tanpa_nilai_lama(self):
        assessment = Assessment.objects.create(
            subject=self.mapel, academic_year=self.tahun, semester=self.semester,
            nama='STS Manual', kategori='STS',
        )
        component = AssessmentComponent.objects.create(
            assessment=assessment, nama='STS', tipe='TES', nilai_maksimal=100,
        )
        AssessmentResult.objects.create(
            student=self.siswa, component=component, nilai=Decimal('77'),
        )
        hasil = hitung_nilai(self.siswa, self.mapel, self.semester)
        self.assertEqual(hasil['sts'], Decimal('77'))
        self.assertEqual(hasil['nilai'], Decimal('77'))

    def test_api_autosave_validasi_dan_tanpa_duplikat(self):
        assessment = Assessment.objects.create(
            subject=self.mapel, academic_year=self.tahun, semester=self.semester,
            nama='Asesmen API', kategori='SUMATIF_LM',
        )
        component = AssessmentComponent.objects.create(
            assessment=assessment, nama='Nilai', tipe='NILAI', nilai_maksimal=100,
        )
        url = reverse('akademik:asesmen_simpan', args=[assessment.id])
        kirim = self.client.post(
            url,
            data=json.dumps({
                'student': self.siswa.id, 'component': component.id, 'nilai': '85',
            }),
            content_type='application/json',
        )
        self.assertEqual(kirim.status_code, 200)
        self.assertTrue(
            AssessmentResult.objects.filter(
                student=self.siswa, component=component, nilai=Decimal('85')
            ).exists()
        )

        self.client.post(
            url,
            data=json.dumps({
                'student': self.siswa.id, 'component': component.id, 'nilai': '90',
            }),
            content_type='application/json',
        )
        self.assertEqual(
            AssessmentResult.objects.filter(student=self.siswa, component=component).count(),
            1,
        )
        self.assertEqual(
            AssessmentResult.objects.get(student=self.siswa, component=component).nilai,
            Decimal('90'),
        )

        gagal = self.client.post(
            url,
            data=json.dumps({
                'student': self.siswa.id, 'component': component.id, 'nilai': '101',
            }),
            content_type='application/json',
        )
        self.assertEqual(gagal.status_code, 400)
        self.assertEqual(
            AssessmentResult.objects.get(student=self.siswa, component=component).nilai,
            Decimal('90'),
        )

    def test_form_asesmen_menyimpan_komponen(self):
        data = {
            'subject': self.mapel.id,
            'class_group': '',
            'nama': 'Asesmen Baru',
            'kategori': 'SUMATIF_LM',
            'metode': 'TES',
            'tanggal': '',
            'bobot': '100',
            'deskripsi': '',
            'status': 'DRAF',
            'components-TOTAL_FORMS': '1',
            'components-INITIAL_FORMS': '0',
            'components-MIN_NUM_FORMS': '0',
            'components-MAX_NUM_FORMS': '1000',
            'components-0-nama': 'Nilai',
            'components-0-tipe': 'NILAI',
            'components-0-urutan': '1',
            'components-0-bobot': '100',
            'components-0-nilai_maksimal': '100',
            'components-0-wajib': 'on',
        }
        response = self.client.post(reverse('akademik:asesmen_tambah'), data)
        self.assertEqual(response.status_code, 302)
        assessment = Assessment.objects.get(nama='Asesmen Baru')
        self.assertEqual(assessment.semester, self.semester)
        self.assertEqual(assessment.components.count(), 1)

    def test_halaman_dan_ekspor_impor_asesmen(self):
        assessment = Assessment.objects.create(
            subject=self.mapel, academic_year=self.tahun, semester=self.semester,
            nama='Asesmen Halaman', kategori='SUMATIF_LM', status='TERBIT',
        )
        component = AssessmentComponent.objects.create(
            assessment=assessment, nama='Nilai', tipe='NILAI', nilai_maksimal=100,
        )
        urls = [
            reverse('akademik:asesmen_list'),
            reverse('akademik:asesmen_tambah'),
            reverse('akademik:asesmen_ubah', args=[assessment.id]),
            reverse('akademik:asesmen_grid', args=[assessment.id]),
            reverse('akademik:asesmen_impor', args=[assessment.id]),
            reverse('akademik:asesmen_ekspor', args=[assessment.id]),
            reverse('akademik:konfigurasi_nilai'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        from . import excel_io

        wb = Workbook()
        ws = wb.active
        ws.append(['No', 'NIS', 'NISN', 'Nama Peserta Didik', 'Nilai'])
        ws.append([1, self.siswa.nis, self.siswa.nisn, self.siswa.nama, 88])
        data = BytesIO()
        wb.save(data)
        data.seek(0)
        hasil = excel_io.import_asesmen(data, assessment, self.kelas)
        self.assertEqual(hasil['diperbarui'], 1)
        self.assertEqual(
            AssessmentResult.objects.get(student=self.siswa, component=component).nilai,
            Decimal('88'),
        )
        ekspor = excel_io.export_asesmen(assessment, self.kelas)
        self.assertEqual(ekspor.status_code, 200)
        self.assertTrue(ekspor.content)

    def test_konfigurasi_nilai_menolak_ambang_tidak_logis(self):
        response = self.client.post(reverse('akademik:konfigurasi_nilai'), {
            'bobot_lm': '1', 'bobot_sts': '1', 'bobot_sas': '1',
            'bobot_sas_non_tes': '1', 'bobot_sas_tes': '1',
            'metode_pembulatan': 'HALF_UP', 'jumlah_desimal': '2',
            'nilai_min': '0', 'nilai_max': '100',
            'ambang_unggul': '2', 'ambang_perlu_bimbingan': '2', 'aktif': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ambang perlu bimbingan harus lebih kecil')

    def test_hapus_mapel_dengan_nilai_tidak_menimbulkan_error(self):
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=3,
        )
        SummativeLM.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            nomor=1, nilai=Decimal('80'),
        )
        SummativeScore.objects.create(
            student=self.siswa, subject=self.mapel, semester=self.semester,
            sts=Decimal('80'),
        )
        self.mapel.delete()
        self.assertFalse(Assessment.objects.filter(nama__contains='TP 1').exists())


class Tahap5RaporTest(RaporTestBase):
    """Tahap 5: snapshot rapor, alur status, penguncian, dan PDF."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin_tahap5', 't5@uji.id', 'rahasia123')
        self.client.force_login(self.admin)

    def _lengkapi_nilai(self):
        for subject in (self.mapel, self.mapel2):
            SummativeLM.objects.create(
                student=self.siswa, subject=subject, semester=self.semester,
                nomor=1, nilai=Decimal('85'),
            )
            SummativeScore.objects.create(
                student=self.siswa, subject=subject, semester=self.semester,
                sts=Decimal('80'), sas_non_tes=Decimal('90'), sas_tes=Decimal('100'),
            )
        HomeroomNote.objects.create(
            student=self.siswa, semester=self.semester,
            academic_year=self.tahun, catatan='Tingkatkan literasi.',
            sakit=1, izin=2, alpa=0,
        )
        Extracurricular.objects.create(
            student=self.siswa, semester=self.semester, academic_year=self.tahun,
            urutan=1, nama='Pramuka', predikat='A', deskripsi='Aktif',
        )

    def test_susun_report_card_membuat_snapshot_lengkap(self):
        self._lengkapi_nilai()
        card = susun_report_card(self.siswa, self.semester, self.admin)

        self.assertEqual(card.status, 'DRAF')
        self.assertEqual(card.class_group, self.kelas)
        self.assertEqual(card.nilai_mapel.count(), 2)
        self.assertEqual(card.ekskul.count(), 1)
        self.assertEqual(card.catatan_wali, 'Tingkatkan literasi.')
        self.assertEqual(card.sakit, 1)
        grade = card.nilai_mapel.get(subject=self.mapel)
        self.assertIsNotNone(grade.nilai_akhir)
        self.assertEqual(periksa_kelengkapan(card), [])

    def test_snapshot_tidak_berubah_saat_nilai_sumber_diubah(self):
        self._lengkapi_nilai()
        card = susun_report_card(self.siswa, self.semester, self.admin)
        grade = card.nilai_mapel.get(subject=self.mapel)
        nilai_awal = grade.nilai_akhir

        SummativeLM.objects.filter(
            student=self.siswa, subject=self.mapel, semester=self.semester, nomor=1
        ).update(nilai=Decimal('99'))
        grade.refresh_from_db()
        self.assertEqual(grade.nilai_akhir, nilai_awal)

    def test_alur_status_dan_penguncian(self):
        self._lengkapi_nilai()
        card = susun_report_card(self.siswa, self.semester, self.admin)

        ajukan(card, self.admin)
        card.refresh_from_db()
        self.assertEqual(card.status, 'REVIEW')

        setujui(card, self.admin)
        card.refresh_from_db()
        self.assertEqual(card.status, 'APPROVED')
        self.assertIsNotNone(card.approved_at)

        terbitkan(card, self.admin)
        card.refresh_from_db()
        self.assertEqual(card.status, 'PUBLISHED')
        self.assertIsNotNone(card.locked_at)

        with self.assertRaises(ReportLocked):
            susun_report_card(self.siswa, self.semester, self.admin)

        buka_kunci(card, self.admin, 'Revisi nilai')
        card.refresh_from_db()
        self.assertEqual(card.status, 'REVISI')
        self.assertIsNone(card.locked_at)

    def test_ajukan_menolak_rapor_tidak_lengkap(self):
        FormativeScore.objects.create(
            student=self.siswa, objective=self.tp1, semester=self.semester, nilai=3,
        )
        message = HomeroomNote.objects.create(
            student=self.siswa, semester=self.semester, academic_year=self.tahun,
            catatan='Catatan',
        )
        self.assertIsNotNone(message)
        card = susun_report_card(self.siswa, self.semester, self.admin)
        with self.assertRaises(ReportIncomplete):
            ajukan(card, self.admin)

    def test_nilai_tidak_dapat_diubah_setelah_rapor_terbit(self):
        self._lengkapi_nilai()
        card = susun_report_card(self.siswa, self.semester, self.admin)
        ajukan(card, self.admin)
        setujui(card, self.admin)
        terbitkan(card, self.admin)
        before = FormativeScore.objects.count()

        self.client.post(
            reverse('akademik:formatif_entry', args=[self.mapel.id]),
            {f'f_{self.siswa.id}_{self.tp1.id}': 4},
        )
        self.assertEqual(FormativeScore.objects.count(), before)

        assessment = Assessment.objects.filter(subject=self.mapel).first()
        component = assessment.components.first()
        response = self.client.post(
            reverse('akademik:asesmen_simpan', args=[assessment.id]),
            data=json.dumps({
                'student': self.siswa.id, 'component': component.id, 'nilai': 99,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_halaman_rapor_dan_pdf(self):
        self._lengkapi_nilai()
        card = susun_report_card(self.siswa, self.semester, self.admin)
        urls = [
            reverse('akademik:rapor_index'),
            reverse('akademik:rapor_detail', args=[self.siswa.id]),
            reverse('akademik:rapor_sampul', args=[self.siswa.id]),
            reverse('akademik:cetak_semua'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        pdf = self.client.get(reverse('akademik:rapor_pdf', args=[self.siswa.id]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

        pdf_semua = self.client.get(reverse('akademik:rapor_pdf_semua'))
        self.assertEqual(pdf_semua.status_code, 200)
        self.assertTrue(pdf_semua.content.startswith(b'%PDF'))

        self.assertEqual(card.student, self.siswa)

    def test_aksi_workflow_lewat_halaman(self):
        self._lengkapi_nilai()
        card = susun_report_card(self.siswa, self.semester, self.admin)
        response = self.client.post(reverse('akademik:rapor_ajukan', args=[card.id]))
        self.assertEqual(response.status_code, 302)
        card.refresh_from_db()
        self.assertEqual(card.status, 'REVIEW')
        self.assertEqual(self.client.get(reverse('akademik:rapor_index')).status_code, 200)

        self.client.post(reverse('akademik:rapor_setujui', args=[card.id]))
        card.refresh_from_db()
        self.assertEqual(card.status, 'APPROVED')
        self.assertEqual(self.client.get(reverse('akademik:rapor_index')).status_code, 200)

        self.client.post(reverse('akademik:rapor_terbitkan', args=[card.id]))
        card.refresh_from_db()
        self.assertEqual(card.status, 'PUBLISHED')
        self.assertEqual(self.client.get(reverse('akademik:rapor_index')).status_code, 200)

        self.client.post(
            reverse('akademik:rapor_buka_kunci', args=[card.id]),
            {'alasan': 'Perbaikan nilai'},
        )
        card.refresh_from_db()
        self.assertEqual(card.status, 'REVISI')
        self.assertTrue(
            card.nilai_mapel.filter(subject=self.mapel).exists()
        )
