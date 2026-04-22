# Laporan Interpretasi Jejaring Semantik (AJS)

**Sumber data:** Excel: tabel_relasi_ajs_putri_bungsu.xlsx | rows=13
**Ringkas graf:** 16 node, 12 relasi (graf berarah).

## 1) Pusat perputaran narasi (Degree)

Degree tinggi menunjukkan simpul yang paling sering menghubungkan tokoh, konsep, motif, atau tema.
- **putri bungsu** (Tokoh) — 4.0000
- **keutuhan keluarga** (Konsep) — 3.0000
- **penyakit ibunya** (Konsep) — 2.0000
- **kekerasan simbolik** (Motif) — 2.0000
- **Ular N’daung** (Konsep) — 2.0000

## 2) Jembatan makna (Betweenness)

Betweenness tinggi menunjukkan simpul penghubung antarbagian penting dalam jaringan makna.
- **putri bungsu** (Tokoh) — 0.0190
- **penyakit ibunya** (Konsep) — 0.0048
- **kekerasan simbolik** (Motif) — 0.0048
- **keutuhan keluarga** (Konsep) — 0.0000
- **Ular N’daung** (Konsep) — 0.0000

## 3) Simpul paling diacu (PageRank)

PageRank tinggi menunjukkan simpul yang banyak dirujuk oleh relasi-relasi penting.
- **keutuhan keluarga** (Konsep) — 0.1581
- **obat yang ada di kawah gunung** (Konsep) — 0.0952
- **putri bungsu** (Tokoh) — 0.0842
- **kasih sayang dan tanggung jawab** (Tema) — 0.0728
- **dengan pangeran** (Tokoh) — 0.0728

## 4) Klaster makna

- Klaster 1: Kedua kakak perempuan, Ular N’daung, dengan pangeran, kasih sayang dan tanggung jawab, menjadi pangeran, putri bungsu
- Klaster 2: Kekuasaan, Pengorbanan, Perebutan pangeran, kekerasan simbolik, keutuhan keluarga
- Klaster 3: Tiga kakak beradik, obat yang ada di kawah gunung, penyakit ibunya
- Klaster 4: Tanggung jawab, sebagai pengorbanan

## 5) Catatan analisis

- Hasil ini membantu pembacaan close reading, bukan menggantikannya.
- Konsistensi penamaan entitas sangat penting agar node tidak pecah.
- Penambahan kolom SourceType dan TargetType akan membuat hasil lebih rapi.

---

Tafsir akhir tetap berada di tangan pembaca sastra. Mesin hanya bantu memetakan; bukan ikut sidang tafsir. 😄