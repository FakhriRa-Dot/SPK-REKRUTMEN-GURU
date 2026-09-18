import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
os.environ["PATH"] += os.pathsep + r"D:\Graphviz-15.1.1-win32\bin"

from xgboost import plot_tree

from rekrutmen_guru.models import Kandidat, NilaiKriteria
from rekrutmen_guru.utils.xgboost_model import muat_model, KRITERIA_LIST, HasilSeleksi
import numpy as np
import pandas as pd

NAMA_KANDIDAT = 'Selvian, S.Pd'
JUMLAH_TREE_DITAMPILKAN = 5

model = muat_model()
booster = model.get_booster()

# Ambil nilai fitur asli Selvian
k = Kandidat.objects.get(nama=NAMA_KANDIDAT)
nilai_dict = {
    nk.kriteria.nama: nk.nilai
    for nk in NilaiKriteria.objects.filter(kandidat=k).select_related('kriteria')
}
hasil = HasilSeleksi.objects.get(kandidat=k)

nama_fitur = KRITERIA_LIST + ['Nilai Utilitas MARCOS (Ki)']
nilai_fitur = [nilai_dict[kr] for kr in KRITERIA_LIST]
nilai_fitur.append(hasil.nilai_utilitas or 0.0)

print("=" * 70)
print(f"NILAI KANDIDAT: {NAMA_KANDIDAT}")
for nama, nilai in zip(nama_fitur, nilai_fitur):
    print(f"  {nama}: {nilai}")

X = np.array([nilai_fitur], dtype=float)

# Ambil struktur SEMUA pohon dalam bentuk tabel (setiap baris = satu node)
tabel_pohon = booster.trees_to_dataframe()

# XGBoost internal menamai fitur sebagai f0, f1, f2, ... sesuai urutan kolom X
peta_fitur = {f'f{i}': nama for i, nama in enumerate(nama_fitur)}


def telusuri_pohon(tree_id, tabel, x_row, peta_fitur):
    """
    Telusuri manual satu pohon: mulai dari node akar (root),
    ikuti percabangan sesuai nilai fitur kandidat, sampai ke leaf.
    Mengembalikan daftar langkah (untuk dicetak) dan skor leaf akhir.
    """
    pohon = tabel[tabel['Tree'] == tree_id].set_index('ID')
    node_id = f"{tree_id}-0"  # root selalu node ke-0
    langkah = []

    while True:
        baris = pohon.loc[node_id]

        # Kalau ini leaf (tidak ada split lagi)
        if baris['Feature'] == 'Leaf':
            skor = baris['Gain']  # untuk baris leaf, kolom Gain berisi nilai leaf/skor
            langkah.append(f"  -> LEAF, skor = {skor:.5f}")
            return langkah, skor

        fitur_asli = peta_fitur.get(baris['Feature'], baris['Feature'])
        idx_fitur = nama_fitur.index(fitur_asli)
        nilai_kandidat = x_row[idx_fitur]
        ambang = baris['Split']

        if nilai_kandidat < ambang:
            arah = 'Yes (< ambang)'
            node_id = baris['Yes']
        else:
            arah = 'No (>= ambang)'
            node_id = baris['No']

        langkah.append(
            f"  {fitur_asli} = {nilai_kandidat} vs ambang {ambang:.4f} -> {arah}"
        )


print()
print("=" * 70)
print(f"{JUMLAH_TREE_DITAMPILKAN} POHON PERTAMA UNTUK {NAMA_KANDIDAT}")

total_skor_ditampilkan = 0.0
for tree_id in range(JUMLAH_TREE_DITAMPILKAN):
    print(f"\n--- Pohon ke-{tree_id + 1} ---")
    langkah, skor = telusuri_pohon(tree_id, tabel_pohon, nilai_fitur, peta_fitur)
    for baris_langkah in langkah:
        print(baris_langkah)
    total_skor_ditampilkan += skor

print()
print("=" * 70)
print("VERIFIKASI TOTAL SEMUA 100 POHON")

log_odds_asli = model.predict(X, output_margin=True)[0]
proba_asli = 1 / (1 + np.exp(-log_odds_asli))

print(f"Jumlah skor dari {JUMLAH_TREE_DITAMPILKAN} pohon pertama saja: {total_skor_ditampilkan:.5f}")
print(f"Log-odds TOTAL dari semua 100 pohon (base_score sudah termasuk): {log_odds_asli:.5f}")
print(f"Probabilitas Layak (setelah sigmoid): {proba_asli * 100:.2f}%")
print(f"Probabilitas tersimpan di sistem: {hasil.probabilitas_layak}%")
print("=" * 70)

# ── Export gambar 5 pohon pertama ──────────────────────────────────────────
print()
print("=" * 70)
print("EXPORT GAMBAR POHON")
for i in range(JUMLAH_TREE_DITAMPILKAN):
    fig, ax = plt.subplots(figsize=(22, 12))
    plot_tree(model, num_trees=i, ax=ax, rankdir='LR')
    plt.savefig(f'pohon_{i}.png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f'pohon_{i}.png tersimpan (Pohon ke-{i + 1})')
print("=" * 70)