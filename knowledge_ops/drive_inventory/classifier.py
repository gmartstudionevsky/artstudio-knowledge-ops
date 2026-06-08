from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from knowledge_ops.drive_inventory.models import DriveInventoryItem
from knowledge_ops.drive_inventory.normalizer import normalize_name


@dataclass(frozen=True)
class Rule:
    label: str
    tokens: Tuple[str, ...]
    confidence: str = "medium"


OBJECT_RULES = [
    Rule("ARTSTUDIO Nevsky", ("nevsky", "невский", "невск")),
    Rule("ARTSTUDIO Moskovsky", ("moskovsky", "московский", "московск")),
    Rule("ARTSTUDIO M103", ("m103", "м103")),
    Rule("ARTSTUDIO Network / сеть ARTSTUDIO", ("artstudio network", "сеть artstudio", "сеть артстудио")),
    Rule("RBI PM Service / сервисный контур", ("rbi pm service", "сервисный контур")),
    Rule("RBI PM / УК", ("rbi pm", "управляющая компания", "ук")),
    Rule("не объектный / общий документ", ("общий", "general", "common")),
]

DEPARTMENT_RULES = [
    Rule("СПиР / Front Office / Reception", ("спир", "front office", "reception", "ресеп", "ресепш")),
    Rule("бронирование / reservation / booking", ("бронир", "reservation", "booking")),
    Rule("продажи", ("продаж", "sales")),
    Rule("коммерческий отдел / revenue / pricing", ("revenue", "pricing", "тариф", "ценообраз", "коммерч")),
    Rule("маркетинг / SMM / бренд", ("маркет", "smm", "бренд", "макет", "наружная реклама", "презентац")),
    Rule("собственники / owner relations", ("собствен", "owner", "investor")),
    Rule("управляющая компания / УК", ("управляющая компания", " ук ", "rbi pm")),
    Rule("GM / управление объектом", ("gm", "генеральный менеджер", "управление объектом")),
    Rule("операционное управление", ("операцион", "operations")),
    Rule("ХСК / housekeeping", ("хск", "housekeeping", "уборк", "горнич")),
    Rule("ИТС / инженерная служба", ("итс", "инженер", "техническая служба", "оборуд")),
    Rule("безопасность / охрана / пожарная безопасность", ("безопас", "охран", "пожар")),
    Rule("IT / доступы / системы", (" it ", "доступ", "wi-fi", "wifi", "интернет", "телефони")),
    Rule("бухгалтерия", ("бухгалтер", "accounting")),
    Rule("финансы", ("финанс", "payment", "платеж")),
    Rule("касса", ("касса", "кассов")),
    Rule("закупки", ("закуп", "purchase")),
    Rule("склад", ("склад", "остатк")),
    Rule("HR / кадры", ("hr", "кадр", "сотрудник", "персонал")),
    Rule("обучение / адаптация / аттестация", ("обуч", "адаптац", "аттеста", "training")),
    Rule("юридический блок", ("юрид", "legal", "договор", "доверенность")),
    Rule("документооборот", ("документооборот", "эдо")),
    Rule("отчётность", ("отчет", "отчёт", "report")),
    Rule("аналитика", ("аналит", "dashboard")),
    Rule("проектное управление", ("проект", "project")),
    Rule("сервисы гостей", ("гост", "guest", "услуг")),
    Rule("подрядчики", ("подряд", "contractor")),
    Rule("недвижимость / помещения / апартаменты / кадастр / ПИБ", ("кадастр", "пиб", "помещ", "апартамент", "недвиж")),
    Rule("ремонт / CAPEX / OPEX / работы", ("ремонт", "capex", "opex", "работ")),
    Rule("дизайн / комплектация / оснащение", ("дизайн", "комплектац", "оснащ")),
    Rule("медиаархив", ("фото", "video", "видео", "медиа")),
    Rule("архив", ("архив", "archive")),
]

