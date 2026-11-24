from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone


class SchoolProfile(models.Model):
    """Identitas sekolah (data tunggal / singleton)."""

    nama = models.CharField(max_length=150, default='SMP MUHAMMADIYAH SOEKARNO HATTA KOTABUMI')
    npsn = models.CharField(max_length=20, blank=True)
    nss = models.CharField(max_length=30, blank=True)
    alamat = models.CharField(max_length=200, blank=True)
    kode_pos = models.CharField(max_length=10, blank=True)
    desa = models.CharField(max_length=100, blank=True)
    kecamatan = models.CharField(max_length=100, blank=True)
    kabupaten = models.CharField(max_length=100, blank=True)
    provinsi = models.CharField(max_length=100, blank=True)
    website = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    kepala_sekolah = models.CharField(max_length=100, blank=True)
    nktam_kepala = models.CharField(max_length=50, blank=True)
    majelis = models.CharField(
        max_length=200,
        default='MAJELIS PENDIDIKAN DASAR MENENGAH DAN PENDIDIKAN NON FORMAL',
        blank=True,
    )
    pimpinan_daerah = models.CharField(
        max_length=200,
        default='PIMPINAN DAERAH MUHAMMADIYAH LAMPUNG UTARA',
        blank=True,
    )
    tempat_rapor = models.CharField(max_length=100, default='Kotabumi', blank=True)
    logo = models.FileField('Logo Sekolah', upload_to='sekolah/', blank=True, null=True)

    tampilkan_logo = models.BooleanField('Tampilkan logo di rapor', default=True)
    ukuran_logo = models.PositiveSmallIntegerField('Tinggi logo (px)', default=64)
    judul_rapor = models.CharField(
        'Judul Rapor', max_length=150,
        default='LAPORAN HASIL BELAJAR PESERTA DIDIK',
    )
    subjudul_rapor = models.CharField('Subjudul Rapor', max_length=60, default='(Rapor)')
    tampilkan_header = models.BooleanField('Tampilkan majelis & pimpinan daerah', default=True)
    tampilkan_alamat = models.BooleanField('Tampilkan alamat sekolah', default=True)
    tampilkan_ekskul = models.BooleanField('Tampilkan tabel ekstrakurikuler', default=True)
    tampilkan_absensi = models.BooleanField('Tampilkan ketidakhadiran', default=True)
    tampilkan_catatan = models.BooleanField('Tampilkan catatan wali kelas', default=True)

    label_ttd_orang_tua = models.CharField(
        'Label tanda tangan orang tua', max_length=50, default='Orang Tua/Wali'
    )
    label_ttd_kepala = models.CharField(
        'Label tanda tangan kepala sekolah', max_length=50, default='Kepala Sekolah'
    )
    label_ttd_wali = models.CharField(
        'Label tanda tangan wali kelas', max_length=50, default='Wali Kelas'
    )
    tampilkan_ttd_orang_tua = models.BooleanField('Tampilkan kolom orang tua', default=True)
    tampilkan_ttd_kepala = models.BooleanField('Tampilkan kolom kepala sekolah', default=True)
    tampilkan_ttd_wali = models.BooleanField('Tampilkan kolom wali kelas', default=True)

    font_rapor = models.CharField(
        'Jenis huruf rapor',
        max_length=10,
        choices=[('times', 'Times New Roman'), ('arial', 'Arial')],
        default='times',
    )
    ukuran_font = models.PositiveSmallIntegerField('Ukuran huruf rapor (pt)', default=11)
    ukuran_kertas = models.CharField(
        'Ukuran kertas',
        max_length=5,
        choices=[('A4', 'A4 (210 x 297 mm)'), ('F4', 'F4 (215 x 330 mm)')],
        default='A4',
    )

    class Meta:
        verbose_name = 'Identitas Sekolah'
        verbose_name_plural = 'Identitas Sekolah'
        db_table = 'akademik_school'

    def __str__(self):
        return self.nama

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    @property
    def lebar_kertas_mm(self):
        return 215 if self.ukuran_kertas == 'F4' else 210

    @property
    def tinggi_kertas_mm(self):
        return 330 if self.ukuran_kertas == 'F4' else 297


class AcademicYear(models.Model):
    tahun = models.CharField('Tahun Pelajaran', max_length=20, unique=True)
    tanggal_mulai = models.DateField('Tanggal Mulai', null=True, blank=True)
    tanggal_berakhir = models.DateField('Tanggal Berakhir', null=True, blank=True)
    aktif = models.BooleanField(default=False)

    class Meta:
        ordering = ['-tahun']
        verbose_name = 'Tahun Pelajaran'
        verbose_name_plural = 'Tahun Pelajaran'

    def __str__(self):
        return self.tahun

    @classmethod
    def get_aktif(cls):
        return cls.objects.filter(aktif=True).first() or cls.objects.first()


class Semester(models.Model):
    PENDEK = [('I', 'I (Ganjil)'), ('II', 'II (Genap)')]

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='semester_list'
    )
    nama = models.CharField(max_length=2, choices=PENDEK)
    aktif = models.BooleanField(default=False)

    class Meta:
        unique_together = [('academic_year', 'nama')]
        ordering = ['-academic_year__tahun', 'nama']
        verbose_name = 'Semester'
        verbose_name_plural = 'Semester'

    def __str__(self):
        return f'{self.nama} - {self.academic_year.tahun}'

    @classmethod
    def get_aktif(cls):
        return cls.objects.filter(aktif=True).first() or cls.objects.first()


