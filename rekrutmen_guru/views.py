from django.shortcuts import render, redirect
from .models import Kandidat, HasilSeleksi, PeriodeRekrutmen, NilaiKriteria, Kriteria
from .utils.fucom import geometric_mean_rasio, hitung_fucom
from .utils.marcos import hitung_marcos
from .utils.xgboost_model import training_model, prediksi_semua
import openpyxl
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http import JsonResponse

KRITERIA_LIST = [
    'Kualifikasi Akademik',
    'Tes Psikotes',
    'Nilai Akademik',
    'Pengalaman Mengajar',
    'Micro Teaching',
    'Komitmen (Wawancara)',
    'Ruhiyah (Keagamaan)',
    'IQ',
]

def baca_sheet_responden(sheet):
    """
    Membaca sheet responden dari Excel.
    Mengembalikan (urutan_kriteria, rasio_perbandingan).
    """
    data = []
    for row in sheet.iter_rows(min_row=5, max_row=12, min_col=2, max_col=4, values_only=True):
        nama, peringkat, rasio = row
        if nama and peringkat:
            data.append({
                'nama': str(nama).strip(),
                'peringkat': int(peringkat),
                # Kalau rasio None (baris terakhir), default ke 1.0 sementara
                'rasio': float(rasio) if rasio is not None else None
            })

    # Urutkan berdasarkan peringkat
    data.sort(key=lambda x: x['peringkat'])

    urutan = [d['nama'] for d in data]
    # Ambil rasio hanya untuk peringkat 1-6 (bukan yang terakhir)
    rasio = [d['rasio'] for d in data[:-1] if d['rasio'] is not None]

    # Validasi panjang rasio harus = jumlah kriteria - 1
    if len(rasio) != len(urutan) - 1:
        raise ValueError(
            f"Jumlah rasio tidak sesuai. Diharapkan {len(urutan)-1}, didapat {len(rasio)}. "
            f"Pastikan semua baris kecuali peringkat terakhir sudah diisi rasionya."
        )

    return urutan, rasio

def fucom_upload(request):
    if request.method == 'POST':
        if 'file_excel' not in request.FILES:
            kriteria_db = Kriteria.objects.all().order_by('-bobot')
            return render(request, 'sistem/fucom_upload.html', {
                'error': 'File belum dipilih.',
                'kriteria_db': kriteria_db
            })

        file = request.FILES['file_excel']
        if not file.name.endswith('.xlsx'):
            kriteria_db = Kriteria.objects.all().order_by('-bobot')
            return render(request, 'sistem/fucom_upload.html', {
                'error': 'File harus berformat .xlsx',
                'kriteria_db': kriteria_db
            })

        try:
            wb = openpyxl.load_workbook(file)
            sheet_responden = [s for s in wb.sheetnames if s.startswith('Responden_')]

            if len(sheet_responden) < 2:
                kriteria_db = Kriteria.objects.all().order_by('-bobot')
                return render(request, 'sistem/fucom_upload.html', {
                    'error': 'Minimal harus ada 2 sheet responden.',
                    'kriteria_db': kriteria_db
                })

            semua_bobot = []
            for nama_sheet in sheet_responden:
                urutan, rasio = baca_sheet_responden(wb[nama_sheet])
                bobot = hitung_fucom(urutan, rasio)
                semua_bobot.append(bobot)

            bobot_akhir = {}
            total = 0
            for k in KRITERIA_LIST:
                gm = geometric_mean_rasio([b[k] for b in semua_bobot])
                bobot_akhir[k] = gm
                total += gm

            for k in bobot_akhir:
                bobot_akhir[k] = round(bobot_akhir[k] / total, 6)

            for nama, bobot in bobot_akhir.items():
                obj, _ = Kriteria.objects.get_or_create(nama=nama)
                obj.bobot = bobot
                obj.jenis = 'benefit'
                obj.save()

        except ValueError as e:
            kriteria_db = Kriteria.objects.all().order_by('-bobot')
            return render(request, 'sistem/fucom_upload.html', {
                'error': str(e),
                'kriteria_db': kriteria_db
            })
        except Exception as e:
            kriteria_db = Kriteria.objects.all().order_by('-bobot')
            return render(request, 'sistem/fucom_upload.html', {
                'error': f'Gagal memproses file: {str(e)}',
                'kriteria_db': kriteria_db
            })

    kriteria_db = Kriteria.objects.all().order_by('-bobot')
    return render(request, 'sistem/fucom_upload.html', {
        'kriteria_db': kriteria_db
    })

