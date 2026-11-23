"""Prevent simulation fault identifiers from entering the inference bus."""
FORBIDDEN={'stateid','statename','fault','faultid','faulttype','faultname','faultmechanism',
           'faultclass','faultclassid','faultclassname','faultseverity','severity','scenario','scenarioid','scenarioname','groundtruth','label','classlabel'}

def assert_label_blind(value):
    if isinstance(value,dict):
        for key,item in value.items():
            normalized=''.join(c for c in str(key).lower() if c.isalnum())
            if normalized in FORBIDDEN:raise ValueError('Fault-disclosing telemetry key rejected: '+str(key))
            assert_label_blind(item)
    elif isinstance(value,(list,tuple)):
        for item in value:assert_label_blind(item)
