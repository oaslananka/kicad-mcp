from scripts import check_submission_readiness


def test_readme_listing_references_use_current_package_version() -> None:
    result = check_submission_readiness._readme_check()

    assert result.status == "PASS"
