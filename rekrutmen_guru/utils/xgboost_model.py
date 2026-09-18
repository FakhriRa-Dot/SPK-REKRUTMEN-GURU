import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from scipy.stats import spearmanr
from collections import defaultdict
import os
import pickle

from ..models import Kandidat, NilaiKriteria, Kriteria, HasilSeleksi
from .kode_kriteria import get_kode_kriteria 

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

# Path penyimpanan model yang sudah ditraining
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'xgboost_model.pkl')


def ambil_data_training():
    """
    Ambil data kandidat historis dari database untuk training XGBoost.
    Hanya kandidat yang:
    - Semua tahap = hadir
    - Punya label (diterima/tidak_diterima)
    - Punya nilai semua kriteria
    """
    kriteria_db = {k.nama: k for k in Kriteria.objects.filter(nama__in=KRITERIA_LIST)}

    kandidat_qs = Kandidat.objects.filter(
        label__isnull=False,
        status_tahap_1='hadir',
        status_tahap_2='hadir',
        status_tahap_3='hadir',
        status_tahap_4='hadir',
    )

    X, y = [], []

    for kandidat in kandidat_qs:
        nilai_dict = {
            nk.kriteria.nama: nk.nilai
            for nk in NilaiKriteria.objects.filter(
                kandidat=kandidat
            ).select_related('kriteria')
        }

        # Ambil nilai utilitas MARCOS kalau ada
        try:
            hasil = HasilSeleksi.objects.get(kandidat=kandidat)
            nilai_utilitas = hasil.nilai_utilitas or 0.0
        except HasilSeleksi.DoesNotExist:
            nilai_utilitas = 0.0

        # Cek semua kriteria tersedia
        if not all(k in nilai_dict for k in KRITERIA_LIST):
            continue

        # Fitur = nilai 8 kriteria + nilai utilitas MARCOS
        fitur = [nilai_dict[k] for k in KRITERIA_LIST]
        fitur.append(nilai_utilitas)

        X.append(fitur)
        y.append(1 if kandidat.label == 'diterima' else 0)

    return np.array(X, dtype=float), np.array(y, dtype=int)

def training_model():
    """
    Training model XGBoost dari data historis.
    Menyimpan model ke file pkl.
    Return: laporan akurasi
    """
    X, y = ambil_data_training()

    if len(X) == 0:
        raise ValueError("Tidak ada data training yang tersedia.")

    if len(X) < 10:
        raise ValueError(f"Data training terlalu sedikit ({len(X)} baris). Minimal 10 data.")

    # Split data: 80% training, 20% testing
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Hitung skala untuk data tidak seimbang
    # scale_pos_weight = jumlah negatif / jumlah positif
    n_positif = np.sum(y_train == 1)
    n_negatif = np.sum(y_train == 0)
    scale = n_negatif / n_positif if n_positif > 0 else 1

    # Inisialisasi & training model
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=scale,
        random_state=42,
        eval_metric='logloss',
    )
    model.fit(X_train, y_train)
    train_accuracy = model.score(X_train, y_train)
    test_accuracy = model.score(X_test, y_test)
    selisih = abs(train_accuracy - test_accuracy)

    # Evaluasi
    y_pred = model.predict(X_test)
    akurasi = accuracy_score(y_test, y_pred)
    laporan = classification_report(y_test, y_pred, target_names=['Tidak Layak', 'Layak'])

    # Simpan model ke file
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)

    return {
        'akurasi': round(akurasi * 100, 2),
        'laporan': laporan,
        'jumlah_training': len(X_train),
        'jumlah_testing': len(X_test),
        'jumlah_total': len(X),
        'train_accuracy': round(train_accuracy * 100, 2),
        'test_accuracy': round(test_accuracy * 100, 2),
        'selisih_accuracy': round(selisih * 100, 2),
    }


