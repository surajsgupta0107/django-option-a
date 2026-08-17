def compute_kpis(servers):
    """servers: an already-fetched list of Server instances (with reminders/responses
    prefetched) — the one source of truth for dashboard math, used by the DRF
    /api/dashboard/kpis endpoint."""
    total = len(servers)
    under = [s for s in servers if s.status == "Underutilized"]
    reminded = [s for s in servers if s.reminders.count() > 0]
    responded = [s for s in reminded if s.responses.exists()]
    escalations = [s for s in under if s.reminders.count() >= 2 and not s.responses.exists()]

    reclaim_vcpu = sum((s.reclaimable_vcpu if s.reclaimable_vcpu is not None else (s.cpu_allocated or 0)) for s in under)
    reclaim_mem = sum(
        (s.reclaimable_memory_gb if s.reclaimable_memory_gb is not None else (s.mem_allocated_gb or 0) * 0.5)
        for s in under
    )

    status_breakdown = {"Optimal": 0, "Underutilized": 0, "Overutilized": 0}
    for s in servers:
        status_breakdown[s.status] += 1

    by_env = {}
    for s in servers:
        e = by_env.setdefault(s.environment, {"cpu": [], "memory": [], "storage": []})
        e["cpu"].append(s.cpu_pct)
        e["memory"].append(s.memory_pct)
        if s.storage_pct is not None:
            e["storage"].append(s.storage_pct)

    def avg(vals):
        return round(sum(vals) / len(vals), 1) if vals else None

    by_environment = [
        {"environment": env, "cpu": avg(v["cpu"]), "memory": avg(v["memory"]), "storage": avg(v["storage"])}
        for env, v in by_env.items()
    ]

    app_counts = {}
    for s in under:
        app_counts[s.application] = app_counts.get(s.application, 0) + 1
    top_apps = sorted(app_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]

    return {
        "total_servers": total,
        "underutilized_count": len(under),
        "underutilized_pct": round(len(under) / total * 100, 1) if total else 0,
        "reclaimable_vcpu": round(reclaim_vcpu, 1),
        "reclaimable_memory_gb": round(reclaim_mem, 1),
        "response_rate_pct": round(len(responded) / len(reminded) * 100, 1) if reminded else 0,
        "reminded_count": len(reminded),
        "escalations": len(escalations),
        "status_breakdown": status_breakdown,
        "by_environment": by_environment,
        "top_underutilized_applications": [{"application": a, "count": c} for a, c in top_apps],
    }
