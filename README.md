# R2AI Stage 3: truy hồi tài liệu y khoa đa ngôn ngữ (Trần Xuân Vũ)

Mã nguồn của đội Trần Xuân Vũ cho ROAD TO AI 2026, Stage 3. Với mỗi câu hỏi y khoa tiếng Việt, hệ thống trả về các tài liệu liên quan trong corpus đa ngôn ngữ (Việt, Trung, Anh) của BTC, kèm các đoạn trích nguyên văn từ chính các tài liệu đó. Pipeline gồm truy hồi dense BGE-M3, xếp hạng lại bằng nhiều reranker open-weight (Qwen3-Reranker-4B, Qwen3-Reranker-0.6B, Jina Reranker v3.5) hợp nhất bằng RRF, chọn số tài liệu theo F2 kỳ vọng, rồi ghép đoạn nguyên văn. Không fine-tune, không dùng LLM sinh văn bản; bước dựng bài nộp từ tệp điểm đã lưu chạy trên CPU và tất định.

**Tài liệu thuyết minh: [`docs/THUYET_MINH.pdf`](docs/THUYET_MINH.pdf)** (bản Markdown: [`docs/THUYET_MINH.md`](docs/THUYET_MINH.md)).
**Người chấm tái hiện kết quả: [`docs/REPRODUCE.md`](docs/REPRODUCE.md)**. Hướng dẫn đi từng bước: clone, tải dữ liệu, giải nén, chạy `python -m r2ai.reproduce --all` để dựng lại 5 tệp nộp; mỗi bước có lệnh kiểm, kèm bảng lỗi thường gặp.
Dữ liệu: https://drive.google.com/drive/folders/1NUw099da7rR4zd_j3pg_acTUHjfAH09B ([`DATA.md`](DATA.md)). Mô hình: [`MODELS.md`](MODELS.md). Bản đồ mã nguồn: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Bài nộp private

| Tệp | Cấu hình | Lệnh tái hiện |
|---|---|---|
| `1_120A.zip` | 120A | `python -m r2ai.reproduce 120a` |
| `2_D250doconly.zip` | D250-doconly | `python -m r2ai.reproduce d250-doconly` |
| `3_CHrrf.zip` | CH-rrf | `python -m r2ai.reproduce ch-rrf` |
| `4_120A-en3.zip` | 120A + 3 tài liệu tiếng Anh | `python -m r2ai.reproduce 120a-en3` |
| `5_120A-en10.zip` | 120A + 10 tài liệu tiếng Anh | `python -m r2ai.reproduce 120a-en10` |

