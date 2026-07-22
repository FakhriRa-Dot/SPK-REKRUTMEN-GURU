import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import os
import pickle

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
    }


def prediksi_semua():
    """
    Prediksi kelayakan semua kandidat yang sudah selesai semua tahap.
    Update hasil ke tabel HasilSeleksi.
    """
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_1='hadir',
        status_tahap_2='hadir',
        status_tahap_3='hadir',
        status_tahap_4='hadir',
    )

    hasil_list = []
    for kandidat in kandidat_qs:
        try:
            hasil_prediksi = prediksi_kandidat(kandidat)

            # Simpan ke HasilSeleksi
            obj, _ = HasilSeleksi.objects.get_or_create(kandidat=kandidat)
            obj.prediksi = hasil_prediksi['prediksi']
            obj.probabilitas = hasil_prediksi['probabilitas']
            obj.save()

            hasil_list.append({
                'nama': kandidat.nama,
                'prediksi': hasil_prediksi['prediksi'],
                'probabilitas': hasil_prediksi['probabilitas'],
                'nilai_utilitas': obj.nilai_utilitas,
                'ranking': obj.ranking,
            })
        except Exception as e:
            print(f"Skip {kandidat.nama}: {e}")
            continue

    return hasil_list

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
    kontribusi = []
    for i, nama in enumerate(KRITERIA_LIST):
        k_obj = kriteria_db.get(nama)
        bobot = k_obj.bobot if k_obj else 0
        nilai = nilai_dict.get(nama, 0)
        kontrib = round(float(nilai) * float(bobot), 2)
        kontribusi.append({
            'kode': f'C{i+1}',
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