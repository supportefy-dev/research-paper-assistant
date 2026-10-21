#!/usr/bin/env python3
"""reviews.py - mine real, public peer reviews so the review panel checks what reviewers really complain about.

Sources (all free, no login; status verified live on 2026-10-21):
  openreview   OpenReview API v2 full-text search of review notes (ML/CS venues: ICLR, NeurIPS, ...)
  elife        eLife API: public reviews (2023+ model) and decision letters (2013-2022) of research articles
  f1000        F1000Research extapi: search + JATS XML with open reviewer reports
  peerj        PeerJ: BLOCKED for scripts (Cloudflare challenge on every article/review page). The
               command tries once with a browser user agent, reports the block and returns 0 reviews.

Commands
  pull       fetch reviews by keyword into a JSONL file
  classify   tag every complaint sentence with a category and print frequencies with quoted examples
  selftest   positive case (classifier on bundled real sentences) + negative controls (praise, keyword
             list, boilerplate, planted non-complaint)

Relevance filter (pull): every source searches full text OR-like, so one query word is a hit.
  - A multi-word phrase in double quotes ("social media" students) must appear in the paper's
    title/abstract/review text (case-insensitive).
  - Otherwise at least two query words must appear, not counting the filler words performance,
    study, social, media, impact, effect, analysis, model, data (when the query has fewer than two
    other words, all of them must appear). --loose keeps every hit.

Classify: a sentence is tagged only when it carries a complaint cue (not, no, lack, unclear,
insufficient, missing, weak, limited, should, needs, must, however, concern, fails, does not, cannot,
questionable, overstate, unsupported, inconsistent, confus-, why, how, plus n't contractions, without and
under-developed/-explored/-powered). Praise
without a negation ("The paper is well written") and keyword lists (Social Media; Academic Performance;
...) are skipped and counted. --show-untagged N lists sentences that got no tag.

Examples
  python -X utf8 reviews.py pull --query "social media academic performance" --source elife --n 20 --out reviews.jsonl
  python -X utf8 reviews.py pull --query '"social media" students grades' --source all --n 20 --out reviews.jsonl
  python -X utf8 reviews.py classify reviews.jsonl --out complaints.md --show-untagged 20
  python -X utf8 reviews.py selftest

The script never invents a review: a query with no hits reports 0 and exits 1.
"""

import argparse
import collections
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import http_get, as_json, HTTPError, clean, table, short, TODAY  # noqa: E402

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-paper-assistant/1.0"
# Generic words never counted as query words.
STOP = {"the", "and", "for", "with", "from", "that", "this", "into", "between", "among", "their",
        "using", "based", "toward", "towards", "about"}
# Filler words that appear in almost every abstract: they count as query words only when the query
# has nothing else.
FILLER = {"performance", "study", "studies", "social", "media", "impact", "impacts", "effect", "effects",
          "analysis", "analyses", "model", "models", "data"}
QUOTE_RE = re.compile(r'["“”]([^"“”]+)["“”]')

# ---------------------------------------------------------------- taxonomy

