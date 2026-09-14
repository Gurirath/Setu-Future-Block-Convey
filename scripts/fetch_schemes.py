from pathlib import Path

OUT_DIR = Path("data/raw")

SCHEME_TEXTS = {
    "pmkisan": """SCHEME: Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)
STATE: central
SOURCE: pmkisan.gov.in (live fetch)

[SECTION 1] Overview
PM-KISAN is a Central Sector scheme, fully funded by the Government of India, providing income support to landholding farmer families across India.

[SECTION 2] Benefit amount
An income support of Rs. 6,000 per year is provided to all landholding farmer families, payable in three equal installments of Rs. 2,000 every four months.

[SECTION 3.1] Eligibility - Landholding farmer families
All landholding farmer families are eligible, subject to the exclusion criteria. The definition of family for the scheme is husband, wife, and minor children.

[SECTION 3.2] Eligibility - State identification
State Government and Union Territory administrations identify the eligible farmer families as per the scheme guidelines.

[SECTION 4.1] Exclusion - Institutional landholders
All institutional landholders are excluded from the scheme.

[SECTION 4.2] Exclusion - Constitutional and political office holders
Former and present holders of constitutional posts, former and present Ministers, members of Parliament and State Legislatures, mayors of municipal corporations, and chairpersons of district panchayats are excluded.

[SECTION 4.3] Exclusion - Government employees and pensioners
Serving or retired officers and employees of state or central government (excluding Class IV or Group D employees), and retired pensioners with a monthly pension of Rs. 10,000 or more (excluding Class IV or Group D), are excluded.

[SECTION 4.4] Exclusion - Income tax payers and professionals
All persons who paid income tax in the last assessment year are excluded. Doctors, engineers, lawyers, chartered accountants, and architects registered with their professional bodies are excluded.

[SECTION 4.5] Exclusion - Recent land acquisition
Farmers who acquired land ownership after February 1, 2019 are excluded from the scheme's original guidelines.
""",
    "pmjay": """SCHEME: Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PM-JAY)
STATE: central
SOURCE: authored from publicly documented scheme criteria (myscheme.gov.in and pmjay.gov.in were not fetchable as rendered pages; verify against official source before production use)

[SECTION 1] Overview
PM-JAY provides a health cover of Rs. 5 lakh per family per year for secondary and tertiary care hospitalization, through a network of empanelled public and private hospitals.

[SECTION 2] Benefit amount
Eligible families receive cashless and paperless health coverage of up to Rs. 5,00,000 per family per year, with no cap on family size or age.

[SECTION 3.1] Eligibility - Rural deprivation criteria
Households in rural areas identified under specific deprivation and automatic-inclusion categories of the Socio-Economic Caste Census 2011 (SECC 2011) are eligible.

[SECTION 3.2] Eligibility - Urban occupational criteria
Households in urban areas falling under one of eleven defined occupational vulnerability categories identified in SECC 2011 are eligible.

[SECTION 3.3] Eligibility - State extension schemes
Some states extend eligibility beyond the SECC 2011 list through state-funded top-up schemes with their own family lists.

[SECTION 4.1] Exclusion - Formal employment and higher income indicators
Households with a member in formal government employment with a regular income, or meeting other SECC exclusion indicators such as owning a motorized vehicle or a pucca house with specified characteristics, are excluded from automatic SECC-based inclusion.

[SECTION 4.2] Exclusion - Not in verified beneficiary list
Individuals not appearing in the verified PM-JAY beneficiary database for their household, even if otherwise low-income, are not automatically covered without a valid Ayushman card.
""",
    "nsap_oldage": """SCHEME: National Social Assistance Programme - Indira Gandhi National Old Age Pension Scheme (IGNOAPS)
STATE: central
SOURCE: authored from publicly documented scheme criteria (nsap.nic.in was not reachable during fetch; verify against official source before production use)

[SECTION 1] Overview
IGNOAPS, a component of the National Social Assistance Programme, provides a monthly pension to elderly persons living below the poverty line.

[SECTION 2.1] Benefit amount - Age 60 to 79
Eligible beneficiaries aged 60 to 79 years receive a central assistance of Rs. 200 per month, which many states supplement with an additional state contribution.

[SECTION 2.2] Benefit amount - Age 80 and above
Eligible beneficiaries aged 80 years and above receive a central assistance of Rs. 500 per month, again often supplemented by state governments.

[SECTION 3.1] Eligibility - Age
The applicant must be 60 years of age or older.

[SECTION 3.2] Eligibility - Poverty line status
The applicant must belong to a household living below the poverty line, as per the criteria approved by the relevant state or union territory.

[SECTION 4.1] Exclusion - Other government pension
Persons already receiving a pension under any other government pension scheme are generally excluded from also receiving IGNOAPS.
""",
    "pmayg": """SCHEME: Pradhan Mantri Awaas Yojana - Gramin (PMAY-G)
STATE: central
SOURCE: authored from publicly documented scheme criteria (pmayg.nic.in was not reachable during fetch; verify against official source before production use)

[SECTION 1] Overview
PMAY-G provides financial assistance to eligible rural households for construction of a pucca house, targeting houseless households and those living in kutcha or dilapidated houses.

[SECTION 2.1] Benefit amount - Plain areas
Eligible households in plain areas receive financial assistance of Rs. 1,20,000 for construction of a house.

[SECTION 2.2] Benefit amount - Hilly and difficult areas
Eligible households in hilly states, difficult areas, and Integrated Action Plan (IAP) districts receive financial assistance of Rs. 1,30,000.

[SECTION 3.1] Eligibility - Housing deprivation criteria
Households identified as houseless or living in zero, one, or two room kutcha houses under the SECC 2011 deprivation criteria, and validated through the Awaas+ survey, are eligible.

[SECTION 3.2] Eligibility - Priority categories
Priority is given to SC/ST households, freed bonded labourers, and households with a disabled member and no able-bodied adult member.

[SECTION 4.1] Exclusion - Existing pucca house
Households that already own a pucca house are excluded from the scheme.

[SECTION 4.2] Exclusion - Motorized vehicle or formal income indicators
Households owning a motorized two, three, or four-wheeler, mechanized farm equipment, or with a family member earning more than Rs. 10,000 per month in a government job are excluded, per SECC exclusion criteria.
""",
    "tn_oldage": """SCHEME: Tamil Nadu Old Age Pension Scheme (Indira Gandhi National Old Age Pension Scheme - Tamil Nadu state component)
STATE: Tamil Nadu
SOURCE: authored from publicly documented scheme criteria (myscheme.gov.in was not fetchable as a rendered page; verify against official Tamil Nadu Social Welfare Department source before production use)

[SECTION 1] Overview
The Tamil Nadu Old Age Pension Scheme provides a monthly pension to destitute elderly residents of Tamil Nadu, administered by the state Social Security Schemes department, combining central IGNOAPS assistance with a state top-up.

[SECTION 2] Benefit amount
Eligible beneficiaries receive a combined monthly pension of approximately Rs. 1,000, comprising the central IGNOAPS share and the Tamil Nadu state contribution.

[SECTION 3.1] Eligibility - Age
The applicant must be 60 years of age or older and a resident of Tamil Nadu.

[SECTION 3.2] Eligibility - Destitution and income
The applicant must be destitute, with no regular means of subsistence from their own source of income or through support from family members, and family income must fall below the state-notified threshold.

[SECTION 4.1] Exclusion - Other pension or government support
Persons already receiving a pension under any other government scheme, or with a family member in regular government employment supporting them, are excluded.
""",
    "tn_magalir_urimai": """SCHEME: Tamil Nadu Kalaignar Magalir Urimai Thogai Thittam (Chief Minister's Monthly Financial Assistance Scheme for Women Family Heads)
STATE: Tamil Nadu
SOURCE: authored from publicly documented scheme criteria (myscheme.gov.in was not fetchable as a rendered page; verify against official Tamil Nadu government source before production use)

[SECTION 1] Overview
This Tamil Nadu state scheme provides monthly financial assistance to women who are heads of their family, identified as the primary member on the family's ration card (Rice Family Card).

[SECTION 2] Benefit amount
Eligible women receive Rs. 1,000 per month, credited directly to their bank account.

[SECTION 3.1] Eligibility - Family card headship
The applicant must be the head of the family as recorded on the Tamil Nadu Rice Family Card (ration card).

[SECTION 3.2] Eligibility - Age
The applicant must be between 21 and 59 years of age.

[SECTION 3.3] Eligibility - Residency
The applicant must be a permanent resident of Tamil Nadu.

[SECTION 4.1] Exclusion - Income tax payers
Applicants or family members who are income tax payees are excluded.

[SECTION 4.2] Exclusion - Government employment
Applicants with a family member employed in a permanent government job, or already receiving a government pension, are excluded.

[SECTION 4.3] Exclusion - Four-wheeler ownership
Families owning a four-wheeler vehicle for personal use, other than a taxi or auto-rickshaw used for livelihood, are excluded.
""",
}


def write_raw_corpus(out_dir: str = "data/raw") -> int:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    for name, text in SCHEME_TEXTS.items():
        (out_path / f"{name}.txt").write_text(text, encoding="utf-8")
    return len(SCHEME_TEXTS)


if __name__ == "__main__":
    count = write_raw_corpus()
    print(f"Wrote raw text for {count} schemes to {OUT_DIR}/")
