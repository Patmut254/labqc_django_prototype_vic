import json
from collections import OrderedDict
from datetime import date
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from .models import Sample, SlumpTest, CuringStrengthTest
from .forms import SampleForm, SlumpTestForm, CuringStrengthTestForm


def _role(user):
    try:
        return user.profile.role
    except Exception:
        return None


def role_required(*allowed_roles):
    """Restrict a view to specific Profile roles. Superusers always pass."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser or _role(request.user) in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(
                request,
                "Your account role doesn't have access to that section.",
            )
            return redirect("dashboard")
        return wrapped
    return decorator


@login_required
def dashboard(request):
    role = _role(request.user)

    total_samples = Sample.objects.count()
    total_slump = SlumpTest.objects.count()
    slump_nonconforming = sum(1 for t in SlumpTest.objects.select_related("sample") if not t.within_limit())

    strength_28 = CuringStrengthTest.objects.filter(curing_age_days=28).select_related("sample")
    total_strength = CuringStrengthTest.objects.count()
    strength_28_list = list(strength_28)
    strength_passed = sum(1 for t in strength_28_list if t.passed() is True)
    strength_checked = len(strength_28_list)
    pass_rate = round((strength_passed / strength_checked) * 100) if strength_checked else None

    # Samples registered per month, last 6 calendar months that have data (falls back gracefully if empty)
    monthly = (
        Sample.objects.annotate(month=TruncMonth("casting_date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    month_data = list(monthly)[-6:]
    max_month_count = max((m["count"] for m in month_data), default=0)
    chart_bars = [
        {
            "label": m["month"].strftime("%b %Y") if m["month"] else "—",
            "count": m["count"],
            "pct": round((m["count"] / max_month_count) * 100) if max_month_count else 0,
        }
        for m in month_data
    ]

    # Sample volume by concrete grade, ranked
    grade_counts = (
        Sample.objects.values("concrete_grade").annotate(count=Count("id")).order_by("-count")
    )
    max_grade_count = max((g["count"] for g in grade_counts), default=0)
    grade_ranking = [
        {
            "label": g["concrete_grade"],
            "count": g["count"],
            "pct": round((g["count"] / max_grade_count) * 100) if max_grade_count else 0,
        }
        for g in grade_counts
    ]

    context = {
        "role": role,
        "total_samples": total_samples,
        "total_slump": total_slump,
        "slump_nonconforming": slump_nonconforming,
        "total_strength": total_strength,
        "pass_rate": pass_rate,
        "strength_checked": strength_checked,
        "chart_bars": chart_bars,
        "grade_ranking": grade_ranking,
    }
    return render(request, "qc/dashboard.html", context)


@role_required("lab_technician")
def registration(request):
    if request.method == "POST":
        form = SampleForm(request.POST)
        if form.is_valid():
            sample = form.save(commit=False)
            sample.registered_by = request.user
            sample.save()
            messages.success(request, f"Sample {sample.sample_id} registered.")
            return redirect("registration")
    else:
        form = SampleForm()
    samples = Sample.objects.select_related("registered_by").order_by("-created_at")
    return render(request, "qc/registration.html", {"form": form, "samples": samples})


@role_required("lab_technician")
def slump_test(request):
    if request.method == "POST":
        form = SlumpTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.tested_by = request.user
            test.save()
            messages.success(request, f"Slump result recorded for {test.sample.sample_id}.")
            return redirect("slump_test")
    else:
        form = SlumpTestForm()
    tests = SlumpTest.objects.select_related("sample", "tested_by").order_by("-test_date")
    return render(request, "qc/slump_test.html", {"form": form, "tests": tests})


@role_required("lab_technician")
def curing_strength(request):
    if request.method == "POST":
        form = CuringStrengthTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.tested_by = request.user
            test.save()
            messages.success(request, f"{test.curing_age_days}-day result recorded for {test.sample.sample_id}.")
            return redirect("curing_strength")
    else:
        form = CuringStrengthTestForm()
    tests = CuringStrengthTest.objects.select_related("sample", "tested_by").order_by("-test_date")
    return render(request, "qc/curing_strength.html", {"form": form, "tests": tests})


@login_required
def sample_search(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        results = (
            Sample.objects.filter(
                Q(sample_id__icontains=query)
                | Q(project_name__icontains=query)
                | Q(batch_no__icontains=query)
                | Q(mixer_id__icontains=query)
            )
            .select_related("registered_by")
            .order_by("-created_at")
        )
    return render(request, "qc/search_results.html", {"query": query, "results": results})


@role_required("site_engineer", "project_manager")
def reporting(request):
    total_samples = Sample.objects.count()
    total_slump = SlumpTest.objects.count()
    slump_nonconforming = [t for t in SlumpTest.objects.select_related("sample") if not t.within_limit()]
    strength_tests = CuringStrengthTest.objects.select_related("sample")
    total_strength = strength_tests.count()
    strength_28 = [t for t in strength_tests if t.curing_age_days == 28]
    strength_failed = [t for t in strength_28 if t.passed() is False]
    strength_passed = [t for t in strength_28 if t.passed() is True]

    non_conformance_log = []
    for t in slump_nonconforming:
        non_conformance_log.append({
            "sheet": "Slump Test", "sample_id": t.sample.sample_id,
            "issue": f"Slump {t.slump_mm}mm exceeds {t.sample.acceptance_limit_mm()}mm limit",
            "date": t.test_date,
        })
    for t in strength_failed:
        non_conformance_log.append({
            "sheet": "Curing and Strength", "sample_id": t.sample.sample_id,
            "issue": f"28-day compressive strength ({t.compressive_strength_nmm2()} N/mm2) below acceptance limit ({t.sample.strength_limit()} N/mm2)",
            "date": t.test_date,
        })
    non_conformance_log.sort(key=lambda r: r["date"])

    # Chart data: strength development per sample across curing ages
    # (prefer samples that have all four curing-age results, for a cleaner demonstration chart)
    complete_ids = [
        s.id for s in Sample.objects.all()
        if s.strength_tests.count() == 4
    ][:6]
    chart_samples = Sample.objects.filter(id__in=complete_ids)
    curing_chart = {"ages": [7, 14, 21, 28], "series": []}
    for s in chart_samples:
        values = []
        for age in [7, 14, 21, 28]:
            t = s.strength_tests.filter(curing_age_days=age).first()
            values.append(t.compressive_strength_nmm2() if t else None)
        curing_chart["series"].append({"label": s.sample_id, "data": values})

    # --- Figure 6.1: recorded slump vs acceptance limit, per sample ---
    slump_chart = {"labels": [], "slump": [], "limit": []}
    for t in SlumpTest.objects.select_related("sample").order_by("sample__sample_id"):
        slump_chart["labels"].append(t.sample.sample_id)
        slump_chart["slump"].append(t.slump_mm)
        slump_chart["limit"].append(t.sample.acceptance_limit_mm())

    # --- Figure 6.3: distribution of test outcomes across all curing/strength results ---
    outcome_counts = {"Pass": 0, "Fail - Non-Conforming": 0, "In Progress": 0}
    for t in strength_tests:
        if t.curing_age_days != 28:
            outcome_counts["In Progress"] += 1
        elif t.passed():
            outcome_counts["Pass"] += 1
        else:
            outcome_counts["Fail - Non-Conforming"] += 1
    outcome_pie = {"labels": list(outcome_counts.keys()), "data": list(outcome_counts.values())}

    # --- Figure 6.4: non-conformance count, slump vs 28-day strength ---
    nonconformance_bar = {
        "labels": ["Slump Test", "Compressive Strength Test"],
        "data": [len(slump_nonconforming), len(strength_failed)],
    }

    context = {
        "total_samples": total_samples,
        "total_slump": total_slump,
        "slump_nonconforming_count": len(slump_nonconforming),
        "total_strength": total_strength,
        "strength_failed_count": len(strength_failed),
        "strength_passed_count": len(strength_passed),
        "non_conformance_log": non_conformance_log,
        "slump_chart": json.dumps(slump_chart),
        "outcome_pie": json.dumps(outcome_pie),
        "nonconformance_bar": json.dumps(nonconformance_bar),
        "curing_chart": json.dumps(curing_chart),
    }
    return render(request, "qc/reporting.html", context)