# Each category: (label, regex). A sentence can carry several tags. Keywords are
# written for English reviews; none of the open sources below carries Arabic reviews.
TAXONOMY = [
    ("methodology_sample", r"""
        sample\s*size|small\s+sample|sample\s+of|\bsampl(?:e|es|ing)\b|participants?|respondents?|\bcohorts?\b|
        \bn\s*=\s*\d|under-?powered|power\s+(?:analysis|calculation)|control\s+(?:group|condition|arm)|confound|
        selection\s+bias|recruit|response\s+rate|generali[sz](?:e|ed|ability|ation)|external\s+validity|
        representativ|single\s+(?:site|dataset|benchmark|institution|cent(?:er|re))|only\s+(?:one|a\s+single)\s+(?:dataset|benchmark|task|model)|
        \bvalidity\b|reliabilit|\binstruments?\b|questionnaire|survey\s+(?:design|instrument|items?)|operationali[sz]|
        experimental\s+(?:design|setup|protocol)|study\s+design|research\s+design|\bdesign\s+(?:is|was|of\s+the)|
        \bablation|evaluation\s+(?:is|was|protocol|setup)|cross-?validation|limited\s+(?:dataset|evaluation|experiments?|data)|
        self-?report|inclusion\s+criteria|exclusion\s+criteria|randomi[sz]|\bblind(?:ed|ing)\b|dropout|attrition|
        cross-?sectional|longitudinal|\bprocedure\b|data\s+collection|measurement\s+(?:error|invariance)|
        common\s+method\s+(?:bias|variance)|convenience\s+sample|pilot\s+(?:study|test)|training\s+(?:data|set)|test\s+set|
        data\s+leakage|hyper-?parameters?\s+(?:were|are|tuned|selection)|\bdatasets?\b|confined\s+to|
        experiments?\s+(?:are|were|is|only|lack)|\bsettings?\s+(?:is|are)\s+(?:too|only|limited)|
        experimental\s+(?:evaluation|section|validation|setup|results?)|quantitative\s+(?:validation|evaluation)|interpretab|
        (?:more|additional|further|stronger)\s+(?:experiments?|evaluation|validation|evidence)
    """),
    ("statistics_analysis", r"""
        statistic|signific|\bp-?values?\b|\bp\s*[<=>]\s*[0.]|confidence\s+interval|effect\s+size|regression|
        \banova\b|\bt-?tests?\b|correlat|multiple\s+(?:comparisons?|testing)|bonferroni|error\s+bars?|
        standard\s+(?:deviation|error)|\bvariance\b|random\s+seeds?|\bseeds\b|how\s+many\s+runs|averaged\s+over|
        statistical\s+(?:test|method|analysis|analyses|power|model)|normality|multicollinearity|mediat(?:ion|or)|moderat(?:ion|or)|
        model\s+fit|outliers?|missing\s+data|imputation|\bsem\b|factor\s+analysis|cronbach|\balpha\s*=|
        chi-?square|non-?parametric|\bbayesian|\bprior\b|likelihood|\bmetrics?\b|\baccuracy\b|\bf1\b|\bauc\b|
        \bstd\b|\bvariability|significance\s+test|hypothesis\s+test|post-?hoc|interaction\s+(?:term|effect)|
        covariates?|adjust(?:ed|ment)\s+for|clustered|hierarchical\s+(?:model|linear)|\bci\b|
        \bpower\s+of\s+the\s+(?:study|analysis|test)|statistical\s+power|\bmedian\b|percentages?\s+(?:are|were|should)
    """),
    ("novelty_contribution", r"""
        \bnovel(?:ty)?\b|incremental|contribution|prior\s+work|already\s+(?:known|shown|proposed|exists?|been)|
        (?:very\s+)?similar\s+to\s+(?:the\s+)?(?:work|approach|method|paper|idea)|what\s+is\s+new|\btrivial\b|
        straightforward\s+(?:extension|combination|application)|significance\s+of\s+(?:the|this)|
        (?:not|un)clear\s+(?:what|why)\s+(?:the|this)\s+(?:paper|work|study|contribution)|\bmotivat(?:ion|ed|e)\b|
        why\s+(?:is|should|do|does)\s+(?:this|the|we|one)|well-?known|marginal\s+(?:improvement|gain|benefit)|
        limited\s+(?:improvement|novelty|contribution|significance)|not\s+(?:very\s+)?(?:surprising|interesting)|
        adds?\s+(?:little|nothing)|(?:practical|theoretical|clinical)\s+(?:relevance|implications?|value)|
        \bscope\s+of\s+(?:the|this)\s+journal|out\s+of\s+scope|research\s+(?:question|gap)|\bgap\b|
        originality|rehash|re-?invent|differ(?:s|ence)?\s+from\s+(?:prior|previous|existing)
    """),
    ("theory", r"""
        theor(?:y|ies|etical|etically)|\bframework\b|conceptual|hypothes[ie]s|\bconstructs?\b|\bmechanism|\brationale\b|
        justif(?:y|ied|ication)|assumption|\bintuition|explain\s+why|no\s+explanation|unexplained|\bdefinitions?\b|
        (?:not|poorly|ill|un)[- ]defined|\bformal(?:ism|isation|ization)\b|\bproof\b|\blemma\b|\btheorem\b|derivation|
        \bparadigm\b|logic\s+of\s+the|why\s+(?:would|does|do)\s+(?:this|it|the)\s+(?:work|hold|happen|matter)|
        grounded\s+in|\bunderpin|no\s+(?:clear\s+)?(?:reason|basis)\s+(?:for|to|why)
    """),
    ("writing_clarity", r"""
        \bclarity\b|\bunclear\b|\bclearer\b|\bconfus(?:ing|ed)\b|hard\s+to\s+(?:follow|read|understand|parse)|
        difficult\s+to\s+(?:follow|understand|read)|\btypos?\b|\bgrammar\b|grammatical|\bwording\b|\bnotation\b|
        readab|rewrit|restructur|organi[sz]ation\s+of|poorly\s+(?:written|organi[sz]ed|structured)|too\s+long|
        \bverbose\b|\bconcise\b|terminolog|ambiguous|\bdefine\s+(?:the|what|these|this)|\babstract\s+(?:is|should|does)|
        \bintroduction\s+(?:is|should|does|needs)|section\s+\d|\bparagraph\b|\bsentence\b|proof-?read|
        \benglish\b|language\s+(?:of\s+the|needs|is|editing|polish)|inconsisten|\bspelling\b|
        should\s+be\s+(?:rephrased|reworded|clarified|explained|stated)|please\s+(?:clarify|explain|rephrase|specify|state)|
        not\s+(?:well\s+)?(?:explained|described|presented)|presentation\s+(?:is|of|could|needs)|
        acronyms?|abbreviations?|\bjargon\b|\bflow\b|\bstructure\s+of\s+the\s+(?:paper|manuscript|article)|
        \bformatting\b|\blayout\b|\bcitation\s+(?:style|format)\b
    """),
    ("literature_coverage", r"""
        literature|related\s+work|\bcite[ds]?\b|\bcitations?\b|\breferences?\b|missing\s+(?:work|reference|citation|discussion\s+of|comparison)|
        prior\s+(?:work|studies|research|literature)|previous\s+(?:work|studies|research|literature)|earlier\s+(?:work|studies)|
        compar(?:e|ed|ison)\s+(?:with|to|against)|\bcomparisons?\b|\bbaselines?\b|state-?of-?the-?art|\bsota\b|
        recent\s+(?:work|studies|papers|advances|methods)|\bomit|\boverlook|ignore[sd]?\s+(?:the|prior|existing|recent)|
        existing\s+(?:work|methods|approaches|studies|literature)|seminal|\bsurvey\s+of\b|not\s+(?:discussed|mentioned|cited|compared)|
        (?:should|could)\s+(?:also\s+)?(?:cite|discuss|compare|mention)
    """),
    ("ethics_data_availability", r"""
        \bethic(?:s|al)\b|\birb\b|ethics\s+(?:committee|approval|board)|informed\s+consent|\bconsent\b|anonymi[sz]|
        \bprivacy\b|data\s+(?:availab|sharing|access|statement|are\s+not\s+available)|code\s+(?:is|will\s+be|availab|release|not\s+provided)|
        open-?source|reproduc|replicab|replicat(?:e|ion)|\bgithub\b|\brepositor(?:y|ies)\b|supplementar|
        (?:materials?|data|code)\s+(?:are|is)\s+(?:not\s+)?(?:available|provided|shared|released)|conflicts?\s+of\s+interest|
        \bfunding\b|pre-?regist|\bbias(?:es|ed)?\s+(?:in|of)\s+(?:the\s+)?(?:data|dataset|sample|corpus)|\bfairness\b|
        \bharm(?:s|ful)?\b|dual[- ]use|\blicen[sc]e\b|\bconsent\b|vulnerable\s+(?:population|group)|\bdeception\b|
        plagiar|duplicate\s+(?:publication|submission)|\bcopyright\b|data\s+protection|\bgdpr\b|welfare|
        declaration|disclos(?:e|ure)|\btransparen(?:cy|t)\b|checklist|\bconsort\b|\bprisma\b|\bstrobe\b|\bcoreq\b
    """),
    ("overclaiming_causal", r"""
        over-?claim|over-?stat(?:e|ed|ement)|exaggerat|too\s+strong|strong\s+claims?|
        claims?\s+(?:that\s+)?(?:is|are|seems?)\s+not\s+(?:fully\s+)?(?:supported|justified|warranted|substantiated)|
        unsupported|not\s+(?:fully\s+)?supported\s+by|does\s+not\s+(?:support|follow|warrant|justify)|
        cannot\s+(?:conclude|be\s+concluded|infer|be\s+inferred|claim)|\bcausal(?:ity|ly)?\b|causation|
        \bcauses?\b|\bcaused\b|correlation(?:al)?\s+(?:does|is|should)\s+not|correlation\s+(?:is\s+)?not\s+causation|
        generali[sz](?:e|ation|ing)\s+(?:beyond|to\s+other|these\s+(?:results|findings))|\bspeculat|tone\s+down|
        \btemper(?:ed)?\b|misleading|conclusions?\s+(?:is|are|seems?|go|goes)\s+(?:not|too|beyond|stronger)|
        limitations?\s+(?:is|are|should|need|section|of\s+the\s+study|were\s+not)|should\s+(?:be\s+)?(?:acknowledg|discuss\s+the\s+limitation)|
        reverse\s+causality|endogeneity|\bconfounded\b|\bdemonstrates?\s+that\s+.*\b(?:causes?|leads?\s+to)|
        \bsuggests?\b\s+rather\s+than|hedg(?:e|ing)|overly\s+(?:optimistic|confident)|does\s+not\s+(?:prove|establish|demonstrate)|
        (?:title|abstract)\s+(?:claims?|promises?|suggests?|overstates?)
    """),
    ("figures_tables", r"""
        \bfigures?\b|\bfig\.|\btables?\b|\bplots?\b|\baxis\b|\baxes\b|\blegends?\b|\bcaptions?\b|\bfonts?\b|
        visuali[sz]|\bdiagrams?\b|illustrat|\bcharts?\b|\bpanels?\b|\bhistogram|\bheat-?map|
        \bgraphs?\b|\bscatter|\bbar\s+(?:chart|plot|graph)|\bbox-?plots?\b|\bschematic|\bsupplementary\s+(?:figure|table)|
        error\s+bars?|\by-?axis|\bx-?axis|colou?r\s+(?:scheme|coding|scale)|\blow\s+resolution|\bimage\s+quality
    """),
]
TAX_RE = [(name, re.compile(pat, re.I | re.X)) for name, pat in TAXONOMY]
CATEGORY_LABELS = {
    "methodology_sample": "Methodology / sample / design",
    "statistics_analysis": "Statistics / analysis",
    "novelty_contribution": "Novelty / contribution / motivation",
    "theory": "Theory / rationale / definitions",
    "writing_clarity": "Writing / clarity / presentation",
    "literature_coverage": "Literature coverage / comparisons",
    "ethics_data_availability": "Ethics / data and code availability / reporting",
    "overclaiming_causal": "Overclaiming / causal language / limitations",
    "figures_tables": "Figures / tables",
}

