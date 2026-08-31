"""Logika inti pengolahan data feedback expert (terpisah dari UI Streamlit
supaya mudah diuji dan digunakan ulang)."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = {"NIK", "Name", "Question", "Answer"}
PLACEHOLDER_VALUES = {"-", "", "nan", "none", "null"}

CLASS_COLOR = {
    "Underperform": "#E24B4A",
    "Cukup Bagus": "#EF9F27",
    "Excellent": "#1D9E75",
}


@dataclass
class ExpertResult:
    name: str
    n_participants: int
    average_score: float  # skala 0-100
    question_scores: pd.DataFrame  # kolom: Question, Nilai
    comments: pd.DataFrame  # kolom: NIK, Name, Question, Answer
    participant_scores: pd.DataFrame  # kolom: NIK, Name, Question, Nilai (skala 0-10), Nilai100
    participant_avg: pd.DataFrame  # kolom: NIK, Name, Nilai (rata2 skala 0-10), Nilai100 -- 1 baris per peserta
    raw: pd.DataFrame
    numeric_questions: list = field(default_factory=list)
    text_questions: list = field(default_factory=list)


def is_placeholder(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip().lower() in PLACEHOLDER_VALUES


def detect_numeric_questions(df: pd.DataFrame) -> tuple[list, list]:
    """Deteksi otomatis pertanyaan rating (numerik) vs pertanyaan teks bebas."""
    numeric_qs, text_qs = [], []
    for question, group in df.groupby("Question"):
        answers = group["Answer"].dropna()
        answers = answers[~answers.astype(str).str.strip().str.lower().isin(PLACEHOLDER_VALUES)]
        if len(answers) == 0:
            text_qs.append(question)
            continue
        numeric_ok = pd.to_numeric(answers, errors="coerce").notna()
        ratio_numeric = numeric_ok.mean()
        if ratio_numeric >= 0.6:
            numeric_qs.append(question)
        else:
            text_qs.append(question)
    return numeric_qs, text_qs


def process_expert_sheet(expert_name: str, df: pd.DataFrame) -> ExpertResult:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Sheet '{expert_name}' tidak punya kolom wajib: {', '.join(sorted(missing))}"
        )

    numeric_qs, text_qs = detect_numeric_questions(df)

    numeric_df = df[df["Question"].isin(numeric_qs)].copy()
    numeric_df["AnswerNum"] = pd.to_numeric(numeric_df["Answer"], errors="coerce")
    numeric_df = numeric_df.dropna(subset=["AnswerNum"])

    # rata-rata per peserta (semua pertanyaan rating), skala asli lalu dikali 10 -> 0-100
    per_participant = numeric_df.groupby(["NIK", "Name"])["AnswerNum"].mean().reset_index()
    per_participant["Nilai100"] = per_participant["AnswerNum"] * 10

    overall_average = (
        round(per_participant["Nilai100"].mean(), 2) if len(per_participant) else 0.0
    )

    # 1 baris per peserta: rata-rata nilai (skala 0-10) yang DIA berikan ke expert ini,
    # dipakai untuk menghitung "jumlah peserta yang menilai Rendah/Tinggi" (bukan per jawaban)
    participant_avg = per_participant.rename(columns={"AnswerNum": "Nilai"})[
        ["NIK", "Name", "Nilai", "Nilai100"]
    ].copy()
    participant_avg["Nilai"] = participant_avg["Nilai"].round(2)
    participant_avg["Nilai100"] = participant_avg["Nilai100"].round(2)

    # rata-rata per pertanyaan (skala 0-100)
    per_question = numeric_df.groupby("Question")["AnswerNum"].mean().reset_index()
    per_question["Nilai"] = (per_question["AnswerNum"] * 10).round(2)
    per_question = per_question[["Question", "Nilai"]]

    # kumpulkan jawaban teks bebas (saran/masukan), buang placeholder kosong
    text_df = df[df["Question"].isin(text_qs)].copy()
    text_df = text_df[~text_df["Answer"].apply(is_placeholder)]
    comments = text_df[["NIK", "Name", "Question", "Answer"]].reset_index(drop=True)

    # nilai mentah per peserta per pertanyaan (untuk tabel detail + kategori Rendah/Tinggi)
    participant_scores = numeric_df[["NIK", "Name", "Question", "AnswerNum"]].rename(
        columns={"AnswerNum": "Nilai"}
    )
    participant_scores["Nilai100"] = (participant_scores["Nilai"] * 10).round(2)
    participant_scores = participant_scores.reset_index(drop=True)

    return ExpertResult(
        name=expert_name,
        n_participants=df["NIK"].nunique(),
        average_score=overall_average,
        question_scores=per_question,
        comments=comments,
        participant_scores=participant_scores,
        participant_avg=participant_avg,
        raw=df,
        numeric_questions=numeric_qs,
        text_questions=text_qs,
    )


def classify(score: float, low: float, high: float) -> str:
    if score < low:
        return "Underperform"
    if score < high:
        return "Cukup Bagus"
    return "Excellent"


def categorize_score(nilai: float, threshold: float = 8.0) -> str:
    """Kategori nilai individual dari satu peserta untuk satu pertanyaan.
    Skala nilai mengikuti skala asli di raw data (biasanya 0-10)."""
    return "Rendah" if nilai < threshold else "Tinggi"


def load_workbook(uploaded_file) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(uploaded_file)
    sheets = {}
    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        if df.empty or not REQUIRED_COLUMNS.issubset(set(str(c).strip() for c in df.columns)):
            continue
        sheets[sheet_name] = df
    return sheets


def build_download_excel(
    results: list[ExpertResult], low: float, high: float, score_threshold: float = 8.0
) -> bytes:
    summary_rows = []
    question_rows = []
    comment_rows = []
    participant_rows = []

    for r in results:
        kelas = classify(r.average_score, low, high)
        summary_rows.append(
            {
                "Expert": r.name,
                "Jumlah Peserta": r.n_participants,
                "Rata-rata Nilai": r.average_score,
                "Klasifikasi": kelas,
            }
        )
        for _, row in r.question_scores.iterrows():
            question_rows.append(
                {"Expert": r.name, "Pertanyaan": row["Question"], "Nilai": row["Nilai"]}
            )
        for _, row in r.comments.iterrows():
            comment_rows.append(
                {
                    "Expert": r.name,
                    "NIK": row["NIK"],
                    "Nama Peserta": row["Name"],
                    "Pertanyaan": row["Question"],
                    "Jawaban": row["Answer"],
                }
            )
        for _, row in r.participant_scores.iterrows():
            participant_rows.append(
                {
                    "Expert": r.name,
                    "NIK": row["NIK"],
                    "Nama Peserta": row["Name"],
                    "Pertanyaan": row["Question"],
                    "Nilai": row["Nilai"],
                    "Nilai (skala 100)": row["Nilai100"],
                    "Kategori": categorize_score(row["Nilai"], score_threshold),
                }
            )

    summary_df = pd.DataFrame(summary_rows).sort_values("Rata-rata Nilai", ascending=False)
    question_df = pd.DataFrame(question_rows)
    comment_df = pd.DataFrame(comment_rows)
    participant_df = pd.DataFrame(participant_rows)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Ringkasan Expert", index=False)
        question_df.to_excel(writer, sheet_name="Nilai per Pertanyaan", index=False)
        participant_df.to_excel(writer, sheet_name="Nilai per Peserta", index=False)
        comment_df.to_excel(writer, sheet_name="Komentar Peserta", index=False)
    buffer.seek(0)
    return buffer.getvalue()