def download_template_fucom(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.http import HttpResponse

    wb = openpyxl.Workbook()
    header_fill = PatternFill("solid", start_color="2d7d8e")
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    kriteria_list = [
        'Kualifikasi Akademik', 'IQ', 'Tes Psikotes', 'Nilai Akademik',
        'Pengalaman Mengajar', 'Micro Teaching', 'Komitmen (Wawancara)',
        'Ruhiyah (Keagamaan)',
    ]

    def buat_sheet(wb, nama_sheet, nama_responden, jabatan):
        ws = wb.create_sheet(nama_sheet)
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 25

        # Header
        ws.merge_cells('A1:D1')
        ws['A1'] = f'INPUT FUCOM — {nama_sheet.upper()}'
        ws['A1'].font = Font(bold=True, color='FFFFFF', size=12)
        ws['A1'].fill = header_fill
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 28

        # Info responden
        ws['A2'] = 'Nama Responden'
        ws['B2'] = nama_responden
        ws['A3'] = 'Jabatan'
        ws['B3'] = jabatan
        ws.merge_cells('B2:D2')
        ws.merge_cells('B3:D3')

        # Header tabel
        headers = ['No', 'Nama Kriteria', 'Peringkat (1=Terpenting)', 'Rasio ke Peringkat Berikutnya']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = Font(bold=True, color='FFFFFF', size=10)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = border
        ws.row_dimensions[4].height = 30

        # Data kriteria
        for i, nama in enumerate(kriteria_list):
            row = i + 5
            fill = PatternFill("solid", start_color="DEEAF1") if i % 2 == 0 else PatternFill("solid", start_color="FFFFFF")
            data = [i+1, nama, '', '']
            for col, val in enumerate(data, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font = Font(size=10)
                cell.fill = fill
                cell.border = border
                cell.alignment = Alignment(horizontal='center' if col != 2 else 'left', vertical='center')

        # Catatan
        ws.merge_cells(f'A{len(kriteria_list)+5}:D{len(kriteria_list)+5}')
        ws[f'A{len(kriteria_list)+5}'] = '⚠ Kolom Rasio pada peringkat terakhir dikosongkan.'
        ws[f'A{len(kriteria_list)+5}'].font = Font(italic=True, color='FF0000', size=9)

    # Hapus sheet default
    del wb['Sheet']

    # Buat 2 sheet responden
    buat_sheet(wb, 'Responden_1', '', '')
    buat_sheet(wb, 'Responden_2', '', '')

    # Return sebagai file download
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Template_FUCOM.xlsx"'
    wb.save(response)
    return response

# ── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'sistem/login.html', {'error': 'Username atau password salah.'})
    return render(request, 'sistem/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# ── Main ──────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def dashboard(request):
    from .models import Kandidat, HasilSeleksi
    total = Kandidat.objects.count()
    layak = HasilSeleksi.objects.filter(prediksi='Layak').count()
    tidak_layak = HasilSeleksi.objects.filter(prediksi='Tidak Layak').count()
    proses = Kandidat.objects.filter(label__isnull=True).count()
    kandidat_terbaru = Kandidat.objects.order_by('-created_at')[:5]
    tahap_count = {
        'psikotes'   : Kandidat.objects.filter(status_tahap_2='hadir').count(),
        'kompetensi' : Kandidat.objects.filter(status_tahap_2='hadir').count(),
        'wawancara'  : Kandidat.objects.filter(status_tahap_3='hadir').count(),
        'micro'      : Kandidat.objects.filter(status_tahap_4='hadir').count(),
    }
    return render(request, 'sistem/dashboard.html', {
        'total': total,
        'layak': layak,
        'tidak_layak': tidak_layak,
        'proses': proses,
        'kandidat_terbaru': kandidat_terbaru,
        'tahap_count': tahap_count,
    })

@login_required(login_url='login')
def pipeline(request):
    from .models import Kandidat
    tahap1 = Kandidat.objects.filter(
        status_tahap_1='hadir',
        status_tahap_2='menunggu'
    )
    tahap2 = Kandidat.objects.filter(
        status_tahap_2='dipanggil'
    )
    tahap3 = Kandidat.objects.filter(
        status_tahap_2='hadir',
        status_tahap_3='menunggu'
    )
    tahap4 = Kandidat.objects.filter(
        status_tahap_3='dipanggil'
    )
    tahap5 = Kandidat.objects.filter(
        status_tahap_4='dipanggil'
    )
    return render(request, 'sistem/pipeline.html', {
        'tahap1': tahap1,
        'tahap2': tahap2,
        'tahap3': tahap3,
        'tahap4': tahap4,
        'tahap5': tahap5,
    })

def tambah_periode(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        nama = data.get('nama', '').strip()
        if not nama:
            return JsonResponse({'error': 'Nama periode tidak boleh kosong'}, status=400)
        from .models import PeriodeRekrutmen
        periode, created = PeriodeRekrutmen.objects.get_or_create(nama=nama)
        return JsonResponse({
            'id': periode.id,
            'nama': periode.nama,
            'created': created
        })
    return JsonResponse({'error': 'Method tidak diizinkan'}, status=405)
    
@login_required(login_url='login')
def input_kandidat(request):
    from .models import BidangStudi, PeriodeRekrutmen
    if request.method == 'POST':
        from .models import Kandidat
        nama = request.POST.get('nama')
        jenjang = request.POST.get('jenjang')
        bidang_nama = request.POST.get('bidang_studi_nama', '').strip()
        ipk = request.POST.get('ipk') or None
        pengalaman = request.POST.get('pengalaman_mengajar') or 0
        periode_id = request.POST.get('periode') or None
        foto = request.FILES.get('foto')

        # Buat bidang studi baru kalau belum ada
        bidang, _ = BidangStudi.objects.get_or_create(nama=bidang_nama)

        kandidat = Kandidat.objects.create(
            nama=nama,
            jenjang_pendidikan=jenjang,
            bidang_studi=bidang,
            ipk=ipk,
            pengalaman_mengajar=pengalaman,
            periode_id=periode_id,
            foto=foto,
            status_tahap_1='hadir',
        )
        return redirect('administrasi')

    bidang_list = BidangStudi.objects.all().order_by('nama')
    periode_list = PeriodeRekrutmen.objects.all().order_by('-id')
    return render(request, 'sistem/input_kandidat.html', {
        'bidang_list': bidang_list,
        'periode_list': periode_list,
    })

# ── Tahap Seleksi ─────────────────────────────────────────────────────────────
@login_required(login_url='login')
def administrasi(request):
    from .models import Kandidat
    from django.core.paginator import Paginator
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_1='hadir',
        status_tahap_2='menunggu'
    ).order_by('-created_at')
    paginator = Paginator(kandidat_qs, 15)
    page_number = request.GET.get('page')
    kandidat_list = paginator.get_page(page_number)
    return render(request, 'sistem/administrasi.html', {'kandidat_list': kandidat_list})

@login_required(login_url='login')
def psikotes(request):
    from .models import Kandidat
    from django.core.paginator import Paginator
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_2='dipanggil'
    ).order_by('-created_at')
    paginator = Paginator(kandidat_qs, 15)
    page_number = request.GET.get('page')
    kandidat_list = paginator.get_page(page_number)
    return render(request, 'sistem/psikotes.html', {'kandidat_list': kandidat_list})

@login_required(login_url='login')
def kompetensi(request):
    from .models import Kandidat
    from django.core.paginator import Paginator
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_2='hadir',
        status_tahap_3='menunggu'
    ).order_by('-created_at')
    paginator = Paginator(kandidat_qs, 15)
    page_number = request.GET.get('page')
    kandidat_list = paginator.get_page(page_number)
    return render(request, 'sistem/kompetensi.html', {'kandidat_list': kandidat_list})

@login_required(login_url='login')
def wawancara(request):
    from .models import Kandidat
    from django.core.paginator import Paginator
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_3='dipanggil'
    ).order_by('-created_at')
    paginator = Paginator(kandidat_qs, 15)
    page_number = request.GET.get('page')
    kandidat_list = paginator.get_page(page_number)
    return render(request, 'sistem/wawancara.html', {'kandidat_list': kandidat_list})

