# Hướng dẫn tái hiện cho người chấm

Mục tiêu: từ một máy mới, clone repo, tải dữ liệu, rồi dựng lại 5 tệp đã nộp (`1_120A.zip`, `2_D250doconly.zip`, `3_CHrrf.zip`, `4_120A-en3.zip`, `5_120A-en10.zip`), **trùng từng byte** với các ZIP đã nộp. Chỉ cần làm theo thứ tự các bước dưới đây. Mỗi bước có lệnh kiểm kết quả trước khi sang bước sau.

Lệnh viết cho bash: Linux, hoặc Git Bash trên Windows (không dùng WSL bash của `System32`). Đã kiểm: Windows 11 + Git Bash, Python 3.12, ngày 03/11/2026, cả 5 tệp PASS (thuyết minh mục 5.4). Linux chưa kiểm.

## 0. Cần chuẩn bị

| Hạng mục | Yêu cầu |
|---|---|
| Hệ điều hành | Linux x86_64 hoặc Windows 10/11 + [Git for Windows](https://git-scm.com/download/win) (có Git Bash, `tar`, `sha256sum`) |
| Python | 3.11–3.13 (đã kiểm 3.12). Đường dẫn tới `python` **không được có dấu cách** |
| CPU / RAM | RAM ≥ 16 GB (mỗi bước ghép đoạn dùng khoảng 5,5 GB) |
| GPU | **Không cần** |
| Ổ đĩa | ≥ 60 GB trống: 23,8 GB gói tải về, khoảng 24 GB sau giải nén, khoảng 6 GB đầu ra, khoảng 6 GB mô hình |
| Mạng | Tải khoảng 24 GB từ Google Drive, khoảng 5,5 GB từ Hugging Face, khoảng 3 GB gói Python (torch) |
| Thời gian | Chạy `--all` (5 tệp nộp) khoảng 4 giờ 25 phút trên laptop i5-13420H |

## 1. Clone và cài đặt

```bash
git clone https://github.com/TranVu2005/r2ai-stage3-submission r2ai-stage3
cd r2ai-stage3
python -m venv .venv
source .venv/bin/activate                 # Windows (Git Bash): source .venv/Scripts/activate
python -m pip install -U pip
python -m pip install -e ".[reproduce,dev]" -c configs/environment.constraints.txt \
    --extra-index-url https://download.pytorch.org/whl/cu128
python -m r2ai.reproduce --list           # kiểm: in 5 dòng "submission" và 2 dòng "check"
```

* Phiên bản mọi gói được khoá trong `configs/environment.constraints.txt`. **Không** cài phiên bản khác: pyarrow, numpy, pandas, polars, transformers và tokenizers quyết định từng byte của ZIP.
* Bánh xe `torch==2.11.0+cu128` vẫn chạy được trên máy không có GPU hay driver CUDA.

## 2. Tải dữ liệu

Thư mục chia sẻ (chỉ đọc): https://drive.google.com/drive/folders/1NUw099da7rR4zd_j3pg_acTUHjfAH09B

```
R2AI-Stage3/
  data/            8 gói r2ai-*.tar, 8 tệp r2ai-*.SHA256SUMS (SHA256 từng tệp trong gói), SHA256SUMS, data-manifest.csv
  submissions/     5 ZIP bài nộp: 1_120A.zip … 5_120A-en10.zip
  SHA256SUMS       SHA256 của 8 gói và 5 ZIP (đường dẫn tương đối từ thư mục này)
  data-manifest.csv, README_DATA.txt
```

**Tải cả thư mục, giữ nguyên cấu trúc** (`data/`, `submissions/`, `SHA256SUMS`). Với `--all`, cả 8 gói đều cần. Thư mục `submissions/` ở gốc chỉ để đối chiếu nhanh, vì các ZIP này cũng có trong `data/r2ai-submissions.tar`; nếu không tải nó, dùng `sha256sum -c SHA256SUMS --ignore-missing`. Bảng ở `DATA.md` mục 4 cho biết gói nào ứng với bài nào nếu chỉ chạy một phần. Cách tải:

* trình duyệt: mở từng tệp rồi chọn Tải xuống. Google Drive nén thư mục lớn thành nhiều tệp `.zip` nên tải **từng tệp** sẽ an toàn hơn tải cả thư mục;
* hoặc công cụ dòng lệnh như `rclone` (remote kiểu `drive`) hoặc `gdown --folder <link>`. Các công cụ này chưa được đội kiểm trên thư mục này; nếu Google báo vượt hạn mức tải, thử lại sau hoặc dùng trình duyệt.

Kiểm toàn vẹn, chạy trong thư mục đã tải (`R2AI-Stage3/`):

```bash
sha256sum -c SHA256SUMS                    # kiểm: 13 dòng "OK" (8 gói + 5 ZIP)
```

## 3. Giải nén vào một thư mục gốc

Đường dẫn trong gói là `data/…`, `out/runs/…`, `submissions/…`. Giải nén **mọi** gói vào **cùng một** thư mục gốc `R2AI_ROOT`. Thư mục này có thể nằm ngoài repo; nếu giải nén vào chính thư mục repo thì bỏ được `--root` ở bước 6.

```bash
D=$PWD                                     # thư mục đã tải (R2AI-Stage3/)
export R2AI_ROOT=/duong/dan/r2ai-root      # Windows: dùng dấu "/" (D:/r2ai-root)
mkdir -p "$R2AI_ROOT"
for t in "$D"/data/r2ai-*.tar; do tar -xf "$t" -C "$R2AI_ROOT"; done        # Git Bash với đường dẫn có ổ đĩa: tar --force-local -xf …
(cd "$R2AI_ROOT" && for f in "$D"/data/r2ai-*.SHA256SUMS; do sha256sum -c "$f" --quiet && echo "ok $f"; done)   # kiểm: 8 dòng "ok"
```

Đo trên SSD: giải nén khoảng 2 phút, kiểm từng tệp khoảng 2,5 phút. Sau bước này, `$R2AI_ROOT` có `data/`, `out/runs/`, `submissions/`.

## 4. Đề bài của BTC

Đề bài không nằm trong gói vì thuộc BTC. Validator đọc 2 tệp của dataset `AIGuruTinix/ViBioMIR`:

```bash
hf download AIGuruTinix/ViBioMIR query.parquet links_corpus_vi_en_zh.parquet --repo-type dataset --local-dir "$R2AI_ROOT/data/raw"
ls "$R2AI_ROOT"/data/raw/        # kiểm: có query.parquet và links_corpus_vi_en_zh.parquet
```

`hf` là CLI của `huggingface-hub` đã cài ở bước 1. Lệnh cũ `huggingface-cli` không còn chạy ở phiên bản này. Nếu dataset yêu cầu đăng nhập, chạy `hf auth login` bằng tài khoản của người chấm.

## 5. Mô hình (Hugging Face, theo revision ghim)

Dựng lại từ tệp điểm có sẵn không chạy reranker nào. Chỉ cần tokenizer BGE-M3 và tokenizer Qwen3-Reranker-0.6B:

```bash
export HF_HOME=$R2AI_ROOT/hf_home
hf download BAAI/bge-m3 --revision 5617a9f61b028005a4858fdac845db406aefb181                 # khoảng 4,3 GB
hf download Qwen/Qwen3-Reranker-0.6B --revision e61197ed45024b0ed8a2d74b80b4d909f1255473    # khoảng 1,2 GB
export HF_HUB_OFFLINE=1
```

Mã chỉ đọc đúng các revision này (`src/r2ai/hf_models.py`, `MODELS.md`). Đo ngày 03/11/2026: tải từ HF khoảng 30 MB/s, nhưng có lúc chậm hẳn. Nếu chậm, cứ chạy lại lệnh: tệp đã tải xong được giữ lại.

## 6. Dựng lại 5 tệp nộp

```bash
python -m r2ai.reproduce --root "$R2AI_ROOT" --all          # 5 tệp nộp, chỉ cần CPU, khoảng 4 giờ 25 phút
```

`--all` chạy lần lượt hai nhóm: `120a` (1_120A, 4_120A-en3, 5_120A-en10), rồi `public` (2_D250doconly, 3_CHrrf). Có thể chạy riêng từng tệp, ví dụ `python -m r2ai.reproduce --root "$R2AI_ROOT" 120a ch-rrf`. Kết quả đúng là bảng sau, mã thoát 0:

```
target        status   submission                             zip
120a          PASS     1_120A.zip (120A)                      …/s49-120a/3c/120A-p4b-v3-full+w768-t1536.zip
120a-en3      PASS     4_120A-en3.zip (120A + 3 en docs)      …/en3/120A-p4b-v3-en3.zip
120a-en10     PASS     5_120A-en10.zip (120A + 10 en docs)    …/en10/120A-p4b-v3-en10.zip
d250-doconly  PASS     2_D250doconly.zip (D250-doconly)       …/s49-public/compose/P-D250-doconly.zip
ch-rrf        PASS     3_CHrrf.zip (CH-rrf)                   …/s49-public/chrrf/CH-rrf-full+w768-t1536.zip
```

* PASS chỉ được báo khi ZIP do **chính lần chạy này** ghi ra và trùng từng byte với tệp đã nộp cùng tên trong `submissions/`. Có thể tự đối chiếu: `cmp <zip dựng ra> submissions/<tên tệp>`.
* Log của từng nhóm và báo cáo JSON nằm ở `$R2AI_ROOT/out/runs/reproduce/`. Báo cáo validator của BTC cho từng ZIP là tệp `*.validate.json` đặt cạnh ZIP; mỗi tệp phải có `"ok": true`.
* Thư mục làm việc của 120A-en3/en10 mang dấu thời gian của lần chạy. Hai nhóm `120a` và `public` ghi vào thư mục cố định `out/runs/s49-120a/{3b,3c}` và `out/runs/s49-public/`. Lượt kiểm của đội chạy từ một gốc mới. Nếu muốn chạy lại hai nhóm này từ đầu, dùng một `R2AI_ROOT` mới hoặc đổi tên các thư mục đó trước khi chạy.
* Các dòng sau là bình thường, không phải lỗi: `pool.npz differs from 45f69e56 (not read by the cosine13 apply …)` và `cmax shards differ in bytes from the archived manifests (content checked separately)`. Thuyết minh mục 5.5 giải thích lý do.

**Kiểm thêm (không bắt buộc, không phải bài nộp):**

```bash
python -m r2ai.reproduce --root "$R2AI_ROOT" 120a-nop1      # 120A dựng thuần từ corpus, không dùng text khôi phục (thuyết minh mục 5.5)
```

## 7. Kiểm thử mã (tuỳ chọn)

```bash
python -m pytest -q        # 03/11/2026: 1.083 passed, 8 skipped
```

Test cần gói tuỳ chọn `[probe]` hoặc dữ liệu không phát hành sẽ tự bỏ qua, kèm lý do.

## 8. Lỗi thường gặp

| Thông báo | Nguyên nhân, cách xử lý |
|---|---|
| `bash not found` hoặc script chạy bằng WSL | Cài Git for Windows, hoặc đặt `R2AI_BASH="C:/Program Files/Git/bin/bash.exe"` |
| `the scripts call $PY unquoted: use a Python whose path has no space` | Tạo venv ở đường dẫn không có dấu cách |
| `… out/runs not found: extract the data packages …` | Sai `--root`, hoặc chưa giải nén vào cùng một thư mục (bước 3) |
| `[<nhóm>] missing inputs below …` | Thiếu gói, hoặc thiếu 2 tệp đề bài BTC (bước 4). Danh sách tệp thiếu được in kèm |
| `… is not in the Hugging Face cache (HF_HOME) nor at …` | Chưa tải mô hình hoặc `HF_HOME` sai (bước 5). Lệnh `hf download` cần chạy được in kèm |
| `Cannot open: No such file or directory` khi `tar` trên Windows | Đường dẫn có ổ đĩa (`D:/…`): dùng `tar --force-local` |
| `DIFF …` / `FAIL` | Kiểm lại bước 1 (phiên bản gói khác constraints?), bước 2 và 3 (`sha256sum -c`), rồi gửi `$R2AI_ROOT/out/runs/reproduce/*.log` cho đội |
| Hết RAM | Đóng ứng dụng khác. Lệnh chỉ chạy một bước ghép đoạn tại một thời điểm (khoảng 5,5 GB) |

## 9. Ngoài phạm vi kiểm trùng byte

* Chấm lại reranker từ đầu (Qwen3-Reranker-4B trên Kaggle 2×T4, C-max và Jina trên GPU): làm được bằng mã trong repo (`README.md`, mục "Phần cứng và thời gian"), nhưng không nằm trong đường tái hiện vì đã có tệp điểm trong gói.
* Crawl lại web: không cho kết quả trùng byte, vì trang nguồn đã thay đổi.
