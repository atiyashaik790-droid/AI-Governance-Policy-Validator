"""Validated national identifiers for the English Presidio pipeline."""

import re
from datetime import date

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.predefined_recognizers import (
    EsNifRecognizer, InVehicleRegistrationRecognizer, ItDriverLicenseRecognizer,
    ItFiscalCodeRecognizer, ItIdentityCardRecognizer, ItPassportRecognizer,
    ItVatCodeRecognizer, SgFinRecognizer,
)


def valid(entity: str, value: str) -> bool:
    if entity == "FI_PERSONAL_ID":
        match = re.fullmatch(r"(\d{2})(\d{2})(\d{2})([+\-ABCDEFUVWXY])(\d{3})([0-9A-Y])", value.upper())
        if not match:
            return False
        day, month, year, century, individual, check = match.groups()
        base = {"+":1800,"-":1900,"A":2000,"B":2000,"C":2000,"D":2000,"E":2000,"F":2000,"U":1900,"V":1900,"W":1900,"X":1900,"Y":1900}[century]
        try:
            date(base + int(year), int(month), int(day))
        except ValueError:
            return False
        alphabet = "0123456789ABCDEFHJKLMNPRSTUVWXY"
        return individual != "000" and check == alphabet[int(day + month + year + individual) % 31]
    compact = re.sub(r"[ -]", "", value).upper()
    if entity == "IN_PAN":
        return bool(re.fullmatch(r"[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]", compact))
    if entity == "AU_ABN":
        return len(compact) == 11 and compact.isdigit() and sum(
            (int(digit) - (index == 0)) * weight
            for index, (digit, weight) in enumerate(zip(compact, (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)))
        ) % 89 == 0
    if entity == "AU_ACN":
        return len(compact) == 9 and compact.isdigit() and (10 - sum(
            int(digit) * weight for digit, weight in zip(compact[:8], (8, 7, 6, 5, 4, 3, 2, 1))
        ) % 10) % 10 == int(compact[-1])
    if entity == "AU_TFN":
        weights = (1, 4, 3, 7, 5, 8, 6, 9, 10) if len(compact) == 9 else (10, 7, 8, 4, 6, 3, 5, 1)
        return len(compact) in (8, 9) and compact.isdigit() and sum(int(d) * w for d, w in zip(compact, weights)) % 11 == 0
    if entity == "PL_PESEL":
        if len(compact) != 11 or not compact.isdigit():
            return False
        month = int(compact[2:4])
        if month % 20 not in range(1, 13):
            return False
        day = int(compact[4:6])
        return 1 <= day <= 31 and (10 - sum(int(d) * w for d, w in zip(compact[:10], (1, 3, 7, 9, 1, 3, 7, 9, 1, 3))) % 10) % 10 == int(compact[-1])
    if entity == "IN_AADHAAR":
        if len(compact) != 12 or not compact.isdigit() or compact[0] not in "23456789":
            return False
        multiplication = ((0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),(3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),(6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),(9,8,7,6,5,4,3,2,1,0))
        permutation = ((0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),(5,8,0,3,7,9,6,1,4,2),(8,9,1,6,0,4,3,5,2,7),(9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),(2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8))
        checksum = 0
        for index, digit in enumerate(reversed(compact)):
            checksum = multiplication[checksum][permutation[index % 8][int(digit)]]
        return checksum == 0
    if entity == "AU_MEDICARE":
        return len(compact) == 10 and compact.isdigit() and sum(int(d) * w for d, w in zip(compact[:8], (1,3,7,9,1,3,7,9))) % 10 == int(compact[8]) and compact[9] != "0"
    if entity == "KR_RRN":
        if len(compact) != 13 or not compact.isdigit() or compact[6] not in "12345678":
            return False
        try:
            year = int(compact[:2]) + (1900 if compact[6] in "1256" else 2000)
            date(year, int(compact[2:4]), int(compact[4:6]))
        except ValueError:
            return False
        return (11 - sum(int(d) * w for d, w in zip(compact[:12], (2,3,4,5,6,7,8,9,2,3,4,5))) % 11) % 10 == int(compact[-1])
    if entity == "TH_TNIN":
        return len(compact) == 13 and compact.isdigit() and compact[0] != "0" and (11 - sum(int(d) * w for d, w in zip(compact[:12], range(13, 1, -1))) % 11) % 10 == int(compact[-1])
    return False