class Teacher(models.Model):
    """Data guru sekaligus akun login untuk pengisian nilai."""

    JENIS_KELAMIN = [('L', 'Laki-Laki'), ('P', 'Perempuan')]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guru',
        verbose_name='Akun Login',
    )
    nama = models.CharField('Nama Guru', max_length=120)
    nik = models.CharField('NIK', max_length=20, blank=True)
    nip = models.CharField('NIP', max_length=30, blank=True)
    nktam = models.CharField('NKTAM', max_length=30, blank=True)
    jenis_kelamin = models.CharField('L/P', max_length=1, choices=JENIS_KELAMIN, default='L')
    tempat_lahir = models.CharField('Tempat Lahir', max_length=100, blank=True)
    tanggal_lahir = models.DateField('Tanggal Lahir', null=True, blank=True)
    pendidikan = models.CharField('Pendidikan Terakhir', max_length=150, blank=True)
    jurusan = models.CharField('Jurusan', max_length=150, blank=True)
    tahun_lulus = models.CharField('Tahun Lulus', max_length=12, blank=True)
    jabatan = models.CharField('Jabatan', max_length=120, blank=True)
    email = models.EmailField(blank=True)
    no_hp = models.CharField('No. HP', max_length=25, blank=True)
    alamat = models.CharField(max_length=255, blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Data Guru'
        verbose_name_plural = 'Data Guru'

    def __str__(self):
        return self.nama

    @property
    def username(self):
        return self.user.username if self.user_id else '-'

    @property
    def inisial(self):
        bagian = [b for b in self.nama.split() if b]
        return ''.join(b[0] for b in bagian[:2]).upper() or 'G'


class Grade(models.Model):
    """Tingkat kelas (VII/VIII/IX) beserta fasenya."""

    nama = models.CharField('Tingkat', max_length=10, unique=True)
    fase = models.CharField('Fase', max_length=5, default='D')
    urutan = models.PositiveSmallIntegerField('Urutan', default=0)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['urutan', 'nama']
        verbose_name = 'Tingkat Kelas'
        verbose_name_plural = 'Tingkat Kelas'

    def __str__(self):
        return self.nama


class ClassGroup(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='kelas_list'
    )
    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='kelas_list',
        verbose_name='Tingkat',
    )
    tingkat = models.CharField('Tingkat', max_length=10, default='VII')
    nama = models.CharField('Nama Kelas', max_length=50, default='Al-Lathif')
    fase = models.CharField(max_length=5, default='D')
    aktif = models.BooleanField('Kelas Aktif', default=False)
    wali_kelas_guru = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kelas_wali',
        verbose_name='Wali Kelas',
    )
    wali_kelas = models.CharField('Nama Wali Kelas (teks)', max_length=100, blank=True)
    nktam_wali = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [('academic_year', 'tingkat', 'nama')]
        ordering = ['tingkat', 'nama']
        verbose_name = 'Kelas'
        verbose_name_plural = 'Kelas'

    def __str__(self):
        return f'{self.tingkat} {self.nama}'

    def save(self, *args, **kwargs):
        """Jaga agar `grade` dan `tingkat` tetap sinkron (transisi skema)."""
        update_fields = kwargs.get('update_fields')
        berubah = set()
        if self.grade_id:
            grade = self.grade
            if self.tingkat != grade.nama:
                self.tingkat = grade.nama
                berubah.add('tingkat')
            if not self.fase:
                self.fase = grade.fase
                berubah.add('fase')
        elif self.tingkat:
            default_fase = self.fase or 'D'
            urutan = {'VII': 1, 'VIII': 2, 'IX': 3}.get(self.tingkat, 0)
            grade, _ = Grade.objects.get_or_create(
                nama=self.tingkat,
                defaults={'fase': default_fase, 'urutan': urutan},
            )
            self.grade = grade
            berubah.add('grade')
        if update_fields is not None and berubah:
            kwargs['update_fields'] = set(update_fields) | berubah
        super().save(*args, **kwargs)


    @property
    def nama_lengkap(self):
        return f'{self.tingkat} {self.nama}'

    @property
    def nama_wali(self):
        if self.wali_kelas_guru_id:
            return self.wali_kelas_guru.nama
        return self.wali_kelas

    @property
    def nktam_wali_aktif(self):
        if self.wali_kelas_guru_id:
            return self.wali_kelas_guru.nktam
        return self.nktam_wali



class Subject(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='mata_pelajaran',
        verbose_name='Tahun Pelajaran',
    )
    nama = models.CharField('Mata Pelajaran', max_length=100)
    kode = models.CharField('Kode Mapel', max_length=20, blank=True)
    deskripsi = models.TextField('Deskripsi', blank=True)
    urutan = models.PositiveSmallIntegerField('Urutan', default=0)

    class Meta:
        unique_together = [('academic_year', 'nama')]
        ordering = ['urutan', 'nama']
        verbose_name = 'Mata Pelajaran'
        verbose_name_plural = 'Mata Pelajaran'

    def __str__(self):
        return self.nama


class TeachingAssignment(models.Model):
    """Pembagian tugas mengajar: guru pengampu tiap mapel per kelas/tahun.

    `semester` kosong berarti penugasan berlaku untuk seluruh tahun pelajaran
    (perilaku lama). Bila diisi, penugasan berlaku khusus semester tersebut.
    """

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='penugasan', verbose_name='Guru'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='penugasan', verbose_name='Mata Pelajaran'
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.CASCADE, related_name='penugasan', verbose_name='Kelas'
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='penugasan',
        verbose_name='Tahun Pelajaran',
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, null=True, blank=True,
        related_name='penugasan', verbose_name='Semester',
    )

    class Meta:
        ordering = ['subject__urutan']
        verbose_name = 'Pembagian Mengajar'
        verbose_name_plural = 'Pembagian Mengajar'
        constraints = [
            models.UniqueConstraint(
                fields=['class_group', 'subject', 'academic_year'],
                condition=models.Q(semester__isnull=True),
                name='uniq_penugasan_tahun',
            ),
            models.UniqueConstraint(
                fields=['class_group', 'subject', 'semester'],
                condition=models.Q(semester__isnull=False),
                name='uniq_penugasan_semester',
            ),
        ]

    def __str__(self):
        return f'{self.subject.nama} - {self.class_group.nama_lengkap} - {self.teacher.nama}'

    def clean(self):
        errors = {}
        tahun = self.academic_year_id
        if self.class_group_id and self.class_group.academic_year_id != tahun:
            errors['class_group'] = 'Kelas bukan milik tahun pelajaran yang dipilih.'
        if self.subject_id and self.subject.academic_year_id != tahun:
            errors['subject'] = 'Mata pelajaran bukan milik tahun pelajaran yang dipilih.'
        if self.semester_id and self.semester.academic_year_id != tahun:
            errors['semester'] = 'Semester bukan milik tahun pelajaran yang dipilih.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.academic_year_id is None and self.class_group_id:
            self.academic_year = self.class_group.academic_year
        self.full_clean()
        super().save(*args, **kwargs)



