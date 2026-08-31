"""
Prototype: Web Pengolah & Visualisasi Feedback Expert
Telkom Corporate University - Expert Management

Cara jalankan:
    pip install -r requirements.txt
    streamlit run app.py

Fungsi:
- Upload file Excel raw feedback (satu sheet per expert, format long).
- Bersihkan & olah data secara otomatis (tanpa perlu Excel manual lagi).
- Hitung rata-rata nilai per expert & per pertanyaan.
- Tampilkan jawaban teks (saran/masukan) peserta.
- Klasifikasi expert: Underperform / Cukup Bagus / Excellent (threshold bisa diatur).
- Visualisasi interaktif (bar chart, pie chart, radar chart).
- Download hasil olahan dalam format Excel siap pakai.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from core import (
    CLASS_COLOR,
    REQUIRED_COLUMNS,
    build_download_excel,
    categorize_score,
    classify,
    load_workbook,
    process_expert_sheet,
)

SCORE_CATEGORY_COLOR = {"Rendah": "#E24B4A", "Tinggi": "#1D9E75"}

st.set_page_config(page_title="Expert Feedback Analyzer", page_icon="📊", layout="wide")

st.title("📊 Expert Feedback Analyzer")
st.caption(
    "Prototype internal — Expert Management, Telkom Corporate University. "
    "Upload data mentah feedback kegiatan, sistem otomatis membersihkan, "
    "menghitung, dan memvisualisasikan performa expert."
)

with st.sidebar:
    st.header("1. Upload data")
    uploaded_file = st.file_uploader(
        "File Excel raw feedback (.xlsx)", type=["xlsx"], accept_multiple_files=False
    )
    st.caption(
        "Format yang didukung: 1 sheet per expert, kolom minimal "
        "NIK, Name, Question, Answer (seperti file Answer Attempt)."
    )

    st.header("2. Threshold klasifikasi expert")
    low_th = st.number_input("Batas bawah Underperform -> Cukup Bagus", value=86.0, step=1.0)
    high_th = st.number_input("Batas bawah Cukup Bagus -> Excellent", value=90.0, step=1.0)
    if low_th >= high_th:
        st.warning("Batas bawah harus lebih kecil dari batas atas.")

    st.header("3. Threshold nilai individual")
    score_th = st.number_input(
        "Batas nilai per jawaban (skala 0-10): di bawah = Rendah, sama/di atas = Tinggi",
        value=8.0,
        step=0.5,
    )

if uploaded_file is None:
    st.info("Upload file Excel raw feedback di sidebar untuk mulai.")
    st.stop()

try:
    sheets = load_workbook(uploaded_file)
except Exception as e:
    st.error(f"Gagal membaca file: {e}")
    st.stop()

if not sheets:
    st.error(
        "Tidak ada sheet dengan format yang sesuai. Pastikan setiap sheet expert "
        f"punya kolom: {', '.join(sorted(REQUIRED_COLUMNS))}."
    )
    st.stop()

results = []
errors = []
for expert_name, df in sheets.items():
    try:
        results.append(process_expert_sheet(expert_name, df))
    except Exception as e:
        errors.append(str(e))

for err in errors:
    st.warning(err)

if not results:
    st.error("Tidak ada data expert yang berhasil diolah.")
    st.stop()

results.sort(key=lambda r: r.average_score, reverse=True)

summary_df = pd.DataFrame(
    [
        {
            "Expert": r.name,
            "Jumlah Peserta": r.n_participants,
            "Rata-rata Nilai": r.average_score,
            "Klasifikasi": classify(r.average_score, low_th, high_th),
        }
        for r in results
    ]
)

tab_ringkasan, tab_detail, tab_data = st.tabs(
    ["Ringkasan", "Detail per Expert", "Data Mentah"]
)

with tab_ringkasan:
    col1, col2, col3 = st.columns(3)
    col1.metric("Jumlah Expert", len(results))
    col2.metric("Total Peserta (unik per sheet)", int(summary_df["Jumlah Peserta"].sum()))
    col3.metric("Rata-rata Keseluruhan", f"{summary_df['Rata-rata Nilai'].mean():.2f}")

    st.subheader("Tabel ringkasan")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    c1, c2 = st.columns([2, 1])
    with c1:
        bar = px.bar(
            summary_df,
            x="Rata-rata Nilai",
            y="Expert",
            orientation="h",
            color="Klasifikasi",
            color_discrete_map=CLASS_COLOR,
            text="Rata-rata Nilai",
        )
        bar.update_layout(yaxis={"categoryorder": "total ascending"}, height=400)
        st.plotly_chart(bar, use_container_width=True)
    with c2:
        pie = px.pie(
            summary_df,
            names="Klasifikasi",
            color="Klasifikasi",
            color_discrete_map=CLASS_COLOR,
            hole=0.4,
        )
        pie.update_layout(height=400)
        st.plotly_chart(pie, use_container_width=True)

    download_bytes = build_download_excel(results, low_th, high_th, score_th)
    st.download_button(
        "Download hasil olahan (Excel)",
        data=download_bytes,
        file_name="Hasil_Olahan_Feedback_Expert.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with tab_detail:
    expert_choice = st.selectbox("Pilih expert", [r.name for r in results])
    r = next(x for x in results if x.name == expert_choice)
    kelas = classify(r.average_score, low_th, high_th)

    c1, c2 = st.columns(2)
    c1.metric("Rata-rata nilai", f"{r.average_score:.2f}")
    c2.metric("Klasifikasi", kelas)

    st.subheader("Rata-rata nilai per pertanyaan")
    if len(r.question_scores):
        radar = go.Figure()
        radar.add_trace(
            go.Scatterpolar(
                r=r.question_scores["Nilai"],
                theta=r.question_scores["Question"],
                fill="toself",
                name=r.name,
            )
        )
        radar.update_layout(
            polar={"radialaxis": {"visible": True, "range": [0, 100]}},
            showlegend=False,
            height=420,
        )
        st.plotly_chart(radar, use_container_width=True)
        st.dataframe(r.question_scores, use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada pertanyaan rating (numerik) terdeteksi pada sheet ini.")

    st.subheader("Nilai per peserta")
    if len(r.participant_avg):
        # Kategori dihitung per PESERTA (rata-rata nilai yang dia berikan ke expert ini),
        # bukan per baris jawaban -> 1 peserta cuma dihitung 1x.
        avg_df = r.participant_avg.copy()
        avg_df["Kategori"] = avg_df["Nilai"].apply(lambda v: categorize_score(v, score_th))
        avg_df = avg_df.rename(
            columns={"Name": "Nama Peserta", "Nilai": "Rata-rata Nilai", "Nilai100": "Rata-rata Nilai (skala 100)"}
        )

        counts = (
            avg_df["Kategori"].value_counts().reindex(["Rendah", "Tinggi"]).fillna(0).astype(int)
        )
        count_df = pd.DataFrame({"Kategori": counts.index, "Jumlah Peserta": counts.values})

        c1, c2 = st.columns([1, 2])
        with c1:
            m1, m2 = st.columns(2)
            m1.metric("Jumlah peserta menilai Rendah", int(counts["Rendah"]))
            m2.metric("Jumlah peserta menilai Tinggi", int(counts["Tinggi"]))
        with c2:
            cat_bar = px.bar(
                count_df,
                x="Kategori",
                y="Jumlah Peserta",
                color="Kategori",
                color_discrete_map=SCORE_CATEGORY_COLOR,
                text="Jumlah Peserta",
            )
            cat_bar.update_layout(height=220, showlegend=False)
            st.plotly_chart(cat_bar, use_container_width=True)

        st.caption(
            "Kategori di atas berdasarkan rata-rata nilai (skala 0-10) yang diberikan "
            f"masing-masing peserta ke expert ini: di bawah {score_th:g} = Rendah, "
            f"{score_th:g} ke atas = Tinggi."
        )
        st.dataframe(
            avg_df[["NIK", "Nama Peserta", "Rata-rata Nilai", "Rata-rata Nilai (skala 100)", "Kategori"]],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Lihat rincian nilai per jawaban (per pertanyaan)"):
            detail_df = r.participant_scores.copy()
            detail_df["Kategori"] = detail_df["Nilai"].apply(
                lambda v: categorize_score(v, score_th)
            )
            detail_df = detail_df.rename(
                columns={
                    "Name": "Nama Peserta",
                    "Question": "Pertanyaan",
                    "Nilai100": "Nilai (skala 100)",
                }
            )
            st.dataframe(
                detail_df[
                    ["NIK", "Nama Peserta", "Pertanyaan", "Nilai", "Nilai (skala 100)", "Kategori"]
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Tidak ada data nilai individual pada sheet ini.")

    st.subheader("Jawaban teks / saran dari peserta")
    if len(r.comments):
        st.dataframe(
            r.comments.rename(
                columns={"Name": "Nama Peserta", "Question": "Pertanyaan", "Answer": "Jawaban"}
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Tidak ada jawaban teks yang tercatat untuk expert ini.")

with tab_data:
    expert_choice2 = st.selectbox(
        "Lihat data mentah expert", [r.name for r in results], key="raw_select"
    )
    r2 = next(x for x in results if x.name == expert_choice2)
    st.caption(f"Pertanyaan rating terdeteksi: {', '.join(r2.numeric_questions) or '-'}")
    st.caption(f"Pertanyaan teks terdeteksi: {', '.join(r2.text_questions) or '-'}")
    st.dataframe(r2.raw, use_container_width=True)