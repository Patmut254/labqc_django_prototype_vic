from django.db import models
from django.contrib.auth.models import User

ROLE_CHOICES = [
    ("lab_technician", "Lab Technician"),
    ("site_engineer", "Site Engineer"),
    ("project_manager", "Project Manager"),
]

GRADE_LIMITS = {
    # Grade: (max acceptable slump mm, 28-day strength acceptance N/mm2)
    "Grade 20": (90, 20),
    "Grade 25": (90, 25),
    "Grade 30": (100, 30),
    "Grade 35": (100, 35),
}

GRADE_CHOICES = [(g, g) for g in GRADE_LIMITS]

CURING_AGE_CHOICES = [(7, "7 days"), (14, "14 days"), (21, "21 days"), (28, "28 days")]


class Profile(models.Model):
    """Extends Django's built-in User with the lab role used for dashboard restriction."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Sample(models.Model):
    """Sample Registration module — every batch is registered here first."""
    sample_id = models.CharField(max_length=20, unique=True, editable=False)
    project_name = models.CharField(max_length=200)
    batch_no = models.CharField(max_length=20)
    mixer_id = models.CharField(max_length=20)
    casting_date = models.DateField()
    concrete_grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    registered_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="registered_samples")
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.sample_id:
            last = Sample.objects.order_by("id").last()
            next_num = (last.id + 1) if last else 1
            self.sample_id = f"SMP-{next_num:04d}"
        super().save(*args, **kwargs)

    def acceptance_limit_mm(self):
        return GRADE_LIMITS[self.concrete_grade][0]

    def strength_limit(self):
        return GRADE_LIMITS[self.concrete_grade][1]

    def __str__(self):
        return self.sample_id


class SlumpTest(models.Model):
    """Slump Test module — fresh-concrete workability at the point of testing."""
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE, related_name="slump_test")
    test_date = models.DateField()
    slump_mm = models.PositiveIntegerField()
    tested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="slump_tests")
    witnessed_by = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    def within_limit(self):
        return self.slump_mm <= self.sample.acceptance_limit_mm()

    def status_label(self):
        return "Yes" if self.within_limit() else "No - Non-Conforming"

    def __str__(self):
        return f"{self.sample.sample_id} slump"


class CuringStrengthTest(models.Model):
    """Curing and Strength module — 7/14/21/28-day cycle, auto-calculated strength."""
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name="strength_tests")
    curing_age_days = models.PositiveSmallIntegerField(choices=CURING_AGE_CHOICES)
    test_date = models.DateField()
    load_kn = models.DecimalField(max_digits=8, decimal_places=2, help_text="Failure load in kN")
    cross_sectional_area_mm2 = models.DecimalField(max_digits=10, decimal_places=2)
    tested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="strength_tests")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("sample", "curing_age_days")
        ordering = ["sample__sample_id", "curing_age_days"]

    def compressive_strength_nmm2(self):
        # strength (N/mm2) = load (N) / area (mm2); load entered in kN -> convert to N
        if self.cross_sectional_area_mm2:
            return round((float(self.load_kn) * 1000) / float(self.cross_sectional_area_mm2), 2)
        return None

    def passed(self):
        if self.curing_age_days != 28:
            return None  # only the 28-day result is checked against the acceptance limit
        return self.compressive_strength_nmm2() >= self.sample.strength_limit()

    def __str__(self):
        return f"{self.sample.sample_id} @ {self.curing_age_days}d"
