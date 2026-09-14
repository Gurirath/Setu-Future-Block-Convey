from agent.profile import UserProfile

GENERIC_QUERY = "general welfare scheme eligibility"


def build_query(profile: UserProfile) -> str:
    parts = []

    if profile.land_size_acres is not None:
        parts.append(f"landholding {profile.land_size_acres} acres")
    if profile.age is not None:
        parts.append(f"age {profile.age}")
    if profile.monthly_income is not None:
        parts.append(f"monthly income {profile.monthly_income} rupees")
    if profile.state:
        parts.append(f"state {profile.state}")
    if profile.district:
        parts.append(f"district {profile.district}")
    if profile.social_category:
        parts.append(f"social category {profile.social_category}")
    if profile.is_bpl:
        parts.append("has a Below Poverty Line card")
    if profile.is_destitute:
        parts.append("no regular income or family support")
    if profile.has_pucca_house is True:
        parts.append("lives in a pucca house")
    elif profile.has_pucca_house is False:
        parts.append("houseless or living in a kutcha house")
    if profile.has_ration_card:
        parts.append("name is on the family ration card")
    if profile.is_income_tax_payer:
        parts.append("pays income tax")
    if profile.is_government_employee:
        parts.append("has a government job")
    if profile.existing_benefits:
        parts.append("already receiving " + ", ".join(profile.existing_benefits))

    if not parts:
        return GENERIC_QUERY
    return ", ".join(parts)
