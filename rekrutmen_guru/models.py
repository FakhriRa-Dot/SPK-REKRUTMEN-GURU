from django.db import models

class BidangStudi(models.Model):
    nama = models.CharField(max_length=100)

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name_plural = "Bidang Studi"


class PeriodeRekrutmen(models.Model):
    # Contoh isi: "Januari 2025", "Maret 2026"
    nama = models.CharField(max_length=50)

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name_plural = "Periode Rekrutmen"


class Kriteria(models.Model):
    nama = models.CharField(max_length=100)
    bobot = models.FloatField(null=True, blank=True)
    jenis = models.CharField(max_length=10, choices=[('benefit', 'Benefit'), ('cost', 'Cost')])

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name_plural = "Kriteria"

class Kandidat(models.Model):
    JENJANG_CHOICES = [
        ('D3', 'D3'),
        ('D4', 'D4'),
        ('S1', 'S1'),
        ('S2', 'S2'),
        ('S3', 'S3'),
    ]

    STATUS_CHOICES = [
        ('menunggu', 'Menunggu'),
        ('dipanggil', 'Dipanggil'),
        ('hadir', 'Hadir'),
        ('gugur', 'Gugur'),
    ]

    # Data pribadi
    foto                = models.ImageField(upload_to='foto_kandidat/', null=True, blank=True)
    nama                = models.CharField(max_length=100)
    bidang_studi        = models.ForeignKey(BidangStudi, on_delete=models.SET_NULL, null=True)
    jenjang_pendidikan  = models.CharField(max_length=5, choices=JENJANG_CHOICES, null=True, blank=True)
    ipk                 = models.FloatField(null=True, blank=True)
    pengalaman_mengajar = models.IntegerField(default=0)
    periode             = models.ForeignKey(PeriodeRekrutmen, on_delete=models.SET_NULL, null=True, blank=True)

    # Status per tahap rekrutmen
    # Setiap tahap diisi panitia: menunggu → dipanggil → hadir/gugur
    status_tahap_1 = models.CharField(
        max_length=10, choices=STATUS_CHOICES,
        default='hadir',  # Tahap 1 = input data, kalau sudah diinput berarti hadir
        verbose_name='Status Kualifikasi Akademik'
    )
    status_tahap_2 = models.CharField(
        max_length=10, choices=STATUS_CHOICES,
        default='menunggu',
        verbose_name='Status Psikotes & IQ'
    )
    status_tahap_3 = models.CharField(
        max_length=10, choices=STATUS_CHOICES,
        default='menunggu',
        verbose_name='Status Wawancara & Ruhiyah'
    )
    status_tahap_4 = models.CharField(
        max_length=10, choices=STATUS_CHOICES,
        default='menunggu',
        verbose_name='Status Micro Teaching'
    )

    # Catatan per tahap
    note_wawancara = models.TextField(null=True, blank=True)
    note_micro_teaching = models.TextField(null=True, blank=True)

    # Label historis untuk training XGBoost
    label = models.CharField(
        max_length=20,
        choices=[('diterima', 'Diterima'), ('tidak_diterima', 'Tidak Diterima')],
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    keputusan_akhir = models.CharField(
        max_length=20,
        choices=[
            ('diterima', 'Diterima'),
            ('tidak_diterima', 'Tidak Diterima'),
        ],
        null=True, blank=True,
        verbose_name='Keputusan Akhir Yayasan'
    )
    keputusan_tanggal = models.DateTimeField(null=True, blank=True)

    def semua_tahap_selesai(self):
        """
        Cek apakah kandidat sudah menyelesaikan semua tahap.
        Hanya kandidat yang semua tahapnya 'hadir' yang bisa dihitung MARCOS + XGBoost.
        """
        return all([
            self.status_tahap_1 == 'hadir',
            self.status_tahap_2 == 'hadir',
            self.status_tahap_3 == 'hadir',
            self.status_tahap_4 == 'hadir',
        ])

    def __str__(self):
        return self.nama

class NilaiKriteria(models.Model):
    kandidat = models.ForeignKey(Kandidat, on_delete=models.CASCADE, related_name='nilai')
    kriteria = models.ForeignKey(Kriteria, on_delete=models.CASCADE)
    nilai = models.FloatField()

    def __str__(self):
        return f"{self.kandidat.nama} - {self.kriteria.nama}: {self.nilai}"

    class Meta:
        verbose_name_plural = "Nilai Kriteria"
        unique_together = ('kandidat', 'kriteria')


class HasilSeleksi(models.Model):
    kandidat = models.OneToOneField(Kandidat, on_delete=models.CASCADE)
    nilai_utilitas = models.FloatField(null=True, blank=True)
    ranking = models.IntegerField(null=True, blank=True)
    prediksi = models.CharField(max_length=20, null=True, blank=True)
    probabilitas = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Hasil - {self.kandidat.nama}"

    class Meta:
        verbose_name_plural = "Hasil Seleksi"