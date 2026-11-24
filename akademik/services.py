from decimal import Decimal, ROUND_DOWN, ROUND_HALF_DOWN, ROUND_HALF_UP, ROUND_UP

from .models import (
    AssessmentObjective,
    AssessmentResult,
    ClassGroup,
    Extracurricular,
    FormativeScore,
    GradeConfiguration,
    HomeroomNote,
    School,
    Semester,
    Student,
    Subject,
)

MAX_LM = 10

ROUNDING = {
    'HALF_UP': ROUND_HALF_UP,
    'HALF_DOWN': ROUND_HALF_DOWN,
    'UP': ROUND_UP,
    'DOWN': ROUND_DOWN,
}


def q2(value):
    """Bulatkan ke 2 desimal."""
    if value is None:
        return None
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def bulatkan(value, konfigurasi=None):
    """Bulatkan nilai sesuai konfigurasi dan jepit pada batas nilai."""
    if value is None:
        return None
    nilai = Decimal(value)
    if konfigurasi is None:
        return q2(nilai)
    desimal = int(konfigurasi.jumlah_desimal)
    kuantum = Decimal(1).scaleb(-desimal)
    hasil = nilai.quantize(
        kuantum, rounding=ROUNDING.get(konfigurasi.metode_pembulatan, ROUND_HALF_UP)
    )
    if hasil < konfigurasi.nilai_min:
        hasil = Decimal(konfigurasi.nilai_min)
    if hasil > konfigurasi.nilai_max:
        hasil = Decimal(konfigurasi.nilai_max)
    return hasil


def _rata(values):
    bersih = [Decimal(v) for v in values if v is not None]
    if not bersih:
        return None
    return sum(bersih) / Decimal(len(bersih))


def _rata_terbobot(pasangan):
    """Rata-rata tertimbang dari pasangan (nilai, bobot), abaikan yang kosong."""
    total_bobot = Decimal('0')
    total = Decimal('0')
    for nilai, bobot in pasangan:
        if nilai is None:
            continue
        bobot = Decimal(bobot or 0)
        if bobot <= 0:
            continue
        total += Decimal(nilai) * bobot
        total_bobot += bobot
    if total_bobot <= 0:
        return None
    return total / total_bobot


def konfigurasi_nilai(subject, semester):
    return GradeConfiguration.get_config(subject, semester.academic_year)


def angka(value):
    """Format angka gaya Indonesia (koma desimal, tanpa nol berekor)."""
    if value in (None, ''):
        return '-'
    d = q2(value)
    teks = f'{d:.2f}'.rstrip('0').rstrip('.')
    return teks.replace('.', ',')


def tanggal_indonesia(value, dengan_hari=False):
    if not value:
        return '-'
    bulan = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
    ]
    hari = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    teks = f'{value.day} {bulan[value.month - 1]} {value.year}'
    if dengan_hari:
        teks = f'{hari[value.weekday()]}, {teks}'
    return teks


def semester_aktif():
    return Semester.get_aktif()


def kelas_aktif():
    aktif = (
        ClassGroup.objects.filter(academic_year__aktif=True, aktif=True).first()
        or ClassGroup.objects.filter(academic_year__aktif=True).first()
    )
    return aktif or ClassGroup.objects.first()


def daftar_siswa(class_group):
    if class_group is None:
        return Student.objects.none()
    return Student.objects.in_class(class_group).filter(aktif=True).order_by('no_urut')


def daftar_mapel(tahun=None):
    if tahun is None:
        semester = Semester.get_aktif()
        tahun = semester.academic_year if semester else None
    if tahun is None:
        return Subject.objects.none()
    return Subject.objects.filter(academic_year=tahun)


def nilai_formatif_map(student, subject, semester):
    links = AssessmentObjective.objects.filter(
        assessment__subject=subject,
        assessment__semester=semester,
        assessment__kategori='FORMATIF',
    ).values_list('assessment_id', 'objective_id')
    objective_by_assessment = dict(links)
    data = {}
    results = AssessmentResult.objects.filter(
        student=student,
        component__assessment__subject=subject,
        component__assessment__semester=semester,
        component__assessment__kategori='FORMATIF',
    ).values_list('component__assessment_id', 'nilai')
    for assessment_id, nilai in results:
        objective_id = objective_by_assessment.get(assessment_id)
        if objective_id is not None and nilai is not None:
            data[objective_id] = nilai
    if not data:
        data = dict(
            FormativeScore.objects.filter(
                student=student,
                objective__subject=subject,
                objective__academic_year=semester.academic_year,
                semester=semester,
            ).values_list('objective_id', 'nilai')
        )
    return data


