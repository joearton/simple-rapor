"""Data demo lintas tahun: satu angkatan naik dari VII ke IX."""

from datetime import date
from decimal import Decimal
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from akademik.assessment_sync import sinkron_ulang_legacy
from akademik.models import (
    AcademicYear,
    ClassGroup,
    EvaluasiFormatif,
    EvaluasiSumatif,
    ExtracurricularActivity,
    ExtracurricularEnrollment,
    FormativeScore,
    HomeroomNote,
    LearningObjective,
    LearningOutcome,
    ReportCard,
    Semester,
    Student,
    Subject,
    SummativeLM,
    SummativeScore,
    Teacher,
    TeachingAssignment,
)
from akademik.reporting import ajukan, setujui, susun_report_card, terbitkan

from .seed_demo import (
    CATATAN,
    GURU,
    MAPEL,
    NAMA_BELAKANG,
    NAMA_DEPAN_L,
    NAMA_DEPAN_P,
    TP_ISI,
)

TAHUN_LALU = '2025/2026'
TAHUN_INI = '2026/2027'
TAHUN_DEPAN = '2027/2028'
JUMLAH_SISWA = 20


class Command(BaseCommand):
    help = 'Buat data demo lintas tahun untuk satu angkatan VII-VIII-IX.'

    def handle(self, *args, **options):
        jika_ada = AcademicYear.objects.filter(
            tahun__in=(TAHUN_LALU, TAHUN_DEPAN)
        ).exists()
        if jika_ada:
            raise CommandError(
                'Data tahun lintas sudah ada. Hapus tahun 2025/2026 dan '
                '2027/2028 terlebih dahulu jika ingin mengulang.'
            )
        with transaction.atomic():
            self._isi()
        self.stdout.write(self.style.SUCCESS(
            'Data lintas tahun dibuat: satu angkatan VII → VIII → IX.'
        ))

    def _guru(self, nama, index):
        guru, _ = Teacher.objects.get_or_create(
            nama=nama,
            defaults={
                'jenis_kelamin': 'L',
                'nktam': f'NKTAM-LT-{index:03d}',
                'jabatan': 'Guru Mata Pelajaran',
                'email': f'guru.lt{index}@smpmuh.sch.id',
                'aktif': True,
            },
        )
        return guru

    def _mapel(self, tahun):
        subjects = {}
        for nama, kode, urutan in MAPEL:
            subject, _ = Subject.objects.get_or_create(
                academic_year=tahun,
                nama=nama,
                defaults={'kode': kode, 'urutan': urutan},
            )
            subjects[nama] = subject
            cp, _ = LearningOutcome.objects.get_or_create(
                subject=subject,
                urutan=1,
                defaults={
                    'kode': f'CP-{kode}',
                    'fase': 'D',
                    'deskripsi': f'Peserta didik mampu memahami konsep dasar {nama.lower()}.',
                },
            )
            for nomor, isi in enumerate(TP_ISI[nama], start=1):
                LearningObjective.objects.get_or_create(
                    subject=subject,
                    academic_year=tahun,
                    nomor=nomor,
                    defaults={
                        'deskripsi': isi,
                        'kode': f'{kode}.{nomor}',
                        'learning_outcome': cp,
                        'aktif': True,
                    },
                )
            EvaluasiFormatif.objects.get_or_create(
                subject=subject,
                nama=f'Kuis {nama}',
                defaults={
                    'jenis': 'kuis',
                    'tanggal': date(2025, 8, 10),
                    'bobot': Decimal('20'),
                    'aktif': True,
                },
            )
            EvaluasiSumatif.objects.get_or_create(
                subject=subject,
                nama=f'STS {nama}',
                defaults={
                    'jenis': 'sts',
                    'tanggal': date(2025, 9, 21),
                    'bobot': Decimal('40'),
                    'aktif': True,
                },
            )
        return subjects

    def _isi(self):
        rnd = random.Random(20251125)
        admin = User.objects.filter(is_superuser=True).order_by('id').first()

        tahun_lalu, _ = AcademicYear.objects.get_or_create(
            tahun=TAHUN_LALU,
            defaults={
                'tanggal_mulai': date(2025, 7, 14),
                'tanggal_berakhir': date(2026, 6, 30),
                'aktif': False,
            },
        )
        tahun_ini = AcademicYear.objects.get(tahun=TAHUN_INI)
        tahun_depan, _ = AcademicYear.objects.get_or_create(
            tahun=TAHUN_DEPAN,
            defaults={
                'tanggal_mulai': date(2027, 7, 12),
                'tanggal_berakhir': date(2028, 6, 30),
                'aktif': False,
            },
        )
        sem_lalu, _ = Semester.objects.get_or_create(
            academic_year=tahun_lalu, nama='I', defaults={'aktif': False}
        )
        Semester.objects.get_or_create(
            academic_year=tahun_lalu, nama='II', defaults={'aktif': False}
        )
        sem_ini, _ = Semester.objects.get_or_create(
            academic_year=tahun_ini, nama='I'
        )
        Semester.objects.get_or_create(academic_year=tahun_ini, nama='II')
        sem_depan, _ = Semester.objects.get_or_create(
            academic_year=tahun_depan, nama='I', defaults={'aktif': False}
        )
        Semester.objects.get_or_create(
            academic_year=tahun_depan, nama='II', defaults={'aktif': False}
        )

        kelas_lalu, _ = ClassGroup.objects.get_or_create(
            academic_year=tahun_lalu,
            tingkat='VII',
            nama='Al-Lathif',
            defaults={'fase': 'D', 'aktif': True},
        )
        kelas_ini = ClassGroup.objects.filter(
            academic_year=tahun_ini, tingkat='VIII', nama='Al-Lathif'
        ).first()
        if kelas_ini is None:
            raise CommandError('Kelas VIII 2026/2027 tidak ditemukan.')
        kelas_depan, _ = ClassGroup.objects.get_or_create(
            academic_year=tahun_depan,
            tingkat='IX',
            nama='Al-Lathif',
            defaults={'fase': 'D', 'aktif': True},
        )

        # Guru dibutuhkan untuk pembagian mengajar dan pembina.
        guru_mapel = {}
        for index, (nama, mapel, _, _) in enumerate(GURU, start=1):
            guru_mapel[mapel] = self._guru(nama, index)
        pembina = guru_mapel.get('PJOK')

        mapel_lalu = self._mapel(tahun_lalu)
        mapel_ini = self._mapel(tahun_ini)
        mapel_depan = self._mapel(tahun_depan)

        for tahun, kelas, mapel_set in (
            (tahun_lalu, kelas_lalu, mapel_lalu),
            (tahun_ini, kelas_ini, mapel_ini),
            (tahun_depan, kelas_depan, mapel_depan),
        ):
            for nama, subject in mapel_set.items():
                TeachingAssignment.objects.get_or_create(
                    subject=subject,
                    class_group=kelas,
                    academic_year=tahun,
                    semester=None,
                    defaults={'teacher': guru_mapel[nama]},
                )

        siswa = []
        for i in range(JUMLAH_SISWA):
            jk = 'L' if i % 2 == 0 else 'P'
            pool = NAMA_DEPAN_L if jk == 'L' else NAMA_DEPAN_P
            nama = f'{pool[i % len(pool)]} {NAMA_BELAKANG[(i * 3) % len(NAMA_BELAKANG)]}'
            nis = f'2525{i + 1:03d}'
            nisn = f'002525{i + 1:04d}'
            student, _ = Student.objects.get_or_create(
                nis=nis,
                defaults={
                    'class_group': kelas_lalu,
                    'no_urut': i + 1,
                    'nisn': nisn,
                    'nama': nama,
                    'jenis_kelamin': jk,
                    'tempat_lahir': 'Kotabumi',
                    'tanggal_lahir': date(2012, (i % 12) + 1, (i % 26) + 1),
                    'agama': 'Islam',
                    'alamat': f'Jl. Angkatan No. {i + 1}, Kotabumi',
                    'nama_ayah': f'Bapak {NAMA_DEPAN_L[i % len(NAMA_DEPAN_L)]}',
                    'nama_ibu': f'Ibu {NAMA_DEPAN_P[i % len(NAMA_DEPAN_P)]}',
                    'aktif': True,
                },
            )
            siswa.append(student)

        kegiatan = []
        for urutan, nama in enumerate(
            ('Pramuka', 'Futsal', 'Seni Tari', 'Palang Merah Remaja'), start=1
        ):
            activity, _ = ExtracurricularActivity.objects.get_or_create(
                nama=nama,
                defaults={'pembina': pembina, 'aktif': True, 'urutan': urutan},
            )
            kegiatan.append(activity)

        self._nilai_dan_catatan(siswa, mapel_lalu, sem_lalu, rnd, kegiatan)
        for i, student in enumerate(siswa):
            student.class_group = kelas_ini
            # Kelas VIII 2026/2027 sudah memiliki siswa demo lain.
            student.no_urut = 100 + i + 1
            student.save()
        self._nilai_dan_catatan(siswa, mapel_ini, sem_ini, rnd, kegiatan)
        for i, student in enumerate(siswa):
            student.class_group = kelas_depan
            student.no_urut = i + 1
            student.save()
        self._nilai_dan_catatan(siswa, mapel_depan, sem_depan, rnd, kegiatan)
        sinkron_ulang_legacy()

        for semester in (sem_lalu, sem_ini, sem_depan):
            for i, student in enumerate(siswa):
                card = susun_report_card(student, semester, admin)
                ajukan(card, admin)
                setujui(card, admin)
                terbitkan(card, admin)

    def _nilai_dan_catatan(self, students, subjects, semester, rnd, kegiatan):
        formatif = []
        lm = []
        sumatif = []
        for siswa_index, siswa in enumerate(students):
            for mapel_index, subject in enumerate(subjects.values()):
                dasar = 68 + ((siswa_index * 6 + mapel_index * 4) % 23)
                for nomor, tp in enumerate(
                    subject.tujuan_list.filter(academic_year=semester.academic_year),
                    start=1,
                ):
                    nilai = 4 if dasar >= 82 else 3 if dasar >= 72 else 2
                    formatif.append(FormativeScore(
                        student=siswa,
                        objective=tp,
                        semester=semester,
                        nilai=nilai,
                        deskripsi_tp=tp.deskripsi,
                    ))
                for nomor, selisih in enumerate((-4, 0, 3, 5), start=1):
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
                    sts=Decimal(str(max(55, min(100, dasar - 1)))),
                    sas_non_tes=Decimal(str(max(55, min(100, dasar + 2)))),
                    sas_tes=Decimal(str(max(55, min(100, dasar + 4)))),
                ))
            HomeroomNote.objects.update_or_create(
                student=siswa,
                semester=semester,
                defaults={
                    'academic_year': semester.academic_year,
                    'catatan': CATATAN[siswa_index % len(CATATAN)],
                    'sakit': rnd.randint(0, 2),
                    'izin': rnd.randint(0, 2),
                    'alpa': rnd.randint(0, 1),
                },
            )
            for urutan, activity in enumerate(
                (kegiatan[siswa_index % len(kegiatan)],
                 kegiatan[(siswa_index + 1) % len(kegiatan)]),
                start=1,
            ):
                ExtracurricularEnrollment.objects.update_or_create(
                    student=siswa,
                    activity=activity,
                    semester=semester,
                    defaults={
                        'nilai': Decimal(str(78 + ((siswa_index * 5 + urutan) % 17))),
                        'deskripsi': activity.deskripsi,
                    },
                )
        FormativeScore.objects.bulk_create(formatif, batch_size=500)
        SummativeLM.objects.bulk_create(lm, batch_size=500)
        SummativeScore.objects.bulk_create(sumatif, batch_size=500)
