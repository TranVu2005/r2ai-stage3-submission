# Kiến trúc mã nguồn

Tài liệu này giúp người đọc tìm đúng mã cho từng bước của hệ thống (thuyết minh: `docs/THUYET_MINH.md`, mục 1.3–1.6).

## Quy ước tên

Nhiều module và thư mục mang tên dạng `sNN` (`r2ai.s36`, `scripts/s45/` …). `NN` là số thứ tự đợt phát triển trong dự án; tên được **giữ nguyên** vì đường import, tệp config ghim SHA256 và các tệp kết quả đã ghi đều tham chiếu đến chúng. Bảng dưới ánh xạ từng tên sang chức năng.

Một số tệp và gói dữ liệu cũng mang số đợt (`r2ai-s49-inputs.tar`, `out/runs/s49-120a/`…). Tên này được giữ nguyên vì SHA256 trong các tệp `SHA256SUMS` và các tài liệu đều ghi theo tên tệp. `s49` là đợt dựng lại các bài nộp từ gói chia sẻ.

Cột "Vai trò":

* **R**: nằm trên đường dựng lại bài nộp (`python -m r2ai.reproduce`);
* **D**: dựng dữ liệu, chỉ mục, chấm reranker (chạy một lần, kết quả nằm trong các gói dữ liệu);
* **T**: thử nghiệm đã đóng; giữ trong `src/` vì có test đi kèm hoặc module khác import.

## Điểm vào

| Lệnh | Việc |
|---|---|
| `python -m r2ai.reproduce <bài> \| --all` | dựng lại bài nộp từ gói dữ liệu (`--all` = 5 tệp nộp), kiểm trùng byte, in bảng PASS/FAIL (`src/r2ai/reproduce.py`) |
| `scripts/reproduce_public.sh` | CH-rrf, D250-doconly (và bản tham chiếu R0) |
| `scripts/reproduce_120a.sh` | 120A, 120A-en3, 120A-en10, 120A-nop1 |
| `python -m r2ai.release …` | dựng một bài nộp 120A từ config ghim (apply → compose → validator → ZIP) |

`r2ai.reproduce` chỉ gọi hai script `.sh`; mỗi script dừng ở lần lệch SHA256 đầu tiên.

## Gói `src/r2ai`

| Module | Vai trò | Chức năng |
|---|---|---|
| `paths` | R | gốc đọc/ghi (`R2AI_DATA_DIR`, `R2AI_OUT_DIR` …), đọc `.env` |
| `hf_models` | R | revision ghim của mọi mô hình; nạp snapshot qua `huggingface_hub` (cache `HF_HOME`, tải nếu chưa có và không offline), `data/hf_model_cache` chỉ là dự phòng |
| `reproduce` | R | điểm vào tái hiện, kiểm SHA256 |
| `newq` | R | chọn đầu ra CH-rrf từ pool và điểm đã lưu (`apply_selection`, `choose_carriers`, gọi từ `scripts/s45/public_rebuild.py`); `pins` kiểm 79 tệp đầu vào ghim |
| `release` | R | dựng bài nộp 120A từ config ghim |
| `s29` | R | nhúng câu hỏi BGE-M3, vector câu hỏi công khai |
| `s31` | R | pool cosine, mở rộng Pharmacity (`pharmacity_ext`), chấm Qwen3-Reranker-4B (`judge_score`) |
| `s32` | R | C-max: Qwen3-Reranker-0.6B trên các đoạn t256 gần câu hỏi nhất của mỗi tài liệu |
| `s33` | R/T | đối chứng baseline BGE-M3 + bge-reranker-v2-m3; một phần hàm dùng chung cho chấm điểm |
| `s35` | R | Jina Reranker v3.5 trên pool |
| `s36` | R | hợp nhất RRF (`fuse`), hiệu chỉnh p_cal và cắt EF2 (`cal`), chọn carrier (`carriers`), pool d300 (`d300`), làn tiếng Anh (`enlane`), `s36.s37 apply` cho 120A |
| `s37` | R/D | segment 120ask: ingest các lô crawl từ `deploy/s37`, vector đoạn; segment PubMed tiếng Anh (`en`) |
| `s38` | R | ghép đoạn nguyên văn (`compose`: thân bài + cửa sổ 768, ngưỡng T, trần ZIP), registry nguồn text, validator |
| `s41` | R/T | cấu hình chốt CH-rrf và các thử nghiệm trục tài liệu |
| `s43` | T | thử nghiệm trên cấu hình CH-rrf (một phần hàm dùng cho EN-hedge) |
| `eval` | R | thước đo F2 cục bộ (`scorer`), kiểm định dạng bài nộp (`validate`) |
| `index` | D | phân đoạn t256 (`chunk`), nhúng BGE-M3 (`bge_m3`, `build`), segment chỉ mục |
| `canonical` | D | dựng và kiểm corpus canonical (một bản text cho mỗi `doc_id`, `decisions.parquet`) |
| `crawl`, `extract` | D | CLI crawl tiếng Việt và trích xuất text (gọi `vicrawl`) |
| `s27_pharmacity` | D | crawl Pharmacity theo hướng dẫn BTC |
| `cc_coverage`, `cc_longchau` | D | tra Common Crawl (index, WARC), bổ sung text cho URL không crawl trực tiếp được |
| `zh_full`, `zh_full_ingest`, `zh_v2` | D | crawl và ingest tài liệu tiếng Trung |
| `corpus_v2` | D | đọc corpus v2 của BTC (`links_corpus_vi_en_zh.parquet`), gán ngôn ngữ |
| `compose`, `submit`, `retrieve` | T | bộ dựng bài nộp và truy hồi thế hệ đầu (BM25 + BGE-M3 sparse/dense) |
| `selective`, `dupes`, `vi_quality`, `zh_sample`, `probe`, `gold_check` | T | khảo sát dữ liệu, chọn crawl, phát hiện trùng lặp, công cụ kiểm nhãn thủ công |

