"""Deterministic qualification inputs for the background execution gates."""
import hashlib
import json


def workload():
    tasks = [
        {"workspace": workspace, "task": index, "points": index % 13}
        for workspace in (0, 1)
        for index in range(1, 501)
    ]
    reminders = [
        {"workspace": index % 2, "task": index // 2 + 1,
         "offset_seconds": index // 2 if index < 120 else 20,
         "expires_after_seconds": 60}
        for index in range(150)
    ]
    reports = [
        {"workspace": index % 2, "report": index, "first": 1, "last": 500,
         "expires_after_seconds": 180, "attempt_seconds": 20}
        for index in range(40)
    ]
    return {"tasks": tasks, "reminders": reminders, "reports": reports}


def verify_profile():
    first = workload()
    assert first == workload()
    tasks = {(row["workspace"], row["task"]) for row in first["tasks"]}
    reminders = {(row["workspace"], row["task"]) for row in first["reminders"]}
    assert len(tasks) == 1000 and len(reminders) == 150 and reminders <= tasks
    assert sum(row["offset_seconds"] == 20 for row in first["reminders"]) == 32
    assert len(first["reports"]) == 40
    for workspace in (0, 1):
        assert sum(row["workspace"] == workspace for row in first["reports"]) == 20
    assert max(len(json.dumps(row)) for row in first["reports"] + first["reminders"]) <= 128
    digest = hashlib.sha256(json.dumps(first, sort_keys=True).encode()).hexdigest()
    return {"tasks": len(tasks), "reminders": len(reminders), "bulk": 40, "sha256": digest}


if __name__ == "__main__":
    print(json.dumps(verify_profile(), sort_keys=True))
