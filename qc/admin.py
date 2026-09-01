from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from .models import Profile, Sample, SlumpTest, CuringStrengthTest


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile (role)"


class UserAdmin(DjangoUserAdmin):
    """Adds the QC role directly onto the standard Django user admin, so an
    admin can create an account and set its role (Lab Technician / Site
    Engineer / Project Manager) in a single screen at /admin/auth/user/add/."""
    inlines = (ProfileInline,)
    list_display = ("username", "first_name", "last_name", "role_display", "is_staff", "is_superuser")

    def role_display(self, obj):
        try:
            return obj.profile.get_role_display()
        except Profile.DoesNotExist:
            return "—"
    role_display.short_description = "Role"

    def get_inline_instances(self, request, obj=None):
        # Don't show the Profile inline while creating a user (it doesn't
        # exist yet); it appears once the user has been saved once.
        if not obj:
            return []
        return super().get_inline_instances(request, obj)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sample_id", "project_name", "concrete_grade", "casting_date", "registered_by")
    list_filter = ("concrete_grade",)
    search_fields = ("sample_id", "project_name", "batch_no")


@admin.register(SlumpTest)
class SlumpTestAdmin(admin.ModelAdmin):
    list_display = ("sample", "test_date", "slump_mm", "tested_by", "within_limit")
    list_filter = ("test_date",)


@admin.register(CuringStrengthTest)
class CuringStrengthTestAdmin(admin.ModelAdmin):
    list_display = ("sample", "curing_age_days", "test_date", "compressive_strength_nmm2", "tested_by")
    list_filter = ("curing_age_days",)


admin.site.register(Profile)
