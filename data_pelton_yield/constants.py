import os

# physical constants
p = 1000  # water density kg/m^3
g = 9.81  # m/s^2 gravitational acceleration

# columns
cols = ["timestamp", "Portata [l/s]", "Potenza [kW]", "Pressione [bar]"]
required_cols = ["Portata [l/s]", "Potenza [kW]"]

# curve settings
TREBISACCE_HEAD = 183  # meters
FLOW_BIN_LS = 0.10     # bin size in l/s

# hampel filter settings
HAMPEL_WINDOW_SIZE = 50  # default window size
HAMPEL_N_SIGMA = 3.0     # sigma threshold for outlier detection

# output dirs
CHARTS_DIR = os.path.join("..", "portale_hydro_3_0", "portale", "static", "portale", "pelton_yield_charts")
LOCAL_CHARTS_DIR = os.path.join("charts_archive", "last_computed_charts")