# A sentence is a complaint candidate only when it carries one of these cues.
CUE = re.compile(r"""
    \bnot\b|\bno\b|\black(?:s|ed|ing)?\b|\bunclear\b|\binsufficient(?:ly)?\b|\bmissing\b|\bweak(?:ly|er|ness(?:es)?)?\b|
    \blimited\b|\bshould\b|\bneeds?\s+to\b|\bneeds\b|\bneeded\b|\bmust\b|\bhowever\b|\bconcern(?:s|ed|ing)?\b|
    \bfails?\b|\bfailed\b|\bfail(?:s|ed)?\s+to\b|\bdoes\s+not\b|\bdid\s+not\b|\bdo\s+not\b|\bcannot\b|\bcan\s+not\b|
    \bquestionable\b|\boverstat(?:e|es|ed|ement|ing)\b|\bunsupported\b|\binconsistent(?:ly|cy|cies)?\b|\bconfus\w*|
    \bwhy\b|\bhow\b|n't\b|\bwithout\b|\bunder(?:developed|explored|specified|powered|reported|stated|studied)\b
""", re.I | re.X)
# Positive words: a sentence with one of these and no negation below is praise and is skipped.
PRAISE = re.compile(r"""
    well[- ](?:written|organi[sz]ed|designed|done|presented|motivated|argued|structured|executed|conducted)|
    clearly\s+(?:written|presented|explained|described)|\bexcellent|\bimpressive|\binteresting|\bconvincing|
    \bcompelling|\bthorough(?:ly)?\b|\brigorous(?:ly)?\b|\bsound\b|\bsolid\b|\bstrong\s+(?:paper|work|study|contribution|evidence|results?|motivation)|
    \bappreciate|\bcommend|\bcongratulat|\bapplaud|\bnice(?:ly)?\b|\bgood\b|\bvaluable|\btimely\b|\belegant|
    \bcareful(?:ly)?\b|\benjoy(?:ed|able)|\bpleas(?:ed|ure|ant)\b|\bpraise|\bmerit|\bstrength\b|\badmirabl|
    \bnovel\s+(?:and|contribution|idea|approach)|\bi\s+lik(?:e|ed)\b|\beasy\s+to\s+(?:follow|read)|\bhigh[- ]quality|
    \bclear\s+(?:writing|presentation|exposition|structure)
""", re.I | re.X)
# Negations and contrast words: praise that carries one is a complaint after all ("well written but...").
NEGATION = re.compile(r"""
    \bnot\b|\bno\b|n't\b|\black|\bhowever\b|\bbut\b|\balthough\b|\bthough\b|\byet\b|\bwhile\b|\bunless\b|\bonly\b|\bwithout\b|\bunder(?:developed|explored|specified|powered|reported|stated|studied)\b|
    \brather\b|\binstead\b|\bexcept\b|\bunclear|\binsufficient|\bmissing\b|\bweak|\blimited\b|\bfail|\bcannot\b|
    \bconcern|\bquestionable|\bunsupported|\binconsistent|\bconfus|\boverstat|\bneeds?\b|\bmust\b|\bwhy\b|
    \bshould\b(?!\s+be\s+(?:commended|congratulated|praised|applauded|proud))|\bcould\s+(?:be|have)\b|\bwould\s+(?:be|have|benefit|help)\b|
    \bmore\s+(?:clear|detail|discussion|explanation|analysis|experiments?|evidence)|\bbetter\b|\bimprov|\bclarif|\brevis|\bexpand|\baddress
""", re.I | re.X)
KEYWORDS_HEAD = re.compile(r"^\s*key\s*-?\s*words?\s*:", re.I)


def is_keyword_list(s):
    """'Social Media; Academic Performance; Students' style lists: 3+ semicolon-separated short
    capitalised phrases with no sentence punctuation, or a line that starts with 'Keywords:'."""
    if KEYWORDS_HEAD.match(s or ""):
        return True
    parts = [p.strip(" .") for p in (s or "").split(";")]
    if len(parts) < 3:
        return False
    return all(p and p[0].isupper() and len(p.split()) <= 6 and not re.search(r"[.,:!?()]", p) for p in parts)


def is_praise(s):
    return bool(PRAISE.search(s or "")) and not NEGATION.search(s or "")


def has_cue(s):
    return bool(CUE.search(s or ""))


def sentence_kind(s):
    """'keyword_list' | 'praise' | 'no_cue' | 'cue'."""
    if is_keyword_list(s):
        return "keyword_list"
    if is_praise(s):
        return "praise"
    return "cue" if has_cue(s) else "no_cue"