@login_required(login_url='login')
def micro_teaching(request):
    from .models import Kandidat
    from django.core.paginator import Paginator
    kandidat_qs = Kandidat.objects.filter(
        status_tahap_4='dipanggil'
    ).order_by('-created_at')
    paginator = Paginator(kandidat_qs, 15)
    page_number = request.GET.get('page')
    kandidat_list = paginator.get_page(page_number)
    return render(request, 'sistem/micro_teaching.html', {'kandidat_list': kandidat_list})

@login_required(login_url='login')
def update_status(request, kandidat_id):
    """
    Update status kandidat per tahap.
    aksi: lanjut / gugur
    tahap: 1 / 2 / 3 / 4
    """
    from .models import Kandidat
    if request.method == 'POST':
        kandidat = Kandidat.objects.get(id=kandidat_id)
        aksi = request.POST.get('aksi')
        tahap = request.POST.get('tahap')
        next_url = request.POST.get('next_url', 'administrasi')

        if tahap == '1':
            if aksi == 'lanjut':
                # Hitung dan simpan kualifikasi akademik otomatis
                from .models import NilaiKriteria, Kriteria
                jenjang_map = {
                    'SMA': 1, 'MA': 1, 'SMK': 1,
                    'D3': 2, 'D4': 3,
                    'S1': 4, 'S2': 5, 'S3': 5,
                }
                jenjang = kandidat.jenjang_pendidikan or ''
                kual_ak = jenjang_map.get(jenjang.upper(), 4)
                try:
                    kriteria_kual = Kriteria.objects.get(nama='Kualifikasi Akademik')
                    NilaiKriteria.objects.update_or_create(
                        kandidat=kandidat,
                        kriteria=kriteria_kual,
                        defaults={'nilai': kual_ak}
                    )
                    kriteria_peng = Kriteria.objects.get(nama='Pengalaman Mengajar')
                    NilaiKriteria.objects.update_or_create(
                        kandidat=kandidat,
                        kriteria=kriteria_peng,
                        defaults={'nilai': kandidat.pengalaman_mengajar or 0}
                    )
                except Kriteria.DoesNotExist:
                    pass
                kandidat.status_tahap_2 = 'dipanggil'
            elif aksi == 'gugur':
                kandidat.status_tahap_2 = 'gugur'
        elif tahap == '2':
            sub_tahap = request.POST.get('sub_tahap', 'psikotes')
            if aksi == 'lanjut':
                if sub_tahap == 'psikotes':
                    # Lanjut dari psikotes → masuk kompetensi
                    kandidat.status_tahap_2 = 'hadir'
                elif sub_tahap == 'kompetensi':
                    # Lanjut dari kompetensi → masuk wawancara
                    kandidat.status_tahap_3 = 'dipanggil'
            elif aksi == 'gugur':
                kandidat.status_tahap_2 = 'gugur'
        elif tahap == '3':
            if aksi == 'lanjut':
                kandidat.status_tahap_3 = 'hadir'
                kandidat.status_tahap_4 = 'dipanggil'
            elif aksi == 'gugur':
                kandidat.status_tahap_3 = 'gugur'
        elif tahap == '4':
            if aksi == 'lanjut':
                kandidat.status_tahap_4 = 'hadir'
                kandidat.save()
                # Otomatis hitung ulang MARCOS untuk semua kandidat selesai
                try:
                    from .utils.marcos import hitung_marcos
                    hitung_marcos()
                except Exception:
                    pass
                # Otomatis prediksi kandidat ini dengan XGBoost
                try:
                    from .utils.xgboost_model import prediksi_kandidat
                    from .models import HasilSeleksi
                    hasil_prediksi = prediksi_kandidat(kandidat)
                    obj, _ = HasilSeleksi.objects.get_or_create(kandidat=kandidat)
                    obj.prediksi = hasil_prediksi['prediksi']
                    obj.probabilitas = hasil_prediksi['probabilitas']
                    obj.save()
                except Exception:
                    pass
            elif aksi == 'gugur':
                kandidat.status_tahap_4 = 'gugur'
                kandidat.save()

        kandidat.save()
        return redirect(next_url)
    return redirect('administrasi')

