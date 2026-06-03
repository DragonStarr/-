from operator_day.bot.render import render_task
from operator_day.domain import ActionRisk, ModuleId, TaskAction


def test_render_task_is_plain_russian_without_commands() -> None:
    task = TaskAction(
        module_id=ModuleId.REVIEWS,
        title="Ответить покупателю",
        short_text="Готов короткий ответ. Отправить?",
        action_label="Отправить",
        payload={},
        priority=1,
        risk=ActionRisk.CONFIRM,
    )

    text = render_task(task)

    assert "/start" not in text
    assert "Ответить покупателю" in text
    assert "Готов короткий ответ" in text
