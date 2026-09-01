from django import forms
from .models import Sample, SlumpTest, CuringStrengthTest


class SampleForm(forms.ModelForm):
    class Meta:
        model = Sample
        fields = ["project_name", "batch_no", "mixer_id", "casting_date", "concrete_grade", "notes"]
        widgets = {
            "casting_date": forms.DateInput(attrs={"type": "date"}),
            "project_name": forms.TextInput(attrs={"placeholder": "e.g. Lagos-Ibadan Expressway Rehabilitation"}),
            "batch_no": forms.TextInput(attrs={"placeholder": "B-021"}),
            "mixer_id": forms.TextInput(attrs={"placeholder": "MX-01"}),
        }


class SlumpTestForm(forms.ModelForm):
    class Meta:
        model = SlumpTest
        fields = ["sample", "test_date", "slump_mm", "witnessed_by", "notes"]
        widgets = {"test_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # only samples that don't already have a slump test yet
        self.fields["sample"].queryset = Sample.objects.filter(slump_test__isnull=True)


class CuringStrengthTestForm(forms.ModelForm):
    class Meta:
        model = CuringStrengthTest
        fields = ["sample", "curing_age_days", "test_date", "load_kn", "cross_sectional_area_mm2", "notes"]
        widgets = {"test_date": forms.DateInput(attrs={"type": "date"})}
