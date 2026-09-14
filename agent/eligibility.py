from dataclasses import dataclass, field

from agent.profile import UserProfile

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"
INSUFFICIENT_INFO = "insufficient_info"


@dataclass
class EligibilityResult:
    scheme_id: str
    status: str
    reasons: list[str] = field(default_factory=list)
    matched_clause_ids: list[str] = field(default_factory=list)


def _has_existing_pension(profile: UserProfile) -> bool:
    return any("pension" in b.lower() for b in profile.existing_benefits)


def check_pmkisan(profile: UserProfile) -> EligibilityResult:
    if profile.land_size_acres is None:
        return EligibilityResult(
            "pmkisan", INSUFFICIENT_INFO,
            ["landholding size not provided"], ["pmkisan-3.1"],
        )
    if profile.land_size_acres <= 0:
        return EligibilityResult(
            "pmkisan", NOT_ELIGIBLE,
            ["PM-KISAN requires the applicant to be a landholding farmer family"],
            ["pmkisan-3.1"],
        )
    if profile.is_income_tax_payer:
        return EligibilityResult(
            "pmkisan", NOT_ELIGIBLE,
            ["income tax payers are excluded from PM-KISAN"], ["pmkisan-4.4"],
        )
    if profile.is_government_employee:
        return EligibilityResult(
            "pmkisan", NOT_ELIGIBLE,
            ["serving or retired government employees above the pension threshold are excluded"],
            ["pmkisan-4.3"],
        )
    return EligibilityResult(
        "pmkisan", ELIGIBLE,
        ["applicant holds agricultural land and no known exclusion applies"],
        ["pmkisan-3.1"],
    )


def check_pmjay(profile: UserProfile) -> EligibilityResult:
    return EligibilityResult(
        "pmjay", INSUFFICIENT_INFO,
        ["PM-JAY eligibility is determined by checking the SECC/RSBY beneficiary "
         "database, which cannot be verified from self-reported profile information alone"],
        ["pmjay-7"],
    )


def check_nsap(profile: UserProfile) -> EligibilityResult:
    if profile.age is None:
        return EligibilityResult("nsap", INSUFFICIENT_INFO, ["age not provided"], ["nsap-2.3"])
    if profile.age < 60:
        return EligibilityResult(
            "nsap", NOT_ELIGIBLE,
            ["IGNOAPS requires the applicant to be 60 years or older"], ["nsap-2.3"],
        )
    if _has_existing_pension(profile):
        return EligibilityResult(
            "nsap", NOT_ELIGIBLE,
            ["already receiving a pension under another government scheme"], ["nsap-2.4.3"],
        )
    if profile.is_bpl is None:
        return EligibilityResult(
            "nsap", INSUFFICIENT_INFO,
            ["Below Poverty Line status not provided"], ["nsap-2.3"],
        )
    if profile.is_bpl is False:
        return EligibilityResult(
            "nsap", NOT_ELIGIBLE,
            ["IGNOAPS requires the applicant to belong to a Below Poverty Line household"],
            ["nsap-2.3"],
        )
    return EligibilityResult(
        "nsap", ELIGIBLE,
        ["applicant is 60 or older and belongs to a Below Poverty Line household"],
        ["nsap-2.3"],
    )


def check_pmayg(profile: UserProfile) -> EligibilityResult:
    if profile.has_pucca_house is None:
        return EligibilityResult(
            "pmayg", INSUFFICIENT_INFO, ["housing status not provided"], ["pmayg-4.1.1"],
        )
    if profile.has_pucca_house is True:
        return EligibilityResult(
            "pmayg", NOT_ELIGIBLE,
            ["households that already own a pucca house are excluded"], ["pmayg-annexureI"],
        )
    if profile.is_income_tax_payer:
        return EligibilityResult(
            "pmayg", NOT_ELIGIBLE, ["income tax payers are excluded"], ["pmayg-annexureI"],
        )
    if profile.is_government_employee:
        return EligibilityResult(
            "pmayg", NOT_ELIGIBLE,
            ["households with a government employee are excluded"], ["pmayg-annexureI"],
        )
    if profile.monthly_income is not None and profile.monthly_income > 10000:
        return EligibilityResult(
            "pmayg", NOT_ELIGIBLE,
            ["households earning more than Rs. 10,000 per month are excluded"],
            ["pmayg-annexureI"],
        )
    return EligibilityResult(
        "pmayg", ELIGIBLE,
        ["applicant is houseless or living in a kutcha house and no known exclusion applies"],
        ["pmayg-4.1.1", "pmayg-5.1.1"],
    )


