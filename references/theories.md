# Theory registry and theory-fit procedure (AR + EN)

Thirty theories that carry most business, education, psychology, information-systems and health studies in Arab universities and journals. Every source below was resolved on 2026-10-21: journal articles through `python -X utf8 scholar.py verify <DOI>` (Crossref, all `found`, integrity `ok`), books through `scholar.py book --title/--isbn` (Open Library, ISBN shown). Nothing here was typed from memory without that check.

**This registry is not a ledger.** Before a theory source is cited, run `scholar.py add <DOI>` (or `add --isbn <ISBN> --edition-year <year> --publisher "<name>"`) in the project folder, read the abstract, and cite from the ledger. The volume, issue and pages are deliberately left out here so that nobody copies them: `add` fetches them from the registry.

## How to use this file

1. Stage 2 (literature): pick 1 to 2 candidate theories from the selector table, then read their entries.
2. Stage 4 (framework): run the theory-fit procedure at the end of this file on every hypothesis. A hypothesis that maps to no proposition is unsupported by that theory and must be re-argued, re-framed as exploratory, or dropped.
3. Stage 6 (writing): use the template sentences; keep the English theory name in parentheses after the Arabic name the first time it appears.

## Selector: which theory for which question

| The study asks why or whether... | Start with | Also consider |
|---|---|---|
| people adopt or keep using a technology | TAM, UTAUT | ECT (continuance), DOI (spread in a population), IS Success (system-level outcomes) |
| people perform a deliberate behaviour (vote, recycle, vaccinate, report fraud) | TPB | SCT (self-efficacy), HBM / PMT (health threats) |
| employees go beyond the contract, stay, or burn out | Social Exchange, JD-R | COR, Equity, SDT |
| a leader changes follower effort or outcomes | Transformational Leadership | Goal-Setting, Expectancy, Contingency |
| motivation and persistence (work, study, sport) | SDT, Expectancy, Goal-Setting | Self-Regulation, SCT |
| some firms outperform others | RBV, Dynamic Capabilities | Institutional, TCE, Agency, Signalling |
| organisations look alike or adopt practices that do not pay | Institutional | Stakeholder, Contingency |
| governance, boards, ownership, disclosure | Agency, Signalling | Stakeholder, TCE |
| structure, fit and performance | Contingency | RBV |
| learning design, online learning, e-learning satisfaction | Cognitive Load, CoI, Constructivism | Self-Regulation, SCT, TAM |
| media choice, social-media use, gratification | Uses and Gratifications | ECT, TAM |
| preventive health behaviour, fear appeals, compliance | HBM, PMT | TPB, SCT |
| stress, resource loss, recovery | COR, JD-R | SDT |
| perceived fairness of pay, grades, treatment | Equity | Social Exchange |

Abbreviations: TAM Technology Acceptance Model; UTAUT Unified Theory of Acceptance and Use of Technology; TPB Theory of Planned Behavior; JD-R Job Demands-Resources; SDT Self-Determination Theory; RBV Resource-Based View; DOI Diffusion of Innovations; ECT Expectation-Confirmation Theory; SCT Social Cognitive Theory; CoI Community of Inquiry; HBM Health Belief Model; PMT Protection Motivation Theory; COR Conservation of Resources; TCE Transaction Cost Economics.

## Registry

Each entry: name EN | AR, the verified source(s), two-line core propositions (numbered P1, P2... so the fit table can point at them), typical constructs, hypotheses the theory licenses, and the misuse reviewers reject most often.

### 1. Technology Acceptance Model (TAM) | نموذج قبول التكنولوجيا

- **Verified source:** Davis (1989). Perceived usefulness, perceived ease of use, and user acceptance of information technology. *MIS Quarterly*. https://doi.org/10.2307/249008 (verify: found, ok)
- **Propositions:** P1 Intention to use a system is driven by perceived usefulness (PU) and perceived ease of use (PEOU). P2 PEOU also raises PU; both are shaped by external variables (design, training, support), which act only through them.
- **Constructs:** PU, PEOU, behavioural intention, self-reported or actual use; external variables. (Attitude toward use sits in the companion paper Davis, Bagozzi and Warshaw, 1989, *Management Science*: verify it separately before citing attitude.)
- **Hypotheses licensed:** PEOU -> PU (+); PU -> intention / use (+); PEOU -> intention / use (+); intention -> use (+); external variable -> PU/PEOU (+), never external variable -> use directly.
- **Common misuse:** adding "trust", "price" or "social influence" as if Davis proposed them (those belong to extensions or to UTAUT and must be argued from their own sources); treating intention as use; applying TAM to mandatory systems where intention is not a choice.

### 2. Unified Theory of Acceptance and Use of Technology (UTAUT) | النظرية الموحدة لقبول التكنولوجيا واستخدامها

- **Verified source:** Venkatesh, Morris, Davis and Davis (2003). User acceptance of information technology: Toward a unified view. *MIS Quarterly*. https://doi.org/10.2307/30036540 (verify: found, ok)
- **Propositions:** P1 Performance expectancy, effort expectancy and social influence predict intention; facilitating conditions and intention predict use. P2 Gender, age, experience and voluntariness moderate these paths.
- **Constructs:** performance expectancy, effort expectancy, social influence, facilitating conditions, behavioural intention, use behaviour; moderators gender, age, experience, voluntariness.
- **Hypotheses licensed:** each of the three expectancy constructs -> intention (+); facilitating conditions -> use (+); intention -> use (+); moderation of a named path by a named moderator (e.g. effort expectancy -> intention stronger for older users and in early experience).
- **Common misuse:** dropping the moderators and still calling it UTAUT without saying so; adding hedonic motivation, price value and habit (those are UTAUT2, a different source); correlating facilitating conditions with intention, a path the 2003 model does not state.

### 3. Theory of Planned Behavior (TPB) | نظرية السلوك المخطط

