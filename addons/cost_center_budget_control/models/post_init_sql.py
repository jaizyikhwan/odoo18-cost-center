def post_init_hook(env):
    cr = env.cr
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_account_move_line_analytic_distribution_gin ON account_move_line USING GIN (analytic_distribution)",
        "CREATE INDEX IF NOT EXISTS idx_account_move_line_company_state_date ON account_move_line (company_id, parent_state, date)",
        "CREATE INDEX IF NOT EXISTS idx_account_move_line_posted ON account_move_line (company_id, date) WHERE parent_state = 'posted'",
    ]
    for stmt in indexes:
        cr.execute(stmt)

    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'idx_account_move_alloc_ref_company_uniq'
            ) THEN
                IF EXISTS (
                    SELECT 1
                    FROM account_move
                    WHERE ref LIKE 'ALLOC/%'
                      AND state != 'cancel'
                    GROUP BY company_id, ref
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE WARNING 'Skipping creation of idx_account_move_alloc_ref_company_uniq: duplicates exist for ALLOC refs.';
                ELSE
                    EXECUTE 'CREATE UNIQUE INDEX idx_account_move_alloc_ref_company_uniq ON account_move (company_id, ref) WHERE ref LIKE ''ALLOC/%'' AND state != ''cancel''';
                END IF;
            END IF;
        END
        $$;
    """)
