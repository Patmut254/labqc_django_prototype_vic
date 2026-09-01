from django.contrib.auth import get_user_model


def notifications(request):
    """Small, cheap query so the topbar bell can show a live count (and a
    short list) of non-conforming results. Only runs for authenticated users."""
    if not request.user.is_authenticated:
        return {}
    from .models import SlumpTest, CuringStrengthTest

    items = []
    for t in SlumpTest.objects.select_related("sample").order_by("-test_date"):
        if not t.within_limit():
            items.append({
                "sample_id": t.sample.sample_id,
                "text": f"Slump {t.slump_mm}mm exceeds {t.sample.acceptance_limit_mm()}mm limit",
            })
    for t in CuringStrengthTest.objects.filter(curing_age_days=28).select_related("sample").order_by("-test_date"):
        if t.passed() is False:
            items.append({
                "sample_id": t.sample.sample_id,
                "text": f"28-day strength ({t.compressive_strength_nmm2()} N/mm2) below {t.sample.strength_limit()} N/mm2 limit",
            })
    return {
        "open_nonconformance_count": len(items),
        "notification_items": items[:8],
    }


def nav_permissions(request):
    """Exposes which sidebar sections the current user's role can reach, so
    the sidebar only shows links a role can actually use (mirrors the
    role_required() checks in views.py)."""
    if not request.user.is_authenticated:
        return {}
    user = request.user
    try:
        role = user.profile.role
    except Exception:
        role = None
    is_super = user.is_superuser
    return {
        "can_enter_data": is_super or role == "lab_technician",
        "can_view_reporting": is_super or role in ("site_engineer", "project_manager"),
    }
