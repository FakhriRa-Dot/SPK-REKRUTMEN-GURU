from django.contrib import admin
from .models import BidangStudi, PeriodeRekrutmen, Kriteria, Kandidat, NilaiKriteria, HasilSeleksi

admin.site.register(BidangStudi)
admin.site.register(PeriodeRekrutmen)
admin.site.register(Kriteria)
admin.site.register(Kandidat)
admin.site.register(NilaiKriteria)
admin.site.register(HasilSeleksi)