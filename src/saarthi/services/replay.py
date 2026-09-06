from __future__ import annotations

from saarthi.domain.contracts import TraceEvent


class TraceReplayService:
    """Reconstructs the committed field view from append-only mutation evidence."""

    def replay_fields(self, events: list[TraceEvent]) -> tuple[dict[str, object], int]:
        fields: dict[str, object] = {}
        revision = 0
        for event in events:
            if event.event_type != "application_patch_decided":
                continue
            if not event.payload.get("accepted"):
                continue
            expected_previous = int(event.payload["previous_revision"])
            new_revision = int(event.payload["new_revision"])
            if expected_previous != revision or new_revision != revision + 1:
                raise ValueError(
                    "Trace contains a non-contiguous application revision."
                )
            field = event.payload.get("changed_field")
            if not field:
                raise ValueError("Accepted patch trace is missing the changed field.")
            fields[str(field)] = event.payload.get("new_value")
            revision = new_revision
        return fields, revision
