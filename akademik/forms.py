from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.forms import inlineformset_factory

from .models import (
    AcademicYear,
    Assessment,
    AssessmentComponent,
    ClassGroup,
    EvaluasiFormatif,
    EvaluasiSumatif,
    ExtracurricularActivity,
    ExtracurricularPredicate,
    Grade,
    GradeConfiguration,
    LearningMaterial,
    LearningObjective,
    LearningOutcome,
    LearningTask,
    School,
    Semester,
    Student,
    Subject,
    Teacher,
)


def _pilihan_tingkat():
    """Pilihan tingkat kelas dari master Grade (fallback bila belum diisi)."""
    pilihan = [(g.nama, g.nama) for g in Grade.objects.all()]
    return pilihan or [('VII', 'VII'), ('VIII', 'VIII'), ('IX', 'IX')]


def _grade_dari_tingkat(tingkat, fase='D'):
    if not tingkat:
        return None
    grade, _ = Grade.objects.get_or_create(
        nama=tingkat,
        defaults={'fase': fase or 'D', 'urutan': 0},
    )
    return grade


def _pasang_class(form):
    for name, field in form.fields.items():
        widget = field.widget
        css = 'form-input'
        if isinstance(widget, forms.CheckboxInput):
            css = 'form-check'
        widget.attrs.setdefault('class', css)

        label = str(field.label or name.replace('_', ' ').title())
        if not field.help_text:
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                field.help_text = f'Pilih {label.lower()}.'
            elif isinstance(widget, forms.CheckboxInput):
                field.help_text = f'Centang jika {label.lower()}.'
            else:
                field.help_text = f'Isi {label.lower()}.'

        if not isinstance(widget, (forms.CheckboxInput, forms.FileInput, forms.Select, forms.MultiWidget)):
            if not widget.attrs.get('placeholder') and getattr(widget, 'input_type', 'text') not in ('date', 'datetime-local', 'time'):
                widget.attrs['placeholder'] = f'Masukkan {label.lower()}'
        if name != 'captcha' and field.help_text:
            widget.attrs.setdefault('data-help', str(field.help_text))
    return form


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={
            'autofocus': True,
            'placeholder': 'Masukkan username',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Masukkan password',
            'autocomplete': 'current-password',
        }),
    )
    captcha = CaptchaField(label='Kode Captcha', help_text='Masukkan kode pada gambar.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = [
            'nama', 'npsn', 'nss', 'alamat', 'kode_pos', 'desa', 'kecamatan',
            'kabupaten', 'provinsi', 'website', 'email', 'kepala_sekolah',
            'nktam_kepala', 'majelis', 'pimpinan_daerah', 'tempat_rapor',
            'logo', 'tampilkan_logo', 'ukuran_logo',
            'judul_rapor', 'subjudul_rapor', 'tampilkan_header', 'tampilkan_alamat',
            'tampilkan_ekskul', 'tampilkan_absensi', 'tampilkan_catatan',
            'label_ttd_orang_tua', 'label_ttd_kepala', 'label_ttd_wali',
            'tampilkan_ttd_orang_tua', 'tampilkan_ttd_kepala', 'tampilkan_ttd_wali',
            'font_rapor', 'ukuran_font', 'ukuran_kertas',
        ]
        widgets = {
            'majelis': forms.TextInput(),
            'pimpinan_daerah': forms.TextInput(),
            'logo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('tampilkan_logo', 'tampilkan_header', 'tampilkan_alamat',
                     'tampilkan_ekskul', 'tampilkan_absensi', 'tampilkan_catatan',
                     'tampilkan_ttd_orang_tua', 'tampilkan_ttd_kepala',
                     'tampilkan_ttd_wali'):
            self.fields[name].widget.attrs['class'] = 'form-check'
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-input'
        _pasang_class(self)

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'content_type'):
            if logo.size > 3 * 1024 * 1024:
                raise forms.ValidationError('Ukuran logo maksimal 3 MB.')
            if not logo.content_type.startswith('image/'):
                raise forms.ValidationError('File logo harus berupa gambar.')
        return logo


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['tahun', 'tanggal_mulai', 'tanggal_berakhir']
        widgets = {
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'tanggal_berakhir': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['academic_year', 'nama']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class ClassGroupForm(forms.ModelForm):
    class Meta:
        model = ClassGroup
        fields = ['academic_year', 'tingkat', 'nama', 'fase', 'wali_kelas_guru']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tingkat'] = forms.ChoiceField(
            label='Tingkat',
            choices=_pilihan_tingkat(),
            help_text='Pilih tingkat kelas (master Tingkat Kelas).',
        )
        _pasang_class(self)
        self.fields['wali_kelas_guru'].queryset = Teacher.objects.filter(aktif=True)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.grade = _grade_dari_tingkat(
            self.cleaned_data.get('tingkat'), self.cleaned_data.get('fase')
        )
        if obj.wali_kelas_guru_id:
            guru = obj.wali_kelas_guru
            obj.wali_kelas = guru.nama
            obj.nktam_wali = guru.nktam
        elif not obj.wali_kelas_guru_id:
            obj.wali_kelas = ''
            obj.nktam_wali = ''
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'no_urut', 'nis', 'nisn', 'nama', 'jenis_kelamin', 'tempat_lahir',
            'tanggal_lahir', 'agama', 'pendidikan_sebelumnya', 'alamat',
            'tahun_masuk', 'nama_ayah', 'nama_ibu', 'pekerjaan_ayah',
            'pekerjaan_ibu', 'alamat_orang_tua', 'aktif',
        ]
        widgets = {
            'tanggal_lahir': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['tahun_masuk'].queryset = AcademicYear.objects.order_by('-tahun')
        self.fields['tahun_masuk'].required = True
        self.fields['tahun_masuk'].help_text = (
            'Tahun pertama siswa masuk. Menentukan riwayat kenaikan kelas.'
        )
        if not self.instance.pk:
            aktif = AcademicYear.objects.filter(aktif=True).first()
            if aktif:
                self.fields['tahun_masuk'].initial = aktif
        elif self.instance.tahun_masuk_id is None:
            awal = self.instance.enrollments.order_by('academic_year__tahun').first()
            if awal:
                self.fields['tahun_masuk'].initial = awal.academic_year


class TeacherForm(forms.ModelForm):
    username = forms.CharField(
        label='Username Login',
        required=False,
        help_text='Kosongkan jika guru belum diberi akun login.',
    )
    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Wajib untuk akun baru. Kosongkan bila tidak ingin mengubah password.',
    )
    akun_aktif = forms.BooleanField(
        label='Akun login aktif', required=False, initial=True,
    )

    class Meta:
        model = Teacher
        fields = [
            'nama', 'nik', 'nip', 'nktam', 'jenis_kelamin', 'tempat_lahir',
            'tanggal_lahir', 'pendidikan', 'jurusan', 'tahun_lulus', 'jabatan',
            'email', 'no_hp', 'alamat', 'aktif',
        ]
        widgets = {
            'tanggal_lahir': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username
            self.fields['akun_aktif'].initial = self.instance.user.is_active

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            return ''
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Username sudah dipakai akun lain.')
        return username

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get('username')
        password = cleaned.get('password')
        punya_akun = bool(self.instance and self.instance.pk and self.instance.user_id)
        if username and not punya_akun and not password:
            self.add_error('password', 'Password wajib diisi untuk akun baru.')
        if password and len(password) < 6:
            self.add_error('password', 'Password minimal 6 karakter.')
        return cleaned

    def save(self, commit=True):
        teacher = super().save(commit=commit)
        if not commit:
            return teacher

        username = (self.cleaned_data.get('username') or '').strip()
        password = self.cleaned_data.get('password')
        akun_aktif = self.cleaned_data.get('akun_aktif')

        if username:
            user = teacher.user
            if user is None:
                user = User(username=username)
            user.username = username
            user.email = teacher.email
            user.first_name = teacher.nama
            user.is_staff = False
            user.is_superuser = False
            user.is_active = bool(akun_aktif)
            if password:
                user.set_password(password)
            user.save()
            teacher.user = user
            teacher.save(update_fields=['user'])
        elif teacher.user_id:
            user = teacher.user
            user.email = teacher.email
            user.first_name = teacher.nama
            user.is_active = bool(akun_aktif)
            user.save(update_fields=['email', 'first_name', 'is_active'])
        if teacher.user_id:
            guru_group, _ = Group.objects.get_or_create(name='Guru Mata Pelajaran')
            teacher.user.groups.add(guru_group)
        return teacher


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['academic_year', 'kode', 'nama', 'deskripsi', 'urutan']
        widgets = {'deskripsi': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Username',
            'first_name': 'Nama Depan',
            'last_name': 'Nama Belakang',
            'email': 'E-mail',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class AdminResetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


class UserForm(forms.ModelForm):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('kepala_sekolah', 'Kepala Sekolah'),
        ('operator', 'Operator/Tata Usaha'),
        ('guru', 'Guru Mata Pelajaran'),
        ('siswa', 'Siswa/Orang Tua'),
        ('pengguna', 'Pengguna biasa'),
    ]

    ROLE_GROUP = {
        'super_admin': 'Super Admin',
        'kepala_sekolah': 'Kepala Sekolah',
        'operator': 'Operator/Tata Usaha',
        'guru': 'Guru Mata Pelajaran',
        'siswa': 'Siswa/Orang Tua',
        'pengguna': None,
    }

    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Wajib untuk pengguna baru. Kosongkan bila tidak ingin mengubah.',
    )
    role = forms.ChoiceField(label='Peran', choices=ROLE_CHOICES, initial='pengguna')
    guru = forms.ModelChoiceField(
        label='Terhubung ke Data Guru',
        queryset=Teacher.objects.none(),
        required=False,
        help_text='Untuk peran guru, hubungkan ke profil Data Guru agar mendapat akses mapel.',
    )
    siswa = forms.ModelChoiceField(
        label='Terhubung ke Data Siswa',
        queryset=Student.objects.none(),
        required=False,
        help_text='Untuk peran Siswa/Orang Tua, hubungkan ke data siswa agar dapat melihat rapor terbit.',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        if self.instance.pk:
            guru_qs = Teacher.objects.filter(Q(user__isnull=True) | Q(user=self.instance))
        else:
            guru_qs = Teacher.objects.filter(user__isnull=True)
        self.fields['guru'].queryset = guru_qs.select_related('user')
        if self.instance.pk:
            siswa_qs = Student.objects.filter(
                Q(user__isnull=True) | Q(user=self.instance)
            )
        else:
            siswa_qs = Student.objects.filter(user__isnull=True)
        self.fields['siswa'].queryset = siswa_qs.select_related('class_group')
        if self.instance and self.instance.pk:
            groups = set(self.instance.groups.values_list('name', flat=True))
            if self.instance.is_superuser or 'Super Admin' in groups:
                self.fields['role'].initial = 'super_admin'
            elif 'Kepala Sekolah' in groups:
                self.fields['role'].initial = 'kepala_sekolah'
            elif 'Operator/Tata Usaha' in groups:
                self.fields['role'].initial = 'operator'
            teacher = Teacher.objects.filter(user=self.instance).first()
            if teacher:
                if self.fields['role'].initial == 'pengguna':
                    self.fields['role'].initial = 'guru'
                self.fields['guru'].initial = teacher
            siswa = Student.objects.filter(user=self.instance).first()
            if siswa:
                if self.fields['role'].initial == 'pengguna':
                    self.fields['role'].initial = 'siswa'
                self.fields['siswa'].initial = siswa

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if not self.instance.pk and not password:
            self.add_error('password', 'Password wajib diisi untuk pengguna baru.')
        if password and len(password) < 6:
            self.add_error('password', 'Password minimal 6 karakter.')
        if cleaned.get('role') == 'guru' and not cleaned.get('guru'):
            self.add_error('guru', 'Pilih data guru untuk peran guru.')
        if cleaned.get('role') == 'siswa' and not cleaned.get('siswa'):
            self.add_error('siswa', 'Pilih data siswa untuk peran Siswa/Orang Tua.')
        if cleaned.get('role') == 'super_admin' and password and len(password) < 8:
            self.add_error('password', 'Password Super Admin minimal 8 karakter.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data['role']
        user.is_staff = role == 'super_admin'
        user.is_superuser = role == 'super_admin'
        user.is_active = self.cleaned_data.get('is_active', True)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            target_group = self.ROLE_GROUP.get(role)
            role_groups = Group.objects.filter(name__in=[
                name for name in self.ROLE_GROUP.values() if name
            ])
            user.groups.remove(*role_groups)
            if target_group:
                group, _ = Group.objects.get_or_create(name=target_group)
                user.groups.add(group)
            guru = self.cleaned_data.get('guru')
            if role == 'guru' and guru:
                Teacher.objects.filter(user=user).exclude(pk=guru.pk).update(user=None)
                guru.user = user
                guru.save(update_fields=['user'])
            else:
                Teacher.objects.filter(user=user).update(user=None)

            siswa = self.cleaned_data.get('siswa')
            if role == 'siswa' and siswa:
                Student.objects.filter(user=user).exclude(pk=siswa.pk).update(user=None)
                if siswa.user_id != user.id:
                    siswa.user = user
                    siswa.save(update_fields=['user'])
            else:
                Student.objects.filter(user=user).update(user=None)
        return user


class TujuanPembelajaranForm(forms.ModelForm):
    class Meta:
        model = LearningObjective
        fields = ['subject', 'learning_outcome', 'kode', 'nomor', 'deskripsi', 'guru', 'aktif']
        widgets = {
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['nomor'].required = False
        self.fields['nomor'].help_text = 'Kosongkan untuk melanjutkan nomor otomatis.'
        self.fields['kode'].help_text = 'Opsional, misalnya TP.1 atau 7.1.'
        self.fields['learning_outcome'].help_text = (
            'Opsional. Pilih CP yang menjadi acuan TP ini.'
        )
        self.fields['guru'].queryset = Teacher.objects.filter(aktif=True)

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get('subject')
        cp = cleaned.get('learning_outcome')
        if subject and cp and cp.subject_id != subject.id:
            self.add_error(
                'learning_outcome',
                'CP harus berasal dari mata pelajaran yang sama.',
            )
        return cleaned


class CapaianPembelajaranForm(forms.ModelForm):
    class Meta:
        model = LearningOutcome
        fields = ['subject', 'kode', 'fase', 'deskripsi', 'urutan', 'aktif']
        widgets = {
            'deskripsi': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['urutan'].required = False
        self.fields['urutan'].help_text = 'Kosongkan untuk melanjutkan urutan otomatis.'
        self.fields['kode'].help_text = 'Opsional, misalnya CP.1.'
        self.fields['deskripsi'].help_text = (
            'Tulis capaian pembelajaran sesuai fase, tanpa titik di akhir.'
        )


class MateriPembelajaranForm(forms.ModelForm):
    class Meta:
        model = LearningMaterial
        fields = [
            'subject', 'objectives', 'kode', 'judul', 'deskripsi', 'urutan', 'aktif',
        ]
        widgets = {
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
            'objectives': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['urutan'].required = False
        self.fields['urutan'].help_text = 'Kosongkan untuk melanjutkan urutan otomatis.'
        self.fields['objectives'].help_text = 'Pilih satu atau beberapa TP yang dicakup materi ini.'

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get('subject')
        objectives = cleaned.get('objectives')
        if subject and objectives:
            salah = objectives.exclude(subject=subject)
            if salah.exists():
                self.add_error(
                    'objectives',
                    'Semua TP harus berasal dari mata pelajaran yang sama.',
                )
        return cleaned


class TugasPembelajaranForm(forms.ModelForm):
    class Meta:
        model = LearningTask
        fields = [
            'subject', 'class_groups', 'objectives', 'judul', 'deskripsi',
            'instruksi', 'tanggal_pemberian', 'batas_pengumpulan', 'lampiran',
            'bobot', 'status',
        ]
        widgets = {
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
            'instruksi': forms.Textarea(attrs={'rows': 4}),
            'tanggal_pemberian': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'batas_pengumpulan': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'class_groups': forms.CheckboxSelectMultiple(),
            'objectives': forms.CheckboxSelectMultiple(),
            'lampiran': forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip,.jpg,.jpeg,.png'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['class_groups'].help_text = 'Pilih kelas yang mengerjakan tugas ini.'
        self.fields['objectives'].help_text = 'Pilih TP yang menjadi acuan tugas.'
        self.fields['lampiran'].help_text = 'Opsional, maksimal 10 MB.'

    def clean_lampiran(self):
        lampiran = self.cleaned_data.get('lampiran')
        if lampiran and hasattr(lampiran, 'size') and lampiran.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Ukuran lampiran maksimal 10 MB.')
        return lampiran

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get('subject')
        objectives = cleaned.get('objectives')
        class_groups = cleaned.get('class_groups')
        awal = cleaned.get('tanggal_pemberian')
        akhir = cleaned.get('batas_pengumpulan')
        if subject and objectives:
            salah = objectives.exclude(subject=subject)
            if salah.exists():
                self.add_error(
                    'objectives',
                    'Semua TP harus berasal dari mata pelajaran yang sama.',
                )
        if subject and class_groups:
            salah = class_groups.exclude(academic_year=subject.academic_year)
            if salah.exists():
                self.add_error(
                    'class_groups',
                    'Semua kelas harus berada pada tahun pelajaran mapel ini.',
                )
        if awal and akhir and akhir < awal:
            self.add_error(
                'batas_pengumpulan',
                'Batas pengumpulan tidak boleh sebelum tanggal pemberian.',
            )
        return cleaned




class EvaluasiFormatifForm(forms.ModelForm):
    class Meta:
        model = EvaluasiFormatif
        fields = ['subject', 'nama', 'jenis', 'tanggal', 'bobot', 'deskripsi', 'aktif']
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)

    def clean_bobot(self):
        bobot = self.cleaned_data.get('bobot')
        if bobot is not None and (bobot < 0 or bobot > 100):
            raise forms.ValidationError('Bobot harus antara 0 dan 100.')
        return bobot


class EvaluasiSumatifForm(forms.ModelForm):
    class Meta:
        model = EvaluasiSumatif
        fields = ['subject', 'nama', 'jenis', 'tanggal', 'bobot', 'deskripsi', 'aktif']
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)

    def clean_bobot(self):
        bobot = self.cleaned_data.get('bobot')
        if bobot is not None and (bobot < 0 or bobot > 100):
            raise forms.ValidationError('Bobot harus antara 0 dan 100.')
        return bobot


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            'subject', 'class_group', 'nama', 'kategori', 'metode', 'tanggal',
            'bobot', 'deskripsi', 'status',
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['class_group'].help_text = (
            'Opsional. Kosongkan jika asesmen berlaku untuk semua kelas.'
        )

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get('subject')
        kelas = cleaned.get('class_group')
        if subject and kelas:
            if kelas.academic_year_id != subject.academic_year_id:
                self.add_error(
                    'class_group', 'Kelas harus berada pada tahun pelajaran mapel.'
                )
        return cleaned


class AssessmentComponentForm(forms.ModelForm):
    class Meta:
        model = AssessmentComponent
        fields = [
            'nama', 'tipe', 'urutan', 'bobot', 'nilai_maksimal', 'wajib',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


AssessmentComponentFormSet = inlineformset_factory(
    Assessment,
    AssessmentComponent,
    form=AssessmentComponentForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class GradeConfigurationForm(forms.ModelForm):
    class Meta:
        model = GradeConfiguration
        fields = [
            'bobot_lm', 'bobot_sts', 'bobot_sas', 'bobot_sas_non_tes',
            'bobot_sas_tes', 'metode_pembulatan', 'jumlah_desimal',
            'nilai_min', 'nilai_max', 'ambang_unggul',
            'ambang_perlu_bimbingan', 'aktif',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['aktif'].help_text = 'Gunakan konfigurasi ini untuk perhitungan.'

    def clean(self):
        cleaned = super().clean()
        desimal = cleaned.get('jumlah_desimal')
        minimum = cleaned.get('nilai_min')
        maksimum = cleaned.get('nilai_max')
        unggul = cleaned.get('ambang_unggul')
        perlu = cleaned.get('ambang_perlu_bimbingan')
        if desimal is not None and (desimal < 0 or desimal > 4):
            self.add_error('jumlah_desimal', 'Jumlah desimal harus 0-4.')
        if minimum is not None and maksimum is not None and minimum >= maksimum:
            self.add_error('nilai_max', 'Nilai maksimum harus lebih besar dari minimum.')
        if unggul is not None and perlu is not None and perlu >= unggul:
            self.add_error(
                'ambang_perlu_bimbingan',
                'Ambang perlu bimbingan harus lebih kecil dari ambang unggul.',
            )
        for name in ('bobot_lm', 'bobot_sts', 'bobot_sas'):
            bobot = cleaned.get(name)
            if bobot is not None and bobot < 0:
                self.add_error(name, 'Bobot tidak boleh negatif.')
        total = sum(
            bobot for bobot in (
                cleaned.get('bobot_lm'), cleaned.get('bobot_sts'),
                cleaned.get('bobot_sas'),
            ) if bobot is not None
        )
        if total is not None and total <= 0:
            self.add_error(
                'bobot_lm', 'Minimal salah satu bobot LM/STS/SAS harus lebih dari 0.'
            )
        return cleaned


class ExtracurricularActivityForm(forms.ModelForm):
    class Meta:
        model = ExtracurricularActivity
        fields = ['nama', 'pembina', 'deskripsi', 'urutan', 'aktif']
        widgets = {'deskripsi': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)
        self.fields['pembina'].queryset = Teacher.objects.filter(aktif=True)
        self.fields['urutan'].required = False
        self.fields['urutan'].help_text = 'Kosongkan untuk melanjutkan urutan otomatis.'


class ExtracurricularPredicateForm(forms.ModelForm):
    class Meta:
        model = ExtracurricularPredicate
        fields = ['label', 'batas_min', 'deskripsi', 'urutan', 'aktif']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)

    def clean_batas_min(self):
        nilai = self.cleaned_data.get('batas_min')
        if nilai is not None and (nilai < 0 or nilai > 100):
            raise forms.ValidationError('Batas minimum harus 0-100.')
        return nilai