@login_required(login_url='login')
def input_penilaian(request, kandidat_id):
    from .models import Kandidat, NilaiKriteria, Kriteria
    kandidat = Kandidat.objects.get(id=kandidat_id)
    if request.method == 'POST':
        kriteria_map = {k.nama: k for k in Kriteria.objects.all()}
        fields = {
            'Kualifikasi Akademik': request.POST.get('kualifikasi_akademik'),
            'IQ': request.POST.get('iq'),
            'Tes Psikotes': request.POST.get('tes_psikotes'),
            'Nilai Akademik': request.POST.get('nilai_akademik'),
            'Pengalaman Mengajar': request.POST.get('pengalaman_mengajar'),
            'Micro Teaching': request.POST.get('micro_teaching'),
            'Komitmen (Wawancara)': request.POST.get('komitmen'),
            'Ruhiyah (Keagamaan)': request.POST.get('ruhiyah'),
        }
        for nama_kriteria, nilai in fields.items():
            if nilai and nama_kriteria in kriteria_map:
                NilaiKriteria.objects.update_or_create(
                    kandidat=kandidat,
                    kriteria=kriteria_map[nama_kriteria],
                    defaults={'nilai': float(nilai)}
                )
        kandidat.status_tahap_2 = 'hadir'
        kandidat.status_tahap_3 = 'hadir'
        kandidat.status_tahap_4 = 'hadir'
        kandidat.save()
        return redirect('administrasi')
    nilai_existing = {
        nk.kriteria.nama: nk.nilai
        for nk in NilaiKriteria.objects.filter(kandidat=kandidat).select_related('kriteria')
    }

    nilai_template = {
        'kualifikasi_akademik': nilai_existing.get('Kualifikasi Akademik', ''),
        'iq': nilai_existing.get('IQ', ''),
        'tes_psikotes': nilai_existing.get('Tes Psikotes', ''),
        'nilai_akademik': nilai_existing.get('Nilai Akademik', ''),
        'pengalaman_mengajar': nilai_existing.get('Pengalaman Mengajar', ''),
        'komitmen': nilai_existing.get('Komitmen (Wawancara)', ''),
        'ruhiyah': nilai_existing.get('Ruhiyah (Keagamaan)', ''),
        'micro_teaching': nilai_existing.get('Micro Teaching', ''),
    }

    return render(request, 'sistem/input_penilaian.html', {
        'kandidat': kandidat,
        'nilai': nilai_template,
    })

