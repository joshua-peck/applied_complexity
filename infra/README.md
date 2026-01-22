# Data Architecture
## Medallion Architecture + Landing Zone

To ensure absolute auditability for high-stakes policy decisions, the system maintains an **Indefinite Retention** policy across all layers. This allows for a "Perfect Trace" from final scores back to the original, byte-for-byte API payloads used to generate the signals.

| Layer | Type | Retention | Responsibility | Primary Format |
| :--- | :--- | :--- | :--- | :--- |
| **landing-zone** | Archive | Indefinite | The Evidence Locker. Original, bit-for-bit API payloads (ZIP, XML, JSON) exactly as delivered. | Raw Source |
| **bronze** | System of Record | Indefinite | Structured History. Uniform, queryable snapshots. Schema-on-read enabled via BigLake. | Parquet / GCS |
| **silver** | Analytical Core | Indefinite | The Workbench. Cleaned, stationarized, and time-aligned features (Smoothing, Log-returns, Z-scores). | PostgreSQL |
| **gold** | Decision Layer | Indefinite | Inference Engine. Probabilistic fragility scores and latent regime classifications. | PostgreSQL / Views |

---

## 🛡️ Integrity & Traceability

Because financial stability decisions require high-fidelity justification, the architecture enforces a **Deterministic Lineage Chain**:

1. **Immutable Hashing:** Every file entering the **Landing Zone** is assigned a `SHA-256` hash immediately upon arrival.
2. **Lineage Propagation:** This hash is carried as a `source_file_hash` metadata column through the **Bronze** and **Silver** layers.
3. **Point-in-Time Audit:** Any specific risk score in the **Gold** layer can be traced back to the exact byte-for-byte source file used to generate it, protecting against "silent" upstream data revisions by providers (e.g., FRED).
