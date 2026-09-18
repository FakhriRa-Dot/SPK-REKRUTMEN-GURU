# cek_korelasi_ki_prediksi.py

import numpy as np
from rekrutmen_guru.models import Kandidat, HasilSeleksi
from rekrutmen_guru.utils.xgboost_model import prediksi_semua

# 1. Jalankan prediksi untuk semua kandidat yang lolos 4 tahap
hasil = prediksi_semua()

if not hasil:
    print("Tidak ada hasil prediksi. Pastikan model sudah ditraining dan ada kandidat lolos 4 tahap.")
else:
    # 2. Hitung rata-rata Ki dari kandidat yang berhasil diprediksi
    daftar_ki = [h['nilai_utilitas'] for h in hasil if h['nilai_utilitas'] is not None]
    rata_rata_ki = np.mean(daftar_ki)
    print(f"\nJumlah kandidat diprediksi : {len(hasil)}")
    print(f"Rata-rata Ki (utilitas)    : {rata_rata_ki:.4f}\n")

    # 3. Pisahkan kandidat di atas vs di bawah rata-rata
    di_bawah = [h for h in hasil if h['nilai_utilitas'] is not None and h['nilai_utilitas'] < rata_rata_ki]
    di_atas  = [h for h in hasil if h['nilai_utilitas'] is not None and h['nilai_utilitas'] >= rata_rata_ki]

    print(f"Kandidat di bawah rata-rata Ki : {len(di_bawah)}")
    print(f"Kandidat di atas rata-rata Ki  : {len(di_atas)}\n")

    # 4. Cek: apakah SEMUA kandidat di bawah rata-rata diprediksi Tidak Layak?
    bawah_tapi_layak = [h for h in di_bawah if h['prediksi'] == 'Layak']
    atas_tapi_tidak_layak = [h for h in di_atas if h['prediksi'] == 'Tidak Layak']

    print("=== HASIL PENGECEKAN ===")
    print(f"Di bawah rata-rata TAPI diprediksi LAYAK      : {len(bawah_tapi_layak)}")
    for h in bawah_tapi_layak:
        print(f"   - {h['nama']} | Ki={h['nilai_utilitas']:.4f} | prob={h['probabilitas']}%")

    print(f"\nDi atas rata-rata TAPI diprediksi TIDAK LAYAK : {len(atas_tapi_tidak_layak)}")
    for h in atas_tapi_tidak_layak:
        print(f"   - {h['nama']} | Ki={h['nilai_utilitas']:.4f} | prob={h['probabilitas']}%")

    print("\n=== KESIMPULAN ===")
    if len(bawah_tapi_layak) == 0 and len(atas_tapi_tidak_layak) == 0:
        print("Prediksi XGBoost 100% konsisten dengan posisi Ki terhadap rata-rata.")
        print("-> Argumen pembimbing valid secara empiris di dataset ini.")
    else:
        print("Prediksi XGBoost TIDAK selalu sejalan dengan posisi Ki terhadap rata-rata.")
        print("-> Ki saja tidak cukup menentukan kelayakan; XGBoost menangkap pola dari kombinasi fitur lain.")