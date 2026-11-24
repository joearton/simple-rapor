"""Isi database dengan data demo yang realistis untuk pengecekan aplikasi."""

from datetime import date
from decimal import Decimal
import random

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from akademik.assessment_sync import sinkron_ulang_legacy
from akademik.models import (
    AcademicYear,
    ClassGroup,
    Extracurricular,
    FormativeScore,
    GradeConfiguration,
    HomeroomNote,
    LearningObjective,
    LearningOutcome,
    SchoolProfile,
    Semester,
    Student,
    StudentEnrollment,
    Subject,
    SummativeLM,
    SummativeScore,
    Teacher,
    TeachingAssignment,
)
from akademik.reporting import (
    ajukan,
    setujui,
    susun_report_card,
    terbitkan,
)

TAHUN = '2026/2027'
PASSWORD_DEMO = 'demo12345'

NAMA_DEPAN_L = [
    'Ahmad', 'Muhammad', 'Rizky', 'Fajar', 'Dimas', 'Andi', 'Bagus', 'Yoga',
    'Ilham', 'Reza', 'Farhan', 'Daffa', 'Rafi', 'Aditya', 'Naufal', 'Bima',
    'Satria', 'Arif', 'Galih', 'Hendra', 'Fikri', 'Rangga', 'Yusuf', 'Alif',
]
NAMA_DEPAN_P = [
    'Aisyah', 'Siti', 'Nabila', 'Putri', 'Dewi', 'Rina', 'Zahra', 'Nadia',
    'Intan', 'Lestari', 'Fitri', 'Anisa', 'Bella', 'Citra', 'Dinda', 'Eka',
    'Fadhilah', 'Gita', 'Hana', 'Indah', 'Kirana', 'Maya', 'Nur', 'Salma',
]
NAMA_BELAKANG = [
    'Pratama', 'Saputra', 'Wijaya', 'Lestari', 'Handayani', 'Nugroho',
    'Ramadhan', 'Maulana', 'Kurniawan', 'Sari', 'Hidayat', 'Setiawan',
    'Anggraini', 'Firmansyah', 'Utami', 'Permata', 'Siregar', 'Harahap',
    'Lubis', 'Wulandari',
]

GURU = [
    ('Dra. Siti Aminah', 'Matematika', 'VII Al-Lathif', 'L'),
    ('Ahmad Fauzi, S.Pd.', 'Bahasa Indonesia', 'VIII Al-Lathif', 'L'),
    ('Rina Kartika, S.Pd.', 'IPA', 'VII Ar-Rahman', 'P'),
    ('Dedi Setiawan, S.Pd.', 'IPS', 'IX Al-Lathif', 'L'),
    ('Nurul Hidayah, S.Pd.', 'Bahasa Inggris', None, 'P'),
    ('M. Ridwan, S.Ag.', 'PAIBP', None, 'L'),
    ('Yuni Lestari, S.Pd.', 'PPKn', None, 'P'),
    ('Agus Salim, S.Pd.', 'PJOK', None, 'L'),
    ('Dewi Sartika, S.Sn.', 'Seni Budaya', None, 'P'),
    ('Fajar Pratama, S.Kom.', 'Informatika', None, 'L'),
]

MAPEL = [
    ('Matematika', 'MAT', 1),
    ('Bahasa Indonesia', 'BIN', 2),
    ('IPA', 'IPA', 3),
    ('IPS', 'IPS', 4),
    ('Bahasa Inggris', 'BIG', 5),
    ('PAIBP', 'PAI', 6),
    ('PPKn', 'PKN', 7),
    ('PJOK', 'PJOK', 8),
    ('Seni Budaya', 'SBD', 9),
    ('Informatika', 'INF', 10),
]

