# Mô hình dùng trong các bài nộp

Mọi mô hình đều là open-weight trên Hugging Face, ≤ 15B tham số, phát hành trước 01/08/2026, và được ghim theo commit (revision). Hệ thống không dùng LLM đóng. Không mô hình nào được fine-tune: tất cả dùng nguyên trọng số đã công bố.

## 1. Bảng tổng hợp

| mô hình | link chính thức | revision (commit HF) | giấy phép | tham số | vai trò | có trong bài nộp |
|---|---|---|---|---|---|---|
| BAAI/bge-m3 | https://huggingface.co/BAAI/bge-m3 | `5617a9f61b028005a4858fdac845db406aefb181` | MIT | 0,57B | embedding dense (doc, chunk t256, query) → truy hồi cosine; tokenizer đếm token khi ghép chunk | cả 5 |
| Qwen/Qwen3-Reranker-4B | https://huggingface.co/Qwen/Qwen3-Reranker-4B | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` | Apache-2.0 | 4,0B | rerank (query, doc): P4B; nguồn RRF chính và cơ sở hiệu chỉnh xác suất (p_cal) | cả 5 |
| Qwen/Qwen3-Reranker-0.6B | https://huggingface.co/Qwen/Qwen3-Reranker-0.6B | `e61197ed45024b0ed8a2d74b80b4d909f1255473` | Apache-2.0 | 0,6B | C-max: chấm từng chunk t256, điểm doc = max; chọn cửa sổ 768; tokenizer cắt văn bản 512 token | cả 5 |
| jinaai/jina-reranker-v3.5 | https://huggingface.co/jinaai/jina-reranker-v3.5 | `e8a93f33f0b22108f8c2364f8484ce3422552fbc` | **CC-BY-NC-4.0** (phi thương mại) | 0,6B (nền Qwen3-0.6B) | rerank listwise, nguồn RRF thứ tư | chỉ **120A**, **120A-en3**, **120A-en10** |

Mô hình lịch sử: các mô hình dưới đây không chạy khi dựng bài nộp, nhưng có mặt trong chuỗi dữ liệu.

| mô hình | revision | vì sao nhắc tới |
|---|---|---|
| BAAI/bge-reranker-v2-m3 (Apache-2.0) | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` | Dùng cùng Qwen3-Reranker-0.6B để xếp hạng doc vi trong bài nộp cũ P1-vi+10 (18/10). Từ P1-vi+10, 120A chỉ lấy **số doc mỗi query** (K_q), xem `DATA.md` mục 5 |
| Qwen2.5-7B-Instruct (Ollama `qwen2.5:7b`, Q4_K_M) | (bản Ollama 20/08/2026) | Chỉ dùng trong một thử nghiệm dịch query sang tiếng Anh (bị loại). Không có trong bài nộp nào |

## 2. Cấu hình từng mô hình

### BGE-M3 (embedding)

* Biểu diễn: dense, vector CLS, chuẩn hoá L2, lưu fp16 (1.024 chiều).
* Doc: `doc_text` canonical (title + nội dung), 4.096 ký tự đầu, `max_len` 512 token. Kết quả: `full_doc_dense.npz` gồm 887.151 doc, cộng Pharmacity 979 doc và 120ask theo segment.
* Chunk t256: cùng encoder (`r2ai.index.bge_m3.M3Encoder`), `max_len` 512. Kết quả: `canonical-20261018/vectors/dense.npy`.
* Query: 1.200 query, cùng encoder, fp16. Kết quả: `s29_query_vectors.npz`.
* Làn tiếng Anh (EN-hedge): 239.771 abstract PubMed, cùng công thức.
* Phần cứng: RTX 3050 6 GB, fp16. Chỉ cần GPU khi tạo vector; dựng bài nộp từ vector có sẵn chỉ cần CPU.

### Qwen3-Reranker-4B và 0.6B (pointwise yes/no)

Mẫu prompt dùng chung cho cả hai (`src/r2ai/s31/judge_score.py`):

```
<|im_start|>system
Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>
<|im_start|>user
<Instruct>: {instruction}
<Query>: {query}
<Document>: {doc}<|im_end|>
<|im_start|>assistant
<think>

