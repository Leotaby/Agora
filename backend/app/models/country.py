"""
models/country.py - Nation-states

Every country is a full agent with:
- Economic profile (GDP, inflation, debt, currency regime)
- Political system (democracy score, regime type, government)
- Military + geopolitical power
- Trade and financial openness
- Household population profile (connects to L7)

Preset countries cover: G20 + sanctioned states + key EM + failed states.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RegimeType(str, Enum):
    LIBERAL_DEMOCRACY    = "liberal_democracy"
    FLAWED_DEMOCRACY     = "flawed_democracy"
    HYBRID               = "hybrid_regime"
    AUTHORITARIAN        = "authoritarian"
    TOTALITARIAN         = "totalitarian"
    THEOCRACY            = "theocracy"
    MILITARY_JUNTA       = "military_junta"
    FAILED_STATE         = "failed_state"


class CurrencyRegime(str, Enum):
    FREE_FLOAT           = "free_float"
    MANAGED_FLOAT        = "managed_float"
    CURRENCY_BOARD       = "currency_board"
    DOLLARIZED           = "dollarized"
    CURRENCY_UNION       = "currency_union"       # e.g. Eurozone
    FIXED_PEG            = "fixed_peg"
    CAPITAL_CONTROLS     = "capital_controls"
    HYPERINFLATION       = "hyperinflation"


class GeopoliticalBloc(str, Enum):
    NATO        = "NATO"
    EU          = "EU"
    G7          = "G7"
    G20         = "G20"
    BRICS       = "BRICS"
    SCO         = "SCO"           # Shanghai Cooperation Organisation
    OPEC        = "OPEC"
    ASEAN       = "ASEAN"
    GULF        = "Gulf_Cooperation_Council"
    ISOLATED    = "isolated"
    NONALIGNED  = "non_aligned"


@dataclass
class EconomicProfile:
    gdp_usd_bn: float           # GDP in USD billions
    gdp_per_capita_usd: float
    inflation_pct: float
    unemployment_pct: float
    debt_to_gdp: float          # public debt / GDP
    current_account_gdp: float  # % GDP (negative = deficit)
    fx_reserves_usd_bn: float
    currency_code: str          # ISO 4217
    currency_regime: CurrencyRegime
    dollarization_pct: float = 0.0   # % of savings in foreign currency


@dataclass
class PoliticalProfile:
    regime_type: RegimeType
    democracy_score: float       # 0–10 (EIU democracy index)
    corruption_index: float      # 0–100 (Transparency Intl, higher = less corrupt)
    press_freedom: float         # 0–100 (RSF, higher = more free)
    ruling_party: str
    opposition_strength: float   # 0–1
    election_due_year: Optional[int] = None
    sanctions_target: bool = False
    nuclear_power: bool = False
    un_security_council: bool = False


@dataclass
class MilitaryProfile:
    military_expenditure_gdp: float   # % of GDP
    nuclear_warheads: int = 0
    active_military: int = 0          # personnel
    global_power_index: float = 0.0   # 0–1


@dataclass
class Country:
    """
    A nation-state agent in the NEXUS world.
    Interacts with: institutions (IMF, WTO), other countries (trade, sanctions),
    political actors (government), financial system (central bank, banks),
    corporations (tax, regulation), and households (employer, welfare).
    """
    iso2: str                          # ISO 3166-1 alpha-2
    iso3: str                          # ISO 3166-1 alpha-3
    name: str
    capital: str
    region: str                        # e.g. "Western Europe", "East Asia"
    population_mn: float               # millions
    language: str
    religion_dominant: str

    economy: EconomicProfile = field(default_factory=lambda: EconomicProfile(
        gdp_usd_bn=0, gdp_per_capita_usd=0, inflation_pct=2.0,
        unemployment_pct=5.0, debt_to_gdp=60.0, current_account_gdp=0.0,
        fx_reserves_usd_bn=50.0, currency_code="USD",
        currency_regime=CurrencyRegime.FREE_FLOAT
    ))
    politics: PoliticalProfile = field(default_factory=lambda: PoliticalProfile(
        regime_type=RegimeType.LIBERAL_DEMOCRACY, democracy_score=7.0,
        corruption_index=60.0, press_freedom=60.0, ruling_party="Unknown",
        opposition_strength=0.4
    ))
    military: MilitaryProfile = field(default_factory=lambda: MilitaryProfile(
        military_expenditure_gdp=2.0
    ))

    blocs: list[GeopoliticalBloc] = field(default_factory=list)
    trade_partners: list[str] = field(default_factory=list)    # ISO2 list
    central_bank_id: Optional[str] = None

    def is_sanctioned(self) -> bool:
        return self.politics.sanctions_target

    def is_democratic(self) -> bool:
        return self.politics.democracy_score >= 6.0

    def is_in_eurozone(self) -> bool:
        return self.economy.currency_regime == CurrencyRegime.CURRENCY_UNION and \
               self.economy.currency_code == "EUR"

    def __repr__(self) -> str:
        return f"Country({self.iso2} - {self.name}, GDP=${self.economy.gdp_usd_bn:.0f}bn)"


# ---------------------------------------------------------------------------
# PRESET COUNTRIES - The world population
# ---------------------------------------------------------------------------

def build_usa() -> Country:
    return Country(
        iso2="US", iso3="USA", name="United States of America",
        capital="Washington D.C.", region="North America",
        population_mn=334, language="English", religion_dominant="Christian",
        economy=EconomicProfile(
            gdp_usd_bn=27_360, gdp_per_capita_usd=81_700,
            inflation_pct=3.2, unemployment_pct=3.7,
            debt_to_gdp=123, current_account_gdp=-3.0,
            fx_reserves_usd_bn=244, currency_code="USD",
            currency_regime=CurrencyRegime.FREE_FLOAT,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.LIBERAL_DEMOCRACY, democracy_score=7.85,
            corruption_index=69, press_freedom=73,
            ruling_party="Democratic Party", opposition_strength=0.48,
            election_due_year=2024, nuclear_power=True, un_security_council=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=3.5, nuclear_warheads=5_550, active_military=1_390_000, global_power_index=0.98),
        blocs=[GeopoliticalBloc.NATO, GeopoliticalBloc.G7, GeopoliticalBloc.G20],
        trade_partners=["CN", "MX", "CA", "DE", "JP", "KR", "GB", "FR", "IT", "IN"],
        central_bank_id="FED",
    )


def build_germany() -> Country:
    return Country(
        iso2="DE", iso3="DEU", name="Germany",
        capital="Berlin", region="Western Europe",
        population_mn=84, language="German", religion_dominant="Christian",
        economy=EconomicProfile(
            gdp_usd_bn=4_430, gdp_per_capita_usd=52_800,
            inflation_pct=2.5, unemployment_pct=5.5,
            debt_to_gdp=66, current_account_gdp=5.5,
            fx_reserves_usd_bn=290, currency_code="EUR",
            currency_regime=CurrencyRegime.CURRENCY_UNION,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.LIBERAL_DEMOCRACY, democracy_score=8.8,
            corruption_index=78, press_freedom=83,
            ruling_party="SPD-led coalition", opposition_strength=0.45,
            election_due_year=2025, un_security_council=False,
        ),
        military=MilitaryProfile(military_expenditure_gdp=1.7, nuclear_warheads=0, active_military=183_000, global_power_index=0.72),
        blocs=[GeopoliticalBloc.NATO, GeopoliticalBloc.EU, GeopoliticalBloc.G7, GeopoliticalBloc.G20],
        trade_partners=["CN", "US", "FR", "NL", "IT", "PL", "AT", "CH", "UK", "BE"],
        central_bank_id="ECB",
    )


def build_italy() -> Country:
    return Country(
        iso2="IT", iso3="ITA", name="Italy",
        capital="Rome", region="Southern Europe",
        population_mn=60, language="Italian", religion_dominant="Catholic",
        economy=EconomicProfile(
            gdp_usd_bn=2_250, gdp_per_capita_usd=37_600,
            inflation_pct=1.9, unemployment_pct=6.7,
            debt_to_gdp=137, current_account_gdp=1.8,
            fx_reserves_usd_bn=230, currency_code="EUR",
            currency_regime=CurrencyRegime.CURRENCY_UNION,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.FLAWED_DEMOCRACY, democracy_score=7.69,
            corruption_index=56, press_freedom=73,
            ruling_party="Fratelli d'Italia (Meloni)", opposition_strength=0.42,
            election_due_year=2027,
        ),
        military=MilitaryProfile(military_expenditure_gdp=1.5, active_military=170_000, global_power_index=0.55),
        blocs=[GeopoliticalBloc.NATO, GeopoliticalBloc.EU, GeopoliticalBloc.G7, GeopoliticalBloc.G20],
        trade_partners=["DE", "FR", "US", "CN", "ES", "CH", "UK", "NL", "BE", "PL"],
        central_bank_id="ECB",
    )


def build_china() -> Country:
    return Country(
        iso2="CN", iso3="CHN", name="People's Republic of China",
        capital="Beijing", region="East Asia",
        population_mn=1_410, language="Mandarin", religion_dominant="None (state atheism)",
        economy=EconomicProfile(
            gdp_usd_bn=17_700, gdp_per_capita_usd=12_540,
            inflation_pct=0.3, unemployment_pct=5.1,
            debt_to_gdp=83, current_account_gdp=1.5,
            fx_reserves_usd_bn=3_200, currency_code="CNY",
            currency_regime=CurrencyRegime.MANAGED_FLOAT,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.AUTHORITARIAN, democracy_score=2.12,
            corruption_index=45, press_freedom=15,
            ruling_party="Chinese Communist Party", opposition_strength=0.0,
            nuclear_power=True, un_security_council=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=1.7, nuclear_warheads=500, active_military=2_035_000, global_power_index=0.90),
        blocs=[GeopoliticalBloc.G20, GeopoliticalBloc.BRICS, GeopoliticalBloc.SCO],
        trade_partners=["US", "JP", "KR", "DE", "AU", "VN", "IN", "NL", "UK", "TW"],
        central_bank_id="PBOC",
    )


def build_russia() -> Country:
    return Country(
        iso2="RU", iso3="RUS", name="Russian Federation",
        capital="Moscow", region="Eastern Europe / North Asia",
        population_mn=145, language="Russian", religion_dominant="Orthodox Christian",
        economy=EconomicProfile(
            gdp_usd_bn=1_860, gdp_per_capita_usd=12_800,
            inflation_pct=7.5, unemployment_pct=3.2,
            debt_to_gdp=17, current_account_gdp=3.0,
            fx_reserves_usd_bn=600, currency_code="RUB",
            currency_regime=CurrencyRegime.MANAGED_FLOAT,
            dollarization_pct=0.15,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.AUTHORITARIAN, democracy_score=2.22,
            corruption_index=28, press_freedom=18,
            ruling_party="United Russia (Putin)", opposition_strength=0.05,
            sanctions_target=True, nuclear_power=True, un_security_council=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=5.9, nuclear_warheads=6_257, active_military=1_330_000, global_power_index=0.85),
        blocs=[GeopoliticalBloc.G20, GeopoliticalBloc.BRICS, GeopoliticalBloc.SCO],
        trade_partners=["CN", "DE", "NL", "BY", "TR", "IN", "IT", "KZ", "PL", "FI"],
        central_bank_id="CBR",
    )


def build_iran() -> Country:
    return Country(
        iso2="IR", iso3="IRN", name="Islamic Republic of Iran",
        capital="Tehran", region="Middle East",
        population_mn=87, language="Persian/Farsi", religion_dominant="Shia Islam",
        economy=EconomicProfile(
            gdp_usd_bn=367, gdp_per_capita_usd=4_200,
            inflation_pct=42.0, unemployment_pct=10.4,
            debt_to_gdp=30, current_account_gdp=2.0,
            fx_reserves_usd_bn=10, currency_code="IRR",
            currency_regime=CurrencyRegime.CAPITAL_CONTROLS,
            dollarization_pct=0.40,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.THEOCRACY, democracy_score=2.20,
            corruption_index=25, press_freedom=10,
            ruling_party="Islamic Revolutionary Guard (IRGC)", opposition_strength=0.15,
            sanctions_target=True, nuclear_power=False,
        ),
        military=MilitaryProfile(military_expenditure_gdp=2.5, nuclear_warheads=0, active_military=610_000, global_power_index=0.45),
        blocs=[GeopoliticalBloc.ISOLATED],
        trade_partners=["CN", "IQ", "TR", "AF", "SY", "UA", "IN"],
        central_bank_id="CBI",
    )


def build_north_korea() -> Country:
    return Country(
        iso2="KP", iso3="PRK", name="Democratic People's Republic of Korea",
        capital="Pyongyang", region="East Asia",
        population_mn=26, language="Korean", religion_dominant="Juche ideology",
        economy=EconomicProfile(
            gdp_usd_bn=16, gdp_per_capita_usd=600,
            inflation_pct=55.0, unemployment_pct=0.0,  # forced full employment
            debt_to_gdp=0, current_account_gdp=0.0,
            fx_reserves_usd_bn=0.5, currency_code="KPW",
            currency_regime=CurrencyRegime.CAPITAL_CONTROLS,
            dollarization_pct=0.60,  # black market USD/CNY
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.TOTALITARIAN, democracy_score=1.08,
            corruption_index=17, press_freedom=0,
            ruling_party="Korean Workers' Party (Kim Jong-un)", opposition_strength=0.0,
            sanctions_target=True, nuclear_power=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=25.0, nuclear_warheads=50, active_military=1_280_000, global_power_index=0.30),
        blocs=[GeopoliticalBloc.ISOLATED],
        trade_partners=["CN", "RU"],
        central_bank_id="DPRK_CB",
    )


def build_turkey() -> Country:
    return Country(
        iso2="TR", iso3="TUR", name="Republic of Turkey",
        capital="Ankara", region="Middle East / SE Europe",
        population_mn=85, language="Turkish", religion_dominant="Sunni Islam",
        economy=EconomicProfile(
            gdp_usd_bn=1_100, gdp_per_capita_usd=12_900,
            inflation_pct=65.0, unemployment_pct=9.4,
            debt_to_gdp=32, current_account_gdp=-5.3,
            fx_reserves_usd_bn=98, currency_code="TRY",
            currency_regime=CurrencyRegime.MANAGED_FLOAT,
            dollarization_pct=0.55,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.HYBRID, democracy_score=4.35,
            corruption_index=36, press_freedom=29,
            ruling_party="AKP (Erdogan)", opposition_strength=0.47,
            election_due_year=2028,
        ),
        military=MilitaryProfile(military_expenditure_gdp=2.0, active_military=355_000, global_power_index=0.48),
        blocs=[GeopoliticalBloc.NATO, GeopoliticalBloc.G20],
        trade_partners=["DE", "RU", "CN", "US", "UK", "IT", "FR", "IQ", "AE", "IN"],
        central_bank_id="TCMB",
    )


def build_argentina() -> Country:
    return Country(
        iso2="AR", iso3="ARG", name="Argentine Republic",
        capital="Buenos Aires", region="South America",
        population_mn=46, language="Spanish", religion_dominant="Catholic",
        economy=EconomicProfile(
            gdp_usd_bn=640, gdp_per_capita_usd=13_900,
            inflation_pct=140.0, unemployment_pct=7.7,
            debt_to_gdp=89, current_account_gdp=-1.2,
            fx_reserves_usd_bn=21, currency_code="ARS",
            currency_regime=CurrencyRegime.HYPERINFLATION,
            dollarization_pct=0.75,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.FLAWED_DEMOCRACY, democracy_score=6.9,
            corruption_index=37, press_freedom=62,
            ruling_party="La Libertad Avanza (Milei)", opposition_strength=0.50,
            election_due_year=2025,
        ),
        military=MilitaryProfile(military_expenditure_gdp=0.7, active_military=74_000, global_power_index=0.25),
        blocs=[GeopoliticalBloc.G20, GeopoliticalBloc.BRICS],
        trade_partners=["BR", "CN", "US", "DE", "CL", "BO", "UY", "NL", "IT", "ES"],
        central_bank_id="BCRA",
    )


def build_india() -> Country:
    return Country(
        iso2="IN", iso3="IND", name="Republic of India",
        capital="New Delhi", region="South Asia",
        population_mn=1_440, language="Hindi / English", religion_dominant="Hindu",
        economy=EconomicProfile(
            gdp_usd_bn=3_730, gdp_per_capita_usd=2_590,
            inflation_pct=5.1, unemployment_pct=7.6,
            debt_to_gdp=84, current_account_gdp=-1.5,
            fx_reserves_usd_bn=600, currency_code="INR",
            currency_regime=CurrencyRegime.MANAGED_FLOAT,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.FLAWED_DEMOCRACY, democracy_score=7.04,
            corruption_index=40, press_freedom=45,
            ruling_party="BJP (Modi)", opposition_strength=0.42,
            election_due_year=2029, nuclear_power=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=2.4, nuclear_warheads=164, active_military=1_455_000, global_power_index=0.78),
        blocs=[GeopoliticalBloc.G20, GeopoliticalBloc.BRICS, GeopoliticalBloc.SCO, GeopoliticalBloc.NONALIGNED],
        trade_partners=["US", "CN", "AE", "SA", "RU", "UK", "SG", "DE", "HK", "AU"],
        central_bank_id="RBI",
    )


def build_saudi_arabia() -> Country:
    return Country(
        iso2="SA", iso3="SAU", name="Kingdom of Saudi Arabia",
        capital="Riyadh", region="Middle East",
        population_mn=36, language="Arabic", religion_dominant="Sunni Islam",
        economy=EconomicProfile(
            gdp_usd_bn=1_060, gdp_per_capita_usd=29_400,
            inflation_pct=2.3, unemployment_pct=6.0,
            debt_to_gdp=23, current_account_gdp=5.5,
            fx_reserves_usd_bn=450, currency_code="SAR",
            currency_regime=CurrencyRegime.FIXED_PEG,  # pegged to USD
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.AUTHORITARIAN, democracy_score=1.96,
            corruption_index=52, press_freedom=28,
            ruling_party="Al Saud dynasty (MBS)", opposition_strength=0.02,
        ),
        military=MilitaryProfile(military_expenditure_gdp=6.0, active_military=227_000, global_power_index=0.40),
        blocs=[GeopoliticalBloc.G20, GeopoliticalBloc.OPEC, GeopoliticalBloc.GULF],
        trade_partners=["CN", "JP", "IN", "US", "KR", "AE", "SG", "EG", "PK", "FR"],
        central_bank_id="SAMA",
    )


def build_uk() -> Country:
    return Country(
        iso2="GB", iso3="GBR", name="United Kingdom",
        capital="London", region="Western Europe",
        population_mn=67, language="English", religion_dominant="Christian",
        economy=EconomicProfile(
            gdp_usd_bn=3_090, gdp_per_capita_usd=46_100,
            inflation_pct=3.9, unemployment_pct=4.2,
            debt_to_gdp=101, current_account_gdp=-3.1,
            fx_reserves_usd_bn=185, currency_code="GBP",
            currency_regime=CurrencyRegime.FREE_FLOAT,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.LIBERAL_DEMOCRACY, democracy_score=8.28,
            corruption_index=71, press_freedom=71,
            ruling_party="Labour (Starmer)", opposition_strength=0.44,
            election_due_year=2029, nuclear_power=True, un_security_council=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=2.3, nuclear_warheads=225, active_military=150_000, global_power_index=0.75),
        blocs=[GeopoliticalBloc.NATO, GeopoliticalBloc.G7, GeopoliticalBloc.G20],
        trade_partners=["US", "DE", "FR", "NL", "IE", "CN", "BE", "IT", "ES", "IN"],
        central_bank_id="BOE",
    )


def build_france() -> Country:
    return Country(
        iso2="FR", iso3="FRA", name="French Republic",
        capital="Paris", region="Western Europe",
        population_mn=68, language="French", religion_dominant="Catholic/Secular",
        economy=EconomicProfile(
            gdp_usd_bn=3_050, gdp_per_capita_usd=44_900,
            inflation_pct=2.3, unemployment_pct=7.3,
            debt_to_gdp=111, current_account_gdp=-0.8,
            fx_reserves_usd_bn=240, currency_code="EUR",
            currency_regime=CurrencyRegime.CURRENCY_UNION,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.LIBERAL_DEMOCRACY, democracy_score=7.99,
            corruption_index=71, press_freedom=78,
            ruling_party="Renaissance (Macron)", opposition_strength=0.55,
            election_due_year=2027, nuclear_power=True, un_security_council=True,
        ),
        military=MilitaryProfile(military_expenditure_gdp=1.9, nuclear_warheads=290, active_military=205_000, global_power_index=0.75),
        blocs=[GeopoliticalBloc.NATO, GeopoliticalBloc.EU, GeopoliticalBloc.G7, GeopoliticalBloc.G20],
        trade_partners=["DE", "US", "IT", "ES", "BE", "CN", "NL", "UK", "CH", "PL"],
        central_bank_id="ECB",
    )


def build_japan() -> Country:
    return Country(
        iso2="JP", iso3="JPN", name="Japan",
        capital="Tokyo", region="East Asia",
        population_mn=124, language="Japanese", religion_dominant="Shinto/Buddhist",
        economy=EconomicProfile(
            gdp_usd_bn=4_210, gdp_per_capita_usd=33_900,
            inflation_pct=2.8, unemployment_pct=2.6,
            debt_to_gdp=261, current_account_gdp=3.4,
            fx_reserves_usd_bn=1_290, currency_code="JPY",
            currency_regime=CurrencyRegime.FREE_FLOAT,
        ),
        politics=PoliticalProfile(
            regime_type=RegimeType.LIBERAL_DEMOCRACY, democracy_score=8.40,
            corruption_index=73, press_freedom=70,
            ruling_party="LDP", opposition_strength=0.35,
            election_due_year=2025,
        ),
        military=MilitaryProfile(military_expenditure_gdp=1.2, nuclear_warheads=0, active_military=247_000, global_power_index=0.65),
        blocs=[GeopoliticalBloc.G7, GeopoliticalBloc.G20],
        trade_partners=["CN", "US", "KR", "AU", "TW", "VN", "TH", "DE", "SG", "MY"],
        central_bank_id="BOJ",
    )


# Registry of all preset countries
PRESET_COUNTRIES: dict[str, callable] = {
    "US": build_usa,
    "DE": build_germany,
    "IT": build_italy,
    "CN": build_china,
    "RU": build_russia,
    "IR": build_iran,
    "KP": build_north_korea,
    "TR": build_turkey,
    "AR": build_argentina,
    "IN": build_india,
    "SA": build_saudi_arabia,
    "GB": build_uk,
    "FR": build_france,
    "JP": build_japan,
}


def build_all_countries() -> dict[str, Country]:
    """Build all preset countries and return as ISO2 → Country dict."""
    return {iso2: builder() for iso2, builder in PRESET_COUNTRIES.items()}
