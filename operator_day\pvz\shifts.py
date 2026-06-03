from __future__ import annotations


def build_two_two_schedule(names: list[str], *, days: int) -> list[dict[str, object]]:
    if len(names) < 2:
        raise ValueError("Для графика 2/2 нужны минимум два сотрудника")
    schedule: list[dict[str, object]] = []
    for day in range(1, days + 1):
        pair_index = ((day - 1) // 2) % len(names)
        schedule.append({"day": day, "employee": names[pair_index], "shift": "day"})
    return schedule


def calculate_payroll(
    schedule: list[dict[str, object]], *, hourly_rate: float, hours_per_shift: int
) -> dict[str, float]:
    payroll: dict[str, float] = {}
    for row in schedule:
        employee = str(row["employee"])
        payroll[employee] = payroll.get(employee, 0) + hourly_rate * hours_per_shift
    return payroll


def calculate_payroll_by_rate(
    schedule: list[dict[str, object]],
    *,
    hourly_rates: dict[str, float],
    hours_per_shift: int,
) -> dict[str, float]:
    payroll: dict[str, float] = {}
    for row in schedule:
        employee = str(row["employee"])
        rate = float(hourly_rates.get(employee, 0))
        payroll[employee] = payroll.get(employee, 0) + rate * hours_per_shift
    return payroll
