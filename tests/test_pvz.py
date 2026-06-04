import pytest

from operator_day.pvz.shifts import (
    build_two_two_schedule,
    calculate_payroll,
    calculate_payroll_by_rate,
)


def test_two_two_schedule_alternates_every_two_days() -> None:
    schedule = build_two_two_schedule(["Анна", "Игорь"], days=6)

    assert [row["employee"] for row in schedule] == [
        "Анна",
        "Анна",
        "Игорь",
        "Игорь",
        "Анна",
        "Анна",
    ]


def test_payroll_counts_all_shifts() -> None:
    schedule = build_two_two_schedule(["Анна", "Игорь"], days=4)
    payroll = calculate_payroll(schedule, hourly_rate=200, hours_per_shift=12)

    assert payroll == {"Анна": 4800, "Игорь": 4800}


def test_schedule_requires_two_people() -> None:
    with pytest.raises(ValueError):
        build_two_two_schedule(["Анна"], days=3)


def test_payroll_can_use_individual_rates() -> None:
    schedule = build_two_two_schedule(["Anna", "Igor"], days=4)
    payroll = calculate_payroll_by_rate(
        schedule,
        hourly_rates={"Anna": 250, "Igor": 300},
        hours_per_shift=12,
    )

    assert payroll == {"Anna": 6000, "Igor": 7200}
