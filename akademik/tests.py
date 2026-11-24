from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    AcademicYear,
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
from .services import angka, data_leger, data_rapor, deskripsi_capaian, ringkasan_sumatif


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
