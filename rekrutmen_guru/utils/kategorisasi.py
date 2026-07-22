def kategorisasi_psikotes(nilai):
    if nilai is None:
        return '-'
    nilai = float(nilai)
    if nilai <= 40:
        return 'Tidak Disarankan'
    elif nilai <= 60:
        return 'Dipertimbangkan'
    else:
        return 'Disarankan'

def kategorisasi_komitmen(nilai):
    if nilai is None:
        return '-'
    nilai = float(nilai)
    if nilai <= 50:
        return 'Tidak Disarankan'
    elif nilai <= 75:
        return 'Dipertimbangkan'
    else:
        return 'Disarankan'

def kategorisasi_ruhiyah(nilai):
    if nilai is None:
        return '-'
    nilai = float(nilai)
    if nilai <= 45:
        return 'Tidak Lulus'
    else:
        return 'Lulus'