# Lines that are form boilerplate, not reviewer judgement.
BOILERPLATE = re.compile(r"""
    ^\s*(?:reviewer\s+expertise|competing\s+interests?|conflicts?\s+of\s+interest)\s*:?|
    i\s+confirm\s+that\s+i\s+have\s+read\s+this\s+submission|
    appropriate\s+level\s+of\s+expertise\s+to\s+(?:confirm|state)|
    ^\s*(?:is\s+the\s+(?:work|study\s+design|rationale|statistical\s+analysis|description)|are\s+(?:sufficient|all\s+the\s+source|the\s+conclusions))|
    ^\s*(?:yes|no|partly|n/?a)\s*$|
    ^\s*(?:summary|strengths?|weaknesses?|questions?|limitations?|minor\s+(?:points?|comments?|issues?)|major\s+(?:points?|comments?|issues?))\s*:?\s*$|
    thank\s+(?:you|the\s+authors?)\s+for|i\s+(?:thank|appreciate)\s+the\s+authors?|
    the\s+reviewers\s+have\s+discussed\s+the\s+reviews\s+with\s+one\s+another|
    your\s+article\s+has\s+been\s+(?:reviewed|favorably\s+evaluated)|
    thank\s+you\s+for\s+(?:submitting|sending)|
    this\s+(?:is|was)\s+(?:an?\s+)?(?:important|interesting|timely|well-?written|nice|strong|solid|valuable)|
    ^\s*(?:essential|required)\s+revisions?\s*:?\s*$|
    code\s+of\s+conduct|flag\s+for\s+ethics\s+review|
    the\s+authors\s+(?:have\s+)?(?:addressed|answered)\s+(?:all|most)\s+of\s+my
""", re.I | re.X)
STRENGTH_HEAD = re.compile(r"^\s*\**\s*(?:strengths?|positive\s+(?:points|aspects)|merits?|what\s+i\s+liked)\s*\**\s*:?\s*$", re.I)
OTHER_HEAD = re.compile(r"^\s*\**\s*(?:weakness(?:es)?|limitations?|concerns?|major\s+(?:points?|comments?|issues?|concerns?)|"
                        r"minor\s+(?:points?|comments?|issues?)|questions?|comments?(?:\s+to\s+(?:the\s+)?authors?)?|"
                        r"essential\s+revisions?|recommendations?(?:\s+for\s+(?:the\s+)?authors?)?|"
                        r"(?:public\s+)?review|suggestions?|summary)\s*\**\s*:?\s*$", re.I)


def strip_strengths(text):
    """Drop paragraphs under a 'Strengths:' heading up to the next heading (eLife public reviews).
    Returns (complaint_text, strengths_text)."""
    kept, strengths, in_str = [], [], False
    for line in text.splitlines():
        if STRENGTH_HEAD.match(line):
            in_str = True
            continue
        if in_str and OTHER_HEAD.match(line):
            in_str = False
            continue
        (strengths if in_str else kept).append(line)
    return "\n".join(kept).strip(), "\n".join(strengths).strip()


# ---------------------------------------------------------------- record helpers

def record(**kw):
    base = {"source": "", "review_id": "", "url": "", "paper_title": "", "paper_url": "", "venue": "", "year": None,
            "reviewer": "", "kind": "", "recommendation": "", "text": "", "strengths": "", "summary": "",
            "query": "", "pulled": TODAY}
    base.update(kw)
    base["text"] = (base["text"] or "").strip()
    return base


def query_tokens(q):
    return {w for w in re.findall(r"[a-z0-9]+", (q or "").lower()) if len(w) >= 4 and w not in STOP}


def parse_query(q):
    """{'phrases': quoted multi-word phrases (lowercase, single-spaced), 'tokens': all query words,
    'content': query words that are not filler}."""
    phrases = [re.sub(r"\s+", " ", p.strip().lower()) for p in QUOTE_RE.findall(q or "")]
    phrases = [p for p in phrases if len(p.split()) >= 2]
    tokens = query_tokens(q)
    return {"phrases": phrases, "tokens": tokens, "content": {t for t in tokens if t not in FILLER}}


def _blob(fields):
    return re.sub(r"\s+", " ", " ".join(clean(f) for f in fields if f)).lower()


def year_of(s):
    m = re.search(r"(?:19|20)\d{2}", str(s or ""))
    return int(m.group(0)) if m else None


def on_topic(spec, loose, *fields):
    """Full-text search at every source is OR-like: one word ('quantum') is a hit.
    Quoted multi-word phrases must all appear; otherwise at least two non-filler query
    words must appear (all of them when the query has fewer than two). --loose keeps everything."""
    if loose:
        return True
    if isinstance(spec, str):
        spec = parse_query(spec)
    blob = _blob(fields)
    if spec["phrases"]:
        return all(p in blob for p in spec["phrases"])
    words = spec["content"] or spec["tokens"]
    if not words:
        return True
    return sum(1 for t in words if t in blob) >= min(2, len(words))


def skip_note(source, skipped, spec):
    if not skipped:
        return
    rule = ("the quoted phrase " + " / ".join(f'"{p}"' for p in spec["phrases"]) if spec["phrases"]
            else f"two of the query words {sorted(spec['content'] or spec['tokens'])}" if len(spec["content"] or spec["tokens"]) >= 2
            else f"the query word {sorted(spec['content'] or spec['tokens'])}")
    print(f"[{source}] skipped {skipped} hits whose title/abstract/review text lack {rule} (--loose keeps them)", file=sys.stderr)


# ---------------------------------------------------------------- OpenReview

OR_SECTIONS_COMPLAINT = ("weaknesses", "questions", "limitations", "review", "main_review", "comment", "details_of_ethics_concerns",
                         "technical_quality", "clarity", "experimental_quality", "metareview", "metareview:_summary", "justification")
OR_SKIP = {"title", "rating", "confidence", "soundness", "presentation", "contribution", "code_of_conduct",
           "flag_for_ethics_review", "recommendation", "summary", "strengths", "summary_of_the_paper",
           "summary_of_contributions", "correctness", "empirical_novelty_and_significance", "technical_novelty_and_significance"}


def _or_val(v):
    if isinstance(v, dict):
        v = v.get("value", "")
    if isinstance(v, list):
        v = "; ".join(str(x) for x in v)
    return clean_multiline(str(v or ""))