class LearningOutcome(models.Model):
    """Capaian Pembelajaran (CP) per mata pelajaran."""

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='capaian_list',
        verbose_name='Mata Pelajaran',
    )
    kode = models.CharField('Kode CP', max_length=30, blank=True)
    fase = models.CharField('Fase', max_length=5, default='D')
    deskripsi = models.TextField('Capaian Pembelajaran')
    urutan = models.PositiveSmallIntegerField('Urutan', default=0)
    aktif = models.BooleanField('Aktif', default=True)

    class Meta:
        ordering = ['subject__urutan', 'urutan', 'kode']
        verbose_name = 'Capaian Pembelajaran'
        verbose_name_plural = 'Capaian Pembelajaran'
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'kode'],
                condition=~models.Q(kode=''),
                name='uniq_cp_subject_kode',
            ),
            models.UniqueConstraint(
                fields=['subject', 'urutan'],
                name='uniq_cp_subject_urutan',
            ),
        ]

    def __str__(self):
        label = f'{self.kode} - ' if self.kode else ''
        return f'{label}{self.subject.nama}'


class LearningObjective(models.Model):
    """Tujuan Pembelajaran (TP) per mata pelajaran dan tahun pelajaran."""

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='tujuan_list')
    learning_outcome = models.ForeignKey(
        LearningOutcome,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tujuan_list',
        verbose_name='Capaian Pembelajaran',
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='tujuan_list',
        verbose_name='Tahun Pelajaran',
    )
    guru = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tujuan_list', verbose_name='Guru Pengampu',
    )
    kode = models.CharField('Kode TP', max_length=30, blank=True)
    nomor = models.PositiveSmallIntegerField('Nomor Urut')
    deskripsi = models.TextField('Tujuan Pembelajaran')
    aktif = models.BooleanField('Aktif', default=True)

    class Meta:
        unique_together = [('subject', 'academic_year', 'nomor')]
        ordering = ['subject__urutan', 'nomor']
        verbose_name = 'Tujuan Pembelajaran'
        verbose_name_plural = 'Tujuan Pembelajaran'

    def clean(self):
        if self.learning_outcome_id and self.subject_id:
            if self.learning_outcome.subject_id != self.subject_id:
                raise ValidationError(
                    {'learning_outcome': 'CP harus berasal dari mata pelajaran yang sama.'}
                )

    def __str__(self):
        return f'TP {self.nomor} - {self.subject.nama} ({self.academic_year.tahun})'


class LearningMaterial(models.Model):
    """Materi pembelajaran yang dapat mencakup beberapa TP."""

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='materi_list',
        verbose_name='Mata Pelajaran',
    )
    objectives = models.ManyToManyField(
        LearningObjective, blank=True, related_name='materi_list',
        verbose_name='Tujuan Pembelajaran',
    )
    kode = models.CharField('Kode Materi', max_length=30, blank=True)
    judul = models.CharField('Judul Materi', max_length=200)
    deskripsi = models.TextField('Deskripsi', blank=True)
    urutan = models.PositiveSmallIntegerField('Urutan', default=0)
    aktif = models.BooleanField('Aktif', default=True)

    class Meta:
        ordering = ['subject__urutan', 'urutan', 'judul']
        verbose_name = 'Materi Pembelajaran'
        verbose_name_plural = 'Materi Pembelajaran'

    def __str__(self):
        return self.judul


class LearningTask(models.Model):
    """Tugas pembelajaran (terpisah dari TP)."""

    STATUS = [
        ('DRAF', 'Draf'),
        ('TERBIT', 'Terbit'),
        ('TUTUP', 'Ditutup'),
    ]

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='tugas_pembelajaran',
        verbose_name='Mata Pelajaran',
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='tugas_pembelajaran',
        verbose_name='Tahun Pelajaran',
    )
    class_groups = models.ManyToManyField(
        ClassGroup, blank=True, related_name='tugas_pembelajaran',
        verbose_name='Kelas',
    )
    objectives = models.ManyToManyField(
        LearningObjective, blank=True, related_name='tugas_pembelajaran',
        verbose_name='Tujuan Pembelajaran',
    )
    created_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tugas_dibuat', verbose_name='Dibuat Oleh',
    )
    judul = models.CharField('Judul Tugas', max_length=200)
    deskripsi = models.TextField('Deskripsi', blank=True)
    instruksi = models.TextField('Instruksi', blank=True)
    tanggal_pemberian = models.DateField('Tanggal Pemberian', null=True, blank=True)
    batas_pengumpulan = models.DateField('Batas Pengumpulan', null=True, blank=True)
    lampiran = models.FileField(
        'Lampiran', upload_to='tugas/%Y/%m/', blank=True, null=True,
    )
    bobot = models.DecimalField('Bobot (%)', max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS, default='DRAF')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_pemberian', '-created_at', 'judul']
        verbose_name = 'Tugas Pembelajaran'
        verbose_name_plural = 'Tugas Pembelajaran'

    def __str__(self):
        return self.judul

    def clean(self):
        errors = {}
        if self.academic_year_id and self.subject_id:
            if self.subject.academic_year_id != self.academic_year_id:
                errors['academic_year'] = (
                    'Tahun pelajaran harus sama dengan tahun pelajaran mapel.'
                )
        if (
            self.tanggal_pemberian
            and self.batas_pengumpulan
            and self.batas_pengumpulan < self.tanggal_pemberian
        ):
            errors['batas_pengumpulan'] = (
                'Batas pengumpulan tidak boleh sebelum tanggal pemberian.'
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.academic_year_id is None and self.subject_id:
            self.academic_year = self.subject.academic_year
        self.full_clean()
        super().save(*args, **kwargs)


class LearningTaskSubmission(models.Model):
    """Pengumpulan dan penilaian tugas per siswa."""

    STATUS = [
        ('BELUM', 'Belum Dikumpulkan'),
        ('TERKUMPUL', 'Terkumpul'),
        ('TERLAMBAT', 'Terlambat'),
        ('DINILAI', 'Dinilai'),
    ]

    task = models.ForeignKey(
        LearningTask, on_delete=models.CASCADE, related_name='submissions',
        verbose_name='Tugas',
    )
    student = models.ForeignKey(
        'Student', on_delete=models.CASCADE, related_name='pengumpulan_tugas',
        verbose_name='Peserta Didik',
    )
    file = models.FileField(
        'Berkas', upload_to='pengumpulan/%Y/%m/', blank=True, null=True,
    )
    catatan_siswa = models.TextField('Catatan Siswa', blank=True)
    submitted_at = models.DateTimeField('Waktu Kumpul', null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default='BELUM')
    nilai = models.DecimalField(
        'Nilai', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    catatan_guru = models.TextField('Catatan Guru', blank=True)
    dinilai_oleh = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='penilaian_tugas', verbose_name='Dinilai Oleh',
    )
    dinilai_at = models.DateTimeField('Waktu Dinilai', null=True, blank=True)

    class Meta:
        unique_together = [('task', 'student')]
        ordering = ['student__no_urut']
        verbose_name = 'Pengumpulan Tugas'
        verbose_name_plural = 'Pengumpulan Tugas'

    def __str__(self):
        return f'{self.task.judul} - {self.student.nama}'

    def clean(self):
        if self.task_id and self.student_id:
            tahun_tugas = self.task.academic_year_id
            punya_enrollment = self.student.enrollments.filter(
                academic_year_id=tahun_tugas
            ).exists()
            if not punya_enrollment:
                raise ValidationError(
                    {'student': 'Siswa tidak terdaftar pada tahun pelajaran tugas.'}
                )

    def save(self, *args, **kwargs):
        if self.status in ('TERKUMPUL', 'TERLAMBAT', 'DINILAI') and self.submitted_at is None:
            self.submitted_at = timezone.now()
        if self.status == 'DINILAI' and self.dinilai_at is None:
            self.dinilai_at = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)