def tujuan_aktif(subject, semester):
    return subject.tujuan_list.filter(
        academic_year=semester.academic_year, aktif=True
    ).order_by('nomor')


def deskripsi_capaian(student, subject, semester, objectives=None):
    """Ambil TP unggul/perlu bimbingan dengan ambang dari konfigurasi nilai."""
    if objectives is None:
        objectives = list(
            subject.tujuan_list.filter(academic_year=semester.academic_year).order_by('nomor')
        )
    links = AssessmentObjective.objects.filter(
        assessment__subject=subject,
        assessment__semester=semester,
        assessment__kategori='FORMATIF',
    ).select_related('objective')
    objective_by_assessment = {
        link.assessment_id: link.objective for link in links
    }
    skor = {}
    results = AssessmentResult.objects.filter(
        student=student,
        component__assessment__subject=subject,
        component__assessment__semester=semester,
        component__assessment__kategori='FORMATIF',
    ).select_related('component__assessment')
    for result in results:
        if result.nilai is None:
            continue
        objective = objective_by_assessment.get(result.component.assessment_id)
        if objective is not None:
            skor[objective.id] = result.nilai

    # Fallback untuk data yang belum tersinkron ke asesmen generik.
    if not skor:
        legacy = FormativeScore.objects.filter(
            student=student,
            objective__subject=subject,
            objective__academic_year=semester.academic_year,
            semester=semester,
        )
        skor = {score.objective_id: score.nilai for score in legacy}

    teks_legacy = dict(
        FormativeScore.objects.filter(
            student=student,
            objective__subject=subject,
            objective__academic_year=semester.academic_year,
            semester=semester,
        ).values_list('objective_id', 'deskripsi_tp')
    )
    teks_tp = {
        obj.id: (teks_legacy.get(obj.id) or obj.deskripsi) for obj in objectives
    }

    konfigurasi = konfigurasi_nilai(subject, semester)
    unggul = perlu = None
    if skor:
        tertinggi = max(skor.values())
        if tertinggi >= konfigurasi.ambang_unggul:
            for obj in objectives:
                if skor.get(obj.id) == tertinggi:
                    unggul = obj
                    break
        positif = {oid: v for oid, v in skor.items() if v > 0}
        if positif:
            terendah = min(positif.values())
            if terendah <= konfigurasi.ambang_perlu_bimbingan:
                for obj in objectives:
                    if skor.get(obj.id) == terendah:
                        perlu = obj
                        break

    parts = []
    if unggul:
        parts.append(
            f'Ananda sangat menguasai dalam {teks_tp.get(unggul.id, unggul.deskripsi)}.'
        )
    if perlu:
        parts.append(
            f'Ananda perlu bimbingan dalam {teks_tp.get(perlu.id, perlu.deskripsi)}.'
        )
    return {
        'unggul': unggul,
        'perlu': perlu,
        'teks': ' '.join(parts),
        'konfigurasi': konfigurasi,
    }


def hasil_asesmen(student, subject, semester):
    return AssessmentResult.objects.filter(
        student=student,
        component__assessment__subject=subject,
        component__assessment__semester=semester,
    ).select_related('component__assessment')


def hitung_nilai(student, subject, semester, konfigurasi=None):
    """Hitung nilai rapor dari hasil asesmen generik.

    Komponen kosong tidak dihitung nol. Bobot dinormalisasi hanya dari
    komponen yang terisi, sesuai konfigurasi nilai.
    """
    konfigurasi = konfigurasi or konfigurasi_nilai(subject, semester)
    lm_values, sts_values = [], []
    sas_non_tes, sas_tes = [], []
    for result in hasil_asesmen(student, subject, semester):
        if result.nilai is None:
            continue
        assessment = result.component.assessment
        if assessment.kategori == 'SUMATIF_LM':
            lm_values.append(result.nilai)
        elif assessment.kategori == 'STS':
            sts_values.append(result.nilai)
        elif assessment.kategori == 'SAS':
            if result.component.tipe == 'NON_TES':
                sas_non_tes.append(result.nilai)
            else:
                sas_tes.append(result.nilai)

    rata_lm = _rata(lm_values)
    nilai_sts = _rata(sts_values)
    nilai_non_tes = _rata(sas_non_tes)
    nilai_tes = _rata(sas_tes)
    rata_sas = _rata_terbobot([
        (nilai_non_tes, konfigurasi.bobot_sas_non_tes),
        (nilai_tes, konfigurasi.bobot_sas_tes),
    ])
    nilai = _rata_terbobot([
        (rata_lm, konfigurasi.bobot_lm),
        (nilai_sts, konfigurasi.bobot_sts),
        (rata_sas, konfigurasi.bobot_sas),
    ])
    return {
        'rata_lm': rata_lm,
        'sts': nilai_sts,
        'rata_sas': rata_sas,
        'sas_non_tes': nilai_non_tes,
        'sas_tes': nilai_tes,
        'nilai': bulatkan(nilai, konfigurasi),
        'konfigurasi': konfigurasi,
    }


