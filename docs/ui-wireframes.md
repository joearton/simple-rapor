# Wireframe & Rancangan UI/UX

## 1. Prinsip
- Light theme, dominan hijau sekolah + aksen emas.
- Sidebar kiri (peran), topbar kanan (chip periode, menu pengguna).
- Kartu statistik, tabel padat, filter di atas tabel, pagination di bawah.
- Form panjang memakai tab; error validasi otomatis membuka tab terkait.
- Mobile: sidebar menjadi drawer/horizontal; tabel dapat di-scroll; filter menumpuk.
- Status memakai badge konsisten: Draf, Review, Disetujui, Terbit, Terkunci, Arsip.

## 2. Navigasi per peran

```text
Super Admin        : Beranda | Sekolah | Akademik | Pengguna | Pembelajaran |
                     Asesmen | Rapor | Pengaturan | Audit | Backup
Kepala Sekolah     : Beranda | Monitoring | Leger | Review Rapor | Publikasi
Operator/TU        : Beranda | Siswa | Guru | Kelas | Mapel | Penugasan | Import
Guru Mapel         : Beranda | Tugas | Asesmen Formatif | Asesmen Sumatif |
                     Rekap Mapel | Profil
Wali Kelas         : Beranda | Data Kelas | Rekap Nilai | Catatan | Absensi |
                     Ekskul | Rapor | Profil
Siswa/Orang Tua    : Beranda | Nilai | Rapor | Profil
```

## 3. Dashboard

```text
┌──────────────┬────────────────────────────────────────────────────────┐
│ Sidebar      │ Topbar: [Judul]              [Semester ▼] [User ▼]      │
│              ├────────────────────────────────────────────────────────┤
│ Beranda      │ Hero: Tahun Pelajaran / Semester / Status Periode        │
│ Data Siswa   │                                                        │
│ Guru         │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │
│ Mapel        │ │Siswa   │ │Guru    │ │Kelas   │ │Mapel   │            │
│ Tugas        │ │ 27     │ │ 11     │ │ 1      │ │ 14     │            │
│ Formatif     │ └────────┘ └────────┘ └────────┘ └────────┘            │
│ Sumatif      │ ┌──────────────────────────┐ ┌───────────────────────┐ │
│ Leger        │ │ Kelengkapan Nilai        │ │ Kelengkapan Rapor     │ │
│ Rapor        │ │ ███████░░░ 72%           │ │ ████░░░░ 40%          │ │
│              │ └──────────────────────────┘ └───────────────────────┘ │
│              │ ┌────────────────────────────────────────────────────┐ │
│              │ │ Mapel | Guru | Nilai terisi | Progres | Aksi      │ │
│              │ └────────────────────────────────────────────────────┘ │
└──────────────┴────────────────────────────────────────────────────────┘
```

Kartu statistik dapat diklik menuju daftar terfilter. Grafik tren nilai opsional
memakai Chart.js (rata-rata per mapel/kelas).

## 4. Halaman daftar (master dan rencana)

```text
┌─────────────────────────────────────────────────────────────┐
│ Judul halaman                          [Tambah] [Ekspor]   │
│ Deskripsi singkat                                          │
├─────────────────────────────────────────────────────────────┤
│ [Cari...] [Mapel ▼] [Status ▼] [Terapkan] [Reset]          │
├─────────────────────────────────────────────────────────────┤
│ No | Nama/Judul | Mapel | Guru | Tanggal | Status | Aksi  │
│ 1  | ...        | ...   | ...  | ...     | Aktif  | [Nilai]│
│                                                      [Edit] [Hapus] │
├─────────────────────────────────────────────────────────────┤
│ Menampilkan 1–25 dari 43           [‹] [1] [2] [›]         │
└─────────────────────────────────────────────────────────────┘
```

## 5. Grid input nilai (formatif/sumatif)

```text
┌──────────────────────────────────────────────────────────────┐
│ Evaluasi Sumatif — Matematika       Semester I 2026/2027      │
│ [Cari siswa] [Status ▼] [Ekspor] [Impor] [Kembali]           │
├────┬───────────────────┬─────┬─────┬─────┬──────┬─────┬──────┤
│ No │ Nama              │ LM1 │ LM2 │ ... │ STS  │ SAS │ Rata │
├────┼───────────────────┼─────┼─────┼─────┼──────┼─────┼──────┤
│ 1  │ Ahmad Yani        │ [85]│ [90]│ ... │ [88] │ [90]│ 88,5 │
│ 2  │ Aqila Nayaka      │ [ ] │ [ ] │ ... │ [ ]  │ [ ] │  -   │
│    │                   │     │     │     │      │     │      │
├────┴───────────────────┴─────┴─────┴─────┴──────┴─────┴──────┤
│ Filter: mapel/kelas/asesmen | Simpan | Simpan & lanjut       │
└──────────────────────────────────────────────────────────────┘
```

- Kolom pertama sticky; header sticky; input `min-width:70px`.
- `Enter`/`Tab` berpindah sel; nilai invalid ditandai merah.
- Total dihitung langsung (JS) dan divalidasi ulang server.
- Autosave per baris (AJAX) atau simpan seluruh halaman; semua dalam transaksi.

## 6. Halaman rapor

```text
┌──────────────────────────────────────────────────────────┐
│ Rapor — Ahmad Yani                     [Review] [PDF]    │
│ Status: DRAF   Kelengkapan: 12/14 mapel                  │
├──────────────────────────────────────────────────────────┤
│ Identitas | Nilai mapel | Deskripsi | Catatan | Absensi  │
│ Nilai mapel: No | Mapel | Nilai | Deskripsi capaian      │
│ Ekskul, kehadiran, catatan wali                          │
│ [Ajukan ke Kepala Sekolah]                               │
├──────────────────────────────────────────────────────────┤
│ Preview rapor A4 (HTML) — tombol Cetak/Unduh PDF         │
└──────────────────────────────────────────────────────────┘
```

## 7. Komponen reusable

- `components/sidebar.html`, `navbar.html`, `breadcrumb.html`
- `components/filter_bar.html`, `data_table.html`, `pagination.html`
- `components/form_field.html`, `form_tabs.html`, `modal_confirm.html`
- `components/alert.html`, `badge_status.html`, `empty_state.html`
- `components/grade_grid.html`, `report_preview.html`

## 8. Aksesibilitas dan responsif
- Kontras teks minimal AA; label form selalu terhubung `for/id`.
- Navigasi keyboard untuk grid; aria-label tombol ikon.
- Tabel lebar memakai scroll horizontal dengan kolom nama sticky.
- Form dua kolom menjadi satu kolom di layar < 820px.
- Modal tidak menutup saat klik luar untuk form penting; konfirmasi hapus tetap modal.