`python -m r2ai.reproduce --all` dựng lại cả 5 tệp và báo PASS khi tệp dựng ra trùng từng byte với tệp đã nộp. Các ZIP có trong thư mục `submissions/` của link dữ liệu và là tệp đính kèm của GitHub Release `v1.0` (https://github.com/TranVu2005/r2ai-stage3-submission/releases/tag/v1.0-submission). Mục kiểm thêm, không phải bài nộp: `120a-nop1` (120A dựng thuần từ corpus, không dùng text khôi phục, xem thuyết minh mục 5.5).

## Quickstart

Lệnh viết cho bash (Linux, hoặc Git Bash trên Windows). Bản đầy đủ có lệnh kiểm sau mỗi bước, yêu cầu máy và bảng lỗi thường gặp: [`docs/REPRODUCE.md`](docs/REPRODUCE.md).

**1. Cài đặt** (Python 3.11–3.13; đã kiểm 3.12):

```bash
git clone https://github.com/TranVu2005/r2ai-stage3-submission r2ai-stage3 && cd r2ai-stage3
python -m venv .venv && source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
python -m pip install -U pip
python -m pip install -e ".[reproduce,dev]" -c configs/environment.constraints.txt \
    --extra-index-url https://download.pytorch.org/whl/cu128
```

Phiên bản mọi gói được khoá ở `configs/environment.constraints.txt`. Các gói quyết định byte của ZIP: pyarrow 25.0.1, numpy 2.5.3, pandas 3.0.6, polars 1.44.2, transformers 5.18.0, tokenizers 0.23.2; đổi phiên bản có thể làm ZIP lệch byte dù nội dung giống.

**2. Tải dữ liệu từ link** https://drive.google.com/drive/folders/1NUw099da7rR4zd_j3pg_acTUHjfAH09B: thư mục `data/` (8 gói `r2ai-*.tar`) và tệp `SHA256SUMS` ở gốc. Kiểm toàn vẹn rồi giải nén mọi gói vào **một** thư mục gốc:

```bash
sha256sum -c SHA256SUMS --ignore-missing                  # trong thư mục đã tải
export R2AI_ROOT=/duong/dan/r2ai-root && mkdir -p "$R2AI_ROOT"
for t in data/r2ai-*.tar; do tar -xf "$t" -C "$R2AI_ROOT"; done   # Git Bash, đường dẫn có ổ đĩa (D:/…): thêm --force-local
D=$PWD; (cd "$R2AI_ROOT" && for f in "$D"/data/r2ai-*.SHA256SUMS; do sha256sum -c "$f" --quiet && echo "ok $f"; done)   # từng tệp sau giải nén
```

Đề bài của BTC không nằm trong gói (thuộc BTC): tải dataset `AIGuruTinix/ViBioMIR` vào `$R2AI_ROOT/data/raw/` (validator đọc `query.parquet` và `links_corpus_vi_en_zh.parquet`):

```bash
hf download AIGuruTinix/ViBioMIR query.parquet links_corpus_vi_en_zh.parquet --repo-type dataset --local-dir "$R2AI_ROOT/data/raw"
```

Gói nào cần cho bài nào: [`DATA.md`](DATA.md) mục 4. Mẫu biến đường dẫn: [`configs/paths.example.env`](configs/paths.example.env).

**3. Tokenizer và mô hình** (revision ghim, chi tiết ở [`MODELS.md`](MODELS.md)). Dựng từ tệp điểm chỉ cần tokenizer BGE-M3 và tokenizer Qwen3-Reranker-0.6B:

```bash
export HF_HOME=$R2AI_ROOT/hf_home
hf download BAAI/bge-m3 --revision 5617a9f61b028005a4858fdac845db406aefb181
hf download Qwen/Qwen3-Reranker-0.6B --revision e61197ed45024b0ed8a2d74b80b4d909f1255473
export HF_HUB_OFFLINE=1
```

**4. Dựng lại 5 tệp nộp** (chỉ cần CPU):

```bash
python -m r2ai.reproduce --list                       # các mục dựng được
python -m r2ai.reproduce --root "$R2AI_ROOT" --all    # 5 tệp nộp, in bảng PASS/FAIL (khoảng 4 giờ 25 phút)
python -m r2ai.reproduce --root "$R2AI_ROOT" 120a-nop1    # kiểm thêm, không bắt buộc: 120A dựng thuần từ corpus
```

`r2ai.reproduce` gọi hai script `scripts/reproduce_public.sh` và `scripts/reproduce_120a.sh` (chạy được trực tiếp, xem chú thích đầu mỗi script), so mỗi ZIP với tệp đã nộp và chỉ báo PASS khi ZIP do chính lần chạy đó ghi ra và trùng từng byte. Log và báo cáo JSON: `$R2AI_ROOT/out/runs/reproduce/`. Trên Windows cần Git Bash (biến `R2AI_BASH` nếu không ở chỗ mặc định).

**5. Kiểm thử:** `python -m pytest -q` (test cần gói tuỳ chọn `[probe]` hoặc dữ liệu không phát hành sẽ tự bỏ qua kèm lý do). Kết quả 03/11/2026 trong venv sạch: 1.083 passed, 8 skipped.

## Phần cứng và thời gian

| Việc | Phần cứng | Thời gian (laptop Intel Core i5-13420H, 16 GB RAM, Windows 11) |
|---|---|---|
| Dựng lại 5 tệp nộp từ tệp điểm (`--all`) | CPU, RAM ≥ 16 GB, ổ trống ≥ 60 GB (gói 23,8 GB + giải nén + đầu ra) | khoảng 4 giờ 25 phút (lượt 03/11/2026: nhóm 120A 185,2 phút, nhóm public 79,4 phút) |
| Chấm lại reranker (tuỳ chọn) | Kaggle 2×T4 cho Qwen3-Reranker-4B; GPU ≥ 6 GB cho C-max và Jina | 4B khoảng 15 giờ / 360.000 cặp; C-max khoảng 10 giờ |

Mỗi lần chỉ chạy một bước compose (khoảng 5,5 GB RAM). Đã kiểm trên Windows 11 + Git Bash; Linux chưa kiểm. Chấm lại reranker từ đầu và crawl lại chưa được kiểm tái hiện (web đã thay đổi; bài nộp dựng từ tệp điểm và corpus đã lưu).

## Cấu trúc repo

| Thư mục | Nội dung |
|---|---|
| `src/r2ai/` | thư viện: truy hồi, reranker, chọn đầu ra, ghép đoạn, validator, điểm vào `reproduce` |
| `src/vicrawl/` | crawler và bộ trích xuất theo domain |
| `scripts/` | script tái hiện (`reproduce_*.sh`), dựng dữ liệu, chỉ mục, chấm điểm |
| `configs/` | config chọn đầu ra và tệp ghim đầu vào (không sửa), `paths.example.env`, `environment.constraints.txt` |
| `notebooks/` | notebook Kaggle chấm Qwen3-Reranker-4B |
| `deploy/s37/` | crawler 120ask chạy trên VPS |
| `tests/` | pytest |
| `tools/` | đóng gói dữ liệu, xuất PDF thuyết minh |
| `docs/`, `figures/` | thuyết minh, hướng dẫn tái hiện, kiến trúc; sơ đồ |

## Giấy phép

* Mã nguồn: MIT (tệp [`LICENSE`](LICENSE)).
* Mô hình (không phân phối lại, tải từ Hugging Face): BGE-M3 MIT; Qwen3-Reranker-4B/0.6B Apache-2.0; **Jina Reranker v3.5 CC-BY-NC-4.0 (chỉ dùng phi thương mại)**, nên các tệp điểm Jina trong gói dữ liệu cũng chỉ dùng phi thương mại.
* Dữ liệu: text lấy từ các URL trong corpus của BTC, bản quyền thuộc trang nguồn; abstract PubMed qua Europe PMC theo điều khoản của Europe PMC. Gói dữ liệu chỉ phục vụ việc kiểm tra tái hiện trong khuôn khổ cuộc thi, không cấp phép phân phối lại.
* Đề bài (`AIGuruTinix/ViBioMIR`) thuộc BTC, không đóng gói lại.
