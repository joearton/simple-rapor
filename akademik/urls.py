from django.urls import path

from . import views

app_name = 'akademik'

urlpatterns = [
    path('login/', views.LoginSekolahView.as_view(), name='login'),
    path('logout/', views.logout_sekolah, name='logout'),
    path('ubah-password/', views.UbahPasswordView.as_view(), name='ubah_password'),
    path('profil/', views.profil, name='profil'),

    path('pengguna/', views.pengguna_list, name='pengguna_list'),
    path('pengguna/tambah/', views.pengguna_form, name='pengguna_tambah'),
    path('pengguna/<int:pk>/ubah/', views.pengguna_form, name='pengguna_ubah'),
    path('pengguna/<int:pk>/reset-password/', views.pengguna_reset_password, name='pengguna_reset_password'),
    path('pengguna/<int:pk>/hapus/', views.pengguna_hapus, name='pengguna_hapus'),
    path('audit-log/', views.audit_log, name='audit_log'),
    path('pilih-tahun-pelajaran/', views.pilih_tahun_pelajaran, name='pilih_tahun_pelajaran'),

    path('', views.dashboard, name='dashboard'),
    path('identitas/', views.identitas, name='identitas'),

    path('tahun-pelajaran/', views.tahun_list, name='tahun_list'),
    path('tahun-pelajaran/tambah/', views.tahun_form, name='tahun_tambah'),
    path('tahun-pelajaran/<int:pk>/ubah/', views.tahun_form, name='tahun_ubah'),
    path('tahun-pelajaran/<int:pk>/hapus/', views.tahun_hapus, name='tahun_hapus'),
    path('tahun-pelajaran/<int:pk>/aktifkan/', views.tahun_aktifkan, name='tahun_aktifkan'),
    path('semester/tambah/', views.semester_form, name='semester_tambah'),
    path('semester/<int:pk>/ubah/', views.semester_form, name='semester_ubah'),
    path('semester/<int:pk>/hapus/', views.semester_hapus, name='semester_hapus'),
    path('semester/<int:pk>/aktifkan/', views.semester_aktifkan, name='semester_aktifkan'),
    path('kelas/tambah/', views.kelas_form, name='kelas_tambah'),
    path('kelas/<int:pk>/ubah/', views.kelas_form, name='kelas_ubah'),
    path('kelas/<int:pk>/hapus/', views.kelas_hapus, name='kelas_hapus'),
    path('kelas/<int:pk>/aktifkan/', views.kelas_aktifkan, name='kelas_aktifkan'),

    path('siswa/', views.siswa_list, name='siswa_list'),
    path('siswa/tambah/', views.siswa_form, name='siswa_tambah'),
    path('siswa/<int:pk>/ubah/', views.siswa_form, name='siswa_ubah'),
    path('siswa/<int:pk>/hapus/', views.siswa_hapus, name='siswa_hapus'),

    path('guru/', views.guru_list, name='guru_list'),
    path('guru/tambah/', views.guru_form, name='guru_tambah'),
    path('guru/<int:pk>/ubah/', views.guru_form, name='guru_ubah'),
    path('guru/<int:pk>/hapus/', views.guru_hapus, name='guru_hapus'),

    path('mapel/', views.mapel_list, name='mapel_list'),
    path('mapel/tambah/', views.mapel_form, name='mapel_tambah'),
    path('mapel/<int:pk>/ubah/', views.mapel_form, name='mapel_ubah'),
    path('mapel/<int:pk>/hapus/', views.mapel_hapus, name='mapel_hapus'),

    path('pembagian-mengajar/', views.mengajar, name='mengajar'),

    path('ekspor/<str:kind>/', views.ekspor_data, name='ekspor'),
    path('impor/<str:kind>/', views.impor_data, name='impor'),

    path('tp/', views.tugas_list, name='tp_menu'),
    path('tp/tambah/', views.tugas_form, name='tp_tambah'),
    path('tp/<int:pk>/ubah/', views.tugas_form, name='tp_ubah'),
    path('tp/<int:subject_id>/', views.tugas_list, name='tp_list'),

    path('cp/', views.cp_list, name='cp_menu'),
    path('cp/tambah/', views.cp_form, name='cp_tambah'),
    path('cp/<int:pk>/ubah/', views.cp_form, name='cp_ubah'),
    path('cp/<int:subject_id>/', views.cp_list, name='cp_list'),

    path('materi/', views.materi_list, name='materi_menu'),
    path('materi/tambah/', views.materi_form, name='materi_tambah'),
    path('materi/<int:pk>/ubah/', views.materi_form, name='materi_ubah'),
    path('materi/<int:subject_id>/', views.materi_list, name='materi_list'),

    path('tugas/', views.tugas_pembelajaran_list, name='tugas_pembelajaran_list'),
    path('tugas/tambah/', views.tugas_pembelajaran_form, name='tugas_pembelajaran_tambah'),
    path('tugas/<int:pk>/ubah/', views.tugas_pembelajaran_form, name='tugas_pembelajaran_ubah'),
    path('tugas/<int:pk>/kumpulan/', views.tugas_pembelajaran_detail, name='tugas_pembelajaran_detail'),
    path('tugas/<int:subject_id>/', views.tugas_pembelajaran_list, name='tugas_pembelajaran_list'),

    path('formatif/', views.evaluasi_formatif_list, name='formatif_menu'),
    path('formatif/tambah/', views.evaluasi_formatif_form, name='formatif_evaluasi_tambah'),
    path('formatif/<int:pk>/ubah/', views.evaluasi_formatif_form, name='formatif_evaluasi_ubah'),
    path('formatif/<int:pk>/hapus/', views.evaluasi_formatif_hapus, name='formatif_evaluasi_hapus'),
    path('formatif/<int:subject_id>/nilai/', views.formatif_entry, name='formatif_entry'),

    path('asesmen/', views.asesmen_list, name='asesmen_list'),
    path('asesmen/tambah/', views.asesmen_form, name='asesmen_tambah'),
    path('asesmen/<int:pk>/ubah/', views.asesmen_form, name='asesmen_ubah'),
    path('asesmen/<int:pk>/nilai/', views.asesmen_grid, name='asesmen_grid'),
    path('asesmen/<int:pk>/simpan/', views.asesmen_simpan, name='asesmen_simpan'),
    path('asesmen/<int:pk>/ekspor/', views.asesmen_ekspor, name='asesmen_ekspor'),
    path('asesmen/<int:pk>/impor/', views.asesmen_impor, name='asesmen_impor'),
    path('konfigurasi-nilai/', views.konfigurasi_nilai_view, name='konfigurasi_nilai'),

    path('sumatif/', views.evaluasi_sumatif_list, name='sumatif_menu'),
    path('sumatif/tambah/', views.evaluasi_sumatif_form, name='sumatif_evaluasi_tambah'),
    path('sumatif/<int:pk>/ubah/', views.evaluasi_sumatif_form, name='sumatif_evaluasi_ubah'),
    path('sumatif/<int:pk>/hapus/', views.evaluasi_sumatif_hapus, name='sumatif_evaluasi_hapus'),
    path('sumatif/<int:subject_id>/nilai/', views.sumatif_entry, name='sumatif_entry'),

    path('catatan/', views.catatan_entry, name='catatan_entry'),
    path('ekskul/', views.ekskul_entry, name='ekskul_entry'),
    path('leger/', views.leger, name='leger'),

    path('rapor/', views.rapor_index, name='rapor_index'),
    path('rapor/cetak-semua/', views.cetak_semua, name='cetak_semua'),
    path('rapor/<int:student_id>/', views.rapor_detail, name='rapor_detail'),
    path('rapor/<int:student_id>/sampul/', views.rapor_sampul, name='rapor_sampul'),
]
