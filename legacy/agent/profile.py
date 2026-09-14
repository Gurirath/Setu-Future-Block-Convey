from dataclasses import dataclass, field, asdict


@dataclass
class UserProfile:
    age: int | None = None
    monthly_income: int | None = None
    land_size_acres: float | None = None
    social_category: str | None = None
    state: str | None = None
    district: str | None = None
    existing_benefits: list[str] = field(default_factory=list)
    is_bpl: bool | None = None
    is_destitute: bool | None = None
    has_pucca_house: bool | None = None
    has_ration_card: bool | None = None
    is_income_tax_payer: bool | None = None
    is_government_employee: bool | None = None

    def merge(self, updates: dict) -> None:
        for key, value in updates.items():
            if value is None:
                continue
            if key == "existing_benefits":
                for item in value:
                    if item not in self.existing_benefits:
                        self.existing_benefits.append(item)
                continue
            setattr(self, key, value)

    def to_dict(self) -> dict:
        return asdict(self)


SCHEME_NAMES = {
    "pmkisan": "PM-KISAN",
    "pmjay": "Ayushman Bharat PM-JAY",
    "nsap": "the National Social Assistance Programme old age pension (IGNOAPS)",
    "pmayg": "PMAY-Gramin",
    "tnoap": "the Tamil Nadu Old Age Pension Scheme",
    "cmchis": "CMCHIS",
}

QUESTIONS = {
    "age": {
        "en": "How old are you?",
        "hi": "आपकी उम्र क्या है?",
        "ta": "உங்கள் வயது என்ன?",
    },
    "monthly_income": {
        "en": "What is your monthly family income?",
        "hi": "आपकी मासिक पारिवारिक आय क्या है?",
        "ta": "உங்கள் மாத குடும்ப வருமானம் என்ன?",
    },
    "land_size_acres": {
        "en": "How many acres of land do you own?",
        "hi": "आपके पास कितनी एकड़ ज़मीन है?",
        "ta": "உங்களிடம் எத்தனை ஏக்கர் நிலம் உள்ளது?",
    },
    "state": {
        "en": "Which state do you live in?",
        "hi": "आप किस राज्य में रहते हैं?",
        "ta": "நீங்கள் எந்த மாநிலத்தில் வசிக்கிறீர்கள்?",
    },
    "is_bpl": {
        "en": "Do you have a Below Poverty Line (BPL) card?",
        "hi": "क्या आपके पास बीपीएल कार्ड है?",
        "ta": "உங்களிடம் வறுமைக்கோட்டுக்கு கீழ் (பிபிஎல்) அட்டை உள்ளதா?",
    },
    "is_destitute": {
        "en": "Do you have any regular income, or support from family?",
        "hi": "क्या आपकी कोई नियमित आय है, या परिवार से सहायता मिलती है?",
        "ta": "உங்களுக்கு வழக்கமான வருமானம் அல்லது குடும்ப ஆதரவு உள்ளதா?",
    },
    "has_pucca_house": {
        "en": "Do you currently live in a pucca (permanent, concrete) house?",
        "hi": "क्या आप वर्तमान में पक्के मकान में रहते हैं?",
        "ta": "நீங்கள் தற்போது ஒரு பக்கா (நிரந்தர) வீட்டில் வசிக்கிறீர்களா?",
    },
    "has_ration_card": {
        "en": "Is your name listed on your family's ration card?",
        "hi": "क्या आपका नाम आपके परिवार के राशन कार्ड में है?",
        "ta": "உங்கள் பெயர் உங்கள் குடும்ப ரேஷன் அட்டையில் உள்ளதா?",
    },
}

REQUIRED_SLOTS = {
    "pmkisan": ["land_size_acres"],
    "pmjay": [],
    "nsap": ["age", "is_bpl"],
    "pmayg": ["has_pucca_house"],
    "tnoap": ["state", "age", "is_destitute"],
    "cmchis": ["state", "has_ration_card", "monthly_income"],
}


def missing_slots(scheme_id: str, profile: UserProfile) -> list[str]:
    required = REQUIRED_SLOTS.get(scheme_id, [])
    return [slot for slot in required if getattr(profile, slot) is None]


def scheme_id_from_clause_id(clause_id: str) -> str:
    return clause_id.split("-", 1)[0]
