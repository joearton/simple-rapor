from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg


class School(models.Model):
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


class ClassGroup(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='kelas_list'
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
    nama = models.CharField('Mata Pelajaran', max_length=100, unique=True)
    urutan = models.PositiveSmallIntegerField('Urutan', default=0)

    class Meta:
        ordering = ['urutan', 'nama']
        verbose_name = 'Mata Pelajaran'
        verbose_name_plural = 'Mata Pelajaran'

    def __str__(self):
        return self.nama


class TeachingAssignment(models.Model):
    """Pembagian tugas mengajar: guru pengampu tiap mapel per kelas/tahun."""

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

    class Meta:
        unique_together = [('class_group', 'subject', 'academic_year')]
        ordering = ['subject__urutan']
        verbose_name = 'Pembagian Mengajar'
        verbose_name_plural = 'Pembagian Mengajar'

    def __str__(self):
        return f'{self.subject.nama} - {self.class_group.nama_lengkap} - {self.teacher.nama}'


class LearningObjective(models.Model):
    """Tujuan Pembelajaran (TP) / Lingkup Materi per tahun pelajaran."""

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='tujuan_list')
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
    nomor = models.PositiveSmallIntegerField('Nomor TP')
    deskripsi = models.TextField('Tujuan Pembelajaran / Lingkup Materi')
    aktif = models.BooleanField('Aktif', default=True)

    class Meta:
        unique_together = [('subject', 'academic_year', 'nomor')]
        ordering = ['subject__urutan', 'nomor']
        verbose_name = 'Tujuan Pembelajaran'
        verbose_name_plural = 'Tujuan Pembelajaran'

    def __str__(self):
        return f'TP {self.nomor} - {self.subject.nama} ({self.academic_year.tahun})'


class Student(models.Model):
    JENIS_KELAMIN = [('L', 'Laki-Laki'), ('P', 'Perempuan')]

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

    def save(self, *args, **kwargs):
        if self.objective_id and not self.deskripsi_tp:
            self.deskripsi_tp = self.objective.deskripsi
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

    def __str__(self):
        return f'Catatan {self.student} ({self.semester})'


class Extracurricular(models.Model):
    """Ekstrakurikuler siswa (maksimal 5 per semester)."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='ekstrakurikuler')
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name='ekstrakurikuler'
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

    def __str__(self):
        return f'{self.nama} - {self.student}'