</think>

```

* instruction (vi): `Given a Vietnamese medical question, judge whether the Vietnamese passage answers it`
* instruction (zh): `Given a Vietnamese medical question, judge whether the Chinese passage answers it`
* Điểm = softmax(logit "yes", logit "no") lấy xác suất "yes".
* Cắt doc: 512 token đầu (`truncate_document`, tokenizer Qwen3).

Riêng **4B:**
* Chạy trên Kaggle, 2×T4, fp16 (T4 không có bf16), khoảng 6,7 cặp/giây.
* Notebook `notebooks/s36-kaggle-4b-final.ipynb` là bản đã dùng để chấm.
* Script chấm `judge_score.py` nằm trong gói `r2ai-runs-inputs`.
* Notebook tự kiểm revision, số cặp và SHA của đầu vào.

Riêng **0.6B (C-max):**
* Chạy bf16 trên GPU máy.
* Với mỗi cặp (query, doc), lấy 3 chunk t256 (field answer/body) có cosine BGE-M3 cao nhất với query; chấm từng chunk; điểm doc = max.
* Doc không có chunk dùng điểm của `doc_text`.
* Điểm chunk còn được dùng để chọn cửa sổ 768 token quanh chunk tốt nhất.

### Jina Reranker v3.5 (listwise, chỉ 120A)

* Tải bằng `trust_remote_code` (`modeling.py` của repo đã được đọc trước khi dùng).
* Pool của mỗi query được xáo theo seed (`query_id`) rồi chia thành các khối ≤ 10 doc (layout `b10s0`).
* Điểm gộp nhiều khối theo `JinaForRanking.rerank`. Mã: `src/r2ai/s35/jina.py`.
* Giấy phép CC-BY-NC-4.0 chỉ cho phép dùng phi thương mại. Việc dùng trong cuộc thi là phi thương mại; ghi rõ ở đây để BTC biết.

## 3. Cách tải

```bash
pip install "huggingface-hub==1.33.0"
hf download BAAI/bge-m3 --revision 5617a9f61b028005a4858fdac845db406aefb181
hf download Qwen/Qwen3-Reranker-4B --revision 22e683669bc0f0bd69640a1354a6d0aebcfeede5
hf download Qwen/Qwen3-Reranker-0.6B --revision e61197ed45024b0ed8a2d74b80b4d909f1255473
hf download jinaai/jina-reranker-v3.5 --revision e8a93f33f0b22108f8c2364f8484ce3422552fbc   # chỉ khi chấm lại Jina
```

Sau khi tải, đặt `HF_HOME` trỏ tới cache và `HF_HUB_OFFLINE=1`. Mã chỉ đọc theo revision đã ghim (`src/r2ai/hf_models.py`): trước hết là snapshot của revision đó trong cache `HF_HOME`; nếu chưa có và không bật `HF_HUB_OFFLINE` thì tải đúng revision đó (mô hình công khai, không cần token); bản `data/hf_model_cache/models--<org>--<tên>/snapshots/<revision>` chỉ là dự phòng.

Mô hình **không** được đóng gói lại, vì tải trực tiếp từ HF theo revision là đủ. Tệp `out/runs/reranker-trial/model-pin.json` (gói `r2ai-runs-meta`) ghi SHA256 của từng tệp trong snapshot Qwen3-Reranker-0.6B để đối chiếu sau khi tải.

**Dựng lại bài nộp từ điểm có sẵn chỉ cần:** tokenizer BGE-M3 (đếm token) và tokenizer Qwen3-Reranker-0.6B (cắt văn bản). Không chạy reranker nào.
