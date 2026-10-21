#!/usr/bin/env python3
"""gapmap.py - contradiction mining: find the research gap by where studies disagree.

Collects abstracts (OpenAlex, or candidate files from `scholar.py search --out`),
extracts from each abstract by heuristic: country, population, design, sample size
and the DIRECTION of one named relation (positive / negative / none / mixed), then
reports a population x country matrix, the contradictions, the empty cells that
matter, the exact sentences behind every direction, and three draft gap sentences.

Every extraction is a CANDIDATE made by regex. The sentence it came from is printed
next to it so the agent can confirm or reject it. Nothing here is a verified claim.
Design words in recommendation sentences (future, further, should, warranted,
recommend, needed, call for) are never used as the study's design; a design named
in a sentence that speaks for the study itself (we, our, this study) is 'strong'.

Commands
  run       build the gap map for a topic and a relation
  selftest  run the extractors on built-in synthetic abstracts (no network)

gapmap.json (--json) top-level keys
  summary              studies, relation_sentences, studies_with_relation, directions, strong_direction, strong_only,
                       design_tagged, design_strong, design_unstated, topic, relation, date
  result               the RESULT line, or 'no relation sentences' (then only summary, result and studies are written)
  matrix               "population | country" -> {direction: count}; only cells with a stated direction
  direction_by_design  design -> {direction: count}
  contradictions       {positive: [...], negative: [...], cells: [...]}; strongest studies per side with doi, year, n,
                       design, country, population, strength, confidence, qualifiers, sentence, cues
  empty_cells          list of empty-cell notes (strings)
  sentences            every relation sentence: doi, year, study_direction, sentence_direction, confidence, cues,
                       qualifiers, matched_terms, sentence
  gap_statements       three draft gap sentences (strings; verify before use)
  studies              one object per abstract: doi, title, year, cites, venue, first_author, country, countries,
                       country_context, regions, ambiguous_places, arab_region, population, population_counts,
                       population_context, design, design_confidence (strong / weak / none), design_tags,
                       design_context, design_strength (tag -> strong / weak), design_skipped (designs named only
                       in recommendation sentences), n (integer or null; the value the tables print),
                       sample ({n, how, sentence} or null), direction, direction_confidence, qualifiers,
                       relation_sentences, has_abstract

Examples
  python -X utf8 gapmap.py run --topic '"social media" AND "academic performance"' \
      --relation "social media|academic performance" \
      --syn "social media=social networking,Facebook,Instagram,SNS" \
      --syn "academic performance=academic achievement,GPA,grades" --since 2015 --n 300 \
      --out gapmap.md --json gapmap.json
  python -X utf8 gapmap.py run --in cand.json --relation "sleep|GPA" --out gapmap.md
  python -X utf8 gapmap.py selftest

Cost: a live run is 2 OpenAlex list calls at most (per_page=200, 2 pages = 20 credits).
The fetched corpus is saved (--save-corpus, default gapmap_corpus.json) so reruns
with --in cost nothing.
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import openalex, oa_row, load_ledger, clean, norm_doi, table, short, TODAY, ARABIC_RE, HTTPError  # noqa: E402

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")

# ---------------------------------------------------------------- gazetteer
# "Canonical|alias;alias|demonym;demonym". Matched case-sensitively on word boundaries,
# longest alias first, so 'Nigeria' wins over 'Niger' and 'Papua New Guinea' over 'Guinea'.
GAZETTEER = """
Afghanistan||Afghan
Albania||Albanian
Algeria|الجزائر|Algerian
Angola||Angolan
Argentina||Argentine;Argentinian
Armenia||Armenian
Australia||Australian
Austria||Austrian
Azerbaijan||Azerbaijani
Bahrain|البحرين|Bahraini
Bangladesh||Bangladeshi
Belarus||Belarusian
Belgium||Belgian
Benin||Beninese
Bhutan||Bhutanese
Bolivia||Bolivian
Bosnia and Herzegovina|Bosnia|Bosnian
Botswana||Botswanan
Brazil|Brasil|Brazilian
Brunei||Bruneian
Bulgaria||Bulgarian
Burkina Faso||Burkinabe
Burundi||Burundian
Cambodia||Cambodian
Cameroon||Cameroonian
Canada||Canadian
Chad||Chadian
Chile||Chilean
China|People's Republic of China;PRC;Mainland China|Chinese
Colombia||Colombian
Comoros|جزر القمر|Comorian
Congo|Democratic Republic of the Congo;DR Congo;DRC;Republic of the Congo|Congolese
Costa Rica||Costa Rican
Croatia||Croatian
Cuba||Cuban
Cyprus||Cypriot
Czech Republic|Czechia|Czech
Denmark||Danish;Dane
Djibouti|جيبوتي|Djiboutian
Dominican Republic||Dominican
Ecuador||Ecuadorian
Egypt|مصر|Egyptian
El Salvador||Salvadoran
Estonia||Estonian
Ethiopia||Ethiopian
Fiji||Fijian
Finland||Finnish
France||French
Georgia||Georgian
Germany||German
Ghana||Ghanaian
Greece||Greek
Guatemala||Guatemalan
Guinea|Guinea-Bissau;Equatorial Guinea|Guinean
Haiti||Haitian
Honduras||Honduran
Hong Kong||Hongkonger
Hungary||Hungarian
Iceland||Icelandic
India||Indian
Indonesia||Indonesian
Iran||Iranian
Iraq|العراق|Iraqi
Ireland||Irish
Israel||Israeli
Italy||Italian
Ivory Coast|Cote d'Ivoire|Ivorian
Jamaica||Jamaican
Japan||Japanese
Jordan|الأردن;الاردن|Jordanian
Kazakhstan||Kazakh
Kenya||Kenyan
Kosovo||Kosovar
Kuwait|الكويت|Kuwaiti
Kyrgyzstan||Kyrgyz
Laos||Lao;Laotian
Latvia||Latvian
Lebanon|لبنان|Lebanese
Libya|ليبيا|Libyan
Lithuania||Lithuanian
Luxembourg||Luxembourgish
Madagascar||Malagasy
Malawi||Malawian
Malaysia||Malaysian
Maldives||Maldivian
Mali||Malian
Malta||Maltese
Mauritania|موريتانيا|Mauritanian
Mauritius||Mauritian
Mexico||Mexican
Moldova||Moldovan
Mongolia||Mongolian
Montenegro||Montenegrin
Morocco|المغرب|Moroccan
Mozambique||Mozambican
Myanmar|Burma|Burmese
Namibia||Namibian
Nepal||Nepalese;Nepali
Netherlands|the Netherlands;Holland|Dutch
New Zealand||New Zealander
Nicaragua||Nicaraguan
Niger||Nigerien
Nigeria||Nigerian
North Korea||North Korean
North Macedonia|Macedonia|Macedonian
Norway||Norwegian
Oman|سلطنة عمان;Sultanate of Oman|Omani
Pakistan||Pakistani
Palestine|Palestinian Territories;West Bank;Gaza;فلسطين|Palestinian
Panama||Panamanian
Papua New Guinea||Papua New Guinean
Paraguay||Paraguayan
Peru||Peruvian
Philippines|the Philippines|Filipino;Philippine
Poland||Polish
Portugal||Portuguese
Qatar|قطر|Qatari
Romania||Romanian
Russia|Russian Federation|Russian
Rwanda||Rwandan
Saudi Arabia|KSA;Kingdom of Saudi Arabia;السعودية;المملكة العربية السعودية|Saudi
Senegal||Senegalese
Serbia||Serbian
Sierra Leone||Sierra Leonean
Singapore||Singaporean
Slovakia||Slovak
Slovenia||Slovenian
Somalia|الصومال|Somali
South Africa||South African
South Korea|Korea;Republic of Korea|Korean
Spain||Spanish
Sri Lanka||Sri Lankan
Sudan|السودان|Sudanese
Sweden||Swedish
Switzerland||Swiss
Syria|Syrian Arab Republic;سوريا;سورية|Syrian
Taiwan||Taiwanese
Tajikistan||Tajik
Tanzania||Tanzanian
Thailand||Thai
Togo||Togolese
Trinidad and Tobago||Trinidadian
Tunisia|تونس|Tunisian
Turkey|Türkiye;Turkiye|Turkish
Turkmenistan||Turkmen
Uganda||Ugandan
Ukraine||Ukrainian
United Arab Emirates|UAE;U.A.E.;Emirates;الإمارات;الامارات|Emirati
United Kingdom|UK;U.K.;Britain;Great Britain;England;Scotland;Wales;Northern Ireland|British;English;Scottish;Welsh
United States|USA;U.S.A.;U.S.;US;United States of America;America|American
Uruguay||Uruguayan
Uzbekistan||Uzbek
Venezuela||Venezuelan
Vietnam|Viet Nam|Vietnamese
Yemen|اليمن|Yemeni
Zambia||Zambian
Zimbabwe||Zimbabwean
"""
ARAB_STATES = {"Algeria", "Bahrain", "Comoros", "Djibouti", "Egypt", "Iraq", "Jordan", "Kuwait", "Lebanon", "Libya",
               "Mauritania", "Morocco", "Oman", "Palestine", "Qatar", "Saudi Arabia", "Somalia", "Sudan", "Syria",
               "Tunisia", "United Arab Emirates", "Yemen"}
GCC = {"Bahrain", "Kuwait", "Oman", "Qatar", "Saudi Arabia", "United Arab Emirates"}
REGION_RE = re.compile(r"\b(Middle East(?:ern)?|MENA|Arab(?: world| countries| region| states| Gulf)?|Gulf (?:region|states|countries)|GCC|"
                       r"Sub-Saharan Africa|East Asia|Southeast Asia|South Asia|Central Asia|Latin America|Western Europe|Eastern Europe|"
                       r"Europe|Africa|Asia|North America|Scandinavia|Balkans|Caribbean|Oceania)\b|"
                       r"(الشرق الأوسط|الوطن العربي|العالم العربي|الدول العربية|الخليج العربي|دول الخليج)")
ARAB_REGION_WORDS = re.compile(r"Middle East|MENA|Arab|Gulf|GCC|الشرق الأوسط|الوطن العربي|العالم العربي|الدول العربية|الخليج", re.I)
AMBIGUOUS_PLACES = {"Jordan", "Georgia", "Chad", "Niger", "Mali", "Guinea", "Turkey", "Oman", "Congo"}


def _build_gazetteer():
    canon_of, names = {}, []
    for line in GAZETTEER.strip().splitlines():
        canon, aliases, demonyms = (line.split("|") + ["", ""])[:3]
        for name in [canon] + [a for a in aliases.split(";") if a] + [d for d in demonyms.split(";") if d]:
            canon_of[name] = canon
            names.append(name)
    names.sort(key=len, reverse=True)
    pat = "|".join(re.escape(n) for n in names)
    # Latin names need word boundaries; Arabic names get a non-letter guard plus an optional 'و/ب/ل/في' prefix.
    rx = re.compile(r"(?<![A-Za-z؀-ۿ])(?:[وبل]|في )?(" + pat + r")(?![A-Za-z؀-ۿ])")
    return canon_of, rx


COUNTRY_CANON, COUNTRY_RE = _build_gazetteer()
# Arabic 'عمان' is both Oman and Amman: matched only as part of 'سلطنة عمان' above.

# ---------------------------------------------------------------- populations
# (label, regex). Order = specificity; the first student subgroups absorb the generic 'students' count.
POP_GROUPS = [
    ("medical students", r"medical (?:college |school )?students|medicine students|medical undergraduates"),
    ("nursing students", r"nursing students|student nurses"),
    ("undergraduates", r"undergraduates?\b|undergraduate students|college students|bachelor'?s? students|freshm[ae]n|sophomores"),
    ("postgraduates", r"postgraduates?\b|postgraduate students|graduate students|master'?s students|doctoral students|phd students|"
                      r"طلاب الدراسات العليا|طلبة الدراسات العليا"),
    ("university students", r"university students|higher education students|tertiary students|students at (?:a |the )?(?:[A-Z]\w+ )?university|"
                            r"students of [A-Z][\w ]+ University|طلاب الجامع[ةا]ت?|طلبة الجامع[ةا]ت?|الطلبة الجامعيين|الطلاب الجامعيين|طالبات الجامع[ةا]"),
    ("school students", r"high[- ]school students|secondary[- ]school (?:students|pupils)|secondary students|middle[- ]school students|"
                        r"primary[- ]school (?:students|pupils)|elementary (?:school )?students|school students|schoolchildren|pupils|"
                        r"adolescents|teenagers|طلاب المدارس|طلبة المدارس|المراهقين|المراهقون|طلاب المرحلة الثانوية"),
    ("students (unspecified)", r"students|learners|طلاب|طلبة|الطالبات|طالبات"),
    ("teachers", r"teachers|faculty members|academics|lecturers|instructors|educators|المعلمين|المعلمات|المعلمون|معلمي|أعضاء هيئة التدريس"),
    ("nurses", r"nurses|nursing staff|الممرضين|الممرضات|الممرضون"),
    ("healthcare workers", r"health ?care (?:workers|professionals|providers|staff)|physicians|doctors|clinicians|medical staff|"
                           r"العاملين في (?:القطاع )?الصحي|الأطباء"),
    ("employees", r"employees|workers|staff|workforce|personnel|office workers|الموظفين|الموظفون|العاملين|العاملون|العمال"),
    ("managers", r"managers|executives|supervisors|المديرين|المدراء"),
    ("SMEs / firms", r"\bSMEs?\b|small and medium(?:-sized)? enterprises|small businesses|firms|companies|enterprises|organi[sz]ations|"
                     r"المنشآت الصغيرة والمتوسطة|الشركات|المؤسسات"),
    ("entrepreneurs", r"entrepreneurs|business owners|start-?ups|رواد الأعمال"),
    ("children", r"children|kids|preschoolers|الأطفال"),
    ("parents", r"parents|mothers|fathers|الوالدين|الأمهات|الآباء"),
    ("patients", r"patients|المرضى"),
    ("athletes", r"athletes|players|الرياضيين"),
    ("general adults", r"adults|general population|general public|consumers|customers|citizens|residents|young adults|emerging adults|"
                       r"internet users|social media users|البالغين|المستهلكين|المواطنين|المستخدمين"),
]
POP_RES = [(label, re.compile(rx, re.I)) for label, rx in POP_GROUPS]
STUDENT_SUBGROUPS = {"medical students", "nursing students", "undergraduates", "postgraduates", "university students", "school students"}

# ---------------------------------------------------------------- designs
DESIGN_GROUPS = [
    ("meta-analysis", r"meta-?analy(?:sis|ses|tic)|systematic review|umbrella review|التحليل البعدي|مراجعة منهجية"),
    ("review", r"literature review|scoping review|narrative review|bibliometric|مراجعة أدبية|مراجعة الأدبيات"),
    ("mixed methods", r"mixed[- ]methods?|sequential explanatory|convergent (?:parallel )?design|المنهج المختلط"),
    ("experiment", r"randomi[sz]ed|\bRCTs?\b|quasi-?experiment(?:al)?|experiment(?:al|s)?\b|"
                   r"intervention (?:study|trial|program|programme|group|was|were)|(?:an|the|our) intervention\b|pre-?test|post-?test|"
                   r"control group|تجريبي|شبه تجريبي|المجموعة الضابطة"),
    ("longitudinal", r"longitudinal|panel (?:data|study|survey)|prospective|cohort study|cross-?lagged|follow-?up|two-?wave|three-?wave|"
                     r"\bwaves?\b|diary study|time-?lagged|دراسة طولية|طولي"),
    ("cross-sectional", r"cross-?sectional|correlational|الدراسة المقطعية|مقطعي|ارتباطي"),
    ("qualitative", r"qualitative|semi-?structured interviews?|in-depth interviews?|\binterviews?\b|focus groups?|thematic analysis|"
                    r"phenomenolog|grounded theory|ethnograph|content analysis|نوعي|المقابلات|مجموعات التركيز|التحليل الموضوعي"),
    ("survey (design unstated)", r"survey|questionnaire|self-?report|استبانة|استبيان|المسح"),
]
DESIGN_RES = [(label, re.compile(rx, re.I)) for label, rx in DESIGN_GROUPS]
DESIGN_PRIORITY = ("mixed methods", "meta-analysis", "review", "experiment", "longitudinal", "cross-sectional", "qualitative",
                   "survey (design unstated)")
DESIGN_WEIGHT = {"meta-analysis": 5, "longitudinal": 4, "experiment": 4, "mixed methods": 3, "cross-sectional": 2,
                 "survey (design unstated)": 1.5, "qualitative": 1, "review": 1, "unstated": 0}
# A sentence that recommends, calls for or hypothesises a design is not the study's design.
DESIGN_SKIP_RE = re.compile(r"\b(?:future|further|warranted|recommend(?:ed|s|ation|ations)?|should|needed|calls? for|"
                            r"suggest(?:s|ed)?\s+(?:that\s+)?(?:a\s+)?future)\b|توصي|يوصي|ينبغي|يجب|مستقبلية|المستقبل", re.I)
# A design named in a sentence that speaks for the study itself (we / our / this study) is a stronger tag.
SELF_NOUN = r"[\w-]*?(?:study|paper|research|article|work|survey|trial|analysis|review|experiment|investigation)"
DESIGN_SELF_RE = re.compile(r"\b(?:we|our|this (?:[\w-]+ ){0,3}" + SELF_NOUN + r"|the (?:present|current) (?:[\w-]+ ){0,2}" + SELF_NOUN + r")\b|"
                            r"هذه الدراسة|الدراسة الحالية|قمنا|أجرينا", re.I)

# ---------------------------------------------------------------- sample size
SAMPLE_NOUN = (r"students|participants|respondents|undergraduates|postgraduates|adolescents|employees|teachers|nurses|users|subjects|"
               r"adults|children|individuals|people|pupils|learners|faculty|workers|managers|patients|youths?|graduates|freshmen|"
               r"firms|companies|enterprises|SMEs|households|parents|teenagers|athletes|physicians|doctors|women|men|"
               r"طالب|طالبة|طالبًا|طالباً|طالبا|طلاب|طلبة|مشارك|مشاركًا|مشاركاً|مشاركا|موظف|موظفًا|موظفاً|معلم|معلمًا|معلماً|معلمة|ممرض|ممرضة|مريض|فرد|فردًا|فرداً|مستجيب|مستجيبًا|شركة|منشأة")
N_PATTERNS = [
    ("N =", re.compile(r"\b[Nn]\s*=\s*(\d[\d,]{0,7})(?!\.\d)")),
    ("sample of", re.compile(r"(?:sample|total)\s+of\s+(\d[\d,]{0,7})\b|(?:عينة|عددهم|قوامها|بلغت)\s*(?:من|مكونة من|قدرها)?\s*\(?(\d[\d,]{0,7})\)?")),
    ("count + noun", re.compile(r"\b(\d[\d,]{0,7})\s+(?:[A-Za-z\-]+\s+){0,3}(?:" + SAMPLE_NOUN + r")\b", re.I)),
]

# ---------------------------------------------------------------- direction lexicon
LINK = r"(?:associat|relat|correlat|effect|impact|influenc|predict|link|contribut|connect|affect|role)"
# STRONG cues state the sign of the relation; WEAK cues are change words that also appear in aims and advice.
POS_STRONG = re.compile(
    r"positive(?:ly)?(?: and (?:statistically )?significant(?:ly)?)?(?:[\w\s,]{0,25})?" + LINK + r"|\bpositively\b|"
    r"\bbeneficial " + LINK + r"|\bdirect(?:ly)? proportional\b|إيجابي|ايجابي|موجب|طردي", re.I)
POS_WEAK = re.compile(
    r"\b(?:increas|improv|enhanc|facilitat|boost|promot|strengthen|foster|benefit|beneficial|favou?rabl)\w*|"
    r"\bhigher(?! education)\b|\bbetter\b|\bgreater\b|\bsupport(?:s|ed|ive)?\b (?:academic|learning|performance|achievement)|"
    r"ارتفاع|تحسين|تحسن|يعزز|تعزيز|زيادة", re.I)
NEG_STRONG = re.compile(
    r"negative(?:ly)?(?: and (?:statistically )?significant(?:ly)?)?(?:[\w\s,]{0,25})?" + LINK + r"|\bnegatively\b|"
    r"\b(?:detrimental|adverse|harmful|inverse)(?:ly)? " + LINK + r"|\binversely\b|\binverse(?:ly)? proportional\b|"
    r"سلبي|سالب|عكسي", re.I)
NEG_WEAK = re.compile(
    r"\b(?:decreas|reduc|lower|poorer|worse|declin|impair|hinder|harm|detriment|adverse|damag|distract|undermin|deteriorat|weaken)\w*|"
    r"\bat the expense of\b|\bprocrastinat\w*|انخفاض|تراجع|تدهور|يضعف|إضعاف|يعيق|ضار|تشتت", re.I)
# Aims, recommendations and hypotheses are not findings: with only weak cues they stay 'unstated'.
AIM_RE = re.compile(r"\b(?:aims?|aimed|purpose|objectives?|goal|recommend\w*|should|urged|guidelines|implications|hypothesi[sz]\w*|"
                    r"we (?:propose|argue|suggest)|highlights? the (?:importance|need)|this (?:study|paper|research|article) (?:examines?|explores?|"
                    r"investigates?|seeks|sought|attempts?)|to (?:examine|explore|investigate|determine|assess|identify)\b|in order to|"
                    r"future research|further research|need(?:s|ed)? to)\b|تهدف|هدفت|يهدف|توصي|يوصي|التوصيات|ينبغي|يجب", re.I)
# Construct qualifiers: the sentence may be about addiction or educational use, not plain use.
QUALIFIER_RE = re.compile(r"\b(addiction|addictive|problematic|excessive|overuse|compulsive|fatigue|multitasking|educational use|"
                          r"academic use|collaborative learning|for learning|for academic purposes|entertainment use|"
                          r"إدمان|الإدمان|المفرط|التعليمي)\b", re.I)
NONE_RE = re.compile(
    r"\b(?:no|non-?|not|neither|without a)\s*(?:statistically\s+)?significant\w*|\binsignificant\w*|\bnot significant\w*|"
    r"\bno (?:significant |direct |clear |meaningful |overall |evidence of (?:a |an )?)?(?:relationship|association|correlation|effect|impact|influence|link|difference)\b|"
    r"\b(?:un|not )related\b|\bdid not (?:predict|affect|influence|correlate|relate|differ|have)\b|\bdoes not (?:predict|affect|influence|correlate|relate)\b|"
    r"\bwas not (?:associated|related|correlated|linked)\b|\bwere not (?:associated|related|correlated|linked)\b|\bfailed to (?:predict|find)\b|"
    r"\bno evidence\b|\bnull (?:effect|finding|result)s?\b|"
    r"لا توجد علاقة|لا يوجد (?:أثر|تأثير|ارتباط|فرق)|غير دال|غير دالة|لم (?:يؤثر|ترتبط|يرتبط)|عدم وجود (?:علاقة|أثر|فروق)", re.I)
MIX_RE = re.compile(
    r"\bmixed\b|\bdepend(?:s|ed|ing)? on\b|\bmoderat(?:ed|es|ing|or|ion)\b|\bcurvilinear\b|\binverted[- ]U\b|\bu-shaped\b|\bnon-?linear\b|"
    r"\bboth positive and negative\b|\bdouble-?edged\b|\bconditional on\b|\bvaries? (?:by|across|with)\b|\bdiffer(?:s|ed) (?:by|across)\b|"
    r"\bwhereas\b|\bbut not\b|\bonly (?:when|for|among|if)\b|"
    r"متباين|يعتمد على|تعتمد على|معدِّل|المعدل|تعديل|خطي الشكل|يختلف باختلاف|تختلف باختلاف", re.I)
NEGATION_BEFORE = re.compile(r"\b(?:no|not|neither|nor|without|lack of|absence of|never|rather than)\b[\w\s]{0,20}$|(?:لا|لم|ليس|ليست|عدم|غير)\s*$")

TERM_STOP = {"of", "the", "and", "in", "on", "a", "an", "to", "with", "for", "among", "between", "their", "its"}
ABBREV = r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bet al\.)(?<!\bvs\.)(?<!\bFig\.)(?<!\bDr\.)(?<!\bNo\.)(?<!\bSt\.)(?<!\bcf\.)(?<!\bapprox\.)"
SENT_SPLIT = re.compile(ABBREV + r"(?<=[.!?؟])\s+(?=[A-Z0-9\"'(\[؀-ۿ])")
DIRECTION_SYMBOL = {"positive": "+", "negative": "-", "none": "0", "mixed": "~"}


# ---------------------------------------------------------------- extraction

def sentences(text):
    text = clean(text)
    if not text:
        return []
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def stem(tok):
    if tok.isupper():
        return tok.lower()             # acronyms (SNS, GPA) are matched whole, never trimmed
    t = tok.lower()
    if len(t) > 5 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 5 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 5 and t.endswith("ed"):
        return t[:-2]
    if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def term_regexes(phrase):
    """A phrase matches a sentence when every content token of it appears as a word prefix.
    'academic performance' matches 'academic performances'; 'GPA' matches 'GPA'; Arabic tokens allow 'ال'."""
    out = []
    for tok in re.findall(r"[\w؀-ۿ'\-]+", phrase):
        if tok.lower() in TERM_STOP or len(tok) < 2:
            continue
        if ARABIC_RE.search(tok):
            out.append(re.compile(r"(?<![\w؀-ۿ])(?:ال)?" + re.escape(tok) + r"[\w؀-ۿ]*"))
        else:
            out.append(re.compile(r"(?<![\w])" + re.escape(stem(tok)) + r"\w*", re.I))
    return out


def parse_relation(relation, syn_args):
    """'a|b' + ['a=s1,s2', 'b=s3'] -> two lists of (label, [token regexes])."""
    if not relation or "|" not in relation:
        return None
    a, b = [x.strip() for x in relation.split("|", 1)]
    syn = {a: [a], b: [b]}
    for s in syn_args or []:
        if "=" not in s:
            continue
        term, alts = s.split("=", 1)
        term = term.strip()
        key = next((k for k in (a, b) if k.lower() == term.lower()), None)
        if key is None:
            print(f"[gapmap] --syn '{term}' is neither side of --relation; ignored", file=sys.stderr)
            continue
        syn[key] += [x.strip() for x in alts.split(",") if x.strip()]
    return [(a, [(alt, term_regexes(alt)) for alt in syn[a]]), (b, [(alt, term_regexes(alt)) for alt in syn[b]])]


def side_hit(side_alts, sentence):
    for alt, regs in side_alts:
        if regs and all(r.search(sentence) for r in regs):
            return alt
    return None


def classify_direction(sentence):
    """-> (direction, cues, confidence).

    confidence 'strong': the sentence states the sign (positively / negative association / no significant...).
    confidence 'weak': only change words (higher, reduced, improve...); these are skipped in aim/recommendation sentences.
    A direction cue preceded by a negation within ~25 chars counts as 'none'."""
    cues = {"positive": [], "negative": [], "none": [], "mixed": []}
    strong = {"positive": False, "negative": False}
    for label, rx, is_strong in (("positive", POS_STRONG, True), ("negative", NEG_STRONG, True),
                                 ("positive", POS_WEAK, False), ("negative", NEG_WEAK, False)):
        for m in rx.finditer(sentence):
            before = sentence[max(0, m.start() - 25): m.start()]
            if NEGATION_BEFORE.search(before):
                cues["none"].append("not " + m.group(0))
            elif m.group(0) not in cues[label]:
                cues[label].append(m.group(0))
                strong[label] = strong[label] or is_strong
    cues["none"] += [m.group(0) for m in NONE_RE.finditer(sentence)]
    cues["mixed"] += [m.group(0) for m in MIX_RE.finditer(sentence)]
    pos, neg, none, mix = (bool(cues[k]) for k in ("positive", "negative", "none", "mixed"))
    sp, sn = strong["positive"], strong["negative"]
    aim = bool(AIM_RE.search(sentence))
    if aim and not (sp or sn or none):
        return "unstated", (["aim/recommendation: " + c for c in cues["positive"] + cues["negative"]][:3]), "weak"
    if mix and (pos or neg or none):
        d, conf = "mixed", "strong"          # an explicit moderator / contrast word states the shape of the relation
    elif sp and sn:
        d, conf = "mixed", "strong"
    elif sp:
        d, conf = "positive", "strong"
    elif sn:
        d, conf = "negative", "strong"
    elif none:
        d, conf = "none", "strong"
    elif pos and neg:
        d, conf = "mixed", "weak"
    elif pos:
        d, conf = "positive", "weak"
    elif neg:
        d, conf = "negative", "weak"
    elif mix:
        d, conf = "mixed", "weak"
    else:
        d, conf = "unstated", "weak"
    flat = [c for k in ("positive", "negative", "none", "mixed") for c in cues[k]]
    return d, flat, conf


def extract_countries(text):
    found, ctx = Counter(), {}
    for m in COUNTRY_RE.finditer(text):
        canon = COUNTRY_CANON[m.group(1)]
        found[canon] += 1
        ctx.setdefault(canon, short(text[max(0, m.start() - 40): m.end() + 40], 110))
    regions = sorted({(m.group(1) or m.group(2)) for m in REGION_RE.finditer(text)})
    return found, ctx, regions


def extract_population(text):
    counts, ctx = {}, {}
    for label, rx in POP_RES:
        ms = list(rx.finditer(text))
        if ms:
            counts[label] = len(ms)
            m = ms[0]
            ctx[label] = short(text[max(0, m.start() - 40): m.end() + 40], 110)
    generic = counts.pop("students (unspecified)", 0)
    subs = [k for k in counts if k in STUDENT_SUBGROUPS]
    if subs:
        best = max(subs, key=lambda k: counts[k])
        counts[best] += generic
    elif generic:
        counts["students (unspecified)"] = generic
    if not counts:
        return "unstated", {}, {}
    primary = max(counts, key=lambda k: (counts[k], -[p[0] for p in POP_GROUPS].index(k)))
    return primary, counts, ctx


def extract_design(text):
    """Sentence by sentence: a recommendation sentence (DESIGN_SKIP_RE) never tags a design; a design named in a
    sentence in the study's own voice (DESIGN_SELF_RE) is 'strong', any other is 'weak'. The primary design is the
    highest-priority strong tag, else the highest-priority weak tag, else 'unstated'."""
    ctx, strength_of, skipped = {}, {}, []
    for s in sentences(text):
        if DESIGN_SKIP_RE.search(s):
            hits = [label for label, rx in DESIGN_RES if rx.search(s)]
            if hits:
                skipped.append({"designs": hits, "sentence": short(s, 160)})
            continue
        level = "strong" if DESIGN_SELF_RE.search(s) else "weak"
        for label, rx in DESIGN_RES:
            m = rx.search(s)
            if m and (label not in ctx or (level == "strong" and strength_of[label] == "weak")):
                ctx[label] = short(s[max(0, m.start() - 40): m.end() + 40], 110)
                strength_of[label] = level
    tags = [label for label in DESIGN_PRIORITY if label in strength_of]
    primary, confidence = "unstated", "none"
    for level in ("strong", "weak"):
        pick = next((label for label in DESIGN_PRIORITY if strength_of.get(label) == level), None)
        if pick:
            primary, confidence = pick, level
            break
    return {"primary": primary, "confidence": confidence, "tags": tags, "context": ctx, "strength": strength_of, "skipped": skipped}


def extract_n(text):
    text = text.translate(ARABIC_DIGITS)
    best = None
    for how, rx in N_PATTERNS:
        vals = []
        for m in rx.finditer(text):
            raw = next(g for g in m.groups() if g)
            try:
                v = int(raw.replace(",", ""))
            except ValueError:
                continue
            if v < 5 or (how != "N =" and 1900 <= v <= 2035):
                continue
            vals.append((v, short(text[max(0, m.start() - 40): m.end() + 40], 110)))
        if vals:
            v, snippet = max(vals)
            best = {"n": v, "how": how, "sentence": snippet}
            break                      # 'N =' beats 'sample of' beats 'count + noun'
    return best


def analyse_study(row, relation):
    title = clean(row.get("title") or "")
    if title and not re.search(r"[.!?؟]$", title):
        title += "."                   # keep the title its own sentence
    text = " ".join(x for x in (title, clean(row.get("abstract") or "")) if x)
    countries, c_ctx, regions = extract_countries(text)
    pop, pop_counts, pop_ctx = extract_population(text)
    design = extract_design(text)
    n = extract_n(text)
    primary_country = countries.most_common(1)[0][0] if countries else None
    arab = bool(set(countries) & ARAB_STATES) or bool(ARAB_REGION_WORDS.search(" ".join(regions)))
    rel_sents = []
    if relation:
        (a, a_alts), (b, b_alts) = relation
        for s in sentences(text):
            ha, hb = side_hit(a_alts, s), side_hit(b_alts, s)
            if ha and hb:
                d, cues, conf = classify_direction(s)
                rel_sents.append({"sentence": s, "direction": d, "confidence": conf, "cues": cues, "matched": [ha, hb],
                                  "qualifiers": sorted({m.group(1).lower() for m in QUALIFIER_RE.finditer(s)})})
    # Study direction: strong sentences outrank weak ones; disagreement among the ones that count = mixed.
    strong_dirs = {x["direction"] for x in rel_sents if x["direction"] != "unstated" and x["confidence"] == "strong"}
    weak_dirs = {x["direction"] for x in rel_sents if x["direction"] != "unstated" and x["confidence"] == "weak"}
    confidence = "strong" if strong_dirs else ("weak" if weak_dirs else "none")
    stated = strong_dirs or weak_dirs
    if not rel_sents:
        direction = "no relation sentence"
    elif not stated:
        direction = "unstated"
    elif len(stated) == 1:
        direction = next(iter(stated))
    else:
        direction = "mixed"
    qualifiers = sorted({q for x in rel_sents for q in x["qualifiers"]})
    return {
        "doi": row.get("doi") or "", "title": row.get("title") or "", "year": row.get("year"),
        "cites": row.get("cites"), "venue": row.get("venue") or "", "first_author": row.get("first_author") or "",
        "country": primary_country, "countries": dict(countries), "country_context": c_ctx, "regions": regions,
        "ambiguous_places": sorted(set(countries) & AMBIGUOUS_PLACES), "arab_region": arab,
        "population": pop, "population_counts": pop_counts, "population_context": pop_ctx,
        "design": design["primary"], "design_confidence": design["confidence"], "design_tags": design["tags"],
        "design_context": design["context"], "design_strength": design["strength"], "design_skipped": design["skipped"],
        "n": n["n"] if n else None, "sample": n,
        "direction": direction, "direction_confidence": confidence, "qualifiers": qualifiers,
        "relation_sentences": rel_sents, "has_abstract": bool(row.get("abstract")),
    }


def strength(st):
    s = DESIGN_WEIGHT.get(st["design"], 0)
    if st.get("n"):
        s += min(math.log10(st["n"]), 4)
    if st.get("cites"):
        s += 0.5 * min(math.log10(st["cites"] + 1), 3)
    return round(s, 1)


# ---------------------------------------------------------------- corpus

def load_candidates(paths):
    rows, seen = [], set()
    for p in paths:
        if p.lower().endswith(".jsonl"):
            items = load_ledger(p)
        else:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("results", data) if isinstance(data, dict) else data
        for r in items:
            key = (norm_doi(r.get("doi") or "").lower() or clean(r.get("title") or "").lower())
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({"doi": norm_doi(r.get("doi") or ""), "title": clean(r.get("title")), "year": r.get("year"),
                         "cites": r.get("cites", (r.get("cited_by") or {}).get("openalex")),
                         "first_author": r.get("first_author") or (r["authors"][0].get("family", "") if r.get("authors") and isinstance(r["authors"][0], dict) else ""),
                         "venue": r.get("venue") or r.get("container") or "", "abstract": clean(r.get("abstract"))})
    return rows


def fetch_openalex(topic, since, n):
    """title_and_abstract.search, per_page=200, at most 2 pages (20 credits). Abstracts rebuilt."""
    filters = [f"title_and_abstract.search:{topic}", "is_retracted:false", "has_abstract:true"]
    if since:
        filters.append(f"from_publication_date:{since}-01-01")
    pages = min(2, max(1, math.ceil(min(n, 400) / 200)))
    rows, total = [], None
    for page in range(1, pages + 1):
        params = {"filter": ",".join(filters), "per_page": 200, "page": page, "sort": "cited_by_count:desc",
                  "select": "id,doi,display_name,publication_year,cited_by_count,primary_location,authorships,type,"
                            "open_access,is_retracted,abstract_inverted_index"}
        print(f"[openalex] list call {page}/{pages} (10 credits): title_and_abstract.search={topic}", file=sys.stderr)
        data = openalex("works", params) or {}
        total = (data.get("meta") or {}).get("count", total)
        got = [oa_row(w) for w in data.get("results", [])]
        rows += got
        if len(got) < 200:
            break
    seen, uniq = set(), []
    for r in rows:
        k = r["doi"].lower() or r["title"].lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq[:n], total


# ---------------------------------------------------------------- reporting

def cell_label(dirs):
    c = Counter(dirs)
    parts = [f"{DIRECTION_SYMBOL[d]}{c[d]}" for d in ("positive", "negative", "none", "mixed") if c[d]]
    return f"{len(dirs)}" + (" (" + " ".join(parts) + ")" if parts else "")


def build_report(studies, topic, relation_text, corpus_note, strong_only=False):
    out, J = [], {}
    rel = [s for s in studies if s["direction"] != "no relation sentence"]
    stated = [s for s in rel if s["direction"] != "unstated" and (not strong_only or s["direction_confidence"] == "strong")]
    n_strong = sum(1 for s in stated if s["direction_confidence"] == "strong")
    by_dir = Counter(s["direction"] for s in stated)
    n_sent = sum(len(s["relation_sentences"]) for s in studies)
    a_txt, b_txt = [x.strip() for x in relation_text.split("|", 1)]

    out.append(f"# Gap map: {a_txt} | {b_txt}")
    out.append("")
    out.append(f"Corpus: {len(studies)} abstracts ({corpus_note}). Relation sentences: {n_sent} in {len(rel)} studies. "
               f"Direction stated in {len(stated)} studies ({n_strong} from a sign-stating sentence, {len(stated) - n_strong} from change words only"
               + (", --strong-only" if strong_only else "") + "): " +
               ", ".join(f"{d} {by_dir[d]}" for d in ("positive", "negative", "none", "mixed") if by_dir[d]) + ".")
    designed = [s for s in studies if s["design"] != "unstated"]
    n_design_strong = sum(1 for s in designed if s["design_confidence"] == "strong")
    out.append(f"Design tagged in {len(designed)} of {len(studies)} studies ({n_design_strong} from a sentence in the study's own voice: "
               f"we / our / this study; {len(designed) - n_design_strong} from another sentence), unstated in {len(studies) - len(designed)}. "
               "Design words in recommendation sentences (future, further, should, warranted...) are not counted.")
    out.append("")
    out.append("Every value below is a regex CANDIDATE with the sentence it came from. Confirm before citing. "
               "The corpus is one OpenAlex query, not a systematic search: 'no study' means 'none in this corpus'. "
               "A 'qualifier' (addiction, problematic, educational use...) means the sentence may be about a narrower construct.")
    out.append("")
    J["summary"] = {"studies": len(studies), "relation_sentences": n_sent, "studies_with_relation": len(rel),
                    "directions": dict(by_dir), "strong_direction": n_strong, "strong_only": strong_only,
                    "design_tagged": len(designed), "design_strong": n_design_strong, "design_unstated": len(studies) - len(designed),
                    "topic": topic, "relation": relation_text, "date": TODAY}

    if n_sent == 0:
        msg = (f"RESULT: NO RELATION SENTENCES. No sentence in {len(studies)} abstracts mentions both terms "
               f"'{a_txt}' and '{b_txt}' (or their synonyms). No matrix, contradictions or gap statements are produced: "
               "either the relation is not studied in this corpus, or the terms need synonyms (--syn), or the topic query is off.")
        out.append(msg)
        J["result"] = "no relation sentences"
        return "\n".join(out), J, msg

    # (1) matrix population x country
    out.append("## 1. Matrix: population x country (studies with a stated direction)")
    out.append("")
    out.append("Cell = count (+positive -negative 0none ~mixed). Countries ranked by study count; Arab-region column aggregates the 22 Arab states.")
    out.append("")
    countries = Counter(s["country"] or "unstated" for s in stated)
    cols = [c for c, _ in countries.most_common(10)]
    if "unstated" in countries and "unstated" not in cols:
        cols.append("unstated")
    pops = [p for p, _ in Counter(s["population"] for s in stated).most_common()]
    matrix = {}
    rows = []
    for p in pops:
        row = [p]
        for c in cols + ["Arab region", "all"]:
            if c == "Arab region":
                cell = [s["direction"] for s in stated if s["population"] == p and s["arab_region"]]
            elif c == "all":
                cell = [s["direction"] for s in stated if s["population"] == p]
            else:
                cell = [s["direction"] for s in stated if s["population"] == p and (s["country"] or "unstated") == c]
            matrix[(p, c)] = dict(Counter(cell))
            row.append(cell_label(cell) if cell else "")
        rows.append(row)
    total_row = ["all"]
    for c in cols + ["Arab region", "all"]:
        if c == "Arab region":
            cell = [s["direction"] for s in stated if s["arab_region"]]
        elif c == "all":
            cell = [s["direction"] for s in stated]
        else:
            cell = [s["direction"] for s in stated if (s["country"] or "unstated") == c]
        total_row.append(cell_label(cell) if cell else "")
    rows.append(total_row)
    out.append(table(rows, ["population \\ country"] + cols + ["Arab region", "all"]))
    out.append("")
    J["matrix"] = {f"{p} | {c}": v for (p, c), v in matrix.items() if v}
    # direction x design
    designs = [d for d, _ in Counter(s["design"] for s in stated).most_common()]
    out.append("Direction x design:")
    out.append("")
    dd = []
    for d in designs:
        cell = [s["direction"] for s in stated if s["design"] == d]
        dd.append([d, cell_label(cell)])
    out.append(table(dd, ["design", "studies (+ - 0 ~)"]))
    out.append("")
    J["direction_by_design"] = {d: dict(Counter(s["direction"] for s in stated if s["design"] == d)) for d in designs}

    # (2) contradictions
    out.append("## 2. Contradictions (same relation, opposite directions)")
    out.append("")
    rank = lambda s: (s["direction_confidence"] == "strong", strength(s))
    pos = sorted([s for s in stated if s["direction"] == "positive"], key=rank, reverse=True)
    neg = sorted([s for s in stated if s["direction"] == "negative"], key=rank, reverse=True)
    J["contradictions"] = {"positive": [], "negative": [], "cells": []}
    if pos and neg:
        out.append(f"{len(pos)} studies report a POSITIVE and {len(neg)} a NEGATIVE relation. Strongest on each side "
                   "(strength = design weight + log10 N + half log10 cites):")
        out.append("")
        for label, group in (("Positive", pos), ("Negative", neg)):
            out.append(f"**{label}**")
            out.append("")
            rows = []
            for s in group[:6]:
                sent = next((x for x in s["relation_sentences"] if x["direction"] == s["direction"] and x["confidence"] == "strong"),
                            next((x for x in s["relation_sentences"] if x["direction"] == s["direction"]), s["relation_sentences"][0]))
                rows.append([str(strength(s)), str(s["year"] or ""), str(s["n"]) if s["n"] is not None else "?",
                             s["design"], s["country"] or "?", s["population"], s["doi"] or "(no DOI)",
                             s["direction_confidence"], ", ".join(s["qualifiers"]) or "-", short(sent["sentence"], 160)])
                J["contradictions"][label.lower()].append({"doi": s["doi"], "year": s["year"], "n": s["n"],
                                                           "design": s["design"], "country": s["country"], "population": s["population"],
                                                           "strength": strength(s), "confidence": s["direction_confidence"],
                                                           "qualifiers": s["qualifiers"], "sentence": sent["sentence"], "cues": sent["cues"]})
            out.append(table(rows, ["strength", "year", "N", "design", "country", "population", "doi", "confidence", "qualifier",
                                    "sentence (candidate)"]))
            out.append("")
        cells = []
        for (p, c), v in matrix.items():
            if c in ("all",):
                continue
            if v.get("positive") and v.get("negative"):
                cells.append((p, c, v["positive"], v["negative"]))
        # Sharpest first: a named country beats 'unstated', then the smaller side, then the cell size.
        cells.sort(key=lambda x: (x[1] != "unstated", min(x[2], x[3]), x[2] + x[3]), reverse=True)
        if cells:
            out.append("Disagreement inside one cell (same population AND same country/region), the sharpest contradictions:")
            out.append("")
            out.append(table([[p, c, str(a), str(b)] for p, c, a, b in cells], ["population", "country", "+", "-"]))
            out.append("")
            J["contradictions"]["cells"] = [{"population": p, "country": c, "positive": a, "negative": b} for p, c, a, b in cells]
        else:
            out.append("No single population x country cell holds both directions: the disagreement runs across contexts, "
                       "which is itself a candidate explanation (context, not the relation, may differ).")
            out.append("")
    else:
        out.append(f"No contradiction: positive {len(pos)}, negative {len(neg)}. The corpus does not disagree on direction; "
                   "the gap (if any) is in section 3.")
        out.append("")

    # (3) empty cells
    out.append("## 3. Empty cells that matter (in this corpus)")
    out.append("")
    gaps = []
    design_counts = Counter(s["design"] for s in rel)
    for d in ("longitudinal", "experiment", "meta-analysis", "qualitative", "mixed methods"):
        k = design_counts.get(d, 0)
        if k == 0:
            gaps.append(f"No {d} study among the {len(rel)} studies that state the relation.")
        elif k <= 2:
            gaps.append(f"Only {k} {d} stud{'y' if k == 1 else 'ies'} among {len(rel)}.")
    for d in ("positive", "negative"):
        group = [s for s in stated if s["direction"] == d]
        if group:
            strong = [s for s in group if s["design"] in ("longitudinal", "experiment", "meta-analysis")]
            if not strong:
                gaps.append(f"Every {d} finding comes from a cross-sectional/survey/qualitative/unstated design: "
                            f"no longitudinal, experimental or meta-analytic study reports a {d} relation.")
    arab = [s for s in rel if s["arab_region"]]
    if not arab:
        gaps.append("No Arab-region sample (none of the 22 Arab states, no Middle East/MENA/Gulf mention).")
    else:
        present = sorted({c for s in arab for c in s["countries"] if c in ARAB_STATES})
        missing_gcc = sorted(GCC - set(present))
        gaps.append(f"Arab-region studies: {len(arab)} ({', '.join(present) or 'region named, no state'}). "
                    f"GCC states absent: {', '.join(missing_gcc) or 'none'}.")
    pop_counts = Counter(s["population"] for s in rel)
    absent = [p for p, _ in POP_GROUPS if p not in pop_counts and p != "students (unspecified)"]
    gaps.append("Populations with no study: " + ", ".join(absent) + ".")
    big = [s for s in rel if s["n"] is not None and s["n"] >= 1000]
    if not big:
        gaps.append("No study with N >= 1000 (sample size candidates).")
    years = [s["year"] for s in rel if s["year"]]
    if years and max(years) < int(TODAY[:4]) - 1:
        gaps.append(f"Nothing from {int(TODAY[:4]) - 1} onward; latest study is {max(years)}.")
    no_n = sum(1 for s in rel if s["n"] is None)
    gaps.append(f"Sample size not found in {no_n}/{len(rel)} abstracts; country not found in "
                f"{sum(1 for s in rel if not s['country'])}/{len(rel)}; design unstated in {design_counts.get('unstated', 0)}/{len(rel)}.")
    for g in gaps:
        out.append(f"- {g}")
    out.append("")
    J["empty_cells"] = gaps

    # (4) sentences
    out.append("## 4. Sentences behind each direction (confirm these)")
    out.append("")
    J["sentences"] = []
    for d in ("positive", "negative", "none", "mixed", "unstated"):
        group = [s for s in rel if s["direction"] == d]
        if not group:
            continue
        out.append(f"### {d} ({len(group)} studies)")
        out.append("")
        rows = []
        for s in group:
            for x in s["relation_sentences"]:
                rows.append([s["doi"] or short(s["title"], 40), str(s["year"] or ""),
                             x["direction"] + ("" if x["direction"] == "unstated" else f" ({x['confidence']})"),
                             ", ".join(x["cues"][:4]) or "-", ", ".join(x["qualifiers"]) or "-", short(x["sentence"], 220)])
                J["sentences"].append({"doi": s["doi"], "year": s["year"], "study_direction": d, "sentence_direction": x["direction"],
                                       "confidence": x["confidence"], "cues": x["cues"], "qualifiers": x["qualifiers"],
                                       "matched_terms": x["matched"], "sentence": x["sentence"]})
        out.append(table(rows, ["doi", "year", "sentence dir", "cues", "qualifier", "sentence"]))
        out.append("")

    # (5) gap statements
    out.append("## 5. Draft gap statements (VERIFY each number and each cited study before use)")
    out.append("")
    drafts = []
    if pos and neg:
        cell_txt = ""
        if J["contradictions"]["cells"]:
            c0 = J["contradictions"]["cells"][0]
            cell_txt = f" The split persists within one context ({c0['population']}, {c0['country']}: {c0['positive']} positive vs {c0['negative']} negative)."
        drafts.append(f"Of the {len(stated)} studies whose abstracts state the {a_txt}-{b_txt} relation, {len(pos)} report a positive and "
                      f"{len(neg)} a negative association (a further {by_dir.get('none', 0)} find none, {by_dir.get('mixed', 0)} mixed), "
                      f"so its direction remains unsettled.{cell_txt}")
    else:
        drafts.append(f"The {len(stated)} studies that state the {a_txt}-{b_txt} relation agree on its direction "
                      f"({', '.join(f'{d}: {by_dir[d]}' for d in by_dir)}); the open question is therefore not direction but "
                      "the contexts and designs listed below.")
    strong_n = sum(design_counts.get(d, 0) for d in ("longitudinal", "experiment", "meta-analysis"))
    cs = design_counts.get("cross-sectional", 0) + design_counts.get("survey (design unstated)", 0)
    drafts.append(f"{cs} of the {len(rel)} studies are cross-sectional or survey-based while {design_counts.get('longitudinal', 0)} are longitudinal, "
                  f"{design_counts.get('experiment', 0)} experimental and {design_counts.get('meta-analysis', 0)} meta-analytic, so the "
                  f"{a_txt}-{b_txt} relation has " + ("rarely" if strong_n else "not") + " been tested with a design able to order cause and effect.")
    if not arab:
        drafts.append(f"None of the {len(rel)} studies samples an Arab-region population (0 of 22 Arab states, no MENA/Gulf mention), "
                      f"so the {a_txt}-{b_txt} relation is untested in that context; the corpus is dominated by "
                      f"{', '.join(c for c, _ in countries.most_common(3) if c != 'unstated') or 'studies with no stated country'}.")
    else:
        target = (sorted(GCC - {c for s in arab for c in s["countries"]}) or absent[:1] or ["(no empty cell found)"])[0]
        drafts.append(f"Although {len(arab)} studies cover the Arab region ({', '.join(present)}), none samples {target}; "
                      f"and no study in the corpus examines {', '.join(absent[:3]) or 'the populations listed in section 3'}.")
    for i, d in enumerate(drafts, 1):
        out.append(f"{i}. {d} [DRAFT, verify]")
    out.append("")
    J["gap_statements"] = drafts
    out.append("## Not checked")
    out.append("")
    out.append("- Full texts were not read: direction, N, design, country and population come from title + abstract only.")
    out.append("- Studies whose abstracts never name both relation terms in one sentence are excluded from sections 1, 2 and 5.")
    out.append("- 'Jordan', 'Georgia', 'Chad', 'Niger', 'Mali', 'Guinea', 'Turkey', 'Oman' can be names or words, not places.")
    out.append("- Synonyms are only those passed with --syn; a study using other wording for the same construct is missed.")
    out.append("- 'weak' directions rest on change words (higher, reduced, improve); rerun with --strong-only to keep only sign-stating sentences.")
    out.append("- Design tags skip recommendation sentences (future, further, should, warranted, recommend, needed, call for); "
               "a design named only there is listed under design_skipped in the JSON, and a design tag is 'strong' only when its "
               "sentence says we / our / this study.")
    summary = (f"RESULT: {len(stated)} studies state a direction (+{by_dir.get('positive', 0)} -{by_dir.get('negative', 0)} "
               f"0{by_dir.get('none', 0)} ~{by_dir.get('mixed', 0)}; {n_strong} strong) out of {len(studies)} abstracts; "
               f"{len(gaps)} empty-cell notes; {len(drafts)} draft gap statements to verify.")
    J["result"] = summary
    return "\n".join(out), J, summary


# ---------------------------------------------------------------- commands

def cmd_run(a):
    if not a.topic and not a.inputs:
        sys.exit("give --topic (OpenAlex) or --in cand.json")
    if not a.relation:
        if a.topic:
            terms = re.findall(r'"([^"]+)"', a.topic)
            if len(terms) >= 2:
                a.relation = f"{terms[0]}|{terms[1]}"
                print(f"[gapmap] --relation not given: using the first two quoted topic terms: {a.relation}", file=sys.stderr)
        if not a.relation:
            sys.exit("--relation 'term A|term B' is required (or quote two terms in --topic)")
    relation = parse_relation(a.relation, a.syn)
    if not relation:
        sys.exit("--relation must be 'term A|term B'")
    if a.inputs:
        rows = load_candidates(a.inputs)
        note = f"from {', '.join(os.path.basename(p) for p in a.inputs)}"
        total = len(rows)
    else:
        rows, total = fetch_openalex(a.topic, a.since, a.n)
        note = f"OpenAlex title_and_abstract.search {a.topic!r}, since {a.since or 'any'}, {TODAY}, top {len(rows)} of {total} by citations"
        save = a.save_corpus or "gapmap_corpus.json"
        with open(save, "w", encoding="utf-8") as f:
            json.dump({"query": a.topic, "date": TODAY, "source": "openalex", "results": rows}, f, ensure_ascii=False, indent=1)
        print(f"corpus saved to {os.path.abspath(save)} (rerun with --in to avoid new API calls)")
    with_abs = sum(1 for r in rows if r.get("abstract"))
    print(f"corpus: {len(rows)} candidates, {with_abs} with an abstract ({note}); total matches {total}")
    if with_abs == 0:
        sys.exit("no abstracts in the corpus: rerun `scholar.py search ... --abstracts --out` or use --topic")
    studies = [analyse_study(r, relation) for r in rows if r.get("abstract")]
    md, J, summary = build_report(studies, a.topic or "", a.relation, note, a.strong_only)
    J["studies"] = studies
    out = a.out or "gapmap.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(md)
    print()
    print(f"written: {os.path.abspath(out)}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(J, f, ensure_ascii=False, indent=1)
        print(f"written: {os.path.abspath(a.json)}")
    print(summary)
    return 0


SYNTHETIC = [
    {"doi": "10.0000/synthetic.1", "title": "Social media use and academic performance among Jordanian undergraduates", "year": 2021,
     "cites": 12, "first_author": "A. Test",
     "abstract": "This cross-sectional study surveyed 312 undergraduate students at a public university in Jordan. "
                 "Social media use was negatively associated with academic performance (r = -0.21, p < .01). "
                 "Time management partially mediated the effect."},
    {"doi": "10.0000/synthetic.2", "title": "Facebook and GPA: a longitudinal study of Malaysian college students", "year": 2019,
     "cites": 40, "first_author": "B. Test",
     "abstract": "A two-wave longitudinal panel of N = 1,204 college students in Malaysia. "
                 "Educational use of Facebook predicted higher GPA one semester later, whereas entertainment use did not. "
                 "Social media use was positively related to academic achievement when used for study purposes."},
    {"doi": "10.0000/synthetic.3", "title": "Does Instagram hurt grades? Evidence from Egyptian secondary schools", "year": 2022,
     "cites": 3, "first_author": "C. Test",
     "abstract": "We conducted a quasi-experimental intervention with 180 secondary school students in Egypt. "
                 "There was no significant relationship between Instagram use and grades after the intervention."},
    {"doi": "10.0000/synthetic.4", "title": "Nurses, WhatsApp and burnout in Saudi hospitals", "year": 2020,
     "cites": 8, "first_author": "D. Test",
     "abstract": "A qualitative study with semi-structured interviews of 24 nurses in Saudi Arabia. "
                 "Participants described WhatsApp groups as both supportive and exhausting."},
    {"doi": "10.0000/synthetic.5", "title": "Social networking sites and academic performance: a meta-analysis", "year": 2023,
     "cites": 90, "first_author": "E. Test",
     "abstract": "This meta-analysis pooled 57 studies (total N = 48,210 participants). "
                 "Social networking site use showed a small negative correlation with academic performance overall, "
                 "but the association depended on the purpose of use and was moderated by country."},
    {"doi": "10.0000/synthetic.6", "title": "Teacher workload in Finland", "year": 2018, "cites": 1, "first_author": "F. Test",
     "abstract": "A survey of 410 teachers in Finland on workload and job satisfaction. Workload increased over the period."},
    {"doi": "10.0000/synthetic.7", "title": "Collaborative learning through social media in Jordan", "year": 2020, "cites": 25,
     "first_author": "G. Test",
     "abstract": "Questionnaires were completed by 452 undergraduates in Jordan. "
                 "Social media use for collaborative learning was positively associated with academic performance."},
    {"doi": "10.0000/synthetic.8", "title": "Social media and academic performance of university students in Kuwait", "year": 2021,
     "cites": 5, "first_author": "H. Test",
     "abstract": "A cross-sectional survey of 220 university students in Kuwait. "
                 "Social media use was negatively associated with academic performance. "
                 "Further longitudinal studies are warranted to confirm the direction of the effect."},
]


def cmd_selftest(a):
    fails = []

    def check(cond, msg):
        print(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            fails.append(msg)

    rel = parse_relation("social media|academic performance",
                         ["social media=Facebook,Instagram,social networking site", "academic performance=GPA,grades,academic achievement"])
    st = {s["doi"]: s for s in (analyse_study(r, rel) for r in SYNTHETIC)}
    s1, s2, s3, s4, s5, s6, s7, s8 = (st[f"10.0000/synthetic.{i}"] for i in range(1, 9))
    check(s1["direction"] == "negative", f"study 1 direction negative (got {s1['direction']})")
    check(s1["country"] == "Jordan" and s1["arab_region"], f"study 1 country Jordan, Arab region (got {s1['country']})")
    check(s1["population"] == "undergraduates", f"study 1 population undergraduates (got {s1['population']})")
    check(s1["design"] == "cross-sectional", f"study 1 design cross-sectional (got {s1['design']})")
    check(s1["design_confidence"] == "strong", f"study 1 design strong: 'This cross-sectional study' (got {s1['design_confidence']})")
    check(s1["sample"] and s1["sample"]["n"] == 312, f"study 1 N = 312 (got {s1['sample']})")
    check(s1["n"] == 312 and all(isinstance(s["n"], int) or s["n"] is None for s in st.values()),
          "every study has an 'n' key (integer or null) equal to sample.n")
    check(analyse_study({"title": "No numbers", "abstract": "A study without a sample size."}, rel)["n"] is None,
          "a study without a sample size has n = null")
    check(s2["direction"] == "mixed", f"study 2 direction mixed: sentences 'higher ... whereas' + 'positively' (got {s2['direction']})")
    check(any(x["direction"] == "positive" for x in s2["relation_sentences"]), "study 2 has a positive sentence")
    check(s2["sample"] and s2["sample"]["n"] == 1204, f"study 2 N = 1,204 via 'N =' (got {s2['sample']})")
    check(s2["design"] == "longitudinal" and s2["country"] == "Malaysia", f"study 2 longitudinal, Malaysia (got {s2['design']}, {s2['country']})")
    check(s3["direction"] == "none", f"study 3 direction none (got {s3['direction']})")
    check(s3["design"] == "experiment" and s3["population"] == "school students", f"study 3 experiment, school students (got {s3['design']}, {s3['population']})")
    check(s4["direction"] == "no relation sentence", f"study 4 has no relation sentence (got {s4['direction']})")
    check(s4["design"] == "qualitative" and s4["population"] == "nurses" and s4["country"] == "Saudi Arabia",
          f"study 4 qualitative, nurses, Saudi Arabia (got {s4['design']}, {s4['population']}, {s4['country']})")
    check(s5["direction"] == "mixed" and s5["design"] == "meta-analysis", f"study 5 mixed, meta-analysis (got {s5['direction']}, {s5['design']})")
    check(s5["sample"] and s5["sample"]["n"] == 48210, f"study 5 N = 48,210 (got {s5['sample']})")
    check(s6["direction"] == "no relation sentence" and s6["population"] == "teachers", "study 6 off-topic: no relation sentence, teachers")
    # negative control: a recommended design is not the study's design
    check(s8["design"] == "cross-sectional" and "longitudinal" not in s8["design_tags"],
          f"study 8 'Further longitudinal studies are warranted' is NOT tagged longitudinal (got {s8['design']}, tags {s8['design_tags']})")
    check(s8["design_skipped"] and "longitudinal" in s8["design_skipped"][0]["designs"],
          "study 8 records the skipped recommendation sentence under design_skipped")
    check(s8["design_confidence"] == "weak", f"study 8 design weak: no we/our/this study sentence (got {s8['design_confidence']})")
    check(s3["design_confidence"] == "strong" and s5["design_confidence"] == "strong",
          "studies 3 and 5 design strong: 'We conducted' / 'This meta-analysis'")
    md, J, summary = build_report(list(st.values()), "synthetic", "social media|academic performance", "synthetic fixtures")
    check("undergraduates | Jordan" in J["matrix"], "matrix has the undergraduates x Jordan cell")
    check(s7["direction"] == "positive" and s7["design"] == "survey (design unstated)", f"study 7 positive, survey (got {s7['direction']}, {s7['design']})")
    check(len(J["contradictions"]["negative"]) == 2 and len(J["contradictions"]["positive"]) == 1,
          "contradiction lists: 2 negative (studies 1, 8) vs 1 positive (study 7); study 2 is mixed")
    check(J["summary"]["design_tagged"] == 8 and J["summary"]["design_unstated"] == 0 and "Design tagged in 8 of 8 studies" in md,
          f"header states design tagged / unstated counts (got {J['summary']['design_tagged']} / {J['summary']['design_unstated']})")
    check(J["contradictions"]["cells"] and J["contradictions"]["cells"][0]["population"] == "undergraduates"
          and J["contradictions"]["cells"][0]["country"] == "Jordan", "cell contradiction found: undergraduates x Jordan")
    check(len(J["gap_statements"]) == 3, f"3 draft gap statements (got {len(J['gap_statements'])})")
    # negative control: a relation absent from the corpus must yield no matrix
    rel2 = parse_relation("sleep quality|crop yield", [])
    st2 = [analyse_study(r, rel2) for r in SYNTHETIC]
    md2, J2, summary2 = build_report(st2, "synthetic", "sleep quality|crop yield", "synthetic fixtures")
    check(J2["result"] == "no relation sentences" and "matrix" not in J2, "negative control: 'no relation sentences', no matrix")
    print(summary2)
    print(f"RESULT: {'PASS' if not fails else 'FAIL'} ({len(fails)} failed checks)")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="build the gap map",
                       epilog="example: gapmap.py run --topic '\"social media\" AND \"academic performance\"' "
                              "--relation \"social media|academic performance\" --syn \"academic performance=GPA,grades\" --out gapmap.md")
    r.add_argument("--strong-only", action="store_true",
                   help="count only studies whose direction comes from a sign-stating sentence (positively, negative association, no significant...)")
    r.add_argument("--topic", help="OpenAlex title_and_abstract.search query (quote phrases, AND/OR/NOT allowed)")
    r.add_argument("--relation", help="'term A|term B': the relation whose direction is mined")
    r.add_argument("--syn", action="append", help="synonyms for one side: 'term A=alt1,alt2' (repeatable)")
    r.add_argument("--since", type=int, help="earliest publication year")
    r.add_argument("--n", type=int, default=300, help="max abstracts to fetch (<= 400, 200 per OpenAlex call)")
    r.add_argument("--in", dest="inputs", nargs="+", help="candidate files (scholar.py search --abstracts --out) or sources.jsonl; no API calls")
    r.add_argument("--save-corpus", help="where to save the fetched corpus (default gapmap_corpus.json)")
    r.add_argument("--out", default="gapmap.md", help="markdown report (default gapmap.md)")
    r.add_argument("--json", help="also write the full extraction as JSON (top-level keys documented in `gapmap.py --help`)")
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("selftest", help="run the extractors on synthetic abstracts, no network",
                       epilog="example: gapmap.py selftest")
    s.set_defaults(fn=cmd_selftest)
    a = p.parse_args()
    try:
        sys.exit(a.fn(a))
    except HTTPError as e:
        sys.exit(f"network error: {e}")


if __name__ == "__main__":
    main()
