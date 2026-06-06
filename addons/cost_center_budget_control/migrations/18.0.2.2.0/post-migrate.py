def migrate(cr, version):
    """Post-migration hook executed after module upgrade to 18.0.2.2.0.

    Verify post-migration invariants here. Currently a no-op;
    the touch query confirms the hook ran.
    """
    cr.execute("SELECT 1")
