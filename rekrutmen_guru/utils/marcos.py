import numpy as np
from ..models import Kandidat, NilaiKriteria, Kriteria, HasilSeleksi

KRITERIA_LIST = [
    'Kualifikasi Akademik',
    'IQ',
    'Tes Psikotes',
    'Nilai Akademik',
    'Pengalaman Mengajar',
    'Micro Teaching',
    'Komitmen (Wawancara)',
    'Ruhiyah (Keagamaan)',
]

def hitung_marcos(periode_id=None):
    """
    Menghitung ranking kandidat menggunakan metode MARCOS.
    Hanya kandidat yang sudah selesai semua tahap (status_tahap_4='hadir').
    """
    # Ambil bobot dari database
    kriteria_qs = Kriteria.objects.filter(nama__in=KRITERIA_LIST)
    bobot = {k.nama: k.bobot for k in kriteria_qs}

    # Hanya kandidat yang sudah selesai semua tahap
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_1='hadir',
        status_tahap_2='hadir',
        status_tahap_3='hadir',
        status_tahap_4='hadir',
    )
    if periode_id:
        kandidat_qs = kandidat_qs.filter(periode_id=periode_id)

    # Bangun matriks keputusan
    kandidat_list = []
    matriks = []

    for kandidat in kandidat_qs:
        nilai_dict = {
            nk.kriteria.nama: nk.nilai
            for nk in NilaiKriteria.objects.filter(
                kandidat=kandidat
            ).select_related('kriteria')
        }
        if all(k in nilai_dict for k in KRITERIA_LIST):
            kandidat_list.append(kandidat)
            matriks.append([nilai_dict[k] for k in KRITERIA_LIST])

    if not kandidat_list:
        return []

    matriks = np.array(matriks, dtype=float)
    bobot_arr = np.array([bobot[k] for k in KRITERIA_LIST])

    # Solusi ideal dan anti-ideal
    ai  = np.max(matriks, axis=0)
    aai = np.min(matriks, axis=0)

    matriks_extended = np.vstack([aai, matriks, ai])

    # Normalisasi
    norm = matriks_extended / ai

    # Weighted normalized matrix
    weighted = norm * bobot_arr

    # Hitung Si
    Si = np.sum(weighted, axis=1)
    Si_aai = Si[0]
    Si_ai  = Si[-1]
    Si_kandidat = Si[1:-1]

    # Nilai utilitas
    Ki_minus = Si_kandidat / Si_aai
    Ki_plus  = Si_kandidat / Si_ai

    f_Ki_plus  = Ki_plus  / (Ki_plus  + Ki_minus)
    f_Ki_minus = Ki_minus / (Ki_plus  + Ki_minus)

    utilitas = (Ki_plus + Ki_minus) / (
        1 +
        (1 - f_Ki_plus)  / f_Ki_plus +
        (1 - f_Ki_minus) / f_Ki_minus
    )

    # Ranking
    ranking_idx = np.argsort(utilitas)[::-1]

    # Update atau buat hasil — TIDAK hapus prediksi yang sudah ada
    hasil = []
    for rank, idx in enumerate(ranking_idx, start=1):
        kandidat = kandidat_list[idx]
        obj, _ = HasilSeleksi.objects.get_or_create(kandidat=kandidat)
        obj.nilai_utilitas = round(float(utilitas[idx]), 6)
        obj.ranking = rank
        obj.save()
        hasil.append({
            'ranking': rank,
            'nama': kandidat.nama,
            'nilai_utilitas': round(float(utilitas[idx]), 6),
        })

    return hasil


def hitung_marcos_kandidat(kandidat_baru):
    """
    Dipanggil saat kandidat baru selesai tahap 4.
    Hitung ulang semua karena AI/AAI bisa berubah.
    """
    return hitung_marcos()