- **Verified source:** Ajzen (1991). The theory of planned behavior. *Organizational Behavior and Human Decision Processes*. https://doi.org/10.1016/0749-5978(91)90020-T (verify: found, ok)
- **Propositions:** P1 Intention is the immediate antecedent of behaviour and is formed by attitude toward the behaviour, subjective norm and perceived behavioural control (PBC). P2 PBC also predicts behaviour directly when it reflects actual control.
- **Constructs:** attitude, subjective norm, PBC, intention, behaviour; underlying behavioural, normative and control beliefs.
- **Hypotheses licensed:** attitude / subjective norm / PBC -> intention (+); intention -> behaviour (+); PBC -> behaviour (+); belief-based measures -> their direct construct.
- **Common misuse:** measuring attitude toward an object (the bank) instead of the behaviour (using the bank's app); omitting the target behaviour's time, context and target so the constructs do not match; claiming the theory predicts behaviour when only intention was measured.

### 4. Social Exchange Theory | نظرية التبادل الاجتماعي

- **Verified sources:** Homans (1958). Social behavior as exchange. *American Journal of Sociology*. https://doi.org/10.1086/222355; Blau (1964). *Exchange and power in social life*. Wiley (Open Library ISBN 0887386288, later editions 9781138523197); Emerson (1976). Social exchange theory. *Annual Review of Sociology*. https://doi.org/10.1146/annurev.so.02.080176.002003; review used in management: Cropanzano and Mitchell (2005). *Journal of Management*. https://doi.org/10.1177/0149206305279602 (all verify: found, ok)
- **Propositions:** P1 Relationships develop through reciprocal exchanges of valued resources; a benefit received creates an obligation to return one. P2 Repeated fair exchange builds trust, commitment and loyalty; imbalance or breach reduces them.
- **Constructs:** perceived organisational support, leader-member exchange, psychological contract fulfilment or breach, trust, commitment, organisational citizenship behaviour, turnover intention.
- **Hypotheses licensed:** support / fair treatment / LMX -> commitment, OCB, performance (+); breach -> turnover intention (+), OCB (-); trust or commitment as mediator between the benefit received and the reciprocating behaviour.
- **Common misuse:** citing Blau for a direct link from pay to performance (that is an economic, not social, exchange); invoking reciprocity without measuring a benefit on one side and a return on the other; mixing Blau's exchange with Adams's equity (different predictions: equity is about ratio comparison, exchange about reciprocity).

### 5. Job Demands-Resources (JD-R) model | نموذج متطلبات العمل وموارده

- **Verified sources:** Demerouti, Bakker, Nachreiner and Schaufeli (2001). The job demands-resources model of burnout. *Journal of Applied Psychology*. https://doi.org/10.1037/0021-9010.86.3.499; Bakker and Demerouti (2007). The job demands-resources model: State of the art. *Journal of Managerial Psychology*. https://doi.org/10.1108/02683940710733115 (verify: found, ok)
- **Propositions:** P1 Job demands drive a health-impairment process (exhaustion, burnout); job resources drive a motivational process (engagement). P2 Resources buffer the demand -> strain effect and matter most when demands are high.
- **Constructs:** job demands (workload, emotional demands, role conflict), job resources (autonomy, support, feedback), personal resources (a later extension, separate source), exhaustion / burnout, engagement, performance, turnover.
- **Hypotheses licensed:** demands -> exhaustion (+); resources -> engagement (+); resources -> exhaustion (-); resources moderate demands -> exhaustion (buffer); engagement mediates resources -> performance.
- **Common misuse:** calling every variable a "resource" or "demand" after the fact; testing only main effects and still claiming the buffer hypothesis; cross-sectional data presented as the "process".

### 6. Self-Determination Theory (SDT) | نظرية التقرير الذاتي (التحديد الذاتي)

- **Verified sources:** Deci and Ryan (1985). *Intrinsic motivation and self-determination in human behavior*. Plenum (Open Library ISBN 9781489922717); Ryan and Deci (2000). Self-determination theory and the facilitation of intrinsic motivation, social development, and well-being. *American Psychologist*. https://doi.org/10.1037/0003-066X.55.1.68 (verify: found, ok)
- **Propositions:** P1 Satisfying three basic needs (autonomy, competence, relatedness) sustains intrinsic and well-internalised motivation, well-being and persistence. P2 Controlling contexts and rewards that thwart those needs shift motivation toward external regulation and lower quality of engagement.
- **Constructs:** need satisfaction / frustration, autonomy support, intrinsic motivation, the regulation continuum (external, introjected, identified, integrated), amotivation, well-being, persistence.
- **Hypotheses licensed:** autonomy support -> need satisfaction (+) -> autonomous motivation (+) -> performance / well-being / persistence (+); controlling supervision -> need frustration (+) -> ill-being; need satisfaction mediates context -> outcome.
- **Common misuse:** labelling any motivation scale "SDT" without the regulation types; reporting a single "motivation" score (the theory is about quality, not quantity); claiming extrinsic rewards always harm (the theory says controlling rewards do, informational ones need not).

### 7. Expectancy Theory | نظرية التوقع

- **Verified source:** Vroom (1964). *Work and motivation*. Wiley (Open Library ISBN 0471912050; 1995 Jossey-Bass edition 9780898745276)
- **Propositions:** P1 Motivational force = expectancy (effort leads to performance) x instrumentality (performance leads to outcomes) x valence (value of the outcomes). P2 Because the terms multiply, a zero on any one of them removes the motivation to act.
- **Constructs:** expectancy, instrumentality, valence, motivational force, effort, performance, outcomes / rewards.
- **Hypotheses licensed:** expectancy, instrumentality and valence each -> effort (+); their interaction -> effort (+); perceived reward contingency -> performance (+).
- **Common misuse:** testing the three terms additively and calling it Vroom's model; using "expectations of the organisation" (a different meaning); applying it where outcomes are not contingent on performance (fixed grading, seniority pay).

### 8. Transformational Leadership (Bass) | القيادة التحويلية

- **Verified sources:** Bass (1985). *Leadership and performance beyond expectations*. Free Press (Open Library ISBN 0029018102); Bass (1990). From transactional to transformational leadership: Learning to share the vision. *Organizational Dynamics*. https://doi.org/10.1016/0090-2616(90)90061-S (verify: found, ok); origin of the term: Burns (1978). *Leadership*. Harper and Row (Open Library ISBN 9780060105884)
- **Propositions:** P1 Leaders who show idealised influence, inspirational motivation, intellectual stimulation and individualised consideration raise follower effort and performance beyond what contingent reward alone produces (the augmentation effect). P2 Transformational and transactional behaviours coexist in the same leader; laissez-faire is the absence of both.
- **Constructs:** the four I's, contingent reward, management by exception (active, passive), laissez-faire; outcomes: extra effort, satisfaction with the leader, effectiveness, commitment, OCB, innovation.
- **Hypotheses licensed:** transformational leadership -> commitment, OCB, performance, innovation (+); the augmentation effect (transformational adds variance over transactional); mediators such as trust, empowerment, identification.
- **Common misuse:** treating the four dimensions as separate theories; measuring "leadership style" with one item; using Burns (1978) for the four I's (they are Bass's); ignoring common-method bias when followers rate both the leader and the outcome.

