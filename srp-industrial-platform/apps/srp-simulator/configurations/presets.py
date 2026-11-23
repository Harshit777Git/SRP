from shared.contracts import Well, Rod


def presets():
    return [
        Well(asset_id="SRP_001", rods=[Rod(length_m=450, diameter_m=.0222)], stroke_m=1.65, spm=8),
        Well(asset_id="SRP_002", rods=[Rod(length_m=650, diameter_m=.0254),
                                     Rod(length_m=550, diameter_m=.0222)]),
        Well(asset_id="SRP_003", rods=[Rod(length_m=800, diameter_m=.0286),
                                     Rod(length_m=750, diameter_m=.0254),
                                     Rod(length_m=650, diameter_m=.0222)], stroke_m=2.55, spm=5),
    ]