DOCUMENT_RULES = [
    Rule("регламент", ("регламент",)),
    Rule("стандарт", ("стандарт",)),
    Rule("SOP", ("sop",)),
    Rule("инструкция", ("инструкц",)),
    Rule("алгоритм", ("алгоритм",)),
    Rule("чек-лист", ("чек лист", "чек-лист", "checklist")),
    Rule("памятка", ("памятка",)),
    Rule("скрипт", ("скрипт", "script")),
    Rule("шаблон", ("шаблон", "template")),
    Rule("бланк", ("бланк",)),
    Rule("заявление", ("заявлен",)),
    Rule("договор", ("договор", "contract")),
    Rule("дополнительное соглашение", ("доп соглаш", "дополнительное соглашение")),
    Rule("акт", ("акт",)),
    Rule("доверенность", ("доверенность",)),
    Rule("реестр", ("реестр", "registry")),
    Rule("управленческий отчёт", ("управленческий отчет", "управленческий отчёт")),
    Rule("финансовый отчёт", ("финансовый отчет", "финансовый отчёт")),
    Rule("счёт", ("счет", "счёт", "invoice")),
    Rule("КП / коммерческое предложение", ("коммерческое предложение", " кп ")),
    Rule("смета", ("смет",)),
    Rule("спецификация", ("спецификац",)),
    Rule("ТЗ", (" тз ", "техническое задание")),
    Rule("презентация", ("презентац", "presentation")),
    Rule("брендбук", ("брендбук", "brandbook")),
    Rule("макет", ("макет",)),
    Rule("фото", ("фото", "photo", "jpg", "jpeg", "png")),
    Rule("видео", ("видео", "video", "mp4", "mov")),
    Rule("логотип", ("логотип", "logo")),
    Rule("письмо / рассылка", ("письмо", "рассылка", "email")),
    Rule("жалоба", ("жалоб",)),
    Rule("протокол", ("протокол",)),
    Rule("приказ", ("приказ",)),
    Rule("служебная записка", ("служеб",)),
    Rule("должностная инструкция", ("должност",)),
    Rule("график", ("график", "schedule")),
    Rule("табель", ("табель",)),
    Rule("обучающий материал", ("обуч", "training")),
    Rule("база знаний", ("база знаний", "knowledge base")),
    Rule("FAQ", ("faq", "частые вопросы")),
    Rule("правила проживания", ("правила проживания",)),
    Rule("лицензии / сертификаты / обязательные документы", ("лиценз", "сертификат", "обязательн")),
    Rule("пожарные документы", ("пожар",)),
    Rule("техническая документация", ("техническая документация", "паспорт оборудования", "чертеж", "чертёж", "схема")),
    Rule("договор с подрядчиком", ("договор подряд", "подрядчик")),
    Rule("договор с собственником", ("договор собствен",)),
    Rule("реестр собственников", ("реестр собствен",)),
    Rule("реестр апартаментов", ("реестр апартамент",)),
    Rule("архивная копия", ("архив", "archive")),
    Rule("черновик", ("черновик", "draft")),
    Rule("временный файл", ("временн", "temp", "tmp")),
]

PROCESS_RULES = [
    Rule("check-in", ("check-in", "check in", "заезд", "засел")),
    Rule("check-out", ("check-out", "check out", "выезд", "высел")),
    Rule("регистрация гостей", ("регистрац", "миграцион")),
    Rule("бронирование", ("бронир", "booking")),
    Rule("проживание", ("прожив",)),
    Rule("жалобы и конфликты", ("жалоб", "конфликт")),
    Rule("коммуникации с гостями", ("гост", "guest")),
    Rule("коммуникации с собственниками", ("собствен", "owner")),
    Rule("ключи / карты доступа", ("ключ", "карта доступа")),
    Rule("уборка", ("уборк", "housekeeping")),
    Rule("техническая заявка", ("техническая заявка", "заявка")),
    Rule("ремонт", ("ремонт",)),
    Rule("пожарная безопасность", ("пожар",)),
    Rule("охрана", ("охран",)),
    Rule("парковка", ("парков",)),
    Rule("завтраки", ("завтрак",)),
    Rule("дополнительные услуги", ("дополнительные услуги", "доп услуги")),
    Rule("договор управления / аренды", ("договор управления", "аренд")),
    Rule("выплаты собственникам", ("выплат", "собствен")),
    Rule("коммунальные услуги", ("ку", "коммун")),
    Rule("отчёты собственникам", ("отчет собствен", "отчёт собствен")),
    Rule("страхование", ("страх",)),
    Rule("закупки", ("закуп",)),
    Rule("маркетинг", ("маркет",)),
    Rule("продажи", ("продаж",)),
    Rule("тарифы", ("тариф", "pricing")),
    Rule("финансы", ("финанс",)),
    Rule("касса", ("касса",)),
    Rule("бухгалтерия", ("бухгалтер",)),
    Rule("HR", ("hr", "кадр")),
    Rule("обучение", ("обуч",)),
    Rule("бренд / дизайн / медиа", ("бренд", "дизайн", "медиа")),
    Rule("операционные стандарты", ("sop", "стандарт", "регламент")),
    Rule("аналитика", ("аналит",)),
]

AUDIENCE_RULES = [
    Rule("гости", ("гост", "guest")),
    Rule("собственники", ("собствен", "owner")),
    Rule("сотрудники СПиР", ("спир", "front office", "reception")),
    Rule("GM", ("gm", "генеральный менеджер")),
    Rule("ХСК", ("хск", "housekeeping")),
    Rule("ИТС", ("итс", "инженер")),
    Rule("коммерческий отдел", ("коммерч", "revenue", "pricing")),
    Rule("бронирование", ("бронир", "booking")),
    Rule("маркетинг", ("маркет", "smm")),
    Rule("бухгалтерия", ("бухгалтер",)),
    Rule("кадры", ("кадр", "hr")),
    Rule("подрядчики", ("подряд", "contractor")),
    Rule("руководство RBI PM", ("rbi pm", "руковод")),
    Rule("внешние органы / проверяющие", ("провер", "роспотреб", "мчс", "налог")),
    Rule("страховая", ("страх",)),
]