def nilai_lm_map(students, subject, semester):
    qs = AssessmentResult.objects.filter(
        student__in=students,
        component__assessment__subject=subject,
        component__assessment__semester=semester,
        component__assessment__kategori='SUMATIF_LM',
    ).values_list('student_id', 'component__assessment__nomor', 'nilai')
    hasil = {}
    for student_id, nomor, nilai in qs:
        if nomor:
            hasil.setdefault(student_id, {})[nomor] = nilai
    return hasil


def ringkasan_sumatif(students, subject, semester):
    """Data siap tampil untuk halaman input sumatif (gaya spreadsheet)."""
    students = list(students)
    lm_map = nilai_lm_map(students, subject, semester)
    konfigurasi = konfigurasi_nilai(subject, semester)
    rows = []
    for siswa in students:
        lm = lm_map.get(siswa.id, {})
        nilai_lm = [lm.get(i) for i in range(1, MAX_LM + 1)]
        hitung = hitung_nilai(siswa, subject, semester, konfigurasi)
        rows.append({
            'siswa': siswa,
            'lm': nilai_lm,
            'rata_lm': hitung['rata_lm'],
            'sts': hitung['sts'],
            'sas_non_tes': hitung['sas_non_tes'],
            'sas_tes': hitung['sas_tes'],
            'rata_sas': hitung['rata_sas'],
            'nilai_rapor': hitung['nilai'],
            'konfigurasi': konfigurasi,
        })
    return rows


def nilai_akhir_siswa(student, semester):
    """Nilai akhir per mata pelajaran untuk satu siswa."""
    hasil = {}
    for subject in daftar_mapel(semester.academic_year):
        hitung = hitung_nilai(student, subject, semester)
        if all(
            hitung[key] is None
            for key in ('nilai', 'sts', 'rata_lm', 'rata_sas')
        ):
            continue
        hasil[subject.id] = {
            'nilai': hitung['nilai'],
            'sts': hitung['sts'],
            'rata_lm': hitung['rata_lm'],
            'rata_sas': hitung['rata_sas'],
        }
    return hasil


def data_leger(class_group, semester, students=None):
    if students is None:
        students = list(daftar_siswa(class_group))
    else:
        students = list(students)
    subjects = list(daftar_mapel(semester.academic_year))

    rows = []
    for siswa in students:
        nilai_siswa = nilai_akhir_siswa(siswa, semester)
        row = []
        total = Decimal('0')
        jumlah = 0
        for mapel in subjects:
            info = nilai_siswa.get(mapel.id, {})
            n = info.get('nilai')
            row.append(n)
            if n is not None:
                total += Decimal(n)
                jumlah += 1
        rata = total / jumlah if jumlah else None
        rows.append({'siswa': siswa, 'nilai': row, 'rata': rata})
    return {'subjects': subjects, 'rows': rows}


def data_rapor(student, semester):
    subjects = list(daftar_mapel(semester.academic_year))
    nilai = nilai_akhir_siswa(student, semester)
    mapel_rows = []
    for mapel in subjects:
        info = nilai.get(mapel.id, {})
        capaian = deskripsi_capaian(student, mapel, semester)
        mapel_rows.append({
            'subject': mapel,
            'nilai': info.get('nilai'),
            'capaian': capaian['teks'],
        })

    ekskul = list(
        Extracurricular.objects.filter(student=student, semester=semester).order_by('urutan')
    )
    ekskul_rows = (ekskul + [None] * 5)[:5]
    catatan = HomeroomNote.objects.filter(student=student, semester=semester).first()
    return {
        'student': student,
        'semester': semester,
        'mapel_rows': mapel_rows,
        'ekskul': ekskul,
        'ekskul_rows': ekskul_rows,
        'catatan': catatan,
        'school': School.get_solo(),
    }