@login_required(login_url='login')
def input_nilai_tahap(request, kandidat_id, tahap):
    from .models import Kandidat, NilaiKriteria, Kriteria
    kandidat = Kandidat.objects.get(id=kandidat_id)

    if request.method == 'POST':
        kriteria_map = {k.nama: k for k in Kriteria.objects.all()}

        if tahap == 1:
            jenjang_map = {
                'SMA': 1, 'MA': 1, 'SMK': 1,
                'D3': 2, 'D4': 3,
                'S1': 4, 'S2': 5, 'S3': 5,
            }
            jenjang = kandidat.jenjang_pendidikan or ''
            kual_ak = jenjang_map.get(jenjang.upper(), 4)
            fields = {
                'Kualifikasi Akademik': str(kual_ak),
                'Pengalaman Mengajar': str(kandidat.pengalaman_mengajar or 0),
            }
            next_url = 'administrasi'

        elif tahap == 2:
            fields = {
                'IQ': request.POST.get('iq'),
                'Tes Psikotes': request.POST.get('tes_psikotes'),
            }
            next_url = 'psikotes'

        elif tahap == 3:
            fields = {
                'Nilai Akademik': request.POST.get('nilai_akademik'),
                'Pengalaman Mengajar': request.POST.get('pengalaman_mengajar'),
            }
            kandidat.pengalaman_mengajar = request.POST.get('pengalaman_mengajar') or kandidat.pengalaman_mengajar
            kandidat.save()
            next_url = 'kompetensi'

        elif tahap == 4:
            fields = {
                'Komitmen (Wawancara)': request.POST.get('komitmen'),
                'Ruhiyah (Keagamaan)': request.POST.get('ruhiyah'),
            }
            kandidat.note_wawancara = request.POST.get('note_wawancara', '')
            kandidat.save()
            next_url = 'wawancara'

        elif tahap == 5:
            fields = {
                'Micro Teaching': request.POST.get('micro_teaching'),
            }
            kandidat.note_micro_teaching = request.POST.get('note_micro_teaching', '')
            kandidat.save()
            next_url = 'micro_teaching'

        else:
            fields = {}
            next_url = 'administrasi'

        for nama_kriteria, nilai in fields.items():
            if nilai and nama_kriteria in kriteria_map:
                NilaiKriteria.objects.update_or_create(
                    kandidat=kandidat,
                    kriteria=kriteria_map[nama_kriteria],
                    defaults={'nilai': float(nilai)}
                )

        return redirect(next_url)

    # GET — ambil nilai yang sudah ada
    nilai_existing = {
        nk.kriteria.nama: nk.nilai
        for nk in NilaiKriteria.objects.filter(kandidat=kandidat).select_related('kriteria')
    }

    nilai_template = {
        'kualifikasi_akademik': nilai_existing.get('Kualifikasi Akademik', ''),
        'iq': nilai_existing.get('IQ', ''),
        'tes_psikotes': nilai_existing.get('Tes Psikotes', ''),
        'nilai_akademik': nilai_existing.get('Nilai Akademik', ''),
        'pengalaman_mengajar': nilai_existing.get('Pengalaman Mengajar', ''),
        'komitmen': nilai_existing.get('Komitmen (Wawancara)', ''),
        'ruhiyah': nilai_existing.get('Ruhiyah (Keagamaan)', ''),
        'micro_teaching': nilai_existing.get('Micro Teaching', ''),
    }

    return render(request, 'sistem/input_nilai_tahap.html', {
        'kandidat': kandidat,
        'tahap': tahap,
        'nilai': nilai_template,
    })