SENSITIVITY_RULES = [
    Rule("owner_data", ("собствен", "owner", "инвестор")),
    Rule("guest_data", ("гост", "guest", "паспорт", "миграцион")),
    Rule("employee_data", ("сотрудник", "кадр", "hr", "табель", "персонал")),
    Rule("personal_data", ("персональные данные", "паспорт", "снилс", "инн", "телефон")),
    Rule("legal_contract", ("договор", "доверенность", "юрид", "legal")),
    Rule("financial", ("финанс", "платеж", "оплат", "выплат", "счет", "счёт")),
    Rule("accounting", ("бухгалтер", "акт", "счет-фактура", "счёт-фактура")),
    Rule("HR", ("hr", "кадр", "аттеста", "должност")),
    Rule("commercial", ("коммерч", "pricing", "тариф", "кп ")),
    Rule("security", ("охран", "доступ", "ключ", "карта доступа")),
    Rule("fire_safety", ("пожар", "эвакуац")),
    Rule("technical", ("техничес", "инженер", "чертеж", "чертёж", "схема")),
    Rule("media", ("фото", "видео", "медиа")),
    Rule("brand_sensitive", ("бренд", "логотип", "макет")),
    Rule("archive", ("архив", "archive")),
    Rule("operational", ("sop", "регламент", "инструкц", "чек")),
]


def classify_item(item: DriveInventoryItem) -> DriveInventoryItem:
    if item.is_google_sheet_skipped:
        return item
    text = normalize_name(f"{item.full_path} {item.name} {item.extension}")
    item.object_suggestion = choose_label(text, OBJECT_RULES, "объект не определён")
    item.department_suggestion = choose_label(text, DEPARTMENT_RULES, "не определено")
    item.function_suggestion = item.department_suggestion
    item.document_type_suggestion = choose_label(text, DOCUMENT_RULES, "неизвестно")
    item.document_family_suggestion = family_for_document_type(item.document_type_suggestion)
    item.process_suggestion = choose_label(text, PROCESS_RULES, "не определено")
    item.audience_suggestion = choose_label(text, AUDIENCE_RULES, "внутреннее использование")
    item.sensitivity_suggestion = choose_label(text, SENSITIVITY_RULES, "unknown")
    item.retention_suggestion = retention_for(item)
    item.confidence = confidence_for(item)
    item.action_recommendation = "SENSITIVE_REVIEW_REQUIRED" if is_sensitive(item) else "REVIEW_REQUIRED"
    item.reason = build_reason(item)
    return item


def choose_label(text: str, rules: Iterable[Rule], fallback: str) -> str:
    padded = f" {text} "
    for rule in rules:
        if any(token in padded for token in rule.tokens):
            return rule.label
    return fallback


def family_for_document_type(document_type: str) -> str:
    if document_type in {"регламент", "стандарт", "SOP", "инструкция", "алгоритм", "чек-лист", "памятка"}:
        return "стандарты / SOP / инструкции"
    if document_type in {"шаблон", "бланк", "заявление"}:
        return "шаблоны и формы"
    if "договор" in document_type or document_type in {"акт", "доверенность"}:
        return "договорной / юридический контур"
    if "отч" in document_type or document_type in {"реестр", "счёт"}:
        return "отчёты / реестры / финансы"
    if document_type in {"фото", "видео", "логотип", "макет", "презентация", "брендбук"}:
        return "маркетинг / медиа"
    if document_type == "неизвестно":
        return "неизвестно"
    return "операционные документы"


def retention_for(item: DriveInventoryItem) -> str:
    if item.document_type_suggestion in {"черновик", "временный файл"}:
        return "likely_short_term_review"
    if item.sensitivity_suggestion in {"legal_contract", "financial", "accounting", "HR", "employee_data", "owner_data"}:
        return "controlled_retention_review"
    if item.document_type_suggestion == "архивная копия":
        return "archive_review"
    return "standard_review"


def is_sensitive(item: DriveInventoryItem) -> bool:
    return item.sensitivity_suggestion not in {"unknown", "public_internal", "operational", "media", "archive"}


def confidence_for(item: DriveInventoryItem) -> str:
    signals = [
        item.object_suggestion not in {"объект не определён"},
        item.department_suggestion != "не определено",
        item.document_type_suggestion != "неизвестно",
        item.process_suggestion != "не определено",
        item.sensitivity_suggestion != "unknown",
    ]
    count = sum(1 for signal in signals if signal)
    if count >= 3:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def build_reason(item: DriveInventoryItem) -> str:
    parts: List[str] = []
    if item.object_suggestion != "объект не определён":
        parts.append(f"object={item.object_suggestion}")
    if item.department_suggestion != "не определено":
        parts.append(f"department={item.department_suggestion}")
    if item.document_type_suggestion != "неизвестно":
        parts.append(f"type={item.document_type_suggestion}")
    if item.sensitivity_suggestion != "unknown":
        parts.append(f"sensitivity={item.sensitivity_suggestion}")
    return "; ".join(parts) if parts else "No confident filename/path classification rule matched."
