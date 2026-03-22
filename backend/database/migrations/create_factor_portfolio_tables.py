"""
Create factor portfolio persistence tables.
Idempotent - checks table existence before creating.
"""
import logging

from sqlalchemy import text

from database.connection import engine

logger = logging.getLogger(__name__)


def upgrade():
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN "
                "('factor_research_runs', 'factor_portfolio_candidates', 'factor_portfolio_deployments')"
            )
        )
        existing = {row[0] for row in result}

        if "factor_research_runs" not in existing:
            conn.execute(
                text(
                    """
                CREATE TABLE factor_research_runs (
                    id SERIAL PRIMARY KEY,
                    exchange VARCHAR(20) NOT NULL DEFAULT 'hyperliquid',
                    top_n_symbols INTEGER NOT NULL DEFAULT 20,
                    lookback_days INTEGER NOT NULL DEFAULT 180,
                    objective VARCHAR(50) NOT NULL DEFAULT 'return_over_drawdown',
                    factor_scope VARCHAR(50) NOT NULL DEFAULT 'builtin_only',
                    period VARCHAR(10) NOT NULL DEFAULT '1h',
                    prescreen_limit INTEGER NOT NULL DEFAULT 10,
                    status VARCHAR(20) NOT NULL DEFAULT 'success',
                    result_json TEXT,
                    top_factor_json TEXT,
                    top_portfolio_json TEXT,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_factor_research_runs_created_at "
                    "ON factor_research_runs(created_at)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_factor_research_runs_status "
                    "ON factor_research_runs(status)"
                )
            )
            logger.info("Created factor_research_runs table")

        if "factor_portfolio_candidates" not in existing:
            conn.execute(
                text(
                    """
                CREATE TABLE factor_portfolio_candidates (
                    id SERIAL PRIMARY KEY,
                    run_id INTEGER NOT NULL REFERENCES factor_research_runs(id),
                    name VARCHAR(120) NOT NULL,
                    construction_method VARCHAR(80) NOT NULL,
                    score FLOAT,
                    component_count INTEGER NOT NULL DEFAULT 0,
                    components_json TEXT NOT NULL,
                    metrics_json TEXT,
                    is_recommended BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT factor_portfolio_candidates_run_name_key
                        UNIQUE (run_id, name)
                )
                """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_factor_portfolio_candidates_run_id "
                    "ON factor_portfolio_candidates(run_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_factor_portfolio_candidates_recommended "
                    "ON factor_portfolio_candidates(is_recommended)"
                )
            )
            logger.info("Created factor_portfolio_candidates table")

        if "factor_portfolio_deployments" not in existing:
            conn.execute(
                text(
                    """
                CREATE TABLE factor_portfolio_deployments (
                    id SERIAL PRIMARY KEY,
                    run_id INTEGER REFERENCES factor_research_runs(id),
                    portfolio_id INTEGER NOT NULL REFERENCES factor_portfolio_candidates(id),
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    mode VARCHAR(20) NOT NULL DEFAULT 'paper',
                    status VARCHAR(20) NOT NULL DEFAULT 'deployed',
                    program_id INTEGER REFERENCES trading_programs(id),
                    binding_id INTEGER REFERENCES account_program_bindings(id),
                    deployment_config TEXT,
                    deployment_result TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_factor_portfolio_deployments_portfolio_id "
                    "ON factor_portfolio_deployments(portfolio_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_factor_portfolio_deployments_account_mode "
                    "ON factor_portfolio_deployments(account_id, mode)"
                )
            )
            logger.info("Created factor_portfolio_deployments table")

        conn.commit()