# ── Evaluasi & Hasil ──────────────────────────────────────────────────────────
@login_required(login_url='login')
def evaluasi_marcos(request):
    from .models import Kriteria, HasilSeleksi, PeriodeRekrutmen
    from .utils.marcos import hitung_marcos

    if request.method == 'POST':
        hitung_marcos()
        return redirect('evaluasi_marcos')

    periode_aktif = request.GET.get('periode', '')
    kriteria_list = Kriteria.objects.all().order_by('-bobot')
    periode_list = PeriodeRekrutmen.objects.all()

    hasil_qs = HasilSeleksi.objects.filter(
        kandidat__status_tahap_4='hadir'
    ).select_related('kandidat', 'kandidat__periode')

    if periode_aktif:
        hasil_qs = hasil_qs.filter(kandidat__periode_id=periode_aktif)

    semua_hasil = hasil_qs.order_by('ranking')

    nilai_tertinggi = semua_hasil.first().nilai_utilitas if semua_hasil else '-'
    nilai_terendah = semua_hasil.last().nilai_utilitas if semua_hasil else '-'

    return render(request, 'sistem/evaluasi_marcos.html', {
        'kriteria_list': kriteria_list,
        'semua_hasil': semua_hasil,
        'periode_list': periode_list,
        'periode_aktif': periode_aktif,
        'nilai_tertinggi': nilai_tertinggi,
        'nilai_terendah': nilai_terendah,
    })

@login_required(login_url='login')
def prediksi_xgboost(request):
    from .models import HasilSeleksi, PeriodeRekrutmen

    periode_aktif = request.GET.get('periode', '')
    tab_aktif = request.GET.get('tab', 'semua')
    periode_list = PeriodeRekrutmen.objects.all()

    # Tampilkan semua kandidat yang sudah punya prediksi
    hasil_qs = HasilSeleksi.objects.filter(
        kandidat__status_tahap_4='hadir',
        prediksi__isnull=False
    ).select_related('kandidat', 'kandidat__periode', 'kandidat__bidang_studi')

    if periode_aktif:
        hasil_qs = hasil_qs.filter(kandidat__periode_id=periode_aktif)

    layak = hasil_qs.filter(prediksi='Layak').order_by('ranking')
    tidak_layak = hasil_qs.filter(prediksi='Tidak Layak').order_by('ranking')
    semua = hasil_qs.order_by('ranking')

    return render(request, 'sistem/prediksi_xgboost.html', {
        'semua': semua,
        'layak': layak,
        'tidak_layak': tidak_layak,
        'periode_list': periode_list,
        'periode_aktif': periode_aktif,
        'tab_aktif': tab_aktif,
    })

