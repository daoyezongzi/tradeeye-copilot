class TushareTokenMissing(RuntimeError):
    pass


def create_tushare_pro(token: str | None, tushare_module=None):
    if not token:
        raise TushareTokenMissing("TUSHARE_TOKEN is required to create a Tushare client")
    if tushare_module is None:
        import tushare as tushare_module
    return tushare_module.pro_api(token)