def clean_multiline(s):
    """Like scholar.clean but keeps line breaks (headings matter for strength stripping)."""
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    lines = [clean(x) for x in s.replace("\r", "").split("\n")]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def pull_openreview(query, n, since=None, loose=False):
    """OpenReview API v2: /notes/search?term=... (keyless). Review notes carry
    summary/strengths/weaknesses/questions (ICLR style) or a free-text 'review'.
    The paper note itself (forum) is behind a browser challenge for guests, so the
    paper title is empty unless the review repeats it."""
    spec = parse_query(query)
    out, seen, offset, scanned, skipped = [], set(), 0, 0, 0
    while len(out) < n and offset < 400:
        data = as_json(http_get("https://api2.openreview.net/notes/search",
                                params={"term": query, "limit": 50, "offset": offset, "source": "reply"}))
        notes = data.get("notes") or []
        if not notes:
            break
        for note in notes:
            scanned += 1
            inv = " ".join(note.get("invitations") or [note.get("invitation") or ""])
            kind = "meta_review" if "Meta_Review" in inv else "review" if re.search(r"/-/(?:Official_)?Review\b", inv) else ""
            if not kind or note["id"] in seen:
                continue
            c = note.get("content") or {}
            if not isinstance(c, dict):
                continue
            yr = year_of(inv) or year_of(note.get("domain"))
            if since and yr and yr < since:
                continue
            parts = []
            for k, v in c.items():
                if k in OR_SKIP:
                    continue
                txt = _or_val(v)
                if len(txt) > 20:
                    parts.append(f"{k.replace('_', ' ').title()}:\n{txt}")
            text = "\n\n".join(parts)
            if len(text) < 40:
                continue
            seen.add(note["id"])
            strengths, summary = _or_val(c.get("strengths", "")), _or_val(c.get("summary", "")) or _or_val(c.get("summary_of_the_paper", ""))
            if not on_topic(spec, loose, text, strengths, summary, _or_val(c.get("title", ""))):
                skipped += 1
                continue
            forum = note.get("forum") or ""
            out.append(record(
                source="openreview", review_id=note["id"],
                # noteId first: '&noteId' would be read as the HTML entity '&not' by any unescaper.
                url=f"https://openreview.net/forum?noteId={note['id']}&id={forum}",
                paper_title=_or_val(c.get("title", "")) if _or_val(c.get("title", "")).lower() not in ("official review", "review") else "",
                paper_url=f"https://openreview.net/forum?id={forum}",
                venue=(note.get("domain") or inv.split("/Submission")[0]).replace("/Conference", ""),
                year=yr, kind=kind, recommendation=_or_val(c.get("rating", "")) or _or_val(c.get("recommendation", "")),
                text=text, strengths=strengths, summary=summary, query=query))
            if len(out) >= n:
                break
        offset += 50
        if len(notes) < 50:
            break
    skip_note("openreview", skipped, spec)
    return out, scanned


# ---------------------------------------------------------------- eLife

def _elife_text(blocks):
    lines = []
    for b in blocks or []:
        t = b.get("type")
        if t == "paragraph":
            lines.append(clean(b.get("text")))
        elif t == "list":
            for it in b.get("items") or []:
                lines.append("- " + (clean(it) if isinstance(it, str) else _elife_text(it)))
        elif t == "section":
            lines.append(clean(b.get("title")) + ":")
            lines.append(_elife_text(b.get("content")))
        elif b.get("text"):
            lines.append(clean(b.get("text")))
    return "\n".join(x for x in lines if x is not None)


def pull_elife(query, n, since=None, loose=False):
    """eLife API: search research articles, then read publicReviews (new model) or the
    decisionLetter (2013-2022 model) from the article JSON. Reviewed preprints expose
    only the short elifeAssessment through the API, so they are skipped."""
    spec = parse_query(query)
    out, scanned, skipped, page = [], 0, 0, 1
    while len(out) < n and page <= 5:
        r = http_get("https://api.elifesciences.org/search",
                     params={"for": query, "per-page": 25, "page": page, "order": "desc",
                             "type[]": ["research-article", "research-advance", "short-report", "tools-resources"]})
        data = as_json(r) if r is not None else {}
        items = data.get("items") or []
        if not items:
            break
        for it in items:
            scanned += 1
            yr = year_of(it.get("published") or it.get("versionDate"))
            if since and yr and yr < since:
                continue
            art = http_get(f"https://api.elifesciences.org/articles/{it['id']}")
            a = as_json(art) if art is not None else {}
            title = clean(a.get("title") or it.get("title"))
            if not on_topic(spec, loose, title, _elife_text(a.get("abstract", {}).get("content") if isinstance(a.get("abstract"), dict) else []),
                            clean(it.get("impactStatement"))):
                skipped += 1
                continue
            paper_url = f"https://elifesciences.org/articles/{it['id']}"
            for pr in a.get("publicReviews") or []:
                text = _elife_text(pr.get("content"))
                body, strengths = strip_strengths(text)
                if len(body) < 40:
                    continue
                out.append(record(source="elife", review_id=pr.get("id") or pr.get("doi"),
                                  url=f"https://doi.org/{pr['doi']}" if pr.get("doi") else paper_url + "#peer-review",
                                  paper_title=title, paper_url=paper_url, venue="eLife", year=yr,
                                  reviewer=clean(pr.get("title")), kind="public_review", text=body, strengths=strengths,
                                  query=query))
                if len(out) >= n:
                    break
            if len(out) >= n:
                break
            dl = a.get("decisionLetter")
            if dl and dl.get("content"):
                text = _elife_text(dl.get("content"))
                body, strengths = strip_strengths(text)
                if len(body) >= 40:
                    out.append(record(source="elife", review_id=dl.get("doi") or f"{it['id']}-decision",
                                      url=f"https://doi.org/{dl['doi']}" if dl.get("doi") else paper_url + "#decision-letter",
                                      paper_title=title, paper_url=paper_url, venue="eLife", year=yr,
                                      reviewer="Reviewing editor (decision letter, reviewer points merged)",
                                      kind="decision_letter", text=body, strengths=strengths, query=query))
            if len(out) >= n:
                break
        if len(items) < 25:
            break
        page += 1
    skip_note("elife", skipped, spec)
    return out, scanned


# ---------------------------------------------------------------- F1000Research

def _xml_text(el):
    return re.sub(r"\s+", " ", " ".join(el.itertext())).strip() if el is not None else ""


def _xml_paras(body):
    paras = []
    if body is None:
        return paras
    for el in body.iter():
        if el.tag == "p":
            t = _xml_text(el)
            if t:
                paras.append(t)
    return paras


def pull_f1000(query, n, since=None, loose=False):
    """F1000Research extapi: /search?q= returns DOIs (100 per page, loose full-text match);
    /article/xml?doi= returns JATS with <sub-article article-type="reviewer-report">.
    Articles whose title+abstract fail the relevance filter are skipped."""
    spec = parse_query(query)
    out, scanned, skipped, page = [], 0, 0, 1
    while len(out) < n and page <= 3:
        r = http_get("https://f1000research.com/extapi/search", params={"q": query, "page": page})
        dois = re.findall(r"<doi>([^<]+)</doi>", r.text if r is not None else "")
        if not dois:
            break
        for doi in dois:
            scanned += 1
            xr = http_get("https://f1000research.com/extapi/article/xml", params={"doi": doi})
            if xr is None:
                continue
            try:
                root = ET.fromstring(xr.content)
            except ET.ParseError:
                continue
            front = root.find("front")
            title = _xml_text(front.find(".//article-title") if front is not None else None)
            abstract = _xml_text(front.find(".//abstract") if front is not None else None)
            if not on_topic(spec, loose, title, abstract):
                skipped += 1
                continue
            yr = None
            for d in root.iter("pub-date"):
                yr = yr or year_of(d.findtext("year"))
            if since and yr and yr < since:
                continue
            paper_url = f"https://doi.org/{doi}"
            for sa in root.findall("sub-article"):
                if sa.get("article-type") != "reviewer-report":
                    continue
                fm = sa.find("front-stub")
                rdoi = next((e.text for e in (fm.iter("article-id") if fm is not None else []) if e.get("pub-id-type") == "doi"), None)
                names = [" ".join(_xml_text(x) for x in (nm.find("given-names"), nm.find("surname")) if x is not None)
                         for nm in (fm.iter("name") if fm is not None else [])]
                rec = next((m.findtext("meta-value") for m in (fm.iter("custom-meta") if fm is not None else [])
                            if m.findtext("meta-name") == "recommendation"), "")
                paras = [p for p in _xml_paras(sa.find("body")) if not BOILERPLATE.search(p)]
                text = "\n".join(paras)
                if len(text) < 40:
                    continue
                out.append(record(source="f1000", review_id=rdoi or sa.get("id") or "",
                                  url=f"https://doi.org/{rdoi}" if rdoi else paper_url,
                                  paper_title=title, paper_url=paper_url, venue="F1000Research", year=yr,
                                  reviewer=", ".join(x for x in names if x), kind="reviewer_report",
                                  recommendation=clean(rec), text=text, query=query))
                if len(out) >= n:
                    break
            if len(out) >= n:
                break
        if len(dois) < 100:
            break
        page += 1
    skip_note("f1000", skipped, spec)
    return out, scanned


