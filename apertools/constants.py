from numpy import pi

SENTINEL_WAVELENGTH = 5.5465763  # cm
PHASE_TO_CM = SENTINEL_WAVELENGTH / (4 * pi)
P2MM = PHASE_TO_CM * 10 * 365  # (cm / day) -> (mm / yr)

UAVSAR_WAVELENGTH = 23.8403545  # cm
PHASE_TO_CM_UA = UAVSAR_WAVELENGTH / (4 * pi)
P2MM_UA = PHASE_TO_CM_UA * 10 * 365
