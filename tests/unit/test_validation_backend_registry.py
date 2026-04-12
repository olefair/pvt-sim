"""Tests for the external validation backend registry."""

from __future__ import annotations

from pvtcore.validation import (
    ValidationBackendAdoptionStatus,
    CodeReusePolicy,
    ValidationBackendRole,
    approved_validation_backends,
    get_validation_backend,
    iter_validation_backends,
    recommended_coursework_backends,
)


def test_backend_registry_contains_expected_backends() -> None:
    backends = {backend.backend_id: backend for backend in iter_validation_backends()}

    assert set(backends) == {"thermopack", "thermo", "prode", "dwsim", "pyreservoir"}
    assert backends["thermopack"].role == ValidationBackendRole.EOS_REFERENCE
    assert backends["thermo"].role == ValidationBackendRole.PROPERTY_DATA
    assert backends["dwsim"].role == ValidationBackendRole.PROCESS_SIMULATOR
    assert backends["pyreservoir"].role == ValidationBackendRole.LAB_PVT_POSTPROCESSOR


def test_approved_validation_backends_follow_permissive_only_policy() -> None:
    approved = {backend.backend_id: backend for backend in approved_validation_backends()}

    assert set(approved) == {"thermopack", "thermo"}
    assert approved["thermopack"].adoption_status == ValidationBackendAdoptionStatus.APPROVED
    assert approved["thermo"].adoption_status == ValidationBackendAdoptionStatus.APPROVED


def test_backend_registry_reuse_policies_match_repo_policy() -> None:
    thermopack = get_validation_backend("thermopack")
    thermo = get_validation_backend("thermo")
    prode = get_validation_backend("prode")
    dwsim = get_validation_backend("dwsim")
    pyreservoir = get_validation_backend("pyreservoir")

    assert thermopack.code_reuse_policy == CodeReusePolicy.PERMISSIVE_REUSE
    assert thermo.code_reuse_policy == CodeReusePolicy.PERMISSIVE_REUSE
    assert prode.code_reuse_policy == CodeReusePolicy.VALIDATION_ONLY
    assert dwsim.code_reuse_policy == CodeReusePolicy.VALIDATION_ONLY
    assert pyreservoir.code_reuse_policy == CodeReusePolicy.HOLD_FOR_REVIEW
    assert prode.adoption_status == ValidationBackendAdoptionStatus.EXCLUDED_BY_LICENSE_POLICY
    assert dwsim.adoption_status == ValidationBackendAdoptionStatus.EXCLUDED_BY_LICENSE_POLICY
    assert pyreservoir.adoption_status == ValidationBackendAdoptionStatus.PENDING_LICENSE_REVIEW


def test_recommended_coursework_backend_order_prioritizes_equation_backends_first() -> None:
    ordered = [backend.backend_id for backend in recommended_coursework_backends()]

    assert ordered == ["thermopack", "thermo"]
