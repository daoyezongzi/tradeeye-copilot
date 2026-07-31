def summarize_scan_counts(scans) -> dict[str, int]:
    return {
        "days": len(scans),
        "disclosed_count": sum(scan.disclosed_count for scan in scans),
        "ok_count": sum(scan.ok_count for scan in scans),
        "data_not_ready_count": sum(scan.data_not_ready_count for scan in scans),
        "data_incomplete_count": sum(scan.data_incomplete_count for scan in scans),
        "error_count": sum(scan.error_count for scan in scans),
    }