# ---------------------------------------------------------------- PeerJ

def pull_peerj(query, n, since=None, loose=False):
    """PeerJ publishes review histories at peerj.com/articles/<id>/reviews/, but every
    article, JSON and review page sits behind a Cloudflare challenge for scripts.
    One attempt with a browser user agent, then an honest 0."""
    url = "https://peerj.com/articles/index.json"
    try:
        r = http_get(url, params={"q": query}, headers={"User-Agent": BROWSER_UA}, retries=0)
        body = r.text if r is not None else ""
        if r is not None and "application/json" in r.headers.get("content-type", ""):
            print("[peerj] the JSON index answered: parsing is not implemented because it was blocked when "
                  "this module was written. Open an issue in the skill.", file=sys.stderr)
    except HTTPError as e:
        body = e.body or ""
        print(f"[peerj] HTTP {e.status}: {'Cloudflare challenge page' if 'Just a moment' in body else 'blocked'}. "
              f"Read reviews in a browser: https://peerj.com/search/?q={urllib.parse.quote(query)}&type=articles "
              f"then https://peerj.com/articles/<id>/reviews/", file=sys.stderr)
    return [], 0


SOURCES = {"openreview": pull_openreview, "elife": pull_elife, "f1000": pull_f1000, "peerj": pull_peerj}
OR_NO_TITLE = "openreview: paper titles are not exposed by the API for guests; open the review url to see the paper"


def print_titles(new):
    """Full paper titles (no cut), one line per paper with the row numbers that belong to it."""
    papers, or_blank = {}, []
    for i, r in enumerate(new, 1):
        t = r["paper_title"]
        if not t:
            if r["source"] == "openreview":
                or_blank.append(i)
            continue
        papers.setdefault(t, []).append(i)
    print("")
    print("Paper titles (full, row numbers from the table above):")
    for t, idx in papers.items():
        print(f"- #{', #'.join(map(str, idx))}: {t}")
    if or_blank:
        print(f"- #{', #'.join(map(str, or_blank))}: title not exposed ({OR_NO_TITLE})")


def cmd_pull(a):
    names = list(SOURCES) if a.source == "all" else [s.strip() for s in a.source.split(",")]
    bad = [s for s in names if s not in SOURCES]
    if bad:
        sys.exit(f"unknown source(s): {', '.join(bad)}; choose from {', '.join(SOURCES)} or all")
    spec = parse_query(a.query)
    existing = []
    if a.append and os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as f:
            existing = [json.loads(ln) for ln in f if ln.strip()]
    have = {(e["source"], e["review_id"]) for e in existing}
    rows, new, dupes = [], [], 0
    for s in names:
        try:
            recs, scanned = SOURCES[s](a.query, a.n, a.since, a.loose)
            status = "ok" if recs else ("blocked (Cloudflare)" if s == "peerj" else "0 reviews")
        except HTTPError as e:
            recs, scanned, status = [], 0, f"HTTP {e.status}"
        fresh = [r for r in recs if (r["source"], r["review_id"]) not in have]
        dupes += len(recs) - len(fresh)
        new += fresh
        papers = len({r["paper_url"] for r in fresh})
        rows.append([s, status, str(scanned), str(papers), str(len(fresh))])
    with open(a.out, "a" if a.append else "w", encoding="utf-8", newline="\n") as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = len(existing) + len(new)
    rule = ("required phrase: " + ", ".join(f'"{p}"' for p in spec["phrases"]) if spec["phrases"]
            else f"required words: {min(2, len(spec['content'] or spec['tokens']))} of {sorted(spec['content'] or spec['tokens'])}")
    print(f"query: {a.query} | sources: {', '.join(names)} | new reviews: {len(new)} | file: {os.path.abspath(a.out)} "
          f"({total} reviews) | {TODAY}")
    print(f"relevance filter: {'off (--loose)' if a.loose else rule}")
    print(table(rows, ["source", "status", "items scanned", "papers with reviews", "reviews saved"]))
    if new:
        shown = new[:40]
        print(table([[str(i), r["source"], r["kind"], str(r["year"] or ""), r.get("venue", ""), short(r["url"], 70)]
                     for i, r in enumerate(shown, 1)], ["#", "source", "kind", "year", "venue", "review url"]))
        if len(new) > 40:
            print(f"... and {len(new) - 40} more in the file")
        print_titles(shown)
        print("")
        print("Not checked: whether each paper is on your exact topic (the sources match full text; the relevance filter "
              "is a heuristic). Read the paper title before quoting a review as evidence about your field.")
        print(f"RESULT: PASS ({len(new)} real reviews saved" + ("; peerj is blocked for scripts, see above)" if "peerj" in names else ")"))
        return 0
    if dupes:
        print(f"RESULT: PASS (0 new reviews; the {dupes} found are already in the file)")
        return 0
    print("0 reviews found for this query in the chosen sources. Nothing was invented. Try broader words, "
          "--source all, --loose, or openreview for ML/CS topics.")
    print("RESULT: FAIL (0 reviews)")
    return 1


# ---------------------------------------------------------------- classify

SENT_SPLIT = re.compile(r"(?<!\bet al\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\bFig\.)(?<!\bcf\.)(?<!\bSci\.)(?<!\bNo\.)"
                        r"(?<=[.!?])\s+(?=[A-Z0-9(\"'\[])")
BULLET = re.compile(r"^\s*(?:[-*•]+|\(?\d{1,2}[.)]|[a-z][.)]|[WSQ]\d{1,2}[.:)]?|\d{1,2}\.\d{1,2}[.)]?)\s+")