def muat_model():
    """
    Muat model XGBoost dari file pkl.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model belum ditraining. Jalankan training dulu.")

    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)


def prediksi_kandidat(kandidat):
    """
    Prediksi kelayakan satu kandidat menggunakan model XGBoost.
    Kandidat harus sudah punya nilai semua kriteria & nilai utilitas MARCOS.
    Return: {'prediksi': 'Layak'/'Tidak Layak', 'probabilitas': float}
    """
    model = muat_model()

    kriteria_db = {k.nama: k for k in Kriteria.objects.filter(nama__in=KRITERIA_LIST)}

    nilai_dict = {
        nk.kriteria.nama: nk.nilai
        for nk in NilaiKriteria.objects.filter(
            kandidat=kandidat
        ).select_related('kriteria')
    }

    if not all(k in nilai_dict for k in KRITERIA_LIST):
        raise ValueError("Nilai kriteria kandidat belum lengkap.")

    # Ambil nilai utilitas MARCOS
    try:
        hasil = HasilSeleksi.objects.get(kandidat=kandidat)
        nilai_utilitas = hasil.nilai_utilitas or 0.0
    except HasilSeleksi.DoesNotExist:
        nilai_utilitas = 0.0

    fitur = [nilai_dict[k] for k in KRITERIA_LIST]
    fitur.append(nilai_utilitas)

    X = np.array([fitur], dtype=float)
    pred = model.predict(X)[0]
    proba = model.predict_proba(X)[0]

    return {
        'prediksi': 'Layak' if pred == 1 else 'Tidak Layak',
        'probabilitas': round(float(proba[pred]) * 100, 2),
        # Probabilitas kelas "Layak" secara khusus (bukan probabilitas kelas
        # yang diprediksi) — dipakai sebagai dasar ranking XGBoost, terlepas
        # dari label prediksi biner-nya.
        'probabilitas_layak': round(float(proba[1]) * 100, 2),
    }


def prediksi_semua():
    """
    Prediksi kelayakan semua kandidat yang sudah selesai semua tahap.
    Update hasil ke tabel HasilSeleksi, termasuk ranking_xgboost yang
    dihitung per periode berdasarkan probabilitas kelas Layak (descending),
    setara dengan cara ranking MARCOS dihitung per periode berdasarkan Ki.
    """
    kandidat_qs = Kandidat.objects.select_related('periode').filter(
        status_tahap_1='hadir',
        status_tahap_2='hadir',
        status_tahap_3='hadir',
        status_tahap_4='hadir',
    )

    # Kumpulkan dulu semua hasil prediksi per kandidat, dikelompokkan
    # per periode (PeriodeRekrutmen), supaya ranking bisa dihitung per
    # kelompok. Key grouping pakai periode_id (aman untuk kandidat tanpa
    # periode / periode null, dikelompokkan jadi satu grup id=None).
    prediksi_per_periode = defaultdict(list)

    for kandidat in kandidat_qs:
        # Data historis tidak diikutkan dalam ranking XGBoost, sama seperti
        # perlakuannya di halaman Hasil Akhir dan Prediksi.
        if kandidat.periode and kandidat.periode.nama == 'Data Historis':
            continue

        try:
            hasil_prediksi = prediksi_kandidat(kandidat)
            prediksi_per_periode[kandidat.periode_id].append({
                'kandidat': kandidat,
                'hasil_prediksi': hasil_prediksi,
            })
        except Exception as e:
            print(f"Skip {kandidat.nama}: {e}")
            continue

    hasil_list = []

    for periode_id, daftar in prediksi_per_periode.items():
        # Urutkan descending berdasarkan probabilitas kelas Layak
        daftar_terurut = sorted(
            daftar,
            key=lambda d: d['hasil_prediksi']['probabilitas_layak'],
            reverse=True,
        )

        for rank, item in enumerate(daftar_terurut, start=1):
            kandidat = item['kandidat']
            hasil_prediksi = item['hasil_prediksi']

            # Simpan ke HasilSeleksi
            obj, _ = HasilSeleksi.objects.get_or_create(kandidat=kandidat)
            obj.prediksi = hasil_prediksi['prediksi']
            obj.probabilitas = hasil_prediksi['probabilitas']
            obj.probabilitas_layak = hasil_prediksi['probabilitas_layak']
            obj.ranking_xgboost = rank
            obj.save()

            hasil_list.append({
                'nama': kandidat.nama,
                'periode': kandidat.periode.nama if kandidat.periode else None,
                'prediksi': hasil_prediksi['prediksi'],
                'probabilitas': hasil_prediksi['probabilitas'],
                'probabilitas_layak': hasil_prediksi['probabilitas_layak'],
                'nilai_utilitas': obj.nilai_utilitas,
                'ranking': obj.ranking,
                'ranking_xgboost': rank,
            })

    return hasil_list


def hitung_konsistensi_ranking(periode=None):
    """
    Hitung konsistensi antara ranking MARCOS (berdasarkan nilai_utilitas/Ki)
    dan ranking XGBoost (berdasarkan probabilitas kelas Layak) menggunakan
    Spearman's Rank Correlation Coefficient.

    `periode` boleh diisi instance PeriodeRekrutmen atau id-nya, untuk
    membatasi hanya satu periode. Kalau None, menghitung per periode
    secara terpisah lalu mengembalikan hasil untuk masing-masing periode
    (ranking TIDAK pernah digabung lintas periode, sama seperti perlakuan
    ranking MARCOS).

    Return: list of dict, masing-masing berisi nama periode, koefisien rho,
    p-value, jumlah kandidat yang dibandingkan, dan tabel detail per
    kandidat (untuk ditampilkan sebagai tabel di Bab IV).
    """
    qs = HasilSeleksi.objects.select_related('kandidat', 'kandidat__periode').filter(
        ranking__isnull=False,
        ranking_xgboost__isnull=False,
    )

    if periode is not None:
        qs = qs.filter(kandidat__periode=periode)
    else:
        qs = qs.exclude(kandidat__periode__nama='Data Historis')

    per_periode = defaultdict(list)
    for hasil in qs:
        per_periode[hasil.kandidat.periode_id].append(hasil)

    output = []
    for periode_id, daftar in per_periode.items():
        if len(daftar) < 2:
            # Spearman butuh minimal 2 pasangan data untuk bermakna
            continue

        nama_periode = daftar[0].kandidat.periode.nama if daftar[0].kandidat.periode else None

        # Ranking MARCOS yang tersimpan di field `ranking` dihitung secara
        # GLOBAL lintas seluruh data kandidat (bukan per periode), sedangkan
        # `ranking_xgboost` dihitung per periode. Untuk keperluan tabel
        # perbandingan & korelasi di sini, dihitung ulang ranking MARCOS
        # versi LOKAL (dense rank 1..n) khusus untuk kandidat dalam periode
        # yang sama, supaya kedua kolom benar-benar apple-to-apple (1..n).
        # Nilai `ranking` global tetap disimpan terpisah sebagai referensi,
        # tidak diubah di database.
        urutan_lokal = sorted(daftar, key=lambda h: h.nilai_utilitas, reverse=True)
        ranking_marcos_lokal = {h.pk: rank for rank, h in enumerate(urutan_lokal, start=1)}

        rank_marcos = [ranking_marcos_lokal[h.pk] for h in daftar]
        rank_xgb = [h.ranking_xgboost for h in daftar]

        rho, p_value = spearmanr(rank_marcos, rank_xgb)

        detail = sorted(
            [
                {
                    'nama': h.kandidat.nama,
                    'nilai_utilitas': h.nilai_utilitas,
                    'ranking_marcos_global': h.ranking,
                    'ranking_marcos': ranking_marcos_lokal[h.pk],
                    'probabilitas_layak': h.probabilitas_layak,
                    'ranking_xgboost': h.ranking_xgboost,
                    'selisih_ranking': abs(ranking_marcos_lokal[h.pk] - h.ranking_xgboost),
                }
                for h in daftar
            ],
            key=lambda d: d['ranking_marcos'],
        )

        output.append({
            'periode': nama_periode,
            'rho': round(float(rho), 4),
            'p_value': round(float(p_value), 4),
            'jumlah_kandidat': len(daftar),
            'detail': detail,
        })

    return output

def detail_prediksi_kandidat(kandidat):
    """
    Menghasilkan detail prediksi untuk satu kandidat:
    - prediksi, probabilitas
    - kontribusi tiap kriteria (nilai × bobot)
    """
    model = muat_model()

    kriteria_db = {k.nama: k for k in Kriteria.objects.filter(nama__in=KRITERIA_LIST)}

    nilai_dict = {
        nk.kriteria.nama: nk.nilai
        for nk in NilaiKriteria.objects.filter(
            kandidat=kandidat
        ).select_related('kriteria')
    }

    if not all(k in nilai_dict for k in KRITERIA_LIST):
        raise ValueError("Nilai kriteria kandidat belum lengkap.")

    try:
        hasil = HasilSeleksi.objects.get(kandidat=kandidat)
        nilai_utilitas = hasil.nilai_utilitas or 0.0
    except HasilSeleksi.DoesNotExist:
        nilai_utilitas = 0.0

    fitur = [nilai_dict[k] for k in KRITERIA_LIST]
    fitur.append(nilai_utilitas)

    X = np.array([fitur], dtype=float)
    pred = model.predict(X)[0]
    proba = model.predict_proba(X)[0]

    prob_layak = round(float(proba[1]) * 100, 1)
    prob_tidak = round(float(proba[0]) * 100, 1)

    # Kontribusi tiap kriteria = nilai × bobot
    kode_map = get_kode_kriteria()

    kontribusi = []
    for nama in KRITERIA_LIST:
        k_obj = kriteria_db.get(nama)
        bobot = k_obj.bobot if k_obj else 0
        nilai = nilai_dict.get(nama, 0)
        kontrib = round(float(nilai) * float(bobot), 2)
        kontribusi.append({
            'kode': kode_map.get(nama, '?'),   # ← sekarang ikut urutan bobot
            'nama': nama,
            'nilai': nilai,
            'bobot': bobot,
            'kontribusi': kontrib,
        })

    # Urutkan kontribusi tertinggi ke terendah
    kontribusi.sort(key=lambda x: x['kontribusi'], reverse=True)

    return {
        'prediksi': 'Layak' if pred == 1 else 'Tidak Layak',
        'prob_layak': prob_layak,
        'prob_tidak': prob_tidak,
        'nilai_utilitas': nilai_utilitas,
        'kontribusi': kontribusi,
    }