class EvaluasiFormatif(models.Model):
    """Rencana evaluasi formatif yang berkelanjutan pada suatu mata pelajaran."""

    JENIS = [
        ('kuis', 'Kuis'),
        ('latihan', 'Latihan Soal'),
        ('tanya_jawab', 'Tanya Jawab'),
        ('observasi', 'Observasi'),
        ('lain', 'Lainnya'),
    ]

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='evaluasi_formatif',
        verbose_name='Mata Pelajaran',
    )
    nama = models.CharField('Nama Evaluasi', max_length=150)
    jenis = models.CharField(max_length=20, choices=JENIS, default='kuis')
    tanggal = models.DateField('Tanggal', null=True, blank=True)
    bobot = models.DecimalField('Bobot (%)', max_digits=5, decimal_places=2, default=0)
    deskripsi = models.TextField('Deskripsi', blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['subject__urutan', 'tanggal', 'nama']
        verbose_name = 'Evaluasi Formatif'
        verbose_name_plural = 'Evaluasi Formatif'

    def __str__(self):
        return f'{self.nama} - {self.subject.nama}'


class EvaluasiSumatif(models.Model):
    """Rencana evaluasi sumatif pada akhir lingkup materi atau semester."""

    JENIS = [
        ('sts', 'Sumatif Tengah Semester'),
        ('sas', 'Sumatif Akhir Semester'),
        ('ulangan', 'Ulangan Akhir Materi'),
        ('tugas_akhir', 'Tugas Akhir'),
        ('lain', 'Lainnya'),
    ]

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='evaluasi_sumatif',
        verbose_name='Mata Pelajaran',
    )
    nama = models.CharField('Nama Evaluasi', max_length=150)
    jenis = models.CharField(max_length=20, choices=JENIS, default='sts')
    tanggal = models.DateField('Tanggal', null=True, blank=True)
    bobot = models.DecimalField('Bobot (%)', max_digits=5, decimal_places=2, default=0)
    deskripsi = models.TextField('Deskripsi', blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['subject__urutan', 'tanggal', 'nama']
        verbose_name = 'Evaluasi Sumatif'
        verbose_name_plural = 'Evaluasi Sumatif'

    def __str__(self):
        return f'{self.nama} - {self.subject.nama}'


class StudentQuerySet(models.QuerySet):
    def in_class(self, class_group):
        """Siswa yang terdaftar pada kelas tersebut (berdasarkan riwayat enrollment)."""
        if class_group is None:
            return self.none()
        return self.filter(
            enrollments__class_group=class_group,
            enrollments__academic_year=class_group.academic_year,
        ).distinct()


class Student(models.Model):
    JENIS_KELAMIN = [('L', 'Laki-Laki'), ('P', 'Perempuan')]

    objects = StudentQuerySet.as_manager()

    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.CASCADE, related_name='siswa_list'
    )
    no_urut = models.PositiveSmallIntegerField('No Urut')
    nis = models.CharField('NIS', max_length=20, blank=True)
    nisn = models.CharField('NISN', max_length=20, blank=True)
    nama = models.CharField('Nama Peserta Didik', max_length=120)
    jenis_kelamin = models.CharField('L/P', max_length=1, choices=JENIS_KELAMIN, default='L')
    tempat_lahir = models.CharField(max_length=100, blank=True)
    tanggal_lahir = models.DateField(null=True, blank=True)
    agama = models.CharField(max_length=30, blank=True)
    pendidikan_sebelumnya = models.CharField(max_length=100, blank=True)
    alamat = models.CharField(max_length=200, blank=True)
    nama_ayah = models.CharField(max_length=100, blank=True)
    nama_ibu = models.CharField(max_length=100, blank=True)
    pekerjaan_ayah = models.CharField(max_length=100, blank=True)
    pekerjaan_ibu = models.CharField(max_length=100, blank=True)
    alamat_orang_tua = models.CharField(max_length=200, blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['no_urut']
        unique_together = [('class_group', 'no_urut')]
        verbose_name = 'Peserta Didik'
        verbose_name_plural = 'Peserta Didik'

    def __str__(self):
        return self.nama

    @property
    def jk_label(self):
        return 'Laki-Laki' if self.jenis_kelamin == 'L' else 'Perempuan'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Catat/rapikan penempatan kelas pada tahun pelajaran kelas saat ini.
        # Riwayat tahun sebelumnya tidak disentuh.
        if self.class_group_id:
            StudentEnrollment.objects.update_or_create(
                student=self,
                academic_year=self.class_group.academic_year,
                defaults={'class_group': self.class_group},
            )

    def enrollment_for(self, academic_year):
        if academic_year is None:
            return None
        return (
            self.enrollments.select_related('class_group')
            .filter(academic_year=academic_year)
            .first()
        )


class StudentEnrollment(models.Model):
    """Riwayat penempatan siswa pada kelas per tahun pelajaran."""

    STATUS = [
        ('AKTIF', 'Aktif'),
        ('PINDAH', 'Pindah'),
        ('LULUS', 'Lulus'),
        ('KELUAR', 'Keluar'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='enrollments',
        verbose_name='Peserta Didik',
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, related_name='enrollments',
        verbose_name='Kelas',
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='enrollments',
        verbose_name='Tahun Pelajaran',
    )
    tanggal_masuk = models.DateField('Tanggal Masuk', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='AKTIF')
    keterangan = models.TextField('Keterangan', blank=True)

    class Meta:
        unique_together = [('student', 'academic_year')]
        ordering = ['-academic_year__tahun', 'class_group__tingkat', 'class_group__nama']
        verbose_name = 'Penempatan Kelas'
        verbose_name_plural = 'Riwayat Penempatan Kelas'

    def __str__(self):
        return f'{self.student} - {self.class_group.nama_lengkap} ({self.academic_year.tahun})'

    def clean(self):
        errors = {}
        if self.class_group_id and self.academic_year_id:
            if self.class_group.academic_year_id != self.academic_year_id:
                errors['academic_year'] = (
                    'Tahun pelajaran harus sama dengan tahun pelajaran kelas.'
                )
        if self.status in ('LULUS', 'PINDAH') and not self.academic_year_id:
            errors['academic_year'] = 'Tahun pelajaran wajib diisi.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.academic_year_id is None and self.class_group_id:
            self.academic_year = self.class_group.academic_year
        self.full_clean()
        super().save(*args, **kwargs)



class GradeConfiguration(models.Model):
    """Konfigurasi bobot, pembulatan, dan ambang deskripsi nilai."""

    METODE_PEMBULATAN = [
        ('HALF_UP', 'Bulatkan biasa (0,5 ke atas)'),
        ('HALF_DOWN', 'Bulatkan 0,5 ke bawah'),
        ('UP', 'Selalu ke atas'),
        ('DOWN', 'Selalu ke bawah'),
    ]

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='konfigurasi_nilai', verbose_name='Tahun Pelajaran',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='konfigurasi_nilai', verbose_name='Mata Pelajaran',
    )
    bobot_lm = models.DecimalField('Bobot Rata-rata LM', max_digits=5, decimal_places=2, default=1)
    bobot_sts = models.DecimalField('Bobot STS', max_digits=5, decimal_places=2, default=1)
    bobot_sas = models.DecimalField('Bobot Rata-rata SAS', max_digits=5, decimal_places=2, default=1)
    bobot_sas_non_tes = models.DecimalField(
        'Bobot SAS Non Tes', max_digits=5, decimal_places=2, default=1
    )
    bobot_sas_tes = models.DecimalField(
        'Bobot SAS Tes', max_digits=5, decimal_places=2, default=1
    )
    metode_pembulatan = models.CharField(
        max_length=10, choices=METODE_PEMBULATAN, default='HALF_UP'
    )
    jumlah_desimal = models.PositiveSmallIntegerField('Jumlah Desimal', default=2)
    nilai_min = models.DecimalField('Nilai Minimum', max_digits=5, decimal_places=2, default=0)
    nilai_max = models.DecimalField('Nilai Maksimum', max_digits=5, decimal_places=2, default=100)
    ambang_unggul = models.PositiveSmallIntegerField('Ambang Unggul', default=3)
    ambang_perlu_bimbingan = models.PositiveSmallIntegerField(
        'Ambang Perlu Bimbingan', default=2
    )
    aktif = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-academic_year__tahun', 'subject__urutan']
        verbose_name = 'Konfigurasi Nilai'
        verbose_name_plural = 'Konfigurasi Nilai'

    def __str__(self):
        bagian = [str(self.academic_year or 'Semua tahun')]
        bagian.append(str(self.subject or 'Semua mapel'))
        return ' - '.join(bagian)

    @classmethod
    def get_config(cls, subject=None, academic_year=None):
        tahun = academic_year or (subject.academic_year if subject else None)
        qs = cls.objects.filter(aktif=True)
        if subject is not None:
            konfigurasi = qs.filter(subject=subject, academic_year=tahun).first()
            if konfigurasi is None:
                konfigurasi = qs.filter(
                    subject=subject, academic_year__isnull=True
                ).first()
            if konfigurasi is not None:
                return konfigurasi
        if tahun is not None:
            konfigurasi = qs.filter(
                subject__isnull=True, academic_year=tahun
            ).first()
            if konfigurasi is not None:
                return konfigurasi
        konfigurasi = qs.filter(subject__isnull=True, academic_year__isnull=True).first()
        if konfigurasi is None:
            konfigurasi = cls.objects.create()
        return konfigurasi


class Assessment(models.Model):
    """Asesmen generik: formatif, sumatif LM, STS, atau SAS."""

    KATEGORI = [
        ('FORMATIF', 'Formatif'),
        ('SUMATIF_LM', 'Sumatif Lingkup Materi'),
        ('STS', 'Sumatif Tengah Semester'),
        ('SAS', 'Sumatif Akhir Semester'),
    ]
    METODE = [
        ('TES', 'Tes'),
        ('NON_TES', 'Non Tes'),
        ('OBSERVASI', 'Observasi'),
        ('PRAKTIK', 'Praktik'),
        ('PROYEK', 'Proyek'),
        ('PORTOFOLIO', 'Portofolio'),
        ('LAIN', 'Lainnya'),
    ]
    STATUS = [
        ('DRAF', 'Draf'),
        ('TERBIT', 'Terbit'),
        ('TUTUP', 'Ditutup'),
    ]

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='asesmen',
        verbose_name='Mata Pelajaran',
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='asesmen',
        verbose_name='Tahun Pelajaran',
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name='asesmen',
        verbose_name='Semester',
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asesmen', verbose_name='Kelas',
    )
    nomor = models.PositiveSmallIntegerField('Nomor', null=True, blank=True)
    nama = models.CharField('Nama Asesmen', max_length=150)
    kategori = models.CharField(max_length=15, choices=KATEGORI, default='FORMATIF')
    metode = models.CharField(max_length=15, choices=METODE, default='TES')
    tanggal = models.DateField('Tanggal', null=True, blank=True)
    bobot = models.DecimalField('Bobot (%)', max_digits=5, decimal_places=2, default=100)
    deskripsi = models.TextField('Deskripsi', blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='DRAF')
    created_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asesmen_dibuat', verbose_name='Dibuat Oleh',
    )
    aktif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['subject__urutan', 'kategori', 'nomor', 'nama']
        verbose_name = 'Asesmen'
        verbose_name_plural = 'Asesmen'
        constraints = [
            models.UniqueConstraint(
                fields=['subject', 'semester', 'kategori', 'nama'],
                name='uniq_asesmen_mapel_semester_nama',
            ),
        ]

    def __str__(self):
        return f'{self.nama} - {self.subject.nama} ({self.semester})'

    def clean(self):
        errors = {}
        if self.subject_id and self.academic_year_id:
            if self.subject.academic_year_id != self.academic_year_id:
                errors['academic_year'] = 'Tahun pelajaran harus sama dengan mapel.'
        if self.semester_id and self.academic_year_id:
            if self.semester.academic_year_id != self.academic_year_id:
                errors['semester'] = 'Semester bukan milik tahun pelajaran ini.'
        if self.class_group_id and self.academic_year_id:
            if self.class_group.academic_year_id != self.academic_year_id:
                errors['class_group'] = 'Kelas bukan milik tahun pelajaran ini.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.academic_year_id is None and self.subject_id:
            self.academic_year = self.subject.academic_year
        if self.semester_id and self.academic_year_id is None:
            self.academic_year = self.semester.academic_year
        super().save(*args, **kwargs)