TP_ISI = {
    'Matematika': [
        'menjelaskan bilangan bulat dan operasinya',
        'menyelesaikan masalah perbandingan dan skala',
        'menghitung luas dan keliling bangun datar',
    ],
    'Bahasa Indonesia': [
        'menemukan gagasan pokok teks deskripsi',
        'menyusun teks prosedur secara runtut',
        'menyampaikan pendapat dengan santun',
    ],
    'IPA': [
        'mengidentifikasi ciri makhluk hidup',
        'menjelaskan perubahan wujud zat',
        'menyajikan hasil pengamatan sederhana',
    ],
    'IPS': [
        'menjelaskan letak dan kondisi geografis Indonesia',
        'mengidentifikasi keragaman sosial budaya',
        'menjelaskan aktivitas ekonomi masyarakat',
    ],
    'Bahasa Inggris': [
        'memperkenalkan diri secara lisan',
        'menyusun kalimat simple present tense',
        'memahami teks pendek tentang kegiatan sehari-hari',
    ],
    'PAIBP': [
        'membaca Al-Qur’an dengan tartil',
        'menjelaskan makna kejujuran',
        'mencontohkan perilaku hidup bersih',
    ],
    'PPKn': [
        'menjelaskan makna Pancasila',
        'menunjukkan sikap gotong royong',
        'memahami hak dan kewajiban warga sekolah',
    ],
    'PJOK': [
        'mempraktikkan gerak dasar lokomotor',
        'menjelaskan pola makan sehat',
        'bermain bola voli dengan sportif',
    ],
    'Seni Budaya': [
        'menggambar bentuk dengan proporsi',
        'menyanyikan lagu daerah dengan ekspresi',
        'menampilkan karya seni sederhana',
    ],
    'Informatika': [
        'menggunakan aplikasi pengolah kata',
        'menjelaskan keamanan data pribadi',
        'menyusun algoritma sederhana',
    ],
}

CATATAN = [
    'Ananda menunjukkan sikap yang baik dan aktif dalam pembelajaran. Pertahankan semangat belajar dan terus tingkatkan kedisiplinan.',
    'Ananda sudah mengikuti pembelajaran dengan baik. Perlu lebih percaya diri saat menyampaikan pendapat di depan kelas.',
    'Ananda memiliki kemauan belajar yang tinggi. Tingkatkan ketelitian dalam mengerjakan tugas dan latihan soal.',
    'Ananda cukup aktif dalam kegiatan kelas. Manfaatkan waktu belajar di rumah dengan lebih teratur.',
    'Ananda menunjukkan perkembangan yang baik. Terus berlatih membaca dan memperbanyak kosakata.',
]

EKSTRA = [
    ('Pramuka', 'A', 'Aktif dan mampu bekerja sama dalam kelompok.'),
    ('Futsal', 'B', 'Mengikuti latihan dengan disiplin dan sportif.'),
    ('Seni Tari', 'A', 'Menampilkan tari daerah dengan percaya diri.'),
    ('Palang Merah Remaja', 'B', 'Aktif dalam kegiatan kesehatan sekolah.'),
]


