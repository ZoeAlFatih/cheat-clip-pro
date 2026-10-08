# Backlog

## T1 — Refactor monolith frontend/backend + lunasi utang lint (dari audit F21)

Dijadwalkan user 2026-10-08 sebagai task terpisah dari audit (`docs/audit-2026-10-08.md`, F21). Status: belum dimulai.

**Masalah**

| File / fungsi | Ukuran (commit 01560f4) |
|---|---|
| `src/components/ClipStudioSection.tsx` | 4.773 baris, 78 `useState` |
| `src/App.tsx` | 4.647 baris, 60 `useState` |
| `backend/video_engine.py` | 3.068 baris (download, transkripsi, ASS, face tracking, filtergraph, encode) |
| `backend/routers/analyze.py` → `analyze_video` | ~1.100 baris dalam satu fungsi |

ESLint: 81 error + 9 warning bawaan upstream (`no-explicit-any` 34, `no-empty` 18, `no-unused-vars` 13,
`react-hooks/set-state-in-effect` 11, `react-hooks/exhaustive-deps` 9, lainnya 5). Terbanyak di
`ClipStudioSection.tsx` (32), `App.tsx` (24), `ClipTrimmerModal.tsx` (18).

**Urutan kerja yang aman**

1. Safety net dulu: jadikan smoke test end-to-end (upload video → analisis `mock` → batch render → ZIP) sebagai
   Playwright test yang bisa diulang. Saat audit, alur ini dijalankan manual dan menemukan F23–F25.
2. Lint yang mekanis (`no-unused-vars`, `no-empty`, `no-extra-boolean-cast`), lalu jadikan `npm run lint` gate di
   `.github/workflows/ci.yml`. Mulai dengan `--max-warnings` sesuai kondisi saat itu, turunkan bertahap.
3. Pecah `ClipStudioSection.tsx` per panel (canvas/aspect, title, subtitle, audio, watermark, export, preview).
   State yang dipakai lintas panel dipindah ke satu reducer/context, bukan prop drilling 78 state.
4. Pecah `App.tsx`: form input, riwayat, hasil analisis, alur SSE analyze/render.
5. Backend: `analyze_video` dipecah per tahap (sumber → metadata/heatmap → transkrip → Gemini → hasil);
   `video_engine.py` dipecah per domain (download, transcription, subtitles, framing, render).
   Satukan resolver file lokal yang kini tersebar di 6 jalur (lihat catatan F02 di dokumen audit).

**Kriteria selesai**

- Smoke test end-to-end lolos sebelum dan sesudah tiap langkah.
- `npm run lint` tanpa error dan menjadi gate CI.
- Tidak ada file frontend > ~800 baris; tidak ada fungsi backend > ~150 baris.
- `backend.tests.test_audit_fixes` tetap lolos.
