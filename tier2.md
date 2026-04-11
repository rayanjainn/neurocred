# Tier 2: Event Stream Processor & Semantic Classifier

Related Tiers: Tier 2 (Event Stream Processor & Semantic Classifier)

## 1. Overview: Semantic Merchant Classification

In Tier 2, the system performs real-time classification of raw financial events. A critical part of this is **Merchant Category Classification (MCC)**. Unlike traditional systems that rely on rigid, hardcoded lookup tables, FinTwin employs a **lightweight embedded NLP model** to perform semantic categorization.

### 1.1 The Problem with Hardcoded Lookups
- **Cold Start**: New merchants are added to the ecosystem daily; lookups fail for unknown strings.
- **Variability**: The same merchant may appear as "STARBUCKS #123", "STRBCKS COFFEE", or "STARBUCKS ONLINE".
- **Maintenance**: Maintaining a global list of millions of merchant strings is computationally and operationally expensive.

### 1.2 Our Solution: Semantic Embeddings
We use a **bi-encoder architecture** to project merchant strings into a high-dimensional vector space. Classification is then treated as a **similarity search** against a set of "Category Anchors".

---

## 2. Technical Implementation: all-MiniLM-L6-v2

We have selected the **`all-MiniLM-L6-v2`** model from the Sentence-Transformers library as the core embedding engine.

### 2.1 Why this model?
- **Small Footprint**: Only **80MB** (disk) and ~120MB (RAM).
- **Inference Speed**: Optimized for **CPU architecture**. In Tier 2's asynchronous pipeline, it provides sub-millisecond latency for single-string encoding.
- **Dimensionality**: Outputs **384-dimensional** vectors, providing high semantic density without the overhead of 768 or 1024-dim models.
- **Contextual Awareness**: Unlike static word vectors, it understands the relationship between tokens, correctly identifying that "Reliance Fresh" and "Generic Grocery Store" belong to `GROCERIES`.

### 2.2 The "Anchor" Methodology
Instead of a lookup table, we define **Semantic Anchors** for each target category (e.g., `DINING`, `BILLS`, `SALARY`).
1. **Category Vector**: We pre-compute the mean embedding for a set of descriptive keywords for each category.
2. **Real-time Projection**: The raw `merchant_name` is encoded into a vector $v_{m}$.
3. **Similarity Scoring**: We compute the **Cosine Similarity** between $v_{m}$ and all category vectors.
4. **Assignment**: The category with the highest cosine score (above a confidence threshold) is assigned.

---

## 3. Model Comparison & Selection Rationale

| Model | Size | CPU Perf | Semantic Depth | Why not chosen? |
|---|---|---|---|---|
| **FastText** | ~10MB | Extremely High | Low | Word-level only; fails on noisy merchant strings (e.g. codes/IDs). |
| **DistilBERT** | ~250MB | Moderate | High | Higher latency; too heavy for a Tier 2 processing unit. |
| **all-mpnet-base-v2** | ~420MB | Low | Very High | Excellence accuracy is overkill for short merchant strings; too slow on CPU. |
| **all-MiniLM-L6-v2** | **80MB** | **High** | **High** | **Selected**: The "Sweet Spot" for real-time local intelligence. |

---

## 4. Integration with Tier 2 Pipeline

1. **Ingestion**: Raw transaction arrives in Redis Stream (`stream:raw_ingestion`).
2. **Normalization**: Parser extracts amount, timestamp, and raw merchant string.
3. **Semantic Lookup**:
   - If exact match exists in a local cache (LRU), use it.
   - Else, encode string via `MiniLM` and find nearest semantic anchor.
4. **Type Assignment**: Assign `transaction_type` (INCOME/EXPENSE) and `merchant_category`.
5. **Downstream**: The enriched event is pushed to `stream:typed_events` for Tier 3 feature extraction.