### 9. Resource-Based View (RBV) | النظرة القائمة على الموارد

- **Verified sources:** Wernerfelt (1984). A resource-based view of the firm. *Strategic Management Journal*. https://doi.org/10.1002/smj.4250050207; Barney (1991). Firm resources and sustained competitive advantage. *Journal of Management*. https://doi.org/10.1177/014920639101700108 (verify: found, ok)
- **Propositions:** P1 Firms are bundles of heterogeneous, imperfectly mobile resources. P2 A resource that is valuable, rare, inimitable and non-substitutable (VRIN) yields sustained competitive advantage.
- **Constructs:** tangible, intangible and human resources; capabilities; VRIN attributes; competitive advantage; firm performance.
- **Hypotheses licensed:** VRIN resource (e.g. knowledge, reputation, IT capability) -> competitive advantage / performance (+); capability mediates resource -> performance; heterogeneity explains performance differences between firms.
- **Common misuse:** calling any input a "strategic resource" without arguing VRIN; testing at the individual level (RBV is firm-level); tautology (defining the resource by the performance it supposedly causes).

### 10. Dynamic Capabilities | القدرات الديناميكية

- **Verified source:** Teece, Pisano and Shuen (1997). Dynamic capabilities and strategic management. *Strategic Management Journal*. https://doi.org/10.1002/(SICI)1097-0266(199708)18:7<509::AID-SMJ882>3.0.CO;2-Z (verify: found, ok; the DOI contains angle brackets, quote it in the shell)
- **Propositions:** P1 In fast-changing markets advantage comes from the firm's ability to integrate, build and reconfigure its competences (sensing, seizing, reconfiguring). P2 That ability is shaped by the firm's processes, positions and paths and is itself hard to imitate.
- **Constructs:** sensing, seizing, reconfiguring (transforming); absorptive capacity, agility, ambidexterity (related, separately sourced); environmental dynamism; performance.
- **Hypotheses licensed:** dynamic capability -> operational capability / innovation (+) -> performance (+); environmental dynamism moderates dynamic capability -> performance (stronger when dynamic).
- **Common misuse:** measuring static resources and calling them dynamic capabilities; omitting dynamism, the condition the theory depends on; claiming a direct effect on profit when the 1997 paper argues through competences.

### 11. Institutional Theory | النظرية المؤسسية

- **Verified sources:** Meyer and Rowan (1977). Institutionalized organizations: Formal structure as myth and ceremony. *American Journal of Sociology*. https://doi.org/10.1086/226550; DiMaggio and Powell (1983). The iron cage revisited: Institutional isomorphism and collective rationality in organizational fields. *American Sociological Review*. https://doi.org/10.2307/2095101 (verify: found, ok)
- **Propositions:** P1 Organisations adopt structures and practices to gain legitimacy, not only efficiency, and may decouple formal structure from daily work. P2 Within a field, coercive, mimetic and normative pressures make organisations increasingly similar (isomorphism).
- **Constructs:** coercive, mimetic, normative pressure; legitimacy; isomorphism; decoupling; institutional logics (later work, separate source).
- **Hypotheses licensed:** each pressure -> adoption of a practice (ERP, CSR reporting, accreditation) (+); legitimacy mediates pressure -> adoption; uncertainty strengthens mimetic pressure -> adoption; adoption without performance gain (decoupling).
- **Common misuse:** asserting isomorphism from a single organisation; using it to predict performance gains (the theory predicts legitimacy, often at the cost of efficiency); mixing it with RBV without stating that the predictions conflict.

### 12. Stakeholder Theory | نظرية أصحاب المصلحة

- **Verified sources:** Freeman (1984). *Strategic management: A stakeholder approach*. Pitman (Open Library ISBN 0273019139); Donaldson and Preston (1995). The stakeholder theory of the corporation: Concepts, evidence, and implications. *Academy of Management Review*. https://doi.org/10.2307/258887 (verify: found, ok)
- **Propositions:** P1 A firm's success depends on managing relationships with every group that affects or is affected by it, not only shareholders. P2 The theory has descriptive, instrumental and normative versions; the instrumental version predicts that attending to stakeholders improves performance.
- **Constructs:** stakeholder salience (power, legitimacy, urgency, a separate source), stakeholder engagement, CSR, reputation, trust, firm performance.
- **Hypotheses licensed (instrumental version):** stakeholder orientation / CSR -> reputation, loyalty, performance (+); stakeholder pressure -> disclosure (+).
- **Common misuse:** citing Freeman for a moral claim and testing an instrumental one (say which version); treating "stakeholders" as one homogeneous group; using it as a synonym for CSR.

### 13. Social Cognitive Theory (SCT) | النظرية المعرفية الاجتماعية

