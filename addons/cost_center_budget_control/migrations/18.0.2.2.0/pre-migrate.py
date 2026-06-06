def migrate(cr, version):
    """Pre-migration hook executed before module upgrade to 18.0.2.2.0.

    Place schema or data fixes here when needed for future versions.
    Currently a no-op; the touch query confirms the hook ran.
    """
    cr.execute("SELECT 1")
