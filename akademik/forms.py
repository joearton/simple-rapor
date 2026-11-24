from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from django.db.models import Q

from .models import AcademicYear, ClassGroup, School, Semester, Student, Subject, Teacher


def _pasang_class(form):
    for field in form.fields.values():
        css = 'form-input'
        if isinstance(field.widget, forms.CheckboxInput):
            css = 'form-check'
        field.widget.attrs.setdefault('class', css)
    return form


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Masukkan username'}),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Masukkan password'}),
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

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'content_type'):
            if logo.size > 3 * 1024 * 1024:
                raise forms.ValidationError('Ukuran logo maksimal 3 MB.')
            if not logo.content_type.startswith('image/'):
                raise forms.ValidationError('File logo harus berupa gambar.')
        return logo


class KelasForm(forms.ModelForm):
    class Meta:
        model = ClassGroup
        fields = ['tingkat', 'nama', 'fase', 'wali_kelas_guru']
        widgets = {
            'wali_kelas_guru': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['wali_kelas_guru'].queryset = Teacher.objects.filter(aktif=True)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if obj.wali_kelas_guru_id:
            guru = obj.wali_kelas_guru
            obj.wali_kelas = guru.nama
            obj.nktam_wali = guru.nktam
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['tahun']

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
        _pasang_class(self)
        self.fields['wali_kelas_guru'].queryset = Teacher.objects.filter(aktif=True)

    def save(self, commit=True):
        obj = super().save(commit=False)
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
            'nama_ayah', 'nama_ibu', 'pekerjaan_ayah', 'pekerjaan_ibu',
            'alamat_orang_tua', 'aktif',
        ]
        widgets = {
            'tanggal_lahir': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _pasang_class(self)


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
        return teacher


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['nama', 'urutan']

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
        ('admin', 'Administrator'),
        ('guru', 'Guru'),
        ('pengguna', 'Pengguna biasa'),
    ]

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
        if self.instance and self.instance.pk:
            if self.instance.is_staff or self.instance.is_superuser:
                self.fields['role'].initial = 'admin'
            teacher = Teacher.objects.filter(user=self.instance).first()
            if teacher:
                if not self.fields['role'].initial or self.fields['role'].initial != 'admin':
                    self.fields['role'].initial = 'guru'
                self.fields['guru'].initial = teacher

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if not self.instance.pk and not password:
            self.add_error('password', 'Password wajib diisi untuk pengguna baru.')
        if password and len(password) < 6:
            self.add_error('password', 'Password minimal 6 karakter.')
        if cleaned.get('role') == 'guru' and not cleaned.get('guru'):
            self.add_error('guru', 'Pilih data guru untuk peran guru.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data['role']
        user.is_staff = role == 'admin'
        user.is_superuser = role == 'admin'
        user.is_active = self.cleaned_data.get('is_active', True)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            guru = self.cleaned_data.get('guru')
            if guru:
                Teacher.objects.filter(user=user).exclude(pk=guru.pk).update(user=None)
                guru.user = user
                guru.save(update_fields=['user'])
            elif role == 'pengguna':
                Teacher.objects.filter(user=user).update(user=None)
        return user
