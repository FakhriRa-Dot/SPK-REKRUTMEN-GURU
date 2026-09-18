from ..models import Kriteria

def get_kode_kriteria():
    """
    Sumber tunggal pemetaan kriteria → kode C1-C8.
    C1 = bobot tertinggi, C8 = bobot terendah.
    Dipakai di semua halaman yang menampilkan kode C1-C8
    (Evaluasi MARCOS, Detail Prediksi, Hasil, dsb) supaya konsisten.
    """
    kriteria_qs = Kriteria.objects.order_by('-bobot')
    return {k.nama: f'C{i+1}' for i, k in enumerate(kriteria_qs)}