PATTERNS = {
    "IN_PAN": r"(?<![A-Za-z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z](?![A-Za-z0-9])",
    "AU_ABN": r"(?<!\d)(?:\d[ -]?){10}\d(?!\d)",
    "AU_ACN": r"(?<!\d)(?:\d[ -]?){8}\d(?!\d)",
    "AU_TFN": r"(?<!\d)(?:\d[ -]?){7,8}\d(?!\d)",
    "PL_PESEL": r"(?<!\d)\d{11}(?!\d)",
    "IN_AADHAAR": r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)",
    "AU_MEDICARE": r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{2}(?!\d)",
    "KR_RRN": r"(?<!\d)\d{6}[ -]?\d{7}(?!\d)",
    "TH_TNIN": r"(?<!\d)\d[ -]?\d{4}[ -]?\d{5}[ -]?\d{2}[ -]?\d(?!\d)",
    "FI_PERSONAL_ID": r"(?<![A-Za-z0-9])\d{6}[+\-ABCDEFUVWXY]\d{3}[0-9A-Y](?![A-Za-z0-9])",
}

CONTEXT = {
    "IN_PAN": ("pan", "permanent account number"),
    "AU_ABN": ("abn", "australian business number"),
    "AU_ACN": ("acn", "australian company number"),
    "AU_TFN": ("tfn", "tax file number"),
    "PL_PESEL": ("pesel",),
    "IN_AADHAAR": ("aadhaar", "aadhar", "uidai"),
    "AU_MEDICARE": ("medicare",),
    "KR_RRN": ("rrn", "resident registration"),
    "TH_TNIN": ("tin", "tax identification"),
    "FI_PERSONAL_ID": ("hetu", "personal identity code"),
}


class CountryIdentifierRecognizer(EntityRecognizer):
    def __init__(self, entity: str):
        super().__init__(supported_entities=[entity], supported_language="en", name=f"Validated{entity}Recognizer")
        self.entity = entity
        self.pattern = re.compile(PATTERNS[entity], re.I)

    def analyze(self, text, entities, nlp_artifacts=None):
        if self.entity not in entities:
            return []
        results = []
        for match in self.pattern.finditer(text):
            if not valid(self.entity, match.group()):
                continue
            nearby = text[max(0, match.start() - 48):min(len(text), match.end() + 32)].lower()
            if not any(re.search(r"\b" + re.escape(term) + r"\b", nearby) for term in CONTEXT[self.entity]):
                continue
            results.append(RecognizerResult(entity_type=self.entity, start=match.start(), end=match.end(), score=0.85))
        return results


class ContextualNativeRecognizer(EntityRecognizer):
    """Use Presidio's checksum validator with an English label requirement."""

    def __init__(self, native, entity, labels):
        super().__init__(supported_entities=[entity], supported_language="en", name=f"Contextual{entity}Recognizer")
        self.native = native(supported_language="en")
        self.entity = entity
        self.labels = labels

    def analyze(self, text, entities, nlp_artifacts=None):
        if self.entity not in entities:
            return []
        results = self.native.analyze(text, entities, nlp_artifacts)
        filtered = [result for result in results if any(
            re.search(r"\b" + re.escape(label) + r"\b", text[max(0, result.start - 48):min(len(text), result.end + 32)], re.I)
            for label in self.labels
        )]
        for result in filtered:
            result.recognition_metadata = {}
        return filtered


def register_country_recognizers(registry):
    for entity in PATTERNS:
        registry.add_recognizer(CountryIdentifierRecognizer(entity))
    registry.add_recognizer(ContextualNativeRecognizer(ItVatCodeRecognizer, "IT_VAT_CODE", ("VAT", "partita iva", "piva")))
    registry.add_recognizer(ContextualNativeRecognizer(EsNifRecognizer, "ES_NIF", ("NIF", "DNI")))
    for native, entity, labels in (
        (ItDriverLicenseRecognizer, "IT_DRIVER_LICENSE", ("driver license", "driving licence", "patente")),
        (ItFiscalCodeRecognizer, "IT_FISCAL_CODE", ("fiscal code", "codice fiscale")),
        (ItIdentityCardRecognizer, "IT_IDENTITY_CARD", ("identity card", "carta d'identità")),
        (ItPassportRecognizer, "IT_PASSPORT", ("passport", "passaporto")),
        (InVehicleRegistrationRecognizer, "IN_VEHICLE_REGISTRATION", ("vehicle registration", "registration number", "license plate")),
        (SgFinRecognizer, "SG_NRIC_FIN", ("nric", "fin", "singapore identity")),
    ):
        registry.add_recognizer(ContextualNativeRecognizer(native, entity, labels))
