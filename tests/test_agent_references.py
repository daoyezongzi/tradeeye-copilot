from copilot.agent.references import ReferenceValidator


def test_validator_keeps_registered_references():
    validator = ReferenceValidator()
    validator.register(fact_ids=["revenue", "net_profit"], evidence_ids=["000001.SZ:20250630:revenue"])

    kept = validator.filter(
        [
            {"fact_id": "revenue"},
            {"evidence_id": "000001.SZ:20250630:revenue"},
        ]
    )

    assert kept == [
        {"fact_id": "revenue"},
        {"evidence_id": "000001.SZ:20250630:revenue"},
    ]


def test_validator_drops_fake_and_foreign_references():
    validator = ReferenceValidator()
    validator.register(fact_ids=["revenue"], evidence_ids=["000001.SZ:20250630:revenue"])

    kept = validator.filter(
        [
            {"fact_id": "fake_fact"},
            {"evidence_id": "000002.SZ:20250630:revenue"},
            {"fact_id": "revenue", "evidence_id": "000001.SZ:20250630:revenue"},
        ]
    )

    assert kept == [{"fact_id": "revenue", "evidence_id": "000001.SZ:20250630:revenue"}]


def test_validator_ignores_empty():
    validator = ReferenceValidator()
    assert validator.filter([]) == []