def sentences(text):
    """Candidate sentences of a review: strengths blocks and form boilerplate removed.
    Praise and keyword lists are still returned; tag() drops them (classify counts them)."""
    out = []
    text, _ = strip_strengths(text or "")
    for line in text.splitlines():
        line = BULLET.sub("", line).strip()
        line = re.sub(r"^\**([A-Za-z ]{3,40})\**:\s*", lambda m: "" if OTHER_HEAD.match(m.group(1) + ":") else m.group(0), line)
        if not line or BOILERPLATE.search(line):
            continue
        for s in SENT_SPLIT.split(line):
            s = s.strip(" *_`")
            if 25 <= len(s) <= 600 and re.search(r"[A-Za-z]{3}", s) and not BOILERPLATE.search(s):
                out.append(s)
    return out


def tag(sentence):
    """Categories of a complaint sentence; [] for praise, keyword lists and sentences without a complaint cue."""
    if sentence_kind(sentence) != "cue":
        return []
    return [name for name, rx in TAX_RE if rx.search(sentence)]


def cmd_classify(a):
    if not os.path.exists(a.file):
        print(f"{a.file} not found")
        print("RESULT: FAIL (no reviews file)")
        return 1
    with open(a.file, encoding="utf-8") as f:
        reviews = [json.loads(ln) for ln in f if ln.strip()]
    if a.source:
        reviews = [r for r in reviews if r.get("source") in a.source.split(",")]
    if not reviews:
        print(f"0 reviews in {a.file}: nothing to classify, nothing invented.")
        print("RESULT: FAIL (0 reviews)")
        return 1
    per_cat = collections.Counter()
    per_cat_reviews = collections.defaultdict(set)
    per_cat_sources = collections.defaultdict(set)
    examples = collections.defaultdict(list)
    per_source = collections.Counter()
    skipped = collections.Counter()
    n_sent = n_tagged = n_multi = 0
    untagged = []
    for r in reviews:
        for s in sentences(r.get("text", "")):
            n_sent += 1
            per_source[r["source"]] += 1
            kind = sentence_kind(s)
            if kind in ("praise", "keyword_list"):
                skipped[kind] += 1
                continue
            cats = tag(s)
            if not cats:
                untagged.append((kind, s, r))
                continue
            n_tagged += 1
            n_multi += len(cats) > 1
            for c in cats:
                per_cat[c] += 1
                per_cat_reviews[c].add(r["review_id"])
                per_cat_sources[c].add(r["source"])
                # Prefer short, single-tag, clearly negative sentences as examples.
                score = (len(cats) == 1, bool(re.search(r"\b(?:not|no|lack|missing|unclear|should|insufficient|limited|only|weak|poor|fail)\b", s, re.I)), -len(s))
                examples[c].append((score, s, r))
    n_no_cue = sum(1 for k, _, _ in untagged if k == "no_cue")
    lines = [f"# Reviewer complaints: {len(reviews)} reviews, {n_sent} sentences, {n_tagged} tagged ({n_multi} with 2+ tags), "
             f"{len(untagged)} untagged ({n_no_cue} without a complaint cue, {len(untagged) - n_no_cue} with a cue but no category), "
             f"{skipped['praise']} praise and {skipped['keyword_list']} keyword lists skipped | {TODAY}",
             "", f"Source file: `{os.path.abspath(a.file)}`. Query: " + "; ".join(sorted({r.get('query', '') for r in reviews})), "",
             "Tags come from a keyword taxonomy (regex) applied only to sentences that carry a complaint cue "
             "(not, no, lack, unclear, insufficient, missing, weak, limited, should, needs, must, however, concern, fails, "
             "does not, cannot, questionable, overstate, unsupported, inconsistent, confus-, why, how). A tagged sentence is a "
             "*candidate* complaint in that category: read the quoted examples before relying on a frequency. Strengths "
             "sections, praise without a negation and keyword lists were removed before tagging.", "",
             "## Frequencies", ""]
    rows = []
    for c, _ in TAXONOMY:
        k = per_cat[c]
        rows.append([CATEGORY_LABELS[c], str(k), f"{100 * k / n_tagged:.0f}%" if n_tagged else "0%",
                     f"{len(per_cat_reviews[c])}/{len(reviews)}", ", ".join(sorted(per_cat_sources[c]))])
    tbl = table(rows, ["category", "sentences", "% of tagged", "reviews touching it", "sources"])
    lines += [tbl, "", "## By source", "",
              table([[s, str(k), str(sum(1 for r in reviews if r['source'] == s))] for s, k in per_source.most_common()],
                    ["source", "sentences", "reviews"]), "", "## Examples (verbatim, attributed)", ""]
    for c, _ in TAXONOMY:
        lines.append(f"### {CATEGORY_LABELS[c]} ({per_cat[c]})")
        lines.append("")
        seen_reviews = set()
        shown = 0
        for score, s, r in sorted(examples[c], key=lambda x: x[0], reverse=True):
            if r["review_id"] in seen_reviews:
                continue
            seen_reviews.add(r["review_id"])
            who = r.get("reviewer") or r.get("kind") or "reviewer"
            lines.append(f'- "{s}" ({r["source"]}, {who}, {r.get("venue", "")} {r.get("year") or ""}, {r["url"]})')
            shown += 1
            if shown >= a.examples:
                break
        if not shown:
            lines.append("- (no sentence tagged in this category)")
        lines.append("")
    if untagged and a.show_untagged:
        lines += [f"## Untagged sample ({len(untagged)} total; [cue] = complaint cue but no category, [no cue] = no complaint cue; "
                  "add keywords to the taxonomy or the cue list if these are complaints)", ""]
        lines += [f'- [{"cue" if k == "cue" else "no cue"}] "{s}" ({r["source"]}, {r["url"]})' for k, s, r in untagged[:a.show_untagged]]
        lines.append("")
    md = "\n".join(lines)
    print(md)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(md + "\n")
        print(f"saved {os.path.abspath(a.out)}")
    print(f"RESULT: PASS ({len(reviews)} reviews, {n_tagged}/{n_sent} sentences tagged, {skipped['praise']} praise and "
          f"{skipped['keyword_list']} keyword lists skipped; untagged sentences are listed with --show-untagged N)")
    return 0


# ---------------------------------------------------------------- selftest

