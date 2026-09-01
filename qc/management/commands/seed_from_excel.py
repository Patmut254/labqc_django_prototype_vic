"""
Seeds the database from the dissertation's seed_source.xlsx workbook, and
creates every login account documented in README.md:

    technician / engineer / manager / admin   (password: labqc2026)
    user1 ... user10                          (password: labqc2026, role per
                                                the "Role" column in the
                                                Registration sheet - these are
                                                NOT all lab_technician)

Usage:
    python manage.py seed_from_excel seed_source.xlsx
    python manage.py seed_from_excel               # defaults to seed_source.xlsx in BASE_DIR

Safe to re-run: users are updated in place (get_or_create + set_password),
and samples/tests use update_or_create keyed on their natural identifiers,
so running this twice does not create duplicates.
"""
import datetime
from decimal import Decimal

import openpyxl
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from qc.models import Profile, Sample, SlumpTest, CuringStrengthTest

DEMO_PASSWORD = "labqc2026"

ROLE_LABEL_TO_CODE = {
    "Lab Technician": "lab_technician",
    "Site Engineer": "site_engineer",
    "Project Manager": "project_manager",
}


def _parse_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value).strip())


def _rows(ws, header_row_index):
    """Yield non-empty data rows below the given 0-indexed header row."""
    all_rows = list(ws.iter_rows(values_only=True))
    for row in all_rows[header_row_index + 1:]:
        if any(cell is not None for cell in row):
            yield row


class Command(BaseCommand):
    help = "Seed the QC database from seed_source.xlsx and create all documented demo accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "path", nargs="?", default=str(settings.BASE_DIR / "seed_source.xlsx"),
            help="Path to the seed workbook (defaults to seed_source.xlsx in the project root).",
        )

    def handle(self, *args, **options):
        path = options["path"]
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except FileNotFoundError:
            raise CommandError(f"Workbook not found at {path}")

        # ---- 1. Named role-demo accounts + admin superuser -------------------
        self.stdout.write("Creating role-demo accounts (technician/engineer/manager/admin)...")
        role_demo_accounts = {
            "technician": "lab_technician",
            "engineer": "site_engineer",
            "manager": "project_manager",
        }
        for username, role in role_demo_accounts.items():
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(DEMO_PASSWORD)
            user.is_staff = False
            user.save()
            Profile.objects.update_or_create(user=user, defaults={"role": role})

        admin_user, _ = User.objects.get_or_create(username="admin")
        admin_user.set_password(DEMO_PASSWORD)
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # ---- 2. Registration sheet drives which role each User N gets -------
        reg_ws = wb["Registration"]
        reg_rows = list(_rows(reg_ws, header_row_index=3))
        user_roles = {}  # "User 1" -> "Lab Technician" (first row wins; roles are consistent per user)
        for (sample_id, project_name, batch_no, mixer_id, casting_date,
             grade, registered_by, role_label, notes) in reg_rows:
            user_roles.setdefault(registered_by, role_label)

        self.stdout.write(f"Creating {len(user_roles)} numbered user accounts with their real roles...")
        person_to_username = {}
        for person_label, role_label in user_roles.items():
            # "User 7" -> "user7"
            num = "".join(ch for ch in person_label if ch.isdigit())
            username = f"user{num}"
            person_to_username[person_label] = username
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(DEMO_PASSWORD)
            user.first_name = person_label
            user.save()
            role_code = ROLE_LABEL_TO_CODE.get(role_label, "lab_technician")
            Profile.objects.update_or_create(user=user, defaults={"role": role_code})
            self.stdout.write(f"  {username} -> {role_label}")

        def resolve_user(person_label):
            username = person_to_username.get(person_label)
            if not username:
                # Defensive fallback if the sheet ever references someone
                # outside Registration's "Registered By" column.
                num = "".join(ch for ch in person_label if ch.isdigit()) or "0"
                username = f"user{num}"
                person_to_username[person_label] = username
                u, _ = User.objects.get_or_create(username=username)
                u.set_password(DEMO_PASSWORD)
                u.save()
            return User.objects.get(username=username)

        # ---- 3. Registration -> Sample -----------------------------------
        self.stdout.write(f"Seeding {len(reg_rows)} samples...")
        samples_by_id = {}
        for (sample_id, project_name, batch_no, mixer_id, casting_date,
             grade, registered_by, role_label, notes) in reg_rows:
            sample, _ = Sample.objects.update_or_create(
                sample_id=sample_id,
                defaults=dict(
                    project_name=project_name,
                    batch_no=batch_no,
                    mixer_id=mixer_id,
                    casting_date=_parse_date(casting_date),
                    concrete_grade=grade,
                    registered_by=resolve_user(registered_by),
                    notes=notes or "",
                ),
            )
            samples_by_id[sample_id] = sample

        # ---- 4. Slump Test sheet -------------------------------------------
        slump_ws = wb["Slump Test"]
        slump_rows = list(_rows(slump_ws, header_row_index=3))
        self.stdout.write(f"Seeding {len(slump_rows)} slump tests...")
        for (sample_id, test_date, grade, slump_mm, limit_mm, within_limit,
             tested_by, witnessed_by, notes) in slump_rows:
            sample = samples_by_id.get(sample_id)
            if not sample:
                continue
            SlumpTest.objects.update_or_create(
                sample=sample,
                defaults=dict(
                    test_date=_parse_date(test_date),
                    slump_mm=int(slump_mm),
                    tested_by=resolve_user(tested_by),
                    witnessed_by=witnessed_by or "",
                    notes=notes or "",
                ),
            )

        # ---- 5. Curing and Strength sheet ----------------------------------
        curing_ws = wb["Curing and Strength"]
        curing_rows = list(_rows(curing_ws, header_row_index=3))
        self.stdout.write(f"Seeding {len(curing_rows)} curing/strength results...")
        for (sample_id, casting_date, age_days, test_date, cube_ref, load_kn,
             area_mm2, strength, limit, result, tested_by) in curing_rows:
            sample = samples_by_id.get(sample_id)
            if not sample:
                continue
            CuringStrengthTest.objects.update_or_create(
                sample=sample,
                curing_age_days=int(age_days),
                defaults=dict(
                    test_date=_parse_date(test_date),
                    load_kn=Decimal(str(load_kn)),
                    cross_sectional_area_mm2=Decimal(str(area_mm2)),
                    tested_by=resolve_user(tested_by),
                    notes="",
                ),
            )

        total_samples = Sample.objects.count()
        total_slump = SlumpTest.objects.count()
        total_strength = CuringStrengthTest.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Done. {total_samples} samples, {total_slump} slump tests, "
            f"{total_strength} curing/strength results. "
            f"{len(user_roles)} numbered accounts + technician/engineer/manager/admin "
            f"all set to password '{DEMO_PASSWORD}'."
        ))