def check_tnoap(profile: UserProfile) -> EligibilityResult:
    if profile.state and profile.state.lower() != "tamil nadu":
        return EligibilityResult(
            "tnoap", NOT_ELIGIBLE,
            ["this scheme is only for residents of Tamil Nadu"], ["tnoap-3.1"],
        )
    if profile.age is None:
        return EligibilityResult("tnoap", INSUFFICIENT_INFO, ["age not provided"], ["tnoap-3.1"])
    if profile.age < 60:
        return EligibilityResult(
            "tnoap", NOT_ELIGIBLE,
            ["applicant must be 60 years or older"], ["tnoap-3.1"],
        )
    if _has_existing_pension(profile):
        return EligibilityResult(
            "tnoap", NOT_ELIGIBLE,
            ["already receiving a pension under another government scheme"], ["tnoap-4.1"],
        )
    if profile.is_destitute is None:
        return EligibilityResult(
            "tnoap", INSUFFICIENT_INFO,
            ["destitution and income status not provided"], ["tnoap-3.2"],
        )
    if profile.is_destitute is False:
        return EligibilityResult(
            "tnoap", NOT_ELIGIBLE,
            ["applicant must be destitute with income below the state-notified threshold"],
            ["tnoap-3.2"],
        )
    return EligibilityResult(
        "tnoap", ELIGIBLE,
        ["applicant is 60 or older, a Tamil Nadu resident, and destitute"],
        ["tnoap-3.1", "tnoap-3.2"],
    )


def check_cmchis(profile: UserProfile) -> EligibilityResult:
    if profile.state and profile.state.lower() != "tamil nadu":
        return EligibilityResult(
            "cmchis", NOT_ELIGIBLE,
            ["this scheme is only for residents of Tamil Nadu"], ["cmchis-3.1"],
        )
    if profile.has_ration_card is None:
        return EligibilityResult(
            "cmchis", INSUFFICIENT_INFO,
            ["ration card status not provided"], ["cmchis-3.2"],
        )
    if profile.has_ration_card is False:
        return EligibilityResult(
            "cmchis", NOT_ELIGIBLE,
            ["applicant's name must appear on the family ration card"], ["cmchis-3.2"],
        )
    if profile.monthly_income is None:
        return EligibilityResult(
            "cmchis", INSUFFICIENT_INFO, ["income not provided"], ["cmchis-3.3"],
        )
    if profile.monthly_income * 12 >= 120000:
        return EligibilityResult(
            "cmchis", NOT_ELIGIBLE,
            ["annual family income must be under Rs. 1,20,000"], ["cmchis-3.3"],
        )
    return EligibilityResult(
        "cmchis", ELIGIBLE,
        ["applicant is a Tamil Nadu resident on the family ration card with income under the threshold"],
        ["cmchis-3.1", "cmchis-3.2", "cmchis-3.3"],
    )


CHECKERS = {
    "pmkisan": check_pmkisan,
    "pmjay": check_pmjay,
    "nsap": check_nsap,
    "pmayg": check_pmayg,
    "tnoap": check_tnoap,
    "cmchis": check_cmchis,
}


def check_eligibility(scheme_id: str, profile: UserProfile) -> EligibilityResult:
    checker = CHECKERS.get(scheme_id)
    if checker is None:
        return EligibilityResult(scheme_id, INSUFFICIENT_INFO, ["unknown scheme"], [])
    return checker(profile)


def is_known_scheme(scheme_id: str) -> bool:
    return scheme_id in CHECKERS