class AssessmentComponent(models.Model):
    """Komponen nilai di dalam satu asesmen."""

    TIPE = [
        ('NILAI', 'Nilai'),
        ('TES', 'Tes'),
        ('NON_TES', 'Non Tes'),
        ('TUGAS', 'Tugas'),
        ('PRAKTIK', 'Praktik'),
        ('OBSERVASI', 'Observasi'),
        ('LAIN', 'Lainnya'),
    ]

    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name='components',
        verbose_name='Asesmen',
    )
    nama = models.CharField('Nama Komponen', max_length=100)
    tipe = models.CharField(max_length=15, choices=TIPE, default='NILAI')
    urutan = models.PositiveSmallIntegerField('Urutan', default=1)
    bobot = models.DecimalField('Bobot', max_digits=5, decimal_places=2, default=100)
    nilai_maksimal = models.DecimalField(
        'Nilai Maksimal', max_digits=5, decimal_places=2, default=100
    )
    wajib = models.BooleanField('Wajib', default=True)

    class Meta:
        unique_together = [('assessment', 'nama')]
        ordering = ['urutan', 'nama']
        verbose_name = 'Komponen Asesmen'
        verbose_name_plural = 'Komponen Asesmen'

    def __str__(self):
        return f'{self.assessment.nama} - {self.nama}'