- **Verified sources:** Bandura (1977). Self-efficacy: Toward a unifying theory of behavioral change. *Psychological Review*. https://doi.org/10.1037/0033-295X.84.2.191; Bandura (1986). *Social foundations of thought and action: A social cognitive theory*. Prentice-Hall (Open Library ISBN 013815614X); Bandura (2001). Social cognitive theory: An agentic perspective. *Annual Review of Psychology*. https://doi.org/10.1146/annurev.psych.52.1.1 (verify: found, ok)
- **Propositions:** P1 Behaviour, personal factors (cognition, self-efficacy, outcome expectations) and the environment influence one another (triadic reciprocal causation). P2 Self-efficacy, built from mastery, vicarious experience, persuasion and physiological states, determines what people attempt, how long they persist and what they achieve.
- **Constructs:** self-efficacy, outcome expectations, observational learning / modelling, self-regulation, goals, socio-structural facilitators and impediments.
- **Hypotheses licensed:** mastery experience / modelling -> self-efficacy (+); self-efficacy -> performance, persistence, behaviour (+); self-efficacy mediates training -> performance; outcome expectations -> behaviour (+).
- **Common misuse:** measuring general self-esteem or confidence and calling it self-efficacy (it is task-specific); claiming reciprocal causation from one-wave data; citing Bandura for "social learning" of attitudes without a modelling component.

### 14. Diffusion of Innovations (DOI) | نظرية انتشار الابتكارات

- **Verified source:** Rogers (1962; 5th ed. 2003). *Diffusion of innovations*. Free Press (Open Library ISBN 0743222091 for the editions set; 5th edition 0743258231)
- **Propositions:** P1 The rate of adoption of an innovation in a social system depends on its perceived relative advantage, compatibility, complexity, trialability and observability, communicated through channels over time. P2 Adopters are distributed over time as innovators, early adopters, early majority, late majority and laggards; opinion leaders and change agents speed diffusion.
- **Constructs:** the five perceived attributes, adopter categories, innovation-decision process (knowledge, persuasion, decision, implementation, confirmation), communication channels, social system.
- **Hypotheses licensed:** relative advantage, compatibility, trialability, observability -> adoption (+), complexity -> adoption (-); opinion leadership -> rate of adoption (+); adopter category differences in attributes (education, media exposure).
- **Common misuse:** using the five attributes at the individual intention level and calling the study "diffusion" (diffusion is a population process over time); mixing the attributes with TAM constructs without saying which overlap (relative advantage ~ PU, complexity ~ reversed PEOU).

### 15. IS Success Model (DeLone and McLean) | نموذج نجاح نظم المعلومات

- **Verified sources:** DeLone and McLean (1992). Information systems success: The quest for the dependent variable. *Information Systems Research*. https://doi.org/10.1287/isre.3.1.60; DeLone and McLean (2003). The DeLone and McLean model of information systems success: A ten-year update. *Journal of Management Information Systems*. https://doi.org/10.1080/07421222.2003.11045748 (verify: found, ok)
- **Propositions:** P1 System quality, information quality and (2003) service quality affect use / intention to use and user satisfaction. P2 Use and satisfaction influence each other and together produce net benefits, which feed back on both.
- **Constructs:** system quality, information quality, service quality, use / intention to use, user satisfaction, net benefits (individual or organisational impact in 1992).
- **Hypotheses licensed:** each quality -> use (+) and -> satisfaction (+); use <-> satisfaction (+); use -> net benefits (+); satisfaction -> net benefits (+).
- **Common misuse:** adding a quality dimension (e.g. "mobile quality") without arguing it; using the 1992 version's "individual impact" with the 2003 citation; measuring use with self-reported frequency in mandatory settings (the authors warn against it).

### 16. Expectation-Confirmation Theory (ECT) | نظرية تأكيد التوقعات

- **Verified sources:** Oliver (1980). A cognitive model of the antecedents and consequences of satisfaction decisions. *Journal of Marketing Research*. https://doi.org/10.2307/3150499; IS continuance version: Bhattacherjee (2001). Understanding information systems continuance: An expectation-confirmation model. *MIS Quarterly*. https://doi.org/10.2307/3250921 (verify: found, ok)
- **Propositions:** P1 Satisfaction depends on the confirmation (or disconfirmation) of pre-purchase or pre-use expectations by perceived performance. P2 Satisfaction, and in the IS version post-use perceived usefulness, drive the intention to repurchase or continue using.
- **Constructs:** expectation, perceived performance, confirmation, satisfaction, repurchase / continuance intention; post-adoption perceived usefulness (2001).
- **Hypotheses licensed:** confirmation -> satisfaction (+); confirmation -> perceived usefulness (+); perceived usefulness -> satisfaction (+); satisfaction -> continuance intention (+); perceived usefulness -> continuance intention (+).
- **Common misuse:** measuring expectations after use (they must be pre-use or recalled with care); using ECT for first-time adoption (that is TAM / UTAUT territory); treating "confirmation" as "satisfaction".

### 17. Uses and Gratifications | نظرية الاستخدامات والإشباعات

- **Verified source:** Katz, Blumler and Gurevitch (1973). Uses and gratifications research. *Public Opinion Quarterly*. https://doi.org/10.1086/268109 (verify: found, ok)
- **Propositions:** P1 Audiences are active and goal-directed: they select media to satisfy social and psychological needs (information, personal identity, integration and interaction, entertainment). P2 Media compete with other sources of gratification, and gratifications sought and obtained can differ.
- **Constructs:** gratifications sought, gratifications obtained, needs / motives, media exposure, dependency, outcomes (satisfaction, continued use).
- **Hypotheses licensed:** motive X (e.g. social interaction) -> use of platform Y (+); gratifications obtained -> continued use / satisfaction (+); gap between sought and obtained -> switching.
- **Common misuse:** listing motives after a factor analysis and calling the result a theory test; ignoring that needs and gratifications must be measured separately; using it to claim media effects (it explains selection, not effects).

### 18. Self-Regulation / Self-Regulated Learning | التنظيم الذاتي والتعلم المنظم ذاتياً

