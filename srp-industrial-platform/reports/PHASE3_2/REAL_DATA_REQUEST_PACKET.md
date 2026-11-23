# SRP real-data request packet (draft only)

No messages have been sent. These drafts are for user review and direct sending if desired.

## Request to the 2025 multi-source SRP study authors

Paper: [Semi-Supervised Class-Incremental Sucker-Rod Pumping Well Operating Condition Recognition](https://pmc.ncbi.nlm.nih.gov/articles/PMC12031298/)  
Correspondence shown in the paper: `freetzb@163.com` (Bin Zhou).

> Subject: Request for numerical SRP dynamometer/electrical records and reuse terms
>
> Dear Professor Zhou,
>
> I am developing an SRP digital-twin and fault-diagnosis proof of concept. Your paper describes measured ground dynamometer and electrical power records. Would you be willing to share the numerical data, or a small de-identified subset, for independent engineering evaluation and supervised research experiments?
>
> If available, we would need the original ordered load–position samples (and electrical time-series with timestamps), units and sampling details, stable anonymized well/run identifiers, equipment/rod/pump configuration, operating-condition labels, the evidence used to confirm each label, and train/test grouping guidance. Please also specify whether local analysis, model training, retention, publication of derived metrics, and redistribution are permitted, and any required attribution or agreement.
>
> We will preserve the data separately from synthetic records, avoid assigning labels to unlabelled samples, and will not redistribute files or train on them outside the terms you authorize.
>
> Thank you,
> SRP Digital Twin project

## Request to the 2021 study authors

Paper: [A Data-Driven Framework for Classifying Dynamometer Cards](https://pmc.ncbi.nlm.nih.gov/articles/PMC8271678/). The paper reports data access upon reasonable request. Use the corresponding-author address printed in the paper's author/correspondence section; verify the current address there before sending.

> Subject: Request for SRP dynamometer-card numerical dataset and training permission
>
> Dear Dr. Nascimento,
>
> I am following up on your paper's data-availability statement. Could you share the numerical card records underlying the study, with units, point ordering, anonymized well IDs, card/label mapping, label adjudication source, and any associated equipment metadata? A smaller de-identified sample with documented provenance would also be valuable.
>
> Please clarify whether the data can be retained locally and used to train/evaluate a fault-classification model, whether results may be published, and any limits on redistribution or commercial use. We will not infer labels from card shape or use data beyond the permissions you grant.
>
> Thank you,
> SRP Digital Twin project

## Request to the NK dataset maintainer/provider

Dataset: [NK Oil Well Sensor Monitoring](https://huggingface.co/datasets/Arailym-tleubayeva/NK-Oil-Well-Sensor-Monitoring). The card states Apache-2.0 but also requires compliance with the original provider's confidentiality, ownership, and contractual obligations.

> Please confirm the contractual/data-owner conditions that apply to research and ML training; define `dynamometer_area` and the min/max rod-weight semantics and units; confirm whether any raw load–displacement traces, pumping-unit/rod-string configurations, production records, operating-event logs or independently adjudicated fault labels can be released; and verify the timestamp year/date interpretation.

## Intake conditions

Before import into the platform's real-data registry, obtain written terms and verify file hashes, schema, actual numerical sample counts, unique wells/runs, equipment context, labels and their evidence. Any grant should distinguish internal evaluation, supervised model training, publication of metrics and redistribution. Store the permission document beside the data's provenance record. Unknown answers remain `PERMISSION_UNVERIFIED`; no model is trained on such records.
