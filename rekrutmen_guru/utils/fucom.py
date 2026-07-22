import numpy as np
from scipy.optimize import minimize

def geometric_mean_rasio(list_rasio):
    """
    Menggabungkan rasio dari beberapa responden menggunakan geometric mean.
    Contoh: [5.0, 5.0] → hasilnya 5.0
            [2.0, 4.0] → hasilnya 2.83
    """
    arr = np.array(list_rasio, dtype=float)
    return np.exp(np.mean(np.log(arr)))


def hitung_fucom(urutan_kriteria, rasio_perbandingan):
    """
    Menghitung bobot kriteria menggunakan metode FUCOM.

    Parameter:
    - urutan_kriteria : list nama kriteria sudah diurutkan dari paling penting
                        contoh: ['Komitmen', 'Pengalaman', 'Psikotes', ...]
    - rasio_perbandingan : list rasio antar kriteria berurutan (panjang = n-1)
                        contoh: [5.0, 1.5, 2.0, 2.0, 1.5, 1.0]

    Return:
    - dict {nama_kriteria: bobot}
    """
    n = len(urutan_kriteria)

    # Fungsi objektif: minimasi deviasi dari kondisi full consistency
    def objective(w):
        deviasi = 0
        for j in range(n - 1):
            phi = rasio_perbandingan[j]  # rasio kriteria j terhadap j+1
            # Kondisi 1: w[j] / w[j+1] = phi
            deviasi += (w[j] / w[j+1] - phi) ** 2
            # Kondisi 2: w[j] / w[j+2] = phi[j] * phi[j+1] (transitivity)
            if j < n - 2:
                deviasi += (w[j] / w[j+2] - phi * rasio_perbandingan[j+1]) ** 2
        return deviasi

    # Constraint: total bobot = 1
    constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}

    # Batas: setiap bobot antara 0 dan 1
    bounds = [(0.001, 1.0)] * n

    # Nilai awal bobot (dibagi rata dulu)
    w0 = np.array([1.0 / n] * n)

    # Jalankan optimasi
    hasil = minimize(
        objective,
        w0,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )

    # Susun hasil ke dict {nama_kriteria: bobot}
    bobot = {}
    for i, nama in enumerate(urutan_kriteria):
        bobot[nama] = round(hasil.x[i], 6)

    return bobot