class Command(BaseCommand):
    help = 'Isi data demo realistis: guru, siswa, nilai, dan rapor.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Hapus data tahun demo yang sudah ada lalu isi ulang.',
        )

    def handle(self, *args, **options):
        if AcademicYear.objects.filter(tahun=TAHUN).exists() and not options['force']:
            raise CommandError(
                f'Data tahun {TAHUN} sudah ada. Jalankan dengan --force untuk mengganti.'
            )
        with transaction.atomic():
            if options['force']:
                self._bersihkan()
            self._isi()
        self.stdout.write(self.style.SUCCESS('Data demo selesai dibuat.'))
        self.stdout.write(
            'Akun demo (password: %s): demo_kepsek, demo_operator, '
            'demo_wali, demo_guru, demo_siswa' % PASSWORD_DEMO
        )

    def _bersihkan(self):
        from akademik.models import (
            Assessment,
            AssessmentComponent,
            AssessmentObjective,
            AssessmentResult,
            AssessmentRubric,
            LearningTaskSubmission,
            ReportCard,
        )

        tahun = AcademicYear.objects.filter(tahun=TAHUN).first()
        if tahun is None:
            return
        ReportCard.objects.filter(semester__academic_year=tahun).delete()
        LearningTaskSubmission.objects.filter(task__academic_year=tahun).delete()
        AssessmentResult.objects.filter(
            component__assessment__academic_year=tahun
        ).delete()
        AssessmentRubric.objects.filter(
            component__assessment__academic_year=tahun
        ).delete()
        AssessmentObjective.objects.filter(assessment__academic_year=tahun).delete()
        AssessmentComponent.objects.filter(assessment__academic_year=tahun).delete()
        Assessment.objects.filter(academic_year=tahun).delete()
        StudentEnrollment.objects.filter(academic_year=tahun).delete()
        tahun.delete()

    def _akun(self, username, groups, nama_depan='', nama_belakang=''):
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = nama_depan or user.first_name
        user.last_name = nama_belakang or user.last_name
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(PASSWORD_DEMO)
        user.save()
        user.groups.clear()
        for nama_group in groups:
            group, _ = Group.objects.get_or_create(name=nama_group)
            user.groups.add(group)
        return user

    def _isi(self):
        rnd = random.Random(20261124)
        sekolah = SchoolProfile.get_solo()
        sekolah.nama = 'SMP MUHAMMADIYAH SOEKARNO HATTA KOTABUMI'
        sekolah.npsn = '10802345'
        sekolah.nss = '204026001001'
        sekolah.alamat = 'Jl. Soekarno Hatta No. 12'
        sekolah.desa = 'Kotabumi'
        sekolah.kecamatan = 'Kotabumi'
        sekolah.kabupaten = 'Lampung Utara'
        sekolah.provinsi = 'Lampung'
        sekolah.kepala_sekolah = 'Drs. H. Ahmad Fauzi, M.Pd.'
        sekolah.nktam_kepala = 'NKTAM 112233'
        sekolah.tempat_rapor = 'Kotabumi'
        sekolah.save()

        AcademicYear.objects.update(aktif=False)
        tahun, _ = AcademicYear.objects.get_or_create(tahun=TAHUN)
        tahun.tanggal_mulai = date(2026, 7, 13)
        tahun.tanggal_berakhir = date(2027, 6, 30)
        tahun.aktif = True
        tahun.save()
        semester_1, _ = Semester.objects.get_or_create(
            academic_year=tahun, nama='I', defaults={'aktif': True}
        )
        semester_2, _ = Semester.objects.get_or_create(
            academic_year=tahun, nama='II'
        )
        Semester.objects.update(aktif=False)
        semester_1.aktif = True
        semester_1.save(update_fields=['aktif'])

        teachers = {}
        for index, (nama, mapel, wali, jk) in enumerate(GURU):
            teacher, _ = Teacher.objects.get_or_create(
                nama=nama,
                defaults={
                    'jenis_kelamin': jk,
                    'nktam': f'NKTAM-{index + 1:03d}',
                    'jabatan': 'Guru Mata Pelajaran',
                    'email': f'guru{index + 1}@smpmuh.sch.id',
                    'no_hp': f'0812{index + 1:02d}3456',
                    'aktif': True,
                },
            )
            teachers[nama] = teacher

        akun_wali = self._akun(
            'demo_wali', ['Guru Mata Pelajaran'], 'Siti', 'Aminah'
        )
        teachers['Dra. Siti Aminah'].user = akun_wali
        teachers['Dra. Siti Aminah'].save(update_fields=['user'])
        akun_guru = self._akun(
            'demo_guru', ['Guru Mata Pelajaran'], 'Rina', 'Kartika'
        )
        teachers['Rina Kartika, S.Pd.'].user = akun_guru
        teachers['Rina Kartika, S.Pd.'].save(update_fields=['user'])

        kelas_data = [
            ('VII', 'Al-Lathif', 'Dra. Siti Aminah', 24),
            ('VII', 'Ar-Rahman', 'Rina Kartika, S.Pd.', 20),
            ('VIII', 'Al-Lathif', 'Ahmad Fauzi, S.Pd.', 18),
            ('IX', 'Al-Lathif', 'Dedi Setiawan, S.Pd.', 16),
        ]
        kelas_list = []
        ClassGroup.objects.update(aktif=False)
        for index, (tingkat, nama, wali, _) in enumerate(kelas_data):
            kelas, _ = ClassGroup.objects.update_or_create(
                academic_year=tahun,
                tingkat=tingkat,
                nama=nama,
                defaults={
                    'fase': 'D',
                    'wali_kelas_guru': teachers.get(wali),
                    'wali_kelas': wali,
                    'aktif': index == 0,
                },
            )
            kelas_list.append(kelas)

        subjects = {}
        for nama, kode, urutan in MAPEL:
            subject, _ = Subject.objects.get_or_create(
                academic_year=tahun,
                nama=nama,
                defaults={'kode': kode, 'urutan': urutan},
            )
            subject.kode = kode
            subject.urutan = urutan
            subject.save(update_fields=['kode', 'urutan'])
            subjects[nama] = subject
            cp, _ = LearningOutcome.objects.get_or_create(
                subject=subject,
                urutan=1,
                defaults={
                    'kode': f'CP-{kode}',
                    'fase': 'D',
                    'deskripsi': f'Peserta didik mampu memahami dan menerapkan konsep dasar {nama.lower()}.',
                },
            )
            for nomor, isi in enumerate(TP_ISI[nama], start=1):
                LearningObjective.objects.update_or_create(
                    subject=subject,
                    academic_year=tahun,
                    nomor=nomor,
                    defaults={
                        'deskripsi': isi,
                        'kode': f'{kode}.{nomor}',
                        'learning_outcome': cp,
                        'guru': teachers[GURU[(urutan - 1) % len(GURU)][0]],
                        'aktif': True,
                    },
                )

        guru_mapel = {mapel: teachers[nama] for nama, mapel, _, _ in GURU}
        for kelas in kelas_list:
            for nama, _, _ in MAPEL:
                TeachingAssignment.objects.update_or_create(
                    subject=subjects[nama],
                    class_group=kelas,
                    academic_year=tahun,
                    semester=None,
                    defaults={'teacher': guru_mapel[nama]},
                )

        students_by_class = {}
        for kelas_index, (kelas, (_, _, _, jumlah)) in enumerate(zip(kelas_list, kelas_data)):
            siswa_list = []
            dipakai = set()
            for i in range(jumlah):
                jk = 'L' if (i + kelas_index) % 2 == 0 else 'P'
                nama = self._nama_unik(rnd, jk, dipakai, i + kelas_index)
                tanggal = date(
                    2012 - (2 if kelas.tingkat == 'VII' else 1 if kelas.tingkat == 'VIII' else 0),
                    (i % 12) + 1,
                    (i * 3 % 26) + 1,
                )
                siswa, _ = Student.objects.update_or_create(
                    class_group=kelas,
                    no_urut=i + 1,
                    defaults={
                        'nis': f'{26}{kelas_index + 1}{i + 1:03d}',
                        'nisn': f'00{26}{kelas_index + 1}{i + 1:05d}',
                        'nama': nama,
                        'jenis_kelamin': jk,
                        'tempat_lahir': 'Kotabumi',
                        'tanggal_lahir': tanggal,
                        'agama': 'Islam',
                        'pendidikan_sebelumnya': 'SD Negeri Kotabumi',
                        'alamat': f'Jl. Merdeka No. {i + 5}, Kotabumi',
                        'nama_ayah': f'Bapak {rnd.choice(NAMA_DEPAN_L)} {rnd.choice(NAMA_BELAKANG)}',
                        'nama_ibu': f'Ibu {rnd.choice(NAMA_DEPAN_P)} {rnd.choice(NAMA_BELAKANG)}',
                        'pekerjaan_ayah': rnd.choice(['Petani', 'Wiraswasta', 'PNS', 'Karyawan']),
                        'pekerjaan_ibu': rnd.choice(['Ibu Rumah Tangga', 'Guru', 'Pedagang', 'Karyawan']),
                        'alamat_orang_tua': f'Jl. Merdeka No. {i + 5}, Kotabumi',
                        'aktif': True,
                    },
                )
                siswa_list.append(siswa)
            students_by_class[kelas.id] = siswa_list

        for kelas in kelas_list:
            self._isi_nilai(
                students_by_class[kelas.id], subjects, semester_1, rnd
            )
            self._isi_catatan_dan_ekskul(
                students_by_class[kelas.id], semester_1, rnd
            )
        sinkron_ulang_legacy()

        admin = User.objects.filter(is_superuser=True).order_by('id').first()
        cards = []
        for index, siswa in enumerate(students_by_class[kelas_list[0].id]):
            card = susun_report_card(siswa, semester_1, admin)
            cards.append(card)
            if index < 12:
                ajukan(card, admin)
                setujui(card, admin)
                terbitkan(card, admin)
            elif index < 16:
                ajukan(card, admin)
            elif index < 19:
                ajukan(card, admin)
                setujui(card, admin)

        # Akun portal untuk siswa dengan rapor terbit pertama.
        self._akun('demo_siswa', ['Siswa/Orang Tua'], 'Aisyah', 'Pratama')
        portal_user = User.objects.get(username='demo_siswa')
        siswa_portal = cards[0].student
        Student.objects.filter(user=portal_user).exclude(pk=siswa_portal.pk).update(user=None)
        siswa_portal.user = portal_user
        siswa_portal.save(update_fields=['user'])

        self._akun('demo_kepsek', ['Kepala Sekolah'], 'Ahmad', 'Fauzi')
        self._akun('demo_operator', ['Operator/Tata Usaha'], 'Operator', 'Sekolah')
        GradeConfiguration.get_config()

        # Semester II dibuat sebagai periode berikutnya tanpa memaksa nilai.
        semester_2.save()

    def _nama_unik(self, rnd, jk, dipakai, seed):
        pool = NAMA_DEPAN_L if jk == 'L' else NAMA_DEPAN_P
        for percobaan in range(200):
            nama = f'{pool[(seed + percobaan) % len(pool)]} {NAMA_BELAKANG[(seed * 3 + percobaan) % len(NAMA_BELAKANG)]}'
            if nama not in dipakai:
                dipakai.add(nama)
                return nama
        nama = f'{pool[seed % len(pool)]} {NAMA_BELAKANG[seed % len(NAMA_BELAKANG)]} {seed}'
        dipakai.add(nama)
        return nama

    def _isi_nilai(self, students, subjects, semester, rnd):
        FormativeScore.objects.filter(
            student__in=students, semester=semester
        ).delete()
        SummativeLM.objects.filter(student__in=students, semester=semester).delete()
        SummativeScore.objects.filter(student__in=students, semester=semester).delete()

        formatif = []
        lm = []
        sumatif = []
        for index_siswa, siswa in enumerate(students):
            for index_mapel, subject in enumerate(subjects.values()):
                dasar = 70 + ((index_siswa * 7 + index_mapel * 5) % 22)
                for tp in subject.tujuan_list.filter(academic_year=semester.academic_year):
                    nilai = 4 if dasar >= 82 else 3 if dasar >= 70 else 2
                    formatif.append(FormativeScore(
                        student=siswa,
                        objective=tp,
                        semester=semester,
                        nilai=nilai,
                        deskripsi_tp=tp.deskripsi,
                    ))
                for nomor, selisih in enumerate((-5, -1, 3, 5), start=1):
                    lm.append(SummativeLM(
                        student=siswa,
                        subject=subject,
                        semester=semester,
                        nomor=nomor,
                        nilai=Decimal(str(max(55, min(100, dasar + selisih)))),
                    ))
                sumatif.append(SummativeScore(
                    student=siswa,
                    subject=subject,
                    semester=semester,
                    sts=Decimal(str(max(55, min(100, dasar - 2)))),
                    sas_non_tes=Decimal(str(max(55, min(100, dasar + 1)))),
                    sas_tes=Decimal(str(max(55, min(100, dasar + 3)))),
                ))
        FormativeScore.objects.bulk_create(formatif, batch_size=500)
        SummativeLM.objects.bulk_create(lm, batch_size=500)
        SummativeScore.objects.bulk_create(sumatif, batch_size=500)

    def _isi_catatan_dan_ekskul(self, students, semester, rnd):
        HomeroomNote.objects.filter(
            student__in=students, semester=semester
        ).delete()
        Extracurricular.objects.filter(
            student__in=students, semester=semester
        ).delete()
        catatan = []
        ekskul = []
        for index, siswa in enumerate(students):
            catatan.append(HomeroomNote(
                student=siswa,
                semester=semester,
                academic_year=semester.academic_year,
                catatan=CATATAN[index % len(CATATAN)],
                sakit=rnd.randint(0, 2),
                izin=rnd.randint(0, 2),
                alpa=rnd.randint(0, 1),
            ))
            for urutan in (1, 2):
                nama, predikat, deskripsi = EKSTRA[(index + urutan) % len(EKSTRA)]
                ekskul.append(Extracurricular(
                    student=siswa,
                    semester=semester,
                    academic_year=semester.academic_year,
                    urutan=urutan,
                    nama=nama,
                    predikat=predikat,
                    deskripsi=deskripsi,
                ))
        HomeroomNote.objects.bulk_create(catatan, batch_size=200)
        Extracurricular.objects.bulk_create(ekskul, batch_size=200)