- **Verified sources:** Zimmerman (1989). A social cognitive view of self-regulated academic learning. *Journal of Educational Psychology*. https://doi.org/10.1037/0022-0663.81.3.329; Zimmerman (2000). Attaining self-regulation: A social cognitive perspective. In *Handbook of self-regulation*. https://doi.org/10.1016/B978-012109890-2/50031-7; general control-theory root: Carver and Scheier (1982). Control theory: A useful conceptual framework for personality-social, clinical, and health psychology. *Psychological Bulletin*. https://doi.org/10.1037/0033-2909.92.1.111 (verify: found, ok)
- **Propositions:** P1 Learners regulate themselves through a cycle of forethought (goal setting, planning, self-efficacy), performance (self-control, self-observation) and self-reflection (self-judgement, self-reaction). P2 Self-regulatory skill, not ability alone, explains achievement and persists through feedback loops that compare the current state with the goal.
- **Constructs:** goal setting, strategic planning, self-efficacy, self-monitoring, metacognition, time management, help seeking, self-evaluation, attributions, achievement.
- **Hypotheses licensed:** self-regulation strategies -> achievement (+); self-efficacy -> strategy use (+); monitoring / feedback -> goal attainment (+); self-regulation mediates motivation -> achievement.
- **Common misuse:** citing Zimmerman for a single "study habits" scale; confusing self-regulation (process) with self-control (one component); using the 2000 chapter's phases while measuring only one phase.

### 19. Cognitive Load Theory | نظرية الحمل المعرفي

- **Verified sources:** Sweller (1988). Cognitive load during problem solving: Effects on learning. *Cognitive Science*. https://doi.org/10.1207/s15516709cog1202_4; Sweller, van Merrienboer and Paas (1998). Cognitive architecture and instructional design. *Educational Psychology Review*. https://doi.org/10.1023/A:1022193728205 (verify: found, ok)
- **Propositions:** P1 Working memory is limited; learning builds schemas in long-term memory, and instruction that wastes working-memory capacity on irrelevant processing (extraneous load) impairs it. P2 Intrinsic load depends on element interactivity; instructional design should reduce extraneous load and leave capacity for schema construction (germane processing).
- **Constructs:** intrinsic, extraneous, germane load; element interactivity; expertise (expertise reversal); effects such as worked example, split attention, redundancy, modality.
- **Hypotheses licensed:** worked examples / integrated formats -> lower extraneous load -> higher learning (+); prior knowledge moderates design -> learning (expertise reversal); subjective load ratings -> performance (-) for extraneous load.
- **Common misuse:** measuring "load" with one item and splitting it into three types; claiming germane load is a separate measurable quantity (later versions fold it into intrinsic); using the theory for motivation or satisfaction outcomes.

### 20. Constructivism (Piaget, Vygotsky) | النظرية البنائية

- **Verified sources:** Piaget (1952). *The origins of intelligence in children*. International Universities Press (Open Library ISBN 0823639002 for the IUP edition; first English edition set 9780823682072); Vygotsky (1978). *Mind in society: The development of higher psychological processes*. Harvard University Press (Open Library ISBN 0674576292)
- **Propositions:** P1 Learners construct knowledge by assimilating new experience into existing schemas and accommodating schemas when experience does not fit (Piaget). P2 Higher mental functions develop first socially, through interaction with more capable others inside the zone of proximal development, with language as the main tool (Vygotsky, social constructivism).
- **Constructs:** schema, assimilation, accommodation, equilibration, stages; zone of proximal development, scaffolding (the word is from later authors), mediation, collaborative learning.
- **Hypotheses licensed:** active / problem-based / collaborative instruction -> conceptual understanding (+) versus transmission; scaffolding within the ZPD -> task performance (+) then faded; peer interaction -> achievement (+).
- **Common misuse:** using "constructivism" as a slogan for any student-centred method with no mechanism named; citing Vygotsky for "scaffolding" (the term is Wood, Bruner and Ross, 1976, separate source); testing a Piagetian stage claim on adults.

### 21. Community of Inquiry (CoI) | إطار مجتمع الاستقصاء

- **Verified source:** Garrison, Anderson and Archer (1999/2000). Critical inquiry in a text-based environment: Computer conferencing in higher education. *The Internet and Higher Education*. https://doi.org/10.1016/S1096-7516(00)00016-6 (verify: found, ok; Crossref dates the issue 1999, the volume is cited as 2000: use `fix --year` after `add` if the venue wants 2000)
- **Propositions:** P1 Deep online learning emerges from the interaction of three presences: cognitive (practical inquiry: triggering event, exploration, integration, resolution), social and teaching. P2 Teaching presence (design, facilitation, direct instruction) is the element that integrates the other two.
- **Constructs:** teaching presence, social presence, cognitive presence; learning presence (later addition, separate source); perceived learning, satisfaction.
- **Hypotheses licensed:** teaching presence -> social presence (+) and -> cognitive presence (+); social presence -> cognitive presence (+); cognitive presence -> perceived learning / satisfaction (+); teaching presence as moderator or mediator.
- **Common misuse:** applying it to face-to-face classrooms without argument; using the CoI survey as a satisfaction scale; claiming "resolution" was reached from discussion-board counts alone.

### 22. Health Belief Model (HBM) | نموذج المعتقدات الصحية