`src/vicrawl`: crawler bất đồng bộ có thể dừng/tiếp tục (fetch, robots, chia shard) và bộ trích xuất theo domain (`extractors`).

## Thư mục `scripts`

| Đường dẫn | Vai trò | Chức năng |
|---|---|---|
| `reproduce_*.sh`, `reproduce_120a/` | R | ba script tái hiện; `reproduce_120a/run.py` các bước kq / pool13 / apply / cmax-shards / compose |
| `s26/validate_pa3.py` | R | validator chạy sau mỗi compose |
| `s45/exact_top.py`, `s45/public_rebuild.py`, `s45/doc_only.py` | R | thứ tự cosine chính xác, chọn tài liệu + carrier với config chốt, dựng D250-doconly |
| `s48/hedge_on_zip.py` | R | thêm tài liệu tiếng Anh vào ZIP 120A (en3, en10) |
| `crawl.py`, `extract.py`, `build_index.py` | D | crawl, trích xuất, chỉ mục |
| `s26/full_embed.py`, `s37/run_en_embed.ps1` | D | nhúng BGE-M3 toàn corpus, segment tiếng Anh |
| `s32/run_score.ps1`, `s37/run_cmax.ps1`, `s37/d300_cmax.py`, `s36/run_cmax_extra.sh` | D | chấm C-max (GPU) |
| `s35/run_jina.sh`, `s35/run_part2.sh`, `s37/run_jina.ps1`, `s36/run_jina_extra.sh` | D | chấm Jina (GPU) |
| `s40/run_newq_gpu.ps1`, `s40/run_runpod_4b.sh`, `s40/gate_4b.py` | D | chấm C-max (GPU máy) và 4B (Kaggle/RunPod) cho một pool |
| `s36/handoff_s30.py`, `s36/run_120a_p4b_v0.sh`, `s36/run_120a_p4b_v3.sh` | D | dựng 120A lần đầu, ghi manifest ghim `configs/s36-handoff-s30-manifest.json` |
| `s41/*.sh`, `s41/*_public.py` | D | hồi quy cấu hình private trên tập public |
| `s48/check_hedge_zip.py`, `s48/validate_nop1.py`, `s49/check_en_topk.py` | R | kiểm bổ sung cho EN-hedge và 120A-nop1 |
| các CLI ở gốc `scripts/` còn lại | T | lớp tương thích của `r2ai.submit` / `r2ai.retrieve` / `r2ai.eval` |

## Thư mục khác

| Đường dẫn | Nội dung |
|---|---|
| `configs/` | config chọn đầu ra và tệp ghim SHA256 (không sửa: SHA của chúng được kiểm); `paths.example.env` mẫu đường dẫn máy |
| `notebooks/` | notebook Kaggle chấm Qwen3-Reranker-4B (`s36-kaggle-4b-final.ipynb` cho bài nộp cuối) |
| `deploy/s37/` | crawler 120ask chạy trên VPS (độc lập với repo) và script vận hành |
| `tests/` | pytest; test cần dữ liệu tuỳ chọn tự bỏ qua kèm lý do |
| `tools/` | công cụ phát hành: đóng gói dữ liệu (`package.py`), PDF thuyết minh (`build_pdf.py`) |

## Đường dữ liệu khi dựng lại

```
gói dữ liệu (DATA.md) ─► <root>/data, <root>/out/runs
    ├─ public: s45/exact_top ─► s45/public_rebuild (apply) ─► r2ai.s38.compose ─► s45/doc_only ─► ZIP
    └─ 120a:   reproduce_120a/run.py kq ─► pool13 ─► r2ai.s36.s37 apply ─► cmax-shards ─► compose ─► s48/hedge_on_zip ─► ZIP
```

Mọi bước đọc điểm reranker đã lưu, nên dựng lại chỉ cần CPU.