@login_required(login_url='login')
def training_model_view(request):
    from .utils.xgboost_model import training_model, prediksi_semua
    from .utils.marcos import hitung_marcos

    hasil_training = None
    pesan_marcos = None

    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        if aksi == 'training':
            try:
                hasil_training = training_model()
                # Otomatis prediksi ulang semua setelah training
                prediksi_semua()
            except Exception as e:
                hasil_training = {'error': str(e)}
        elif aksi == 'marcos':
            try:
                hitung_marcos()
                # Otomatis prediksi ulang setelah hitung ulang MARCOS
                prediksi_semua()
                pesan_marcos = 'MARCOS berhasil dihitung ulang dan prediksi diperbarui!'
            except Exception as e:
                pesan_marcos = f'Error: {e}'

    return render(request, 'sistem/training.html', {
        'hasil_training': hasil_training,
        'pesan_marcos': pesan_marcos,
    })

@login_required(login_url='login')
def detail_prediksi(request, kandidat_id):
    from .models import Kandidat, HasilSeleksi
    from .utils.xgboost_model import detail_prediksi_kandidat

    kandidat = Kandidat.objects.get(id=kandidat_id)

    try:
        detail = detail_prediksi_kandidat(kandidat)
    except Exception as e:
        detail = None
        error = str(e)

    try:
        hasil = HasilSeleksi.objects.get(kandidat=kandidat)
    except HasilSeleksi.DoesNotExist:
        hasil = None

    return render(request, 'sistem/detail_prediksi.html', {
        'kandidat': kandidat,
        'detail': detail,
        'hasil': hasil,
        'error': error if not detail else None,
    })

@login_required(login_url='login')
def hasil(request):
    from .models import HasilSeleksi, PeriodeRekrutmen
    periode_aktif = request.GET.get('periode', '')
    periode_list = PeriodeRekrutmen.objects.exclude(nama='Data Historis')

    semua = HasilSeleksi.objects.filter(
        kandidat__status_tahap_4='hadir',
        prediksi__isnull=False
    ).exclude(
        kandidat__periode__nama='Data Historis'
    ).select_related('kandidat', 'kandidat__bidang_studi', 'kandidat__periode')

    if periode_aktif:
        semua = semua.filter(kandidat__periode_id=periode_aktif)

    # Re-ranking berdasarkan nilai utilitas
    semua = semua.order_by('-nilai_utilitas')
    hasil_dengan_rank = []
    for i, h in enumerate(semua, start=1):
        hasil_dengan_rank.append({
            'rank_periode': i,
            'obj': h,
        })

    layak = semua.filter(prediksi='Layak')
    tidak = semua.filter(prediksi='Tidak Layak')

    return render(request, 'sistem/hasil.html', {
        'semua': hasil_dengan_rank,
        'total': semua.count(),
        'total_layak': layak.count(),
        'total_tidak': tidak.count(),
        'periode_list': periode_list,
        'periode_aktif': periode_aktif,
    })