class AssessmentObjective(models.Model):
    """Kaitan asesmen dengan TP (untuk deskripsi capaian)."""

    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name='objective_links',
        verbose_name='Asesmen',
    )
    objective = models.ForeignKey(
        LearningObjective, on_delete=models.CASCADE, related_name='assessment_links',
        verbose_name='Tujuan Pembelajaran',
    )
    bobot = models.DecimalField('Bobot', max_digits=5, decimal_places=2, default=1)

    class Meta:
        unique_together = [('assessment', 'objective')]
        verbose_name = 'TP Asesmen'
        verbose_name_plural = 'TP Asesmen'

    def __str__(self):
        return f'{self.assessment.nama} - TP {self.objective.nomor}'


class AssessmentResult(models.Model):
    """Nilai satu siswa pada satu komponen asesmen."""

    STATUS = [('VALID', 'Valid'), ('REVISI', 'Perlu Revisi')]

    component = models.ForeignKey(
        AssessmentComponent, on_delete=models.CASCADE, related_name='results',
        verbose_name='Komponen',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='hasil_asesmen',
        verbose_name='Peserta Didik',
    )
    nilai = models.DecimalField('Nilai', max_digits=8, decimal_places=2, null=True, blank=True)
    predikat = models.CharField('Predikat', max_length=5, blank=True)
    catatan = models.TextField('Catatan', blank=True)
    tanggal = models.DateField('Tanggal', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='VALID')
    dinilai_oleh = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hasil_dinilai', verbose_name='Dinilai Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('component', 'student')]
        ordering = ['student__no_urut']
        verbose_name = 'Hasil Asesmen'
        verbose_name_plural = 'Hasil Asesmen'

    def __str__(self):
        return f'{self.component} - {self.student} = {self.nilai}'

    def clean(self):
        if self.nilai is not None and self.component_id:
            if self.nilai < 0 or self.nilai > self.component.nilai_maksimal:
                raise ValidationError(
                    {'nilai': f'Nilai harus antara 0 dan {self.component.nilai_maksimal}.'}
                )


class AssessmentRubric(models.Model):
    """Rubrik deskriptif per komponen asesmen."""

    component = models.ForeignKey(
        AssessmentComponent, on_delete=models.CASCADE, related_name='rubrics',
        verbose_name='Komponen',
    )
    level = models.CharField('Level/Skor', max_length=20)
    deskripsi = models.TextField('Deskripsi')
    urutan = models.PositiveSmallIntegerField('Urutan', default=1)

    class Meta:
        unique_together = [('component', 'level')]
        ordering = ['urutan', 'level']
        verbose_name = 'Rubrik Asesmen'
        verbose_name_plural = 'Rubrik Asesmen'

    def __str__(self):
        return f'{self.component.nama} - {self.level}'


