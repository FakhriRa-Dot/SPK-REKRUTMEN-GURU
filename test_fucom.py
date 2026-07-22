from rekrutmen_guru.utils.fucom import geometric_mean_rasio, hitung_fucom
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Data dari kuesioner
# Responden 1: Komitmen > Pengalaman > Psikotes > Kualifikasi > Ruhiyah > Nilai Akademik > Micro Teaching
urutan_r1 = ['Komitmen', 'Pengalaman Mengajar', 'Tes Psikotes',
             'Kualifikasi Akademik', 'Ruhiyah', 'Nilai Akademik', 'Micro Teaching']
rasio_r1 = [5.0, 1.0, 1.0, 3.0, 1.0, 1.0]

# Responden 2: Komitmen > Micro Teaching > Psikotes > Nilai Akademik > Pengalaman > Kualifikasi > Ruhiyah
urutan_r2 = ['Komitmen', 'Micro Teaching', 'Tes Psikotes',
             'Nilai Akademik', 'Pengalaman Mengajar', 'Kualifikasi Akademik', 'Ruhiyah']
rasio_r2 = [5.0, 2.0, 3.0, 2.0, 2.0, 1.0]

# Hitung bobot masing-masing responden
bobot_r1 = hitung_fucom(urutan_r1, rasio_r1)
bobot_r2 = hitung_fucom(urutan_r2, rasio_r2)

print("=== Bobot Responden 1 ===")
for k, v in bobot_r1.items():
    print(f"  {k}: {v}")

print("\n=== Bobot Responden 2 ===")
for k, v in bobot_r2.items():
    print(f"  {k}: {v}")

# Gabungkan dengan geometric mean per kriteria
semua_kriteria = ['Kualifikasi Akademik', 'Tes Psikotes', 'Nilai Akademik',
                  'Pengalaman Mengajar', 'Micro Teaching', 'Komitmen', 'Ruhiyah']

print("\n=== Bobot Akhir (Geometric Mean) ===")
total = 0
bobot_akhir = {}
for k in semua_kriteria:
    gm = geometric_mean_rasio([bobot_r1[k], bobot_r2[k]])
    bobot_akhir[k] = gm
    total += gm

# Normalisasi supaya total = 1
print(f"{'Kriteria':<30} {'Bobot':>10}")
print("-" * 42)
for k, v in bobot_akhir.items():
    bobot_norm = v / total
    print(f"{k:<30} {bobot_norm:>10.6f}")
print("-" * 42)
print(f"{'Total':<30} {1.0:>10.6f}")