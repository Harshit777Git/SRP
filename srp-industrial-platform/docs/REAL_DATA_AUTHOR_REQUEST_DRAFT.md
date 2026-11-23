# Draft data request — SRP measured-card dataset

To: freetzb@163.com
Subject: Request for SRP measured dynamometer-card data and reuse terms

Dear Professor Zhou,

I am developing an SRP digital-twin and fault-diagnosis proof of concept. Your 2025 Sensors paper, “Semi-Supervised Class-Incremental Sucker-Rod Pumping Well Operating Condition Recognition Based on Multi-Source Data Distillation” (PMCID PMC12031298; DOI 10.3390/s25082372), describes 1,650 measured condition samples from 60 pumping units over three years, including measured ground dynamometer and electrical power cards.

Would you be able to share the research dataset, or advise the process and conditions for access? For engineering validation, the most useful format would be ordered numerical load-displacement samples for each stroke and, where available, paired electrical time series. If the data are image-only, the original card images and their sampling/axis calibration metadata would still be valuable.

Could you also clarify:

- Which records correspond to each condition and how each label was established (for example, workover, valve test, inspection, or operator annotation)?
- Whether anonymized well/unit IDs and equipment configuration can be included so we can hold out entire wells during evaluation.
- Whether multiple strokes or time periods from the same well can be identified.
- The measurement units, sampling procedure, and whether the cards are raw, filtered, normalized, or reconstructed.
- The license and permitted use for internal engineering benchmarking, supervised model training, and a non-public industrial PoC.
- Any citation, confidentiality, or data-security conditions.

We will preserve provenance, keep source labels separate from model predictions, and will not redistribute the data. We will not use the dataset unless the applicable permissions are clear.

Thank you for your time.

Best regards,
SRP Digital Twin PoC team

---

# Draft data request — PLOS / Scientific Reports SRP card source

To: xyli@sylu.edu.cn
Subject: Request for SRP dynamometer-card labels, equipment metadata, and reuse terms

Dear Professor Li,

I am developing an SRP digital-twin and fault-diagnosis proof of concept. Your 2025 PLOS ONE article, “Electric parameter prediction of rod pumping units based on N-HiTS model” (DOI 10.1371/journal.pone.0326973), publishes four 144-point surface-card workbooks (DC1–DC4) and four electrical-parameter workbooks (ED1–ED4). Your related 2025 Scientific Reports article, “A fault diagnosis model for pumping units based on small sample electric parameters” (DOI 10.1038/s41598-025-07913-7), describes six operating conditions and states that its data are available from the corresponding author on reasonable request.

Would you be able to share the underlying SRP card dataset and advise the access process and permitted uses? We have the public S1 Data archive, but it does not identify a fault condition for each DC file, a well/stroke ID, a card-to-ED crosswalk, or whether each ED workbook contains measured or generated values. We would not infer these mappings ourselves.

For engineering validation and a controlled research PoC, the most useful materials would be:

- Ordered raw load–displacement points for each stroke, with units, cycle direction/phase and acquisition timestamps or sampling intervals.
- The verified label for each card and its evidence source (operator diagnosis, valve test, workover, inspection, or other documented event).
- Anonymized well, run and stroke IDs so evaluation can hold out entire wells and avoid neighboring-stroke leakage.
- The mapping of DC1–DC4 and ED1–ED4 to condition, well, time period and measured-versus-generated origin, including definitions of the `remarks` values 0, 111 and 222.
- Full equipment configuration: pumping-unit geometry and balancing, motor model/rating, rod-string taper/depth, pump depth/diameter, fluid properties and operating rate.
- Explicit permission terms for internal engineering benchmarking, model training and any non-public industrial PoC; please note any non-commercial, attribution, confidentiality or redistribution restrictions.

We observed that the PLOS paper lists a 4 kW motor rating while the related Scientific Reports paper lists 37 kW for the same stated pumping-unit model. Please clarify whether these refer to different motor configurations or studies before we use either as a simulator benchmark. We will keep the two published configurations separate until confirmed.

We will preserve provenance, keep source diagnoses separate from model predictions, and will not redistribute or use the data unless the applicable permissions are clear.

Thank you for your time.

Best regards,
SRP Digital Twin PoC team

---

# Draft data request — Mossoró SRP field-card study

To: maitelli@dca.ufrn.br
Subject: Request for Mossoró SRP dynamometer-card dataset and reuse terms

Dear Professor Maitelli,

I am developing an SRP digital-twin and fault-diagnosis proof of concept. Your paper “Diagnostic of Operation Conditions and Sensor Faults Using Machine Learning in Sucker-Rod Pumping Wells” (Sensors 2021, 21(13), 4546; PMCID PMC8271678; DOI 10.3390/s21134546) reports more than 50,000 dynamometer cards from 38 Mossoró wells, with expert classifications of operating modes and sensor faults, and states that the data are available on request.

Could you share the dataset or advise the access process and permitted use? We are particularly interested in the original load-position vectors per stroke, together with both surface and downhole records where available. The published workflow mentions normalized 100-point downhole cards; raw measurements and exact preprocessing metadata would be most useful for engineering validation.

Please clarify, if possible:

- Exact record count and per-class counts, with class definitions and label source/evidence.
- Whether each downhole card is directly measured, calculated/reconstructed, or expert-derived.
- Whether corresponding raw surface cards, electrical/power signals, production measurements, and timestamped records are available.
- Anonymized well IDs and run/stroke grouping so evaluation can hold out entire wells and avoid adjacent-stroke leakage.
- Equipment and well configuration, units, sampling, normalization, filtering, and data-quality rules.
- Explicit terms for internal engineering benchmarking, model training, and non-public industrial PoC evaluation; any redistribution or commercial-use restrictions.

We will preserve provenance, separate source diagnoses from model predictions, avoid redistribution, and comply with the access and data-use terms you specify.

Thank you for your time.

Best regards,
SRP Digital Twin PoC team