class ReportCard(models.Model):
    """Rapor siswa per semester beserta status persetujuan/publikasi."""

    STATUS = [
        ('DRAF', 'Draf'),
        ('REVIEW', 'Diajukan'),
        ('APPROVED', 'Disetujui'),
        ('PUBLISHED', 'Terbit'),
        ('REVISI', 'Perlu Revisi'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='report_cards',
        verbose_name='Peserta Didik',
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, related_name='report_cards',
        verbose_name='Kelas',
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name='report_cards',
        verbose_name='Semester',
    )
    nomor_urut = models.PositiveSmallIntegerField('Nomor Urut', default=0)
    status = models.CharField(max_length=10, choices=STATUS, default='DRAF')
    catatan_wali = models.TextField('Catatan Wali Kelas', blank=True)
    sakit = models.PositiveSmallIntegerField(default=0)
    izin = models.PositiveSmallIntegerField(default=0)
    alpa = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='report_dibuat', verbose_name='Disusun Oleh',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='report_disetujui', verbose_name='Disetujui Oleh',
    )
    approved_at = models.DateTimeField('Disetujui Pada', null=True, blank=True)
    published_at = models.DateTimeField('Diterbitkan Pada', null=True, blank=True)
    locked_at = models.DateTimeField('Dikunci Pada', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('student', 'semester')]
        ordering = ['class_group__tingkat', 'class_group__nama', 'nomor_urut']
        verbose_name = 'Rapor'
        verbose_name_plural = 'Rapor'

    def __str__(self):
        return f'Rapor {self.student.nama} - {self.semester}'

    @property
    def catatan(self):
        return self.catatan_wali

    @property
    def terkunci(self):
        return self.status == 'PUBLISHED'

    @property
    def bisa_diubah(self):
        return self.status in ('DRAF', 'REVISI')

    def clean(self):
        errors = {}
        if self.semester_id and self.class_group_id:
            if self.class_group.academic_year_id != self.semester.academic_year_id:
                errors['class_group'] = 'Kelas bukan milik tahun pelajaran semester.'
        if self.student_id and self.semester_id:
            enrollment = self.student.enrollments.filter(
                academic_year=self.semester.academic_year_id
            ).first()
            if enrollment is None:
                errors['student'] = 'Siswa tidak terdaftar pada tahun pelajaran semester.'
            elif self.class_group_id and enrollment.class_group_id != self.class_group_id:
                errors['class_group'] = (
                    'Kelas tidak sesuai dengan riwayat penempatan siswa.'
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.semester_id and not self.nomor_urut:
            self.nomor_urut = self.student.no_urut
        super().save(*args, **kwargs)


class ReportSubjectGrade(models.Model):
    """Snapshot nilai rapor per mata pelajaran."""

    report_card = models.ForeignKey(
        ReportCard, on_delete=models.CASCADE, related_name='nilai_mapel',
        verbose_name='Rapor',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='nilai_rapor',
        verbose_name='Mata Pelajaran',
    )
    nilai_lm = models.DecimalField(
        'Rata-rata LM', max_digits=5, decimal_places=2, null=True, blank=True
    )
    nilai_sts = models.DecimalField(
        'STS', max_digits=5, decimal_places=2, null=True, blank=True
    )
    nilai_sas = models.DecimalField(
        'Rata-rata SAS', max_digits=5, decimal_places=2, null=True, blank=True
    )
    nilai_akhir = models.DecimalField(
        'Nilai Akhir', max_digits=5, decimal_places=2, null=True, blank=True
    )
    predikat = models.CharField('Predikat', max_length=5, blank=True)
    deskripsi_otomatis = models.TextField('Deskripsi Otomatis', blank=True)
    deskripsi_final = models.TextField('Deskripsi Final', blank=True)
    urutan = models.PositiveSmallIntegerField('Urutan', default=0)

    class Meta:
        unique_together = [('report_card', 'subject')]
        ordering = ['urutan', 'subject__urutan']
        verbose_name = 'Nilai Rapor'
        verbose_name_plural = 'Nilai Rapor'

    def __str__(self):
        return f'{self.subject.nama} - {self.report_card}'

    @property
    def nilai(self):
        return self.nilai_akhir

    @property
    def capaian(self):
        return self.deskripsi_final or self.deskripsi_otomatis


class ReportCompetencyDescription(models.Model):
    """Jejak TP yang mendasari deskripsi capaian pada rapor."""

    TIPE = [('UNGGUL', 'Unggul'), ('PERLU', 'Perlu Bimbingan')]

    subject_grade = models.ForeignKey(
        ReportSubjectGrade, on_delete=models.CASCADE, related_name='kompetensi',
        verbose_name='Nilai Rapor',
    )
    objective = models.ForeignKey(
        LearningObjective, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deskripsi_rapor', verbose_name='Tujuan Pembelajaran',
    )
    tipe = models.CharField(max_length=10, choices=TIPE)
    teks = models.TextField('Deskripsi')
    urutan = models.PositiveSmallIntegerField('Urutan', default=1)

    class Meta:
        ordering = ['urutan']
        verbose_name = 'Deskripsi Kompetensi Rapor'
        verbose_name_plural = 'Deskripsi Kompetensi Rapor'

    def __str__(self):
        return f'{self.get_tipe_display()} - {self.teks[:60]}'


class ReportExtracurricular(models.Model):
    """Snapshot ekstrakurikuler pada rapor."""

    report_card = models.ForeignKey(
        ReportCard, on_delete=models.CASCADE, related_name='ekskul',
        verbose_name='Rapor',
    )
    urutan = models.PositiveSmallIntegerField('Urutan', default=1)
    nama = models.CharField('Ekstrakurikuler', max_length=100, blank=True)
    predikat = models.CharField('Predikat', max_length=5, blank=True)
    deskripsi = models.CharField('Deskripsi', max_length=200, blank=True)

    class Meta:
        unique_together = [('report_card', 'urutan')]
        ordering = ['urutan']
        verbose_name = 'Ekstrakurikuler Rapor'
        verbose_name_plural = 'Ekstrakurikuler Rapor'

    def __str__(self):
        return f'{self.nama} - {self.report_card}'


class FormativeScore(models.Model):
    """Nilai asesmen formatif per Tujuan Pembelajaran (skala 1-4)."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='nilai_formatif')
    objective = models.ForeignKey(
        LearningObjective, on_delete=models.CASCADE, related_name='nilai_formatif'
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name='nilai_formatif'
    )
    guru = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='nilai_formatif', verbose_name='Guru Penilai',
    )
    nilai = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    deskripsi_tp = models.TextField('Deskripsi TP saat dinilai', blank=True)

    class Meta:
        unique_together = [('student', 'objective', 'semester')]
        verbose_name = 'Nilai Formatif'
        verbose_name_plural = 'Nilai Formatif'

    def clean(self):
        errors = {}
        if self.semester_id and self.objective_id:
            if self.objective.academic_year_id != self.semester.academic_year_id:
                errors['semester'] = (
                    'Semester dan tahun pelajaran TP harus sama.'
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.objective_id and not self.deskripsi_tp:
            self.deskripsi_tp = self.objective.deskripsi
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.student} - {self.objective} = {self.nilai}'


class SummativeLM(models.Model):
    """Nilai sumatif lingkup materi (LM 1..n)."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='nilai_lm')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='nilai_lm')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='nilai_lm')
    guru = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='nilai_lm', verbose_name='Guru Penilai',
    )
    nomor = models.PositiveSmallIntegerField('LM ke-')
    nilai = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = [('student', 'subject', 'semester', 'nomor')]
        ordering = ['nomor']
        verbose_name = 'Nilai Sumatif LM'
        verbose_name_plural = 'Nilai Sumatif LM'

    def clean(self):
        if self.semester_id and self.subject_id:
            if self.subject.academic_year_id != self.semester.academic_year_id:
                raise ValidationError(
                    {'semester': 'Semester dan tahun pelajaran mapel harus sama.'}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.student} - {self.subject} LM{self.nomor} = {self.nilai}'


