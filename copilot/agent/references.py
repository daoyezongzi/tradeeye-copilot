from collections.abc import Iterable


class ReferenceValidator:
    """校验回答引用是否真实存在且属于本会话可引用集合。"""

    def __init__(self) -> None:
        self._facts: set[str] = set()
        self._evidence: set[str] = set()

    def register(self, fact_ids: Iterable[str] = (), evidence_ids: Iterable[str] = ()) -> None:
        self._facts.update(fact_ids)
        self._evidence.update(evidence_ids)

    def filter(self, references: list[dict]) -> list[dict]:
        kept = []
        for reference in references:
            if not isinstance(reference, dict):
                continue
            fact_id = reference.get("fact_id")
            evidence_id = reference.get("evidence_id")
            if fact_id is not None and fact_id not in self._facts:
                fact_id = None
            if evidence_id is not None and evidence_id not in self._evidence:
                evidence_id = None
            if fact_id is None and evidence_id is None:
                continue
            kept.append(
                {
                    key: value
                    for key, value in (("fact_id", fact_id), ("evidence_id", evidence_id))
                    if value is not None
                }
            )
        return kept
