# Expert Feedback Analyzer (Prototype)

Prototype internal untuk **Expert Management, Telkom Corporate University**.
Menggantikan proses olah data feedback expert yang selama ini manual di Excel.

## Fitur
- Upload file Excel raw feedback (format seperti `Answer Attempt...xlsx`: satu sheet per expert).
- Deteksi otomatis pertanyaan rating (angka) vs pertanyaan teks bebas (saran/masukan) — tidak hardcode kata kunci pertanyaan, jadi tetap jalan walau kalimat pertanyaan berubah.
- Hitung otomatis:
  - Rata-rata nilai per expert (skala 0-100)
  - Rata-rata nilai per pertanyaan per expert
  - Daftar jawaban teks/saran dari peserta
- Klasifikasi expert ke 3 kelas: **Underperform / Cukup Bagus / Excellent**, threshold bisa diubah langsung dari sidebar.
- Visualisasi interaktif: bar chart ranking expert, pie chart distribusi klasifikasi, radar chart nilai per pertanyaan.
- Download hasil olahan sebagai file Excel (3 sheet: Ringkasan, Nilai per Pertanyaan, Komentar Peserta) yang siap dipakai ulang di dashboard existing.
- Tidak pakai database — semua proses berjalan in-memory selama sesi (sesuai kebutuhan: dipakai sementara untuk olah data, bukan penyimpanan permanen).

## Cara menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

Lalu buka browser ke alamat yang muncul di terminal (default `http://localhost:8501`).

## Struktur file
- `app.py` — halaman & tampilan Streamlit (UI saja).
- `core.py` — logika pengolahan data (parsing, agregasi, klasifikasi, export Excel). Dipisah dari UI supaya mudah ditest/dipakai ulang.
- `requirements.txt` — daftar dependency.

## Format data input yang didukung
File Excel dengan satu sheet per expert. Tiap sheet minimal punya kolom:
`NIK`, `Name`, `Question`, `Answer` (kolom lain seperti Email, Position, dll boleh ada, akan diabaikan).

Sheet yang tidak punya kolom wajib tersebut otomatis dilewati (misalnya sheet kosong seperti "Worksheet").

## Catatan pengembangan lanjutan
- Threshold klasifikasi saat ini default 70 dan 85 (bisa diubah di sidebar) — sebaiknya didiskusikan dan disesuaikan dengan standar penilaian yang berlaku di Corpu.
- Kalau ke depan perlu dukung multi-file / bandingkan antar batch pelatihan, tinggal tambah `st.file_uploader(accept_multiple_files=True)` dan loop per file.
- Kalau nanti butuh histori/multi-user, baru pertimbangkan tambah database ringan (SQLite dulu) — untuk kebutuhan sekarang tidak diperlukan.