class SummativeScore(models.Model):
    """STS dan Sumatif Akhir Semester (SAS) per siswa/mapel/semester."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='nilai_sumatif')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='nilai_sumatif')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='nilai_sumatif')
    guru = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='nilai_sumatif', verbose_name='Guru Penilai',
    )
    sts = models.DecimalField('STS', max_digits=5, decimal_places=2, null=True, blank=True)
    sas_non_tes = models.DecimalField(
        'SAS Non Tes', max_digits=5, decimal_places=2, null=True, blank=True
    )
    sas_tes = models.DecimalField('SAS Tes', max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = [('student', 'subject', 'semester')]
        verbose_name = 'Nilai Sumatif Akhir'
        verbose_name_plural = 'Nilai Sumatif Akhir'

    def clean(self):
        if self.semester_id and self.subject_id:
            if self.subject.academic_year_id != self.semester.academic_year_id:
                raise ValidationError(
                    {'semester': 'Semester dan tahun pelajaran mapel harus sama.'}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.student} - {self.subject} ({self.semester})'

    @property
    def rata_lm(self):
        agg = self.student.nilai_lm.filter(
            subject=self.subject, semester=self.semester
        ).aggregate(r=Avg('nilai'))
        return agg['r']

    @property
    def rata_sas(self):
        nilai = [v for v in (self.sas_non_tes, self.sas_tes) if v is not None]
        if not nilai:
            return None
        return sum(nilai) / Decimal(len(nilai))

    @property
    def nilai_rapor(self):
        """Rata-rata dari Rata-rata LM, STS, dan Rata-rata SAS."""
        parts = [v for v in (self.rata_lm, self.sts, self.rata_sas) if v is not None]
        if not parts:
            return None
        return sum(Decimal(p) for p in parts) / Decimal(len(parts))


class HomeroomNote(models.Model):
    """Catatan wali kelas dan ketidakhadiran."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='catatan')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='catatan')
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='catatan',
        verbose_name='Tahun Pelajaran',
    )
    guru = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='catatan', verbose_name='Wali Kelas',
    )
    catatan = models.TextField('Catatan Wali Kelas', blank=True)
    sakit = models.PositiveSmallIntegerField(default=0)
    izin = models.PositiveSmallIntegerField(default=0)
    alpa = models.PositiveSmallIntegerField('Tanpa Keterangan', default=0)

    class Meta:
        unique_together = [('student', 'semester')]
        verbose_name = 'Catatan & Absensi'
        verbose_name_plural = 'Catatan & Absensi'

    def clean(self):
        if self.semester_id and self.academic_year_id:
            if self.semester.academic_year_id != self.academic_year_id:
                raise ValidationError(
                    {'academic_year': 'Tahun pelajaran harus sama dengan semester.'}
                )

    def save(self, *args, **kwargs):
        if self.semester_id:
            self.academic_year = self.semester.academic_year
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Catatan {self.student} ({self.semester})'


class Extracurricular(models.Model):
    """Ekstrakurikuler siswa (maksimal 5 per semester)."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='ekstrakurikuler')
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name='ekstrakurikuler'
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='ekstrakurikuler',
        verbose_name='Tahun Pelajaran',
    )
    guru = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ekstrakurikuler', verbose_name='Guru Pembina',
    )
    urutan = models.PositiveSmallIntegerField(default=1)
    nama = models.CharField('Ekstrakurikuler', max_length=100, blank=True)
    predikat = models.CharField(max_length=5, blank=True)
    deskripsi = models.CharField('Deskripsi', max_length=200, blank=True)

    class Meta:
        unique_together = [('student', 'semester', 'urutan')]
        ordering = ['urutan']
        verbose_name = 'Ekstrakurikuler'
        verbose_name_plural = 'Ekstrakurikuler'

    def clean(self):
        if self.semester_id and self.academic_year_id:
            if self.semester.academic_year_id != self.academic_year_id:
                raise ValidationError(
                    {'academic_year': 'Tahun pelajaran harus sama dengan semester.'}
                )

    def save(self, *args, **kwargs):
        if self.semester_id:
            self.academic_year = self.semester.academic_year
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nama} - {self.student}'


class AuditLog(models.Model):
    AKSI = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('CREATE', 'Tambah'),
        ('UPDATE', 'Ubah'),
        ('DELETE', 'Hapus'),
        ('ACTIVATE', 'Aktivasi'),
        ('IMPORT', 'Impor'),
        ('EXPORT', 'Ekspor'),
        ('PUBLISH', 'Publikasi'),
        ('UNLOCK', 'Buka Kunci'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_log',
    )
    aksi = models.CharField(max_length=20, choices=AKSI)
    model = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    deskripsi = models.TextField(blank=True)
    data_lama = models.JSONField(null=True, blank=True)
    data_baru = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Log'

    def __str__(self):
        return f'{self.created_at:%d/%m/%Y %H:%M} - {self.aksi} - {self.model}'


# Alias kompatibilitas: nama lama tetap dapat diimpor sampai kode migrasi selesai.
School = SchoolProfile
