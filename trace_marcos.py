import numpy as np
from rekrutmen_guru.models import Kandidat, NilaiKriteria, Kriteria, HasilSeleksi

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

NAMA_TARGET = 'Selvian, S.Pd'
PERIODE_NAMA = 'Agustus 2026'

# Ambil bobot dari database
kriteria_qs = Kriteria.objects.filter(nama__in=KRITERIA_LIST)
bobot = {k.nama: k.bobot for k in kriteria_qs}

print("=" * 70)
print("BOBOT KRITERIA (FUCOM) YANG DIPAKAI")
print("=" * 70)
for k in KRITERIA_LIST:
    print(f"  {k}: {bobot[k]}")

# Ambil kandidat yang selesai semua tahap — TANPA filter periode,
# karena hitung_marcos() versi produksi (dipanggil dari
# hitung_marcos_kandidat() setiap kali kandidat baru selesai Micro
# Teaching) memanggil hitung_marcos() TANPA argumen periode_id,
# sehingga AI/AAI dihitung dari SELURUH kandidat yang pernah selesai
# 4 tahap di database, bukan cuma satu periode.
kandidat_qs = Kandidat.objects.filter(
    status_tahap_1='hadir',
    status_tahap_2='hadir',
    status_tahap_3='hadir',
    status_tahap_4='hadir',
)

kandidat_list = []
matriks = []

for kandidat in kandidat_qs:
    nilai_dict = {
        nk.kriteria.nama: nk.nilai
        for nk in NilaiKriteria.objects.filter(kandidat=kandidat).select_related('kriteria')
    }
    if all(k in nilai_dict for k in KRITERIA_LIST):
        kandidat_list.append(kandidat)
        matriks.append([nilai_dict[k] for k in KRITERIA_LIST])

matriks = np.array(matriks, dtype=float)
bobot_arr = np.array([bobot[k] for k in KRITERIA_LIST])

print(f"\nJumlah kandidat dalam matriks keputusan: {len(kandidat_list)}")

# Solusi ideal & anti-ideal
ai = np.max(matriks, axis=0)
aai = np.min(matriks, axis=0)

print("\n" + "=" * 70)
print("SOLUSI IDEAL (AI) & ANTI-IDEAL (AAI) PER KRITERIA")
print("=" * 70)
for i, k in enumerate(KRITERIA_LIST):
    print(f"  {k}: AAI={aai[i]}, AI={ai[i]}")

# Index
nama_list = [k.nama for k in kandidat_list]
cocok = [n for n in nama_list if 'Selvian' in n]
print("\nKandidat dengan nama mengandung 'Selvian':", cocok)

if NAMA_TARGET not in nama_list:
    print(f"\nNAMA_TARGET '{NAMA_TARGET}' tidak ditemukan persis. Cek daftar di atas, lalu sesuaikan NAMA_TARGET.")
    raise SystemExit

idx = nama_list.index(NAMA_TARGET)
nilai = matriks[idx]

print(f"\n" + "=" * 70)
print(f"NILAI KRITERIA {NAMA_TARGET}")
print("=" * 70)
for i, k in enumerate(KRITERIA_LIST):
    print(f"  {k}: {nilai[i]}")

# Extended matrix + normalisasi (persis logika hitung_marcos asli)
matriks_extended = np.vstack([aai, matriks, ai])
norm = matriks_extended / ai
weighted = norm * bobot_arr

print("\n" + "=" * 70)
print(f"NORMALISASI & WEIGHTED NORMALIZED MATRIX UNTUK {NAMA_TARGET}")
print("=" * 70)
norm_dewi = norm[idx + 1]  # +1 karena baris ke-0 adalah AAI
weighted_dewi = weighted[idx + 1]
for i, k in enumerate(KRITERIA_LIST):
    print(f"  {k}: nilai={nilai[i]}, norm={norm_dewi[i]:.6f} (={nilai[i]}/{ai[i]}), "
          f"weighted={weighted_dewi[i]:.6f} (=norm x bobot {bobot_arr[i]})")

# Si
Si = np.sum(weighted, axis=1)
Si_aai = Si[0]
Si_ai = Si[-1]
Si_kandidat = Si[1:-1]
Si_dewi = Si_kandidat[idx]

print("\n" + "=" * 70)
print("NILAI Si (JUMLAH WEIGHTED NORMALIZED)")
print("=" * 70)
print(f"  Si(AAI) = {Si_aai:.6f}")
print(f"  Si(AI)  = {Si_ai:.6f}")
print(f"  Si({NAMA_TARGET}) = {Si_dewi:.6f}")

# Ki-, Ki+
Ki_minus = Si_dewi / Si_aai
Ki_plus = Si_dewi / Si_ai

print("\n" + "=" * 70)
print("Ki- DAN Ki+")
print("=" * 70)
print(f"  Ki- = Si / Si(AAI) = {Si_dewi:.6f} / {Si_aai:.6f} = {Ki_minus:.6f}")
print(f"  Ki+ = Si / Si(AI)  = {Si_dewi:.6f} / {Si_ai:.6f} = {Ki_plus:.6f}")

# f(Ki+), f(Ki-)
f_Ki_plus = Ki_plus / (Ki_plus + Ki_minus)
f_Ki_minus = Ki_minus / (Ki_plus + Ki_minus)

print("\n" + "=" * 70)
print("f(Ki+) DAN f(Ki-)")
print("=" * 70)
print(f"  f(Ki+) = Ki+ / (Ki+ + Ki-) = {Ki_plus:.6f} / ({Ki_plus:.6f} + {Ki_minus:.6f}) = {f_Ki_plus:.6f}")
print(f"  f(Ki-) = Ki- / (Ki+ + Ki-) = {Ki_minus:.6f} / ({Ki_plus:.6f} + {Ki_minus:.6f}) = {f_Ki_minus:.6f}")

# Utilitas akhir
utilitas_dewi = (Ki_plus + Ki_minus) / (
    1 +
    (1 - f_Ki_plus) / f_Ki_plus +
    (1 - f_Ki_minus) / f_Ki_minus
)

print("\n" + "=" * 70)
print("NILAI UTILITAS AKHIR (Ki)")
print("=" * 70)
print(f"  f(Ki) = (Ki+ + Ki-) / (1 + (1-f(Ki+))/f(Ki+) + (1-f(Ki-))/f(Ki-))")
print(f"        = ({Ki_plus:.6f} + {Ki_minus:.6f}) / (1 + {(1-f_Ki_plus)/f_Ki_plus:.6f} + {(1-f_Ki_minus)/f_Ki_minus:.6f})")
print(f"        = {utilitas_dewi:.6f}")

hasil_db = HasilSeleksi.objects.get(kandidat=kandidat_list[idx])
print(f"\nNilai utilitas tersimpan di database: {hasil_db.nilai_utilitas}")
print(f"Cocok? {'YA' if abs(utilitas_dewi - hasil_db.nilai_utilitas) < 0.0001 else 'TIDAK'}")