@login_required(login_url='login')
def detail_hasil(request, kandidat_id):
    from .models import Kandidat, HasilSeleksi, NilaiKriteria
    from .utils.xgboost_model import detail_prediksi_kandidat
    from django.db.models import Avg
    from django.utils import timezone

    kandidat = Kandidat.objects.get(id=kandidat_id)

    if request.method == 'POST':
        keputusan = request.POST.get('keputusan_akhir')
        if keputusan in ['diterima', 'tidak_diterima']:
            kandidat.keputusan_akhir = keputusan
            kandidat.keputusan_tanggal = timezone.now()
            # Simpan juga ke label untuk data training periode berikutnya
            kandidat.label = keputusan
            kandidat.save()
        return redirect('detail_hasil', kandidat_id=kandidat_id)

    nilai_dict = {
        nk.kriteria.nama: nk.nilai
        for nk in NilaiKriteria.objects.filter(
            kandidat=kandidat
        ).select_related('kriteria')
    }

    try:
        hasil = HasilSeleksi.objects.get(kandidat=kandidat)
    except HasilSeleksi.DoesNotExist:
        hasil = None

    try:
        detail = detail_prediksi_kandidat(kandidat)
    except Exception:
        detail = None

    rata_rata_ki = HasilSeleksi.objects.filter(
        kandidat__status_tahap_4='hadir',
        nilai_utilitas__isnull=False
    ).aggregate(Avg('nilai_utilitas'))['nilai_utilitas__avg']

    rata_rata_ki = round(rata_rata_ki, 6) if rata_rata_ki else 0
    di_atas_rata = (
        hasil.nilai_utilitas >= rata_rata_ki
    ) if hasil and hasil.nilai_utilitas else False

    tahap_nilai = {
        'administrasi': {
            'Kualifikasi Akademik': nilai_dict.get('Kualifikasi Akademik', '-'),
        },
        'psikotes': {
            'IQ': nilai_dict.get('IQ', '-'),
            'Tes Psikotes': nilai_dict.get('Tes Psikotes', '-'),
        },
        'kompetensi': {
            'Nilai Akademik': nilai_dict.get('Nilai Akademik', '-'),
            'Pengalaman Mengajar': nilai_dict.get('Pengalaman Mengajar', '-'),
        },
        'wawancara': {
            'Komitmen (Wawancara)': nilai_dict.get('Komitmen (Wawancara)', '-'),
            'Ruhiyah (Keagamaan)': nilai_dict.get('Ruhiyah (Keagamaan)', '-'),
        },
        'micro_teaching': {
            'Micro Teaching': nilai_dict.get('Micro Teaching', '-'),
        },
    }

    nilai_list = NilaiKriteria.objects.filter(
        kandidat=kandidat
    ).select_related('kriteria').order_by('kriteria__nama')

    return render(request, 'sistem/detail_hasil.html', {
        'kandidat': kandidat,
        'hasil': hasil,
        'detail': detail,
        'tahap_nilai': tahap_nilai,
        'nilai_list': nilai_list,
        'rata_rata_ki': rata_rata_ki,
        'di_atas_rata': di_atas_rata,
    })

# ── Manajemen ─────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def manajemen_kandidat(request):
    from .models import Kandidat, PeriodeRekrutmen
    from django.core.paginator import Paginator

    periode_aktif = request.GET.get('periode', '')
    status_aktif = request.GET.get('status', '')
    periode_list = PeriodeRekrutmen.objects.all()

    kandidat_qs = Kandidat.objects.all().order_by('-created_at')

    if periode_aktif:
        kandidat_qs = kandidat_qs.filter(periode_id=periode_aktif)

    if status_aktif == 'gugur':
        kandidat_qs = kandidat_qs.filter(
            status_tahap_2='gugur'
        ) | kandidat_qs.filter(
            status_tahap_3='gugur'
        ) | kandidat_qs.filter(
            status_tahap_4='gugur'
        )
    elif status_aktif == 'selesai':
        kandidat_qs = kandidat_qs.filter(status_tahap_4='hadir')
    elif status_aktif == 'aktif':
        kandidat_qs = kandidat_qs.exclude(
            status_tahap_4='hadir'
        ).exclude(
            status_tahap_2='gugur'
        ).exclude(
            status_tahap_3='gugur'
        ).exclude(
            status_tahap_4='gugur'
        )

    paginator = Paginator(kandidat_qs, 15)
    page_number = request.GET.get('page')
    kandidat_list = paginator.get_page(page_number)

    return render(request, 'sistem/manajemen_kandidat.html', {
        'kandidat_list': kandidat_list,
        'periode_list': periode_list,
        'periode_aktif': periode_aktif,
        'status_aktif': status_aktif,
    })

@login_required(login_url='login')
def hapus_kandidat(request, kandidat_id):
    from .models import Kandidat
    if request.method == 'POST':
        kandidat = Kandidat.objects.get(id=kandidat_id)
        kandidat.delete()
    return redirect('manajemen_kandidat')

@login_required(login_url='login')
def manajemen_kriteria(request):
    from .models import Kriteria
    kriteria_list = Kriteria.objects.all().order_by('-bobot')
    return render(request, 'sistem/manajemen_kriteria.html', {
        'kriteria_list': kriteria_list,
    })