- **Verified sources:** Rosenstock (1974). Historical origins of the health belief model. *Health Education Monographs*. https://doi.org/10.1177/109019817400200403; Janz and Becker (1984). The health belief model: A decade later. *Health Education Quarterly*. https://doi.org/10.1177/109019818401100101 (verify: found, ok)
- **Propositions:** P1 A preventive health action is likely when the person feels susceptible to a condition, believes it would be serious, believes the action is beneficial and sees few barriers. P2 Cues to action trigger the behaviour and, in later versions, self-efficacy and modifying factors (age, education) shape the beliefs.
- **Constructs:** perceived susceptibility, perceived severity, perceived benefits, perceived barriers, cues to action, self-efficacy (added later), health motivation.
- **Hypotheses licensed:** susceptibility / severity / benefits -> behaviour or intention (+); barriers -> behaviour (-); cues -> behaviour (+); barriers as the strongest predictor (Janz and Becker's finding) is an expectation, not a proposition.
- **Common misuse:** treating self-efficacy as an original HBM construct (it was added in the 1980s); combining susceptibility and severity into one "threat" score and then citing both; measuring beliefs after the behaviour.

### 23. Protection Motivation Theory (PMT) | نظرية دافعية الحماية

- **Verified source:** Rogers (1975). A protection motivation theory of fear appeals and attitude change. *The Journal of Psychology*. https://doi.org/10.1080/00223980.1975.9915803 (verify: found, ok)
- **Propositions:** P1 A fear appeal motivates protective behaviour through threat appraisal (severity, vulnerability) and coping appraisal (response efficacy, self-efficacy, response cost). P2 Protection motivation (intention) is highest when threat is high and coping is seen as effective and affordable; high threat with low coping produces avoidance.
- **Constructs:** perceived severity, perceived vulnerability, response efficacy, self-efficacy, response cost, rewards of the risky behaviour, fear, protection motivation, behaviour.
- **Hypotheses licensed:** severity / vulnerability / response efficacy / self-efficacy -> protection motivation (+); response cost -> protection motivation (-); coping appraisal moderates threat appraisal -> motivation. Used in information-security compliance and in health.
- **Common misuse:** omitting coping appraisal and running a pure fear study; using "awareness" as the threat construct; citing the 1975 paper for the 1983 revision's constructs (self-efficacy entered in the revision; argue it from a verified later source).

### 24. Conservation of Resources (COR) Theory | نظرية الحفاظ على الموارد

- **Verified source:** Hobfoll (1989). Conservation of resources: A new attempt at conceptualizing stress. *American Psychologist*. https://doi.org/10.1037/0003-066X.44.3.513 (verify: found, ok)
- **Propositions:** P1 People strive to obtain, retain and protect valued resources (objects, conditions, personal characteristics, energies); stress arises when resources are threatened, lost, or not gained after investment. P2 Loss is more salient than gain, and losses spiral: those with fewer resources are more vulnerable to further loss, while resource gain spirals are slower.
- **Constructs:** resource loss, resource gain, resource investment, loss spirals, gain spirals, strain, burnout, well-being, recovery.
- **Hypotheses licensed:** resource loss -> strain / burnout (+) more strongly than gain reduces it (loss primacy); initial resources -> later resources (+) (spiral, needs longitudinal data); investment of resources (training, recovery) -> lower strain.
- **Common misuse:** reading COR as a synonym for JD-R; testing spirals cross-sectionally; calling any positive variable a "resource" without stating what loss it protects against.

### 25. Equity Theory | نظرية العدالة (الإنصاف)

- **Verified sources:** Adams (1963). Towards an understanding of inequity. *Journal of Abnormal and Social Psychology*. https://doi.org/10.1037/h0040968; Adams (1965). Inequity in social exchange. *Advances in Experimental Social Psychology*. https://doi.org/10.1016/S0065-2601(08)60108-2 (verify: found, ok)
- **Propositions:** P1 People compare the ratio of their outcomes to inputs with that of a referent other; inequality of ratios (under- or over-reward) produces tension proportional to its size. P2 The tension motivates restoring equity by changing inputs or outcomes, distorting perceptions, changing the referent, or leaving.
- **Constructs:** inputs, outcomes, referent other, perceived (in)equity, distributive justice (the modern label), tension, restoration behaviours (effort, absenteeism, turnover, theft).
- **Hypotheses licensed:** perceived under-reward -> satisfaction (-), effort (-), turnover intention (+); perceived equity -> commitment (+); over-reward -> guilt and higher input (weaker, often unsupported).
- **Common misuse:** measuring "fairness" of procedures and citing Adams (procedural and interactional justice have their own sources); dropping the referent other, which is the mechanism; predicting symmetric effects for over-reward.

### 26. Agency Theory | نظرية الوكالة

- **Verified sources:** Jensen and Meckling (1976). Theory of the firm: Managerial behavior, agency costs and ownership structure. *Journal of Financial Economics*. https://doi.org/10.1016/0304-405X(76)90026-X; Eisenhardt (1989). Agency theory: An assessment and review. *Academy of Management Review*. https://doi.org/10.5465/amr.1989.4279003 (verify: found, ok)
- **Propositions:** P1 When a principal delegates to an agent with different goals and risk preferences under information asymmetry, the agent may act in self-interest; the resulting monitoring, bonding and residual costs are agency costs. P2 Outcome-based contracts, monitoring (boards, audits, ownership concentration) and information systems align interests and reduce agency costs.
- **Constructs:** information asymmetry, goal conflict, risk aversion, agency cost, monitoring (board independence, audit quality), incentive alignment (managerial ownership, pay-for-performance), ownership concentration, firm performance, earnings management.
- **Hypotheses licensed:** board independence / audit quality -> earnings management (-), disclosure (+), performance (+); managerial ownership -> agency cost (-); ownership concentration -> monitoring (+) with an entrenchment reversal at high levels (needs its own source).
- **Common misuse:** citing Jensen and Meckling for stakeholder or stewardship predictions; assuming every governance variable reduces agency cost regardless of ownership type (family and state ownership change the principal); ignoring endogeneity in governance-performance tests.

### 27. Transaction Cost Economics (TCE) | نظرية تكاليف المعاملات

- **Verified sources:** Coase (1937). The nature of the firm. *Economica*. https://doi.org/10.1111/j.1468-0335.1937.tb00002.x; Williamson (1975). *Markets and hierarchies: Analysis and antitrust implications*. Free Press (Open Library ISBN 9780029353608); Williamson (1981). The economics of organization: The transaction cost approach. *American Journal of Sociology*. https://doi.org/10.1086/227496 (verify: found, ok)
- **Propositions:** P1 Firms exist because using the market has costs (search, contracting, monitoring, enforcement); activities are organised inside the firm when that is cheaper. P2 Asset specificity, uncertainty and transaction frequency, under bounded rationality and opportunism, determine whether market, hybrid or hierarchy governs a transaction.
- **Constructs:** asset specificity, uncertainty, frequency, opportunism, bounded rationality, transaction cost, governance mode (make / buy / ally), contract completeness, trust (as a substitute, separately sourced).
- **Hypotheses licensed:** asset specificity -> vertical integration or relational governance (+); uncertainty -> hierarchy (+); opportunism risk -> contractual safeguards (+); misalignment of governance and transaction attributes -> performance (-).
- **Common misuse:** using TCE to explain individual outsourcing attitudes; measuring "transaction costs" with a satisfaction item; ignoring opportunism, without which the predictions do not follow.

### 28. Signalling Theory | نظرية الإشارة

- **Verified sources:** Spence (1973). Job market signaling. *The Quarterly Journal of Economics*. https://doi.org/10.2307/1882010; Connelly, Certo, Ireland and Reutzel (2011). Signaling theory: A review and assessment. *Journal of Management*. https://doi.org/10.1177/0149206310388419 (verify: found, ok)
- **Propositions:** P1 Under information asymmetry, a party with private information about its quality sends costly, observable signals that lower-quality parties cannot profitably imitate. P2 A signal works only when it is costly, observable and credible to the receiver, and feedback from receivers shapes future signalling.
- **Constructs:** signaller, signal (certification, education, dividends, CSR disclosure, board prestige), receiver, signal cost, observability, credibility, signalling environment, outcome (hiring, investment, legitimacy, price).
- **Hypotheses licensed:** signal X -> receiver belief about quality (+) -> outcome (+); signal cost / credibility moderates signal -> outcome; signal honesty (correlation with true quality) over time.
- **Common misuse:** calling any disclosure a signal without arguing its cost or the asymmetry; using Spence for "signals" between employees and managers without information asymmetry; ignoring that the signal must separate types.

### 29. Contingency Theory | النظرية الموقفية (الظرفية)

- **Verified sources (organisational):** Lawrence and Lorsch (1967). *Organization and environment: Managing differentiation and integration*. Harvard Business School (Open Library ISBN 0256003149; 1986 ed. 9780875841298); Donaldson (2001). *The contingency theory of organizations*. Sage (Open Library ISBN 0761915745). **Leadership version:** Fiedler (1964). A contingency model of leadership effectiveness. *Advances in Experimental Social Psychology*. https://doi.org/10.1016/S0065-2601(08)60051-9 (verify: found, ok)
- **Propositions:** P1 There is no one best way to organise or lead: performance depends on the fit between structure (or leadership style) and contingencies such as environment uncertainty, technology, size and strategy. P2 Misfit produces lower performance and pressure to adapt (structural adaptation to regain fit).
- **Constructs:** contingency (uncertainty, size, technology, strategy, task structure, position power, leader-member relations), structure (formalisation, centralisation, differentiation, integration), leadership style (task- vs relationship-motivated, LPC), fit, performance.
- **Hypotheses licensed:** contingency x structure interaction -> performance (fit as moderation); fit (profile deviation) -> performance (+); mismatch -> structural change; Fiedler: task-oriented leaders perform best in very favourable or very unfavourable situations, relationship-oriented leaders in moderate ones.
- **Common misuse:** testing main effects and calling the study "contingency"; measuring fit as a difference score without the interaction; citing Fiedler for organisational structure or Lawrence and Lorsch for leadership.

### 30. Goal-Setting Theory | نظرية تحديد الأهداف

- **Verified sources:** Locke (1968). Toward a theory of task motivation and incentives. *Organizational Behavior and Human Performance*. https://doi.org/10.1016/0030-5073(68)90004-4; Locke and Latham (1990). *A theory of goal setting and task performance*. Prentice Hall (Open Library ISBN 0139131388); Locke and Latham (2002). Building a practically useful theory of goal setting and task motivation: A 35-year odyssey. *American Psychologist*. https://doi.org/10.1037/0003-066X.57.9.705 (verify: found, ok)
- **Propositions:** P1 Specific, difficult goals lead to higher performance than vague or easy goals, through direction, effort, persistence and strategy development. P2 The effect holds when the person is committed to the goal, receives feedback, has the ability and the task is not too complex; self-efficacy and goal commitment moderate and mediate it.
- **Constructs:** goal specificity, goal difficulty, goal commitment, feedback, self-efficacy, task complexity, performance, learning vs performance goals.
- **Hypotheses licensed:** goal difficulty x commitment -> performance (+); specific goals > "do your best"; feedback moderates goal -> performance; self-efficacy -> goal level chosen (+) and -> performance (+); task complexity weakens the effect.
- **Common misuse:** measuring "having goals" as a trait; omitting commitment and feedback, the boundary conditions; citing goal setting for the content of goals (what to aim at) rather than their properties.

## Source not confirmed (do not cite from this file)

| Theory | Candidate source | Why it is not in the registry |
|---|---|---|
| Constructivism (Piaget) | Piaget (1936). *La naissance de l'intelligence chez l'enfant*. Delachaux et Niestle | The French original was not searched; only the English translation (1952) is confirmed above. Cite the edition actually read. |
| Contingency (leadership) | Fiedler (1967). *A theory of leadership effectiveness*. McGraw-Hill | Open Library lists the book but with no ISBN record, so `add --isbn` cannot ingest it. Cite the 1964 chapter (verified) or supply the ISBN from a physical copy. |
| Contingency (organisational) | Burns and Stalker (1961). *The management of innovation*. Tavistock | Not searched in this pass. Run `scholar.py book --title "The management of innovation" --author Stalker` before citing. |
| Scaffolding (used with constructivism) | Wood, Bruner and Ross (1976). The role of tutoring in problem solving. *Journal of Child Psychology and Psychiatry* | DOI not verified in this pass: `verify 10.1111/j.1469-7610.1976.tb00381.x` before citing. |
| Stakeholder salience | Mitchell, Agle and Wood (1997). *Academy of Management Review* | Not verified in this pass: `verify 10.5465/amr.1997.9711022105` before citing. |
| UTAUT2, PMT revision (1983), HBM self-efficacy (1988), JD-R personal resources | Venkatesh, Thong and Xu (2012); Rogers (1983) chapter; Rosenstock, Strecher and Becker (1988); Xanthopoulou et al. (2007) | Extensions named in the entries above as "separate source"; verify each DOI before using its constructs. |

When one of these is verified later, move it into the entry and record the `verify` or `book` output date next to it.

## Theory-fit procedure (stage 4, before any hypothesis is written into the paper)

A theory licenses a hypothesis only when one of its propositions states the link. The procedure makes that visible, so the reviewer's question "where does H3 come from?" has an answer in the text.

1. **Write every hypothesis in full form:** independent construct, dependent construct, direction (+ / -), level (individual, team, firm), mechanism if mediated, condition if moderated. "H2: Perceived ease of use is positively related to perceived usefulness (individual level, direct)."
2. **Name the theory and its propositions** from the registry (P1, P2). If the study uses two theories, write both and say which one owns which hypothesis.
3. **Map each hypothesis to one proposition.** Build the table below. The proposition must state the same constructs (or a defined operationalisation of them), the same direction and the same level.
4. **Judge the fit:**
   - `fits`: the proposition states the link. Keep.
   - `fits with argument`: the proposition states the link for a broader construct (e.g. "job resources") and the paper argues in one paragraph why the measured variable (e.g. supervisor feedback) is an instance. Keep, with the argument in the text.
   - `unsupported`: no proposition of the named theory states the link. Options, in this order: (a) find another verified theory whose proposition does, and declare a multi-theory framework; (b) argue it from two or more empirical studies in the ledger and label it an exploratory hypothesis or research question; (c) drop it. Never leave an unsupported hypothesis under the theory's name.
5. **Check the boundary conditions** listed in "common misuse": level of analysis, voluntariness, cross-sectional versus process claims, the version of the theory cited.
6. **Check construct fidelity:** the instrument in stage 4 measures the theory's construct, not a neighbour (self-esteem for self-efficacy; satisfaction for confirmation; attitude toward the object for attitude toward the behaviour).
7. **Write the mapping table into the theoretical-framework section** (or an appendix for a thesis). One row per hypothesis.

### Fit table template

| Hypothesis | Constructs (IV -> DV) | Theory, proposition | Fit | Argument or action |
|---|---|---|---|---|
| H1 | PEOU -> PU (+) | TAM P2 | fits | |
| H2 | PU -> intention (+) | TAM P1 | fits | |
| H3 | trust -> intention (+) | none in TAM | unsupported | argued from Gefen et al. (ledger key gefen2003) as an extension; labelled exploratory |
| H4 | intention -> actual use (+) | TAM P1 | fits with argument | use is self-reported frequency; limitation stated |

### Template sentences

| Purpose | English | العربية |
|---|---|---|
| Introduce the theory | This study draws on the Technology Acceptance Model (TAM; Davis, 1989), which holds that... | تستند هذه الدراسة إلى نموذج قبول التكنولوجيا (Technology Acceptance Model, TAM) لدى ديفيز (Davis, 1989)، الذي يفترض أن... |
| Derive a hypothesis (fits) | According to TAM's second proposition, ease of use raises perceived usefulness. Hence: H1: ... | واستناداً إلى الافتراض الثاني في النموذج، فإن سهولة الاستخدام المدركة ترفع الفائدة المدركة؛ وعليه تفترض الدراسة: الفرضية الأولى: ... |
| Derive with argument | TAM does not name X; however, X is an external variable in Davis's sense because..., so its effect should run through PU and PEOU. Hence: H3: ... | لا يذكر النموذج المتغير (س) صراحة، غير أنه يُعد متغيراً خارجياً بالمعنى الذي حدده ديفيز لأنه...، ومن ثم يُتوقع أن يمر أثره عبر الفائدة المدركة وسهولة الاستخدام المدركة؛ وعليه: الفرضية الثالثة: ... |
| Exploratory (unsupported by the theory) | The relationship between X and Y is not stated by TAM. Prior studies report it (A, 2020; B, 2022), so it is examined as an exploratory research question (RQ2) rather than a hypothesis. | لا يتناول النموذج العلاقة بين (س) و(ص)، غير أن دراسات سابقة أشارت إليها (أ، 2020؛ ب، 2022)؛ لذا تُفحص بوصفها سؤالاً استكشافياً (السؤال الثاني) لا فرضية. |
| Multi-theory framework | TAM explains the adoption path (H1, H2), while Expectation-Confirmation Theory (Bhattacherjee, 2001) explains continued use (H4, H5); the two are combined because... | يفسر نموذج قبول التكنولوجيا مسار التبني (الفرضيتان الأولى والثانية)، في حين تفسر نظرية تأكيد التوقعات (Bhattacherjee, 2001) الاستمرار في الاستخدام (الفرضيتان الرابعة والخامسة)؛ وقد جُمع بينهما لأن... |
| Boundary condition stated | TAM assumes voluntary use; because use of the system is mandatory in the study setting, intention is interpreted as acceptance rather than choice (Venkatesh et al., 2003). | يفترض النموذج أن الاستخدام طوعي؛ ولما كان استخدام النظام إلزامياً في بيئة الدراسة، فُسرت النية بوصفها قبولاً لا اختياراً (Venkatesh et al., 2003). |
| Reporting a non-fit in discussion | H3 was not supported, which is consistent with TAM's silence on X and suggests the relationship depends on... | لم تُدعم الفرضية الثالثة، وهو ما يتسق مع عدم تناول النموذج للمتغير (س)، ويشير إلى أن العلاقة قد تتوقف على... |

### Checks before leaving stage 4

| Check | Pass condition |
|---|---|
| Every hypothesis has a row in the fit table | no empty "Theory, proposition" cell |
| No row reads `unsupported` without an action | re-argued, re-labelled exploratory, or dropped |
| Theory sources are in the ledger | `scholar.py list` shows them; `audit` finds the citations |
| Version and boundary stated | the paper names which version (TAM 1989, UTAUT 2003, HBM with or without self-efficacy) and any violated assumption |
| Arabic names carry the English term once | e.g. نظرية السلوك المخطط (Theory of Planned Behavior) |