SELFTEST_POSITIVE = [
    # Real sentences from public reviews (sources verified live on 2026-10-21), plus one planted sentence (marked).
    ("Limited Dataset Evaluation: The experiments are confined to the Social Media Prediction Dataset (SMPD).", "methodology_sample",
     "https://openreview.net/forum?noteId=bvzfqP46ZH&id=adrPcTD2cz"),
    ("Alpha values, and hence p-values, should be adjusted to account for Type-I error on the confirmatory tests.",
     "statistics_analysis", "https://doi.org/10.5256/f1000research.10808.r18117"),
    ("And, they should provide some theoretical reason for why such paths lead nowhere.", "theory",
     "https://doi.org/10.5256/f1000research.10808.r18117"),
    ("Abstract: This portion is confusing to a casual reader.", "writing_clarity",
     "https://doi.org/10.5256/f1000research.4585.r4941"),
    ("Lack of baselines: Although VTS outperforms some traditional metrics (likes, retweets), it is not compared against recent work.",
     "literature_coverage", "https://openreview.net/forum?noteId=e0iexYG2MV&id=FYvZCwdb6F"),
    ("The sample is not justified", "methodology_sample", "(planted)"),
]
SELFTEST_BOILERPLATE = [
    # Planted controls: boilerplate must not even reach the classifier.
    "I confirm that I have read this submission and believe that I have an appropriate level of expertise to confirm that it is of an acceptable scientific standard.",
    "Thank you for submitting your article to eLife.",
    "Reviewer Expertise: NA",
]
SELFTEST_NO_TAG = [
    # (sentence, expected kind): praise and keyword lists must produce no tag even though taxonomy words occur.
    ("The paper is well written and the experiments are convincing.", "praise", "(planted)"),
    ("The sample is large and the statistics are sound, and the authors should be commended.", "praise", "(planted)"),
    ("Leadership Studies; Islamic Business Ethics; Knowledge Management; Innovative Work Behavior; Organizational Effectiveness",
     "keyword_list", "F1000Research reviewer report, real keyword line"),
    ("Social Media; Academic Performance; No Significant Effect; Model Fit; Sample Size", "keyword_list", "(planted, carries cue words)"),
    ("The authors integrate multiple data modalities including textual information, user activity patterns, and profile metadata.",
     "no_cue", "https://openreview.net/forum?noteId=1LtOPch054&id=KxiTeX4Y3R"),
]
SELFTEST_TOPIC = [
    # (query, text, expected on_topic)
    ('"social media" students', "Effects of social media use on university students", True),
    ('"social media" students', "Media coverage and social outcomes among students", False),
    ("social media academic performance", "Academic performance of first-year students", True),
    ("social media academic performance", "Social media marketing effectiveness", False),
    ("twitter engagement classroom", "Using Twitter to increase student engagement in a classroom", True),
    ("twitter engagement classroom", "Quantum error correction with surface codes", False),
    ("twitter engagement classroom", "Twitter use in the classroom", True),
]


def cmd_selftest(a):
    fails = 0
    rows = []
    for s, want, url in SELFTEST_POSITIVE:
        got = tag(s)
        ok = want in got
        fails += not ok
        rows.append(["positive", "PASS" if ok else "FAIL", want, ", ".join(got) or "(none)", short(s, 60)])
    for s in SELFTEST_BOILERPLATE:
        got = sentences(s)
        ok = not got
        fails += not ok
        rows.append(["negative control", "PASS" if ok else "FAIL", "(dropped as boilerplate)",
                     "dropped" if ok else "kept: " + ", ".join(tag(got[0])), short(s, 60)])
    for s, kind, _ in SELFTEST_NO_TAG:
        got_kind, got = sentence_kind(s), tag(s)
        ok = got_kind == kind and not got
        fails += not ok
        rows.append([f"negative control ({kind})", "PASS" if ok else "FAIL", f"{kind}, no tag",
                     f"{got_kind}, " + (", ".join(got) or "no tag"), short(s, 60)])
    for q, text, want in SELFTEST_TOPIC:
        got = on_topic(parse_query(q), False, text)
        ok = got == want
        fails += not ok
        rows.append(["relevance filter", "PASS" if ok else "FAIL", f"{'keep' if want else 'skip'}: {q}", "keep" if got else "skip", short(text, 60)])
    # Strength stripping: praise under 'Strengths:' must not reach the classifier.
    body, strengths = strip_strengths("Summary:\nA study.\nStrengths:\nThe sample is large and the statistics are sound.\nWeaknesses:\nThe sample is not representative.")
    ok = "representative" in body and "sound" not in body and "sound" in strengths
    fails += not ok
    rows.append(["strip strengths", "PASS" if ok else "FAIL", "weaknesses only", short(body.replace("\n", " / "), 40), "Strengths block removed"])
    # Empty file: classify must report 0 and fail, never invent.
    empty = os.path.join(os.path.dirname(os.path.abspath(a.out_dir or ".")), "_empty_reviews.jsonl") if a.out_dir else "_empty_reviews.jsonl"
    open(empty, "w").close()
    ns = argparse.Namespace(file=empty, out=None, source=None, examples=1, show_untagged=0)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_classify(ns)
    os.remove(empty)
    ok = rc == 1 and "0 reviews" in buf.getvalue()
    fails += not ok
    rows.append(["empty file", "PASS" if ok else "FAIL", "RESULT: FAIL (0 reviews)", buf.getvalue().strip().splitlines()[-1][:40], "classify on an empty JSONL"])
    print(table(rows, ["check", "result", "expected", "got", "input"]))
    print("Not checked here: live API calls (run `pull` for that).")
    print(f"RESULT: {'PASS' if not fails else 'FAIL'} ({len(rows) - fails}/{len(rows)} checks)")
    return 1 if fails else 0


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("pull", help="fetch public peer reviews by keyword",
                       epilog='example: reviews.py pull --query \'"social media" academic performance\' --source elife --n 20 --out reviews.jsonl')
    s.add_argument("--query", required=True, help='keywords; a multi-word phrase in double quotes is required verbatim, '
                                                  'otherwise two non-filler query words must appear')
    s.add_argument("--source", default="all", help="elife|openreview|f1000|peerj|all, or a comma list (default all)")
    s.add_argument("--n", type=int, default=20, help="reviews to save per source (default 20)")
    s.add_argument("--since", type=int, help="skip reviews of papers published before this year")
    s.add_argument("--out", default="reviews.jsonl")
    s.add_argument("--append", action="store_true", help="add to an existing file (skips reviews already in it)")
    s.add_argument("--loose", action="store_true", help="keep every search hit (turns the relevance filter off)")
    s.set_defaults(fn=cmd_pull)

    s = sub.add_parser("classify", help="tag complaint sentences by category and print frequencies",
                       epilog="example: reviews.py classify reviews.jsonl --out complaints.md --show-untagged 20")
    s.add_argument("file", nargs="?", default="reviews.jsonl")
    s.add_argument("--out", help="write the markdown report here as well")
    s.add_argument("--source", help="only these sources (comma list)")
    s.add_argument("--examples", type=int, default=3, help="example sentences per category (default 3)")
    s.add_argument("--show-untagged", type=int, default=0, help="also list N untagged sentences (no cue, or cue but no category)")
    s.set_defaults(fn=cmd_classify)

    s = sub.add_parser("selftest", help="classifier and relevance-filter checks with real sentences and planted controls",
                       epilog="example: reviews.py selftest")
    s.add_argument("--out-dir", help=argparse.SUPPRESS)
    s.set_defaults(fn=cmd_selftest)

    a = p.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
