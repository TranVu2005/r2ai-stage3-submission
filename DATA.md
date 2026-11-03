# Dữ liệu: nguồn, thu thập, làm sạch, phân đoạn và gói chia sẻ

Đề bài cho 1.200 query tiếng Việt (`query.parquet`) và danh sách URL corpus (`links_corpus.parquet`: `id`, `url`). Cả hai thuộc dataset `AIGuruTinix/ViBioMIR` trên Hugging Face và **không được đóng gói lại**: tải từ nguồn của BTC. Đội tự lấy text từ chính các URL trong corpus. Hệ thống không thêm text nào từ URL ngoài corpus, và không có text tổng hợp hay dịch trong bài nộp.

## 1. Nguồn và cách thu thập

| nguồn | phạm vi | cách lấy | số doc dùng |
|---|---|---|---:|
| Crawl trực tiếp (vi) | các domain vi của corpus (suckhoecongdongonline, suckhoedoisong, thanhnien, vinmec, medlatec, laodong, …) | crawler riêng `src/vicrawl`, `src/r2ai/crawl` (httpx HTTP/2). Rate theo domain (≤ 1–8 req/s, tự giảm khi gặp 429/503), checkpoint SQLite, shard HTML thô zstd. Chạy từ IP dân dụng Việt Nam | trong 727.681 doc vi canonical |
| Crawl trực tiếp (zh) | cnkang, ask.39.net, familydoctor, 120ask, a-hospital, … | cùng crawler, lane zh. Crawl theo yield (mẫu 2% mỗi domain → ưu tiên domain có ích) | trong 159.470 doc zh canonical |
| Common Crawl | nhathuoclongchau.com.vn (trang chặn crawl trực tiếp) và một số báo vi | chỉ URL có trong corpus. HTTP Range tới `data.commoncrawl.org` theo index CC; ghi WARC filename/offset/length cho từng doc | 85.143 doc (cột `source` = `common_crawl` trong provenance) |
| Re-extract từ HTML thô đã lưu | một số báo vi | extractor theo domain trên HTML đã có | 20.593 doc |
| 120ask | 73.001 URL 120ask chưa có text | crawl lại từ VPS (máy local bị timeout), 1 IP, ≤ 1 req/s, dừng khi gặp 403/429/challenge | 73.000 doc (9 segment) |
| Pharmacity | 5.337 URL | crawl trực tiếp, dừng khi gặp Cloudflare challenge | 979 doc (3 lô) |
| PubMed (tiếng Anh) | 240.000 URL PubMed của corpus | Europe PMC REST API theo PMID (≤ 5 req/s), lấy title + abstract | 239.771 doc (chỉ dùng cho bản EN-hedge) |

**robots.txt:** crawler tôn trọng robots.txt và `crawl-delay` theo mặc định. Có hai ngoại lệ, đều đã duyệt nội bộ (quyết định D21) và chỉ lấy URL thuộc corpus của BTC:
* re-extract một số trang báo vi;
* crawl 120ask.

Ghi trung thực để BTC đánh giá. Hệ thống không dùng proxy xoay vòng, dịch vụ giải captcha, hay chia một domain cho nhiều IP.

**Crawl lại không cho kết quả trùng byte:** nội dung web đã thay đổi, và một phần trang đã gỡ hoặc chặn. Vì vậy hồ sơ chia sẻ **corpus canonical đã trích xuất** làm điểm xuất phát tái hiện, kèm mã crawl/trích xuất để đối chiếu. HTML thô (khoảng 9,8 GB) và CSDL trạng thái crawl (khoảng 9,3 GB) không đưa vào gói, vì là bản sao nguyên văn trang web của bên thứ ba. Nếu BTC yêu cầu, có thể cung cấp riêng.

## 2. Làm sạch và chọn phiên bản (corpus canonical)

`data/canonical-20261018/` có 887.151 doc_id (vi 727.681, zh 159.470), **mỗi doc_id đúng một văn bản**. Mã: `src/r2ai/canonical/`.

* **Trích xuất:** dùng extractor theo domain (tách title / description / question / answer / body, giữ ranh giới đoạn) hoặc trafilatura 2.2.0 cho domain chung. Chỉ chuẩn hoá khoảng trắng; không dịch, không viết lại.
  * `doc_text` = title + các phần theo thứ tự trang.
* **Trùng URL** (http/https/www): gộp nhóm; text gắn với mọi doc_id của nhóm (alias owner).
* **Chọn phiên bản:** một doc_id có thể có nhiều bản text (89.816 doc). Quy tắc chọn:
  * (a) text đang phục vụ trong index, 869.104 doc;
  * (b) lần trích xuất mới nhất đạt ngưỡng chất lượng, 11.008 doc;
  * doc mỏng (thin, 7.039) được giữ nhưng không chunk, không có vector.
  * Từng lựa chọn ghi trong `decisions.parquet`.
