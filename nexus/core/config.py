from dataclasses import dataclass


@dataclass
class Settings:
    working_capacity: int = 10           # turns kept in working memory
    episodic_compress_at: int = 20       # compress after N uncompressed traces
    context_token_budget: int = 8192
    rrf_k: int = 60                      # RRF constant
    default_top_k: int = 10
    short_query_tokens: int = 8          # below this, consider HyDE
    max_hops: int = 3                    # graph BFS depth cap
    degree_cap: int = 8                  # top-N edges expanded per node
    min_resolution_confidence: float = 0.70
    embedding_sim_threshold: float = 0.92
    near_dup_threshold: float = 0.97
    fail_closed: bool = True


SETTINGS = Settings()                    # import-time singleton; tests may replace fields
