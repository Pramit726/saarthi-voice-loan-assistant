from __future__ import annotations

from copy import deepcopy

from .contracts import (
    ApplicationDraft,
    ApplicationPatch,
    CommitResult,
    CommittedFieldValue,
    FieldChangeRecord,
    utc_now,
)
from .enums import ChangeKind, DraftStatus, FieldId
from .fields import FIELD_ORDER, FieldValidationError, normalise_and_validate


class GuardedReducer:
    """The sole authority that may mutate committed application data."""

    projection_dependencies = {FieldId.REQUESTED_AMOUNT, FieldId.PREFERRED_TENURE}

    def apply(
        self,
        draft: ApplicationDraft,
        patch: ApplicationPatch,
        *,
        current_generation_id: int,
        seen_idempotency_keys: set[str] | None = None,
    ) -> CommitResult:
        rejection = self._precondition_failure(
            draft,
            patch,
            current_generation_id=current_generation_id,
            seen_idempotency_keys=seen_idempotency_keys or set(),
        )
        if rejection:
            return CommitResult(
                accepted=False,
                reason_code=rejection,
                previous_revision=draft.revision,
                new_revision=draft.revision,
            )

        try:
            normalized = normalise_and_validate(patch.target_field, patch.normalized_candidate)
        except FieldValidationError as exc:
            return CommitResult(
                accepted=False,
                reason_code=exc.code,
                previous_revision=draft.revision,
                new_revision=draft.revision,
            )

        old_record = draft.fields.get(patch.target_field)
        old_value = old_record.typed_value if old_record else None
        change_kind = ChangeKind.CORRECTION if old_record else ChangeKind.INITIAL
        if old_record and patch.change_kind is not ChangeKind.CORRECTION:
            return CommitResult(
                accepted=False,
                reason_code="existing_field_requires_correction",
                previous_revision=draft.revision,
                new_revision=draft.revision,
            )

        new_revision = draft.revision + 1
        updated = deepcopy(draft)
        updated.fields[patch.target_field] = CommittedFieldValue(
            field_id=patch.target_field,
            typed_value=normalized,
            source_turn_id=patch.source_turn_id,
            source_span=patch.source_span,
            normalizer_version=patch.normalizer_version,
            validator_version=patch.validator_version,
            committed_at_revision=new_revision,
            last_change_kind=change_kind,
        )
        updated.change_history.append(
            FieldChangeRecord(
                target_field=patch.target_field,
                old_value=old_value,
                new_value=normalized,
                source_turn_id=patch.source_turn_id,
                change_kind=change_kind,
                before_revision=draft.revision,
                after_revision=new_revision,
            )
        )
        updated.revision = new_revision
        updated.updated_at = utc_now()
        if patch.target_field in self.projection_dependencies:
            updated.current_projection = None
        if all(field_id in updated.fields for field_id in FIELD_ORDER):
            updated.status = DraftStatus.READY_FOR_REVIEW

        return CommitResult(
            accepted=True,
            reason_code="committed",
            previous_revision=draft.revision,
            new_revision=new_revision,
            changed_field=patch.target_field,
            previous_value=old_value,
            new_value=normalized,
            checkpoint_effect="advance_after_commit",
            draft=updated,
        )

    @staticmethod
    def _precondition_failure(
        draft: ApplicationDraft,
        patch: ApplicationPatch,
        *,
        current_generation_id: int,
        seen_idempotency_keys: set[str],
    ) -> str | None:
        if draft.status is DraftStatus.CANCELLED:
            return "draft_cancelled"
        if patch.session_id != draft.owner_session_id:
            return "session_mismatch"
        if patch.application_id != draft.application_id:
            return "application_mismatch"
        if patch.expected_application_revision != draft.revision:
            return "application_revision_conflict"
        if patch.source_generation_id != current_generation_id:
            return "stale_generation"
        if patch.idempotency_key in seen_idempotency_keys:
            return "duplicate_idempotency_key"
        if not patch.explicit_target:
            return "target_not_explicit"
        if patch.confirmation_required and not patch.confirmed:
            return "confirmation_required"
        if not patch.source_span.strip():
            return "missing_source_evidence"
        return None
