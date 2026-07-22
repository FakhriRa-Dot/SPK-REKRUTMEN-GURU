from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Main
    path('dashboard/', views.dashboard, name='dashboard'),
    path('pipeline/', views.pipeline, name='pipeline'),
    path('input-kandidat/', views.input_kandidat, name='input_kandidat'),
    path('api/tambah-periode/', views.tambah_periode, name='tambah_periode'),

    # Tahap Seleksi
    path('administrasi/', views.administrasi, name='administrasi'),
    path('psikotes/', views.psikotes, name='psikotes'),
    path('kompetensi/', views.kompetensi, name='kompetensi'),
    path('wawancara/', views.wawancara, name='wawancara'),
    path('micro-teaching/', views.micro_teaching, name='micro_teaching'),
    path('input-penilaian/<int:kandidat_id>/', views.input_penilaian, name='input_penilaian'),
    path('kandidat/<int:kandidat_id>/update-status/', views.update_status, name='update_status'),
    path('kandidat/<int:kandidat_id>/input-nilai/<int:tahap>/', views.input_nilai_tahap, name='input_nilai_tahap'),

    # Evaluasi & Hasil
    path('evaluasi/', views.evaluasi_marcos, name='evaluasi_marcos'),
    path('prediksi/', views.prediksi_xgboost, name='prediksi_xgboost'),
    path('prediksi/<int:kandidat_id>/', views.detail_prediksi, name='detail_prediksi'),
    path('hasil/', views.hasil, name='hasil'),
    path('hasil/<int:kandidat_id>/', views.detail_hasil, name='detail_hasil'),

    # Manajemen
    path('manajemen/kandidat/', views.manajemen_kandidat, name='manajemen_kandidat'),
    path('kandidat/<int:kandidat_id>/hapus/', views.hapus_kandidat, name='hapus_kandidat'),
    path('manajemen/kriteria/', views.manajemen_kriteria, name='manajemen_kriteria'),

    path('fucom/', views.fucom_upload, name='fucom_upload'),
    path('fucom/download-template/', views.download_template_fucom, name='download_template_fucom'),

    path('training/', views.training_model_view, name='training_model'),
]