* **Provenance từng doc** (`provenance.parquet`): nguồn, extractor, SHA256 text; với Common Crawl có thêm WARC filename/offset/length.
* **Kiểm bất biến:** ID thuộc corpus, mỗi ID một bản, chunk là chuỗi con nguyên văn của `doc_text`, vector khớp text. Cả bốn đạt 100%.

120ask và Pharmacity là segment riêng, không ghi vào canonical:
* 120ask: `doc_text` = title + question + từng answer theo thứ tự trang.
* Pharmacity: lot docs của đợt crawl.

## 3. Phân đoạn (chunk)

* **t256:** chunker canonical, khoảng 256 token BGE-M3 mỗi chunk, cắt theo field (title / question / answer / body) và ranh giới đoạn. Kết quả: 5.647.948 chunk; offset ký tự `char_start` / `char_end` trỏ vào `doc_text`, nên chunk luôn nguyên văn. Dùng để chọn chunk tốt nhất (C-max) và cửa sổ.
* **Chunk trong bài nộp** (luật `full+w768`):
  * mỗi doc mang chunk (carrier) nhận **thân bài nguyên văn**;
  * nếu thân dài hơn T = 1.536 token, thêm **một cửa sổ 768 token** quanh chunk t256 tốt nhất (theo điểm Qwen3-Reranker-0.6B).
  * Tối đa 2 chunk mỗi doc, đều là chuỗi con nguyên văn của văn bản gốc (validator kiểm).

## 4. Gói chia sẻ

Script: `tools/package.py`, nhóm tệp khai trong `tools/packages.json`. Đầu ra gồm:
* `<gói>.tar` (không nén lại, vì parquet / npz / zip đã nén);
* `<gói>.SHA256SUMS` (SHA256 từng tệp bên trong, đường dẫn tính từ thư mục gốc giải nén; 7 gói còn mang bản sao bên trong tar với tên `SHA256SUMS-<gói>.txt`, riêng `r2ai-runs-scores.tar` thì không);
* `SHA256SUMS` (SHA256 của chính các tệp gói);
* `data-manifest.csv` (gói, đường dẫn, bytes, SHA256 từng tệp; chỉ để tra cứu, không có trong thư mục chia sẻ).

**Cách dùng:** đường dẫn trong gói là `data/…`, `out/runs/…` và `submissions/…`, nên mọi gói được giải nén vào **cùng một** thư mục gốc (`R2AI_ROOT`; có thể là chính checkout của repo). Từng bước có lệnh kiểm: [`docs/REPRODUCE.md`](docs/REPRODUCE.md). Mọi gói nằm trong thư mục `data/` của link chia sẻ (cuối mục này); `python -m r2ai.reproduce --all` (5 tệp nộp) cần cả 8 gói.

| gói | cần cho | dung lượng | nội dung | trong thư mục chia sẻ |
|---|---|---:|---|---|
| `r2ai-data-canonical.tar` | mọi bài | 18,1 GB | `data/canonical-20261018/` (docs, chunks t256, vector BGE-M3 của chunk, provenance, decisions, manifest) | `data/r2ai-data-canonical.tar` |
| `r2ai-data-120ask.tar` | mọi bài | 1,07 GB | `data/s37_120ask/` (9 segment: docs, chunks t256 / cấu trúc, vector, C-max top-3) | `data/r2ai-data-120ask.tar` |
| `r2ai-runs-inputs.tar` | mọi bài | 2,2 GB | vector doc BGE-M3 (`full_doc_dense.npz`), Pharmacity (docs + vector), vector query, `judge_score.py`, vector chunk bổ sung, pin mô hình | `data/r2ai-runs-inputs.tar` |
| `r2ai-runs-scores.tar` | mọi bài | 0,61 GB | toàn bộ tệp điểm của public: Qwen3-Reranker-4B, C-max 0.6B, Jina v3.5, 0.6B (thử nghiệm đầu); pool và registry cặp | `data/r2ai-runs-scores.tar` |
| `r2ai-runs-meta.tar` | mọi bài | 34 MB | manifest run, `cal.json` / `ef2-free.json`, báo cáo build và log của các run tạo bài nộp | `data/r2ai-runs-meta.tar` |
| `r2ai-s49-inputs.tar` | 120A, 120A-en3/en10, CH-rrf | 10 MB | `kq_counts.parquet`, `p1_chunks.parquet`, `p1_chunks_chrrf.parquet`, `P1-vi+10.approval.json` (mục 5) | `data/r2ai-s49-inputs.tar` |
| `r2ai-data-en-pubmed.tar` | 120A-en3, 120A-en10 | 1,19 GB | `data/s37_en/seg37900-en-pubmed` (239.771 abstract + vector) | `data/r2ai-data-en-pubmed.tar` |
| `r2ai-submissions.tar` | CH-rrf, D250-doconly (mốc so sánh) | 0,70 GB | 5 ZIP đã nộp + 2 bản dựng tham chiếu (R0, 120A-nop1). Bước chọn tài liệu của nhóm public so thứ tự tài liệu với `submissions/3_CHrrf.zip` (chỉ đối chiếu, không làm đầu vào) | `data/r2ai-submissions.tar` |

**Thư mục chia sẻ** (https://drive.google.com/drive/folders/1NUw099da7rR4zd_j3pg_acTUHjfAH09B):

```
R2AI-Stage3/
  data/            8 tệp r2ai-*.tar + 8 tệp r2ai-*.SHA256SUMS + SHA256SUMS
  submissions/     1_120A.zip, 2_D250doconly.zip, 3_CHrrf.zip, 4_120A-en3.zip, 5_120A-en10.zip
  SHA256SUMS       kiểm toàn vẹn 8 gói và 5 ZIP sau khi tải (sha256sum -c SHA256SUMS)
  README_DATA.txt  giải nén vào đâu, kiểm toàn vẹn thế nào
```

Mô hình **không** nằm trong gói: tải từ Hugging Face theo revision (`MODELS.md`). Đề bài (`query.parquet`, `links_corpus_vi_en_zh.parquet`) tải từ dataset `AIGuruTinix/ViBioMIR` của BTC vào `data/raw/` (`README.md`, Quickstart bước 2).

**Có gì dựng lại được, có gì không:**
* **Tái tạo được từ gói** (không cần GPU): cả 5 tệp nộp, trùng từng byte (`python -m r2ai.reproduce --all`, `docs/REPRODUCE.md`).
* **Tái tạo được nếu có GPU** (không bắt buộc, vì đã có tệp điểm):
  * vector BGE-M3: nhiều giờ GPU;
  * điểm 4B: Kaggle 2×T4, khoảng 15 giờ cho 360.000 cặp;
  * điểm C-max 0.6B: GPU máy, khoảng 10 giờ;
  * điểm Jina: khoảng 7 giờ GPU.
* **Không tái tạo được trùng byte:** HTML crawl (web đã đổi).

## 5. Hai tệp khôi phục cho 120A

Bài nộp cũ `P1-vi+10.zip` (18/10) và `P-A4-K90-ph.zip` (20/10) bị xoá ngày 29/10 khi dọn ổ đĩa. Bản dựng 120A chỉ cần từ chúng:
* **số doc mỗi query** (K_q, K90);
* **text của các chunk P1.** Đó là đoạn thân bài do bộ trích xuất cũ (P1) tạo từ chính các URL của corpus.

| tệp | nội dung | nguồn |
|---|---|---|
| `kq_counts.parquet` | `query_id`, `K_q`, `K90` = round(0,9·K_q), `n13` = round(1,3·K_q), `source` | audit theo query của `P1-vi+10.approval.json` (lưu trong archive meta; mô tả đúng ZIP P1-vi+10). K_q = `vi_docs_after` + `zh_docs_preserved`. Kiểm: n13 trùng cỡ pool13 cũ ở 1.200/1.200 query; tổng K90 = 195.147 | |
| `p1_chunks.parquet` | `query_id`, `doc_id`, `chunk_order`, `chunk_text`: 1.836 dòng, 956 doc | text chunk P1 khôi phục từ bài nộp `1_120A.zip`: mọi carrier của các doc có thân bài khác thân dựng từ canonical | |
| `p1_chunks_chrrf.parquet` | như trên, cho CH-rrf: 1.834 dòng / 989 doc | khôi phục từ bài nộp `3_CHrrf.zip`, so với thân dựng từ canonical (R0) | |
| `P1-vi+10.approval.json` | báo cáo duyệt của bài nộp P1-vi+10 (audit 1.200 query) | archive meta | |

Bản **120A-nop1** dựng không cần `p1_chunks.parquet`: text lấy hoàn toàn từ canonical / 120ask / Pharmacity. Bản này khác bài nộp đúng 1.800 chunk text; tập doc và carrier y hệt.

## 6. Bản quyền

* Văn bản trong corpus thuộc các trang nguồn. Gói chia sẻ (link chỉ đọc) chỉ phục vụ việc kiểm tra tái hiện trong khuôn khổ cuộc thi; không cấp phép phân phối lại.
* Abstract PubMed lấy qua Europe PMC theo điều khoản sử dụng của Europe PMC.
* Jina Reranker v3.5 có giấy phép CC-BY-NC-4.0 